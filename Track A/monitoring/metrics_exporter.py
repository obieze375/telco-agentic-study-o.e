#!/usr/bin/env python3
"""
Prometheus exporter for Track A experiment results.

Scans RESULTS_DIR for:
  - results.json
  - */results.json

Exposes metrics at GET /metrics (default port 9100).
"""

from __future__ import annotations

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple

from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")
SCRAPE_LOGS = os.environ.get("SCRAPE_LOGS", "true").lower() in {"1", "true", "yes"}
PORT = int(os.environ.get("EXPORTER_PORT", "9100"))

# Gauges — set on each scrape from latest results.json content
scenario_accuracy = Gauge(
    "tracka_scenario_accuracy",
    "Per-scenario accuracy score (0-1)",
    ["run", "scenario_id", "architecture", "model"],
)
scenario_latency = Gauge(
    "tracka_scenario_latency_seconds",
    "Per-scenario end-to-end latency in seconds",
    ["run", "scenario_id", "architecture", "model"],
)
scenario_tool_calls = Gauge(
    "tracka_scenario_tool_calls",
    "Number of tool calls for a scenario",
    ["run", "scenario_id", "architecture", "model"],
)
scenario_iterations = Gauge(
    "tracka_scenario_iterations",
    "Number of agent iterations for a scenario",
    ["run", "scenario_id", "architecture", "model"],
)
run_avg_accuracy = Gauge(
    "tracka_run_avg_accuracy",
    "Average accuracy across scenarios in a run",
    ["run", "architecture", "model"],
)
run_scenario_count = Gauge(
    "tracka_run_scenario_count",
    "Number of scenarios in a run",
    ["run", "architecture", "model"],
)
run_avg_latency = Gauge(
    "tracka_run_avg_latency_seconds",
    "Average scenario latency for a run",
    ["run", "architecture", "model"],
)
run_avg_tool_calls = Gauge(
    "tracka_run_avg_tool_calls",
    "Average tool calls per scenario for a run",
    ["run", "architecture", "model"],
)
run_total_failed_tools = Gauge(
    "tracka_run_total_failed_tools",
    "Total failed tool calls in a run",
    ["run", "architecture", "model"],
)
run_info = Gauge(
    "tracka_run_info",
    "Run metadata (value = scenario count)",
    ["run", "architecture", "model", "model_url"],
)
llm_requests = Gauge(
    "tracka_llm_requests",
    "LLM HTTP responses parsed from log files",
    ["run", "status"],
)

exporter_files_loaded = Gauge(
    "tracka_exporter_results_files_loaded",
    "Number of results.json files loaded on last scrape",
)
exporter_last_scrape = Gauge(
    "tracka_exporter_last_scrape_timestamp",
    "Unix timestamp of last successful scrape",
)


def _discover_results_files(base: Path) -> List[Tuple[str, Path]]:
    """Return list of (run_name, path) for all results.json files."""
    found: List[Tuple[str, Path]] = []
    root_file = base / "results.json"
    if root_file.is_file():
        found.append(("root", root_file))

    for path in sorted(base.glob("*/results.json")):
        run_name = path.parent.name
        found.append((run_name, path))
    return found


def _parse_log_metrics(base: Path, run_name: str) -> None:
    """Optionally parse companion .log files for LLM request counts."""
    if not SCRAPE_LOGS:
        return

    log_candidates = [
        base / f"{run_name}.log",
        base / run_name / "run.log",
        base.parent / f"{run_name}.log",
    ]
    for log_path in log_candidates:
        if not log_path.is_file():
            continue
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for status in ("200", "401", "404", "429", "500"):
            count = len(re.findall(rf'chat/completions "HTTP/1\.1 {status}', text))
            if count:
                llm_requests.labels(run=run_name, status=status).set(count)
        break


def _load_run(run_name: str, path: Path) -> None:
    with path.open(encoding="utf-8") as fp:
        data: Dict[str, Any] = json.load(fp)

    model = data.get("model_name") or "unknown"
    model_url = data.get("model_url") or data.get("model_provider") or "unknown"
    default_architecture = data.get("architecture") or "baseline"
    completions: List[Dict[str, Any]] = data.get("completions") or []
    if not completions:
        return

    accuracies: List[float] = []
    latencies: List[float] = []
    tool_counts: List[float] = []
    failed_tools = 0

    for comp in completions:
        scenario_id = comp.get("scenario_id", "unknown")
        architecture = comp.get("architecture") or default_architecture
        accuracy = float(comp.get("accuracy") or 0.0)
        latency = float(comp.get("latency") or 0.0)
        num_tools = float(comp.get("num_tool_calls") or 0.0)
        num_iters = float(comp.get("num_iterations") or 0.0)

        labels = {
            "run": run_name,
            "scenario_id": scenario_id,
            "architecture": architecture,
            "model": model,
        }
        scenario_accuracy.labels(**labels).set(accuracy)
        scenario_latency.labels(**labels).set(latency)
        scenario_tool_calls.labels(**labels).set(num_tools)
        scenario_iterations.labels(**labels).set(num_iters)

        accuracies.append(accuracy)
        latencies.append(latency)
        tool_counts.append(num_tools)

        for tc in comp.get("tool_calls") or []:
            if tc.get("has_failed"):
                failed_tools += 1

    arch = completions[0].get("architecture") or default_architecture
    run_labels = {"run": run_name, "architecture": arch, "model": model}
    run_scenario_count.labels(**run_labels).set(len(completions))
    run_total_failed_tools.labels(**run_labels).set(failed_tools)
    run_info.labels(
        run=run_name,
        architecture=arch,
        model=model,
        model_url=str(model_url),
    ).set(len(completions))
    if accuracies:
        run_avg_accuracy.labels(**run_labels).set(sum(accuracies) / len(accuracies))
        run_avg_latency.labels(**run_labels).set(sum(latencies) / len(latencies))
        run_avg_tool_calls.labels(**run_labels).set(sum(tool_counts) / len(tool_counts))

    if path.parent.name == "results":
        results_root = path.parent
    else:
        results_root = path.parent.parent
    _parse_log_metrics(results_root, run_name)


def scrape_results() -> int:
    """Clear and reload all metrics from disk."""
    base = Path(RESULTS_DIR)
    if not base.is_dir():
        return 0

    # Reset gauge families (counters accumulate across scrapes for logs — acceptable)
    for metric in (
        scenario_accuracy,
        scenario_latency,
        scenario_tool_calls,
        scenario_iterations,
        run_avg_accuracy,
        run_scenario_count,
        run_avg_latency,
        run_avg_tool_calls,
        run_total_failed_tools,
        run_info,
        llm_requests,
    ):
        metric.clear()

    files = _discover_results_files(base)
    for run_name, path in files:
        try:
            _load_run(run_name, path)
        except Exception as exc:
            print(f"[exporter] failed to load {path}: {exc}")

    exporter_files_loaded.set(len(files))
    exporter_last_scrape.set(time.time())
    return len(files)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/metrics"):
            self.send_response(404)
            self.end_headers()
            return

        scrape_results()
        payload = generate_latest()

        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[exporter] {self.address_string()} {fmt % args}")


def main() -> None:
    print(f"[exporter] watching RESULTS_DIR={RESULTS_DIR} on :{PORT}")
    scrape_results()
    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
