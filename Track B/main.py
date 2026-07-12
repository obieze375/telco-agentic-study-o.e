#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Track B standalone agent — no OpenClaw required.

Calls the local (or remote) CLI tool server via a single execute_cli_command tool,
then writes predictions to results/result.csv.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
import requests
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

CLI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_cli_command",
        "description": (
            "Execute a read-only network device CLI command through the NOC API. "
            "Use Huawei display/*, Cisco show/*, or H3C display/* syntax. "
            "Call tools sequentially — one command at a time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Target device hostname, e.g. Gamma-Aegis-01",
                },
                "command": {
                    "type": "string",
                    "description": "Full CLI command string",
                },
                "question_number": {
                    "type": "integer",
                    "description": "Current problem ID (task id from the question JSON)",
                },
            },
            "required": ["device_name", "command", "question_number"],
        },
    },
}

SYSTEM_PROMPT = """You are an expert IP network troubleshooting agent for a telecom operations challenge.

You investigate problems by calling execute_cli_command to run CLI commands on routers, switches, and firewalls (Huawei, Cisco, H3C).

Rules:
- Call execute_cli_command sequentially (one command per turn).
- Always pass the correct question_number for the current problem.
- Huawei/H3C: display ...   Cisco: show ...
- Read command output carefully before deciding the next command.
- When you have enough evidence, output ONLY the final answer in the exact format requested by the question.
- For link lists use: LocalNode(LocalPort)->RemoteNode(RemotePort) one link per line.
- For paths use: NodeA->NodeB->NodeC on a single line.
- Do not wrap the final answer in markdown or extra commentary.
"""


def resolve_api_key(cli_key: Optional[str] = None) -> str:
    if cli_key:
        return cli_key
    return os.environ.get("NEBIUS_API_KEY") or os.environ.get("AGENT_API_KEY") or "dummy"


def resolve_tool_token(cli_token: Optional[str] = None) -> Optional[str]:
    if cli_token:
        return cli_token
    return os.environ.get("ZINDI_TOKEN") or os.environ.get("TOOL_SERVER_TOKEN")


def setup_logger(log_file: Optional[str] = None, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("track_b_agent")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def extract_answer(text: str) -> str:
    """Pull structured answer lines from the model's final response."""
    if not text:
        return ""

    patterns = [
        r"[\w-]+\([A-Za-z0-9/]+\)\s*->\s*[\w-]+\([A-Za-z0-9/]+\)",
        r"[\w-]+\s*->\s*[\w-]+(?:\s*->\s*[\w-]+)+",
        r"[\w-]+;[^;\n]+;[^;\n]+",
    ]
    for pattern in patterns:
        lines = [ln.strip() for ln in text.strip().splitlines() if re.search(pattern, ln.strip())]
        if lines:
            return "\n".join(lines)

    boxed = re.search(r"\\boxed\{([^}]+)\}", text)
    if boxed:
        return boxed.group(1).strip()

    return text.strip()


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


class Environment:
    def __init__(
        self,
        server_url: str,
        tool_token: Optional[str] = None,
        timeout: float = 60.0,
        verbose: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.tool_token = tool_token
        self.timeout = timeout
        self.verbose = verbose
        self.logger = logger or setup_logger()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.tool_token:
            headers["Authorization"] = f"Bearer {self.tool_token}"
        return headers

    def execute_cli(self, device_name: str, command: str, question_number: int) -> Dict[str, Any]:
        url = f"{self.server_url}/api/agent/execute"
        body = {
            "device_name": device_name,
            "command": command,
            "question_number": question_number,
        }
        session = requests.Session()
        session.trust_env = False
        try:
            resp = session.post(url, json=body, headers=self._headers(), timeout=self.timeout)
            if self.verbose:
                self.logger.info(f"[NOC API] POST {url} body={body} -> {resp.status_code}")
            try:
                return resp.json()
            except Exception:
                return {"error": resp.text, "status_code": resp.status_code}
        except Exception as exc:
            return {"error": str(exc)}

    def run_tool_call(self, tool_call: ToolCall, question_number: int) -> str:
        try:
            args = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON arguments: {tool_call.arguments}"})

        qnum = int(args.get("question_number", question_number))
        result = self.execute_cli(
            device_name=args.get("device_name", ""),
            command=args.get("command", ""),
            question_number=qnum,
        )
        return json.dumps(result, ensure_ascii=False)


class AgentsRunner:
    def __init__(
        self,
        environment: Environment,
        model_url: str,
        model_name: str,
        api_key: str,
        model_provider: Optional[str] = None,
        max_tokens: int = 8000,
        max_retries: int = 3,
        max_iterations: int = 15,
        verbose: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.environment = environment
        self.model_name = model_name
        self.model_provider = model_provider
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.logger = logger or setup_logger(verbose=verbose)
        self.client = OpenAI(
            base_url=model_url,
            api_key=api_key,
            http_client=httpx.Client(verify=False),
        )

    def _model_id(self) -> str:
        if self.model_provider:
            return f"{self.model_provider}/{self.model_name}"
        return self.model_name

    def _call_model(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None):
        call_kwargs: Dict[str, Any] = {
            "model": self._model_id(),
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**call_kwargs)
                return response.choices[0].message
            except (RateLimitError, APIConnectionError, APITimeoutError, APIError) as exc:
                if self.verbose:
                    self.logger.error(traceback.format_exc())
                if hasattr(exc, "status_code") and 400 <= exc.status_code < 500 and exc.status_code != 429:
                    self.logger.error(f"LLM API error: {exc}")
                    return None
                if attempt == self.max_retries:
                    self.logger.error(f"LLM API failed after {self.max_retries} attempts: {exc}")
                    return None
                time.sleep(2 ** (attempt - 1))
            except Exception as exc:
                self.logger.error(f"Unhandled LLM error: {exc}")
                return None
        return None

    def run(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        scenario_id = scenario.get("scenario_id", "")
        task = scenario.get("task", {})
        question_number = int(task.get("id", 0))
        question = task.get("question", "")

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Problem ID: {question_number}\n"
                    f"Scenario ID: {scenario_id}\n\n"
                    f"{question}\n\n"
                    "Investigate using execute_cli_command, then provide the final answer only."
                ),
            },
        ]

        last_content = ""
        num_tool_calls = 0

        for i in range(self.max_iterations):
            self.logger.info(f"\n[Scenario: {scenario_id}] Round {i + 1}")

            msg = self._call_model(messages, tools=[CLI_TOOL])
            if msg is None:
                continue

            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    num_tool_calls += 1
                    tool_call = ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
                    if self.verbose:
                        self.logger.info(f"  tool: {tool_call.name}({tool_call.arguments})")
                    tool_result = self.environment.run_tool_call(tool_call, question_number)
                    messages.append({"role": "tool", "content": tool_result, "tool_call_id": tc.id})
                    if self.verbose:
                        preview = tool_result[:500] + ("..." if len(tool_result) > 500 else "")
                        self.logger.info(f"  result: {preview}")
                continue

            if msg.content:
                last_content = msg.content
                break

        if not last_content:
            self.logger.info(f"[Scenario: {scenario_id}] Requesting final answer")
            messages.append(
                {
                    "role": "user",
                    "content": "Provide your final answer now in the exact format required. Output only the answer.",
                }
            )
            msg = self._call_model(messages, tools=None)
            if msg and msg.content:
                last_content = msg.content

        answer = extract_answer(last_content)
        status = "solved" if answer else "unresolved"

        return {
            "scenario_id": scenario_id,
            "question_number": question_number,
            "status": status,
            "answer": answer,
            "raw_response": last_content,
            "num_tool_calls": num_tool_calls,
            "num_iterations": i + 1,
        }

    def benchmark(
        self,
        scenarios: List[Dict[str, Any]],
        save_dir: str,
        num_attempts: int = 1,
        save_freq: int = 1,
        max_samples: Optional[int] = None,
    ) -> None:
        os.makedirs(save_dir, exist_ok=True)
        if max_samples is not None:
            scenarios = scenarios[:max_samples]

        rows: List[Dict[str, Any]] = []
        traces: List[Dict[str, Any]] = []

        for idx, scenario in enumerate(scenarios):
            scenario_id = scenario.get("scenario_id")
            self.logger.info(f"\n[Scenario {scenario_id}] attempt 1/{num_attempts}")

            response = self.run(scenario)
            answer = response.get("answer", "")
            self.logger.info(f"[Scenario: {scenario_id}] answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")

            rows.append({"scenario_id": scenario_id, "prediction": answer})
            traces.append(response)

            if ((idx + 1) % save_freq == 0) or ((idx + 1) == len(scenarios)):
                pd.DataFrame(rows).to_csv(os.path.join(save_dir, "result.csv"), index=False)
                with open(os.path.join(save_dir, "results.json"), "w", encoding="utf-8") as fp:
                    json.dump(traces, fp, ensure_ascii=False, indent=2)


def load_scenarios(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Track B standalone agent")
    parser.add_argument("--input_json", type=str, default="data/Phase_1/test.json")
    parser.add_argument("--server_url", type=str, default="http://localhost:7860")
    parser.add_argument(
        "--tool_token",
        type=str,
        default=None,
        help="Bearer token for remote tool server (or set ZINDI_TOKEN)",
    )
    parser.add_argument("--model_url", type=str, default="https://openrouter.ai/api/v1")
    parser.add_argument("--model_name", type=str, default="qwen/qwen3.5-35b-a3b")
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="LLM API key (overrides NEBIUS_API_KEY and AGENT_API_KEY)",
    )
    parser.add_argument("--model_provider", type=str, default=None)
    parser.add_argument("--num_attempts", type=int, default=1)
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--save_freq", type=int, default=1)
    parser.add_argument("--max_tokens", type=int, default=8000)
    parser.add_argument("--max_iterations", type=int, default=15)
    parser.add_argument("--save_dir", type=str, default="./results")
    parser.add_argument("--log_file", type=str, default="./log.log")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logger = setup_logger(log_file=args.log_file, verbose=args.verbose)
    scenarios = load_scenarios(args.input_json)

    env = Environment(
        server_url=args.server_url,
        tool_token=resolve_tool_token(args.tool_token),
        verbose=args.verbose,
        logger=logger,
    )
    runner = AgentsRunner(
        environment=env,
        model_url=args.model_url,
        model_name=args.model_name,
        api_key=resolve_api_key(args.api_key),
        model_provider=args.model_provider,
        max_tokens=args.max_tokens,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        logger=logger,
    )
    runner.benchmark(
        scenarios=scenarios,
        save_dir=args.save_dir,
        num_attempts=args.num_attempts,
        save_freq=args.save_freq,
        max_samples=args.max_samples,
    )


if __name__ == "__main__":
    main()
