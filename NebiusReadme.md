# Telco Troubleshooting & Optimization Agentic Challenge — Project Summary

> A plain-English summary of the task, intent, and requirements of this repository.

## 1. What This Is

A global AI competition (run via Zindi / HuggingFace) where participants build **AI agents that diagnose and fix telecom network faults**. The agent does not answer from a static prompt — it must **actively investigate** a simulated network by calling tool APIs (querying device data, running CLI commands), reason over the results, and select the correct fix.

**Core constraint:** Every participant uses the same base model — **`Qwen3.5-35B-A3B`**. You may fine-tune it (LoRA or full fine-tuning), but you may **not** swap in a different architecture or parameter scale. The competition is therefore about **agent design** (tools, skills, memory, RAG, chain-of-thought, fine-tuning), not about who has the largest model.

## 2. The Two Tracks

| | **Track A — Wireless / 5G RAN** | **Track B — IP Networks** |
|---|---|---|
| **Domain** | Radio access: cells, PCI, RSRP/SINR, antenna tilt/azimuth, throughput, drive-test data | Routers / switches / firewalls: OSPF, BGP, VXLAN, SRv6, ISIS, ARP, topology |
| **How the agent acts** | Calls REST tool endpoints (`get_serving_cell_rsrp`, `calculate_tilt_angle`, `optimize_antenna_gain`, etc.) exposed via `/tools` | Runs **real vendor CLI commands** (Huawei / Cisco / H3C) through a sandbox that simulates device output and reproduces realistic syntax errors |
| **Question type** | Multiple-choice: pick the right optimization action(s) from options `C1, C2…` (single- or multi-answer) | Open-ended free text: reconstruct topology, trace paths, localize faults (e.g. `NodeA(port)->NodeB(port)` per line) |
| **Answer format** | `C3` or `C5\|C7\|C11` (ascending, `\|`-separated) | Plain-text answer per the question's format requirement |

**Track A example:** *"User throughput degraded during a drive test — select 2–4 optimization actions"* (adjust power, tilt, neighbor relations, A3 offset thresholds…).

**Track B example:** *"Link planning data for node Gamma-Aegis-01 was deleted; query the live devices and rebuild the link list for all UP interfaces."*

## 3. The Three Phases

| Phase | Name | Dates | Data | Participant Action |
|-------|------|-------|------|--------------------|
| **Phase 1** | Open Practice | 3 Apr – 4 May | Public train + test (Track A: 2000 train / 500 test; Track B: 50 problems) | Run agent locally, submit `result.csv` (unlimited) |
| **Phase 2** | Elimination | 4 May – 18 May | New hidden data, same distribution (A: 500; B: 100) | Limited submissions (A: 3, B: 1). **Top 30 per track advance** |
| **Phase 3** | Final | 18 May – 29 May | **Private** dataset (A: 500; B: 70), run by organizers on provisioned GPUs | Submit `code.zip` (agent + fine-tuned weights). **One submission, no runtime internet** |

- **Phase 1 limits (Track B):** max 1,000 API calls per participant per day; max 2 problems in parallel; sequential tool calls within a single problem.
- **Phase 3:** Organizers deploy your model and code in an isolated environment and run it. A strict **15-minute per-problem cutoff** prevents infinite loops.

## 4. How You're Scored

- **Accuracy = primary metric.**
  - **Track A** uses **IoU** (intersection-over-union of selected options vs. ground truth) — partial credit on multi-answer questions: `accuracy = intersection / union`.
  - **Track B** uses accuracy; in Phase 2, **API-call count** breaks ties (fewer calls on correct problems = higher rank).
- **Speed discount (Phase 3):** final `score = accuracy × discount`.

  | Answering time | Discount |
  |----------------|----------|
  | `< 5 minutes` | 100% |
  | `5 – 10 minutes` | 80% |
  | `10 – 15 minutes` | 60% |
  | `> 15 minutes` | 0% |

- **Phase 3 consistency:** runs **4 independent trials (pass@1)** and takes the fastest correct generation.

## 5. Architecture — What You Can and Cannot Modify

The design deliberately splits the simulator from the agent:

```
        ┌─────────────────┐
        │  Environment    │   private dataset (Phase 3)
        └────────┬────────┘
        ┌────────▼────────┐
        │   server.py     │   tools & simulator — CANNOT be modified
        └────────┬────────┘
   ┌─────────────┼─────────────┐
┌──▼──────┐ ┌────▼────┐ ┌──────▼──────┐
│ main.py │ │ skills  │ │ Qwen3.5-35B │
│ (agent) │ │(optional)│ │ fine-tuned  │
│ EDIT ME │ │         │ │  (optional) │
└─────────┘ └─────────┘ └─────────────┘
```

- **`server.py`** — the sandbox / tool server. **Frozen.**
- **`main.py`** (Track A) / `agent/` (Track B) — **your code**: the tool-calling loop, prompting, and reasoning strategy. The provided versions are working reference agents (OpenAI-style tool-calling loop, capped iterations, extracts a `\boxed{...}` answer).
- **Skills & fine-tuned weights** — optional. Track B ships an example **OpenClaw** agent with domain skills: `infra_maintenance`, `l2_link`, `l3_route`, `adv_tunnel`.

## 6. Final Submission Requirements (Phase 3)

Submit a single archive named **`code.zip`** containing all code, weights, config, and instructions. Running it with **one command, no manual steps, no internet** must produce a `result/` folder with exactly three files:

| File | Contents |
|------|----------|
| `traces.json` | Every completion the agent generated (not only final answers) |
| `results.csv` | One final prediction per problem (`scenario_id,prediction`) |
| `runtime.json` | Per-problem runtime in seconds, via the mandatory `runtime_logger` decorator |

**Rules:**
- Model weights must be `.safetensors` or LoRA adapters — **no pickle-based formats**.
- The submission must be self-contained and reproducible; the base model is deployed via a `deploy.sh` using **vLLM**.
- **Disqualifiers:** wrong filename, non-reproducible run, missing output files, unsafe weight formats, dependence on unavailable private files, or runtime internet access.

## 7. One-Sentence Version

> Build an agent on a fixed 35B Qwen model that autonomously investigates a simulated telecom network — radio side (Track A) or IP/CLI side (Track B) — by calling tools, then outputs correct fault diagnoses and fixes, judged on accuracy and speed, and packaged so organizers can reproduce your exact results offline on a private final dataset.

## 8. Repository Map

```
.
├── README.md                          # Top-level competition overview
├── Track A/                            # Wireless / 5G RAN track
│   ├── main.py                         # Reference agent (editable) — tool-calling loop
│   ├── server.py                       # Tool server / simulator (frozen)
│   ├── utils.py                        # extract_answer, compute_score (IoU), printing
│   ├── _types.py, logger.py            # Helpers
│   ├── data/Phase_1/{train,test}.json  # 2000 train + 500 test scenarios
│   └── examples/traces.json
├── Track B/                            # IP networks track
│   ├── server.py                       # Local CLI sandbox server
│   ├── question_limits_config.json
│   ├── devices_outputs.zip             # Simulated device CLI outputs (unzip locally)
│   ├── agent/                          # Example OpenClaw agent
│   │   ├── openclaw_config/            # IDENTITY/SOUL/USER/AGENTS/TOOLS .md
│   │   ├── skills/                     # infra_maintenance, l2_link, l3_route, adv_tunnel
│   │   └── evaluate_openclaw.py        # Batch evaluation script
│   └── data/Phase_{1,2}/              # test.json + ground truth
└── submission/
    ├── Phase_1/, Phase_2/              # result.csv examples
    └── Phase_3/Competition_Guidelines.md  # Full submission spec + CLI command allowlists
```
