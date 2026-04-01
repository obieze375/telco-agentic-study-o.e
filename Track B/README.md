# Track B: Telco Troubleshooting and Optimization Agentic Challenge

## Competition Overview

This task focuses on IP network operations and maintenance. Participants are required to build intelligent agents that complete IP network fault diagnosis and troubleshooting tasks by calling the CLI simulation interfaces provided by the **Agent Tool Server**.

**Base Model:** The entire competition (Phase 1 / 2 / 3) uses **Qwen3.5-35B-A3B** as the base model. Participants may fine-tune the model (LoRA, full fine-tuning, etc.), but are not allowed to replace it with a different architecture or a model of a different parameter scale.

**Server Core Capabilities:**
- Simulates CLI interactions for network devices (Huawei / Cisco / H3C)
- Supports regex whitelist validation for 45+ command categories
- Faithfully reproduces vendor-level syntax errors (incomplete / unrecognized / ambiguous / wrong parameter)
- Multiple command output file types covering routing tables, BGP, VXLAN, SRv6, and more

---

## Competition Design

### Schedule Overview

| Phase | Name | Duration      | Purpose | Problem Scale & Requirements                     | Participant Actions                                                   |
|-------|------|---------------|---------|--------------------------------------------------|-----------------------------------------------------------------------|
| **Phase 1** | Open Practice | 3 April–4 May | Debug Agent, familiarize with API | 50 problems / Multi vendor / advanced protocols  | Run locally, submit result.csv                                        |
| **Phase 2** | Elimination Round | 4 May-18 May  | Select top participants for Phase 3 | 100 problems / multi-vendor / advanced protocols | Run locally, 1 submission only, upload execution trace and result.csv |
| **Phase 3** | Final | 18 May-29 May | Final ranking | 70 problems / multi-vendor / advanced protocols    | Server-side Docker auto-execution                                     |

### Detailed Problem Distribution

| Phase | Problem Composition                                                 | Task Types | Protocols Covered (examples, not exhaustive) | Device Vendors       |
|-------|---------------------------------------------------------------------|------------|-------------------------------|----------------------|
| **Phase 1** | 32-node financial network & 22-node cloud computing network (50 problems) | Topology reconstruction, path query, fault localization | +LLDP, OSPF, VXLAN            | **Multi-vendor mix** |
| **Phase 2** | 40-node campus network (100)                                        | Topology reconstruction, path query, fault localization | +VLAN, VRRP, MP-BGP           | **Multi-vendor mix** |
| **Phase 3** | 64-node financial network (70)                                      | Topology reconstruction, path query, fault localization | +VXLAN, EVPN, SRv6, ISIS, BGP | **Multi-vendor mix** |

### Phase 1 (Open Practice)

- **Number of Problems:** 50
- **Execution Environment:** Participants run Agent locally
- **Base Model:** Qwen3.5-35B-A3B (participants may fine-tune)
- **API Call Limit:** Max **1,000 API calls per participant per day** (only Phase 1 enforces this daily quota; Phase 2 and Phase 3 do not have this restriction)
- **Scoring:** Participants submit `result.csv`; scored by **accuracy only** (the sole evaluation metric for Phase 1)
- **Tool Call Rules:**
  - Agent must call tools **sequentially** when solving a single problem; no concurrent calls within a problem
  - Max concurrency per participant is **2** (i.e., at most 2 problems running in parallel)
- **Onboarding:** Server source code and local deployment guide provided to help participants deploy locally

### Phase 2 (Elimination Round)

- **Number of Problems:** 100 (released in batches of **20 problems every 3 days**)
- **Base Model:** Qwen3.5-35B-A3B (participants may fine-tune)
- **Submission Limit:** Each participant is allowed **only three submissions**; execution trace must be uploaded to the server. Unlike Phase 1, there is no daily API call quota, but participants must ensure at least a single run completes successfully.
- **Scoring:** **Accuracy** as the primary metric; for participants with the same accuracy, the **number of API calls used to solve correct problems** serves as the secondary metric (fewer calls = higher rank)
- **Selection Mechanism:** Participants reserve a submission time slot; top 30 advance to the final
- **Focus:** Agent generalization across multi-vendor environments and stability in one-shot execution

### Phase 3 (Final)

- **Number of Problems:** 70
- **Participants:** Top 30 selected from Phase 2
- **Execution Environment:** Organizer-provided GPU resources + isolated Docker environment
- **Base Model:** Qwen3.5-35B-A3B (participants may fine-tune)
- **Time Limit:** Must be completed within 24 hours
- **Network Data:** Uses **different network data** from Phase 1 / 2
- **Focus:** Complex protocol reasoning (SRv6/EVPN) and deep fault isolation in large-scale networks (64 nodes)
- **Resource Allocation:**
  - **GPU Resources:** Huawei Cloud GPU instances for deploying the base model, independently allocated per participant
  - **Agent Tool Server:** Deployed on HuggingFace free CPU resources (free within 24h)
- **Base Model:** Qwen3.5-35B-A3B, deployed by the organizer to each participant's GPU instance
- **Submission Requirements:** Participants must upload their **fine-tuned model weights** and **Agent code** to the organizer; the organizer will deploy and execute them in the isolated environment

---

## Authentication & Security

### Agent Tool Server API

To help participants get started quickly, we provide access to an online Agent Tool API with two locations. 
```
- Hong Kong & Others: 124.71.227.61
- China: 120.46.145.77
```


### Token Authentication

All API requests must include a Bearer Token:

```
Authorization: ${Token}
```

Token type is **READ permission**, only allowing calls to the `/api/agent/execute` endpoint.

### Security Measures

| Measure | Implementation |
|---------|---------------|
| Access Authentication | Bearer Token validation |
| Rate Limiting | Nginx rate limit: 50 req/s per IP |
| Daily Quota | 1,000 calls per participant per day (Phase 1 only) |
| Concurrency Limit | Max 2 concurrent per participant |
| Network Isolation | Backends have no public IP; only the router is exposed |
| Fault Isolation | Backend failures are automatically circuit-broken; no impact on other nodes |

---

## API Reference

### Request

```
POST /api/agent/execute
Content-Type: application/json
Authorization: Bearer ${Token}

{
    "device_name": "BoardLeaf1",
    "command": "display ip routing-table"
}
```

### Response

**Success (200):**
```json
{
    "status": "success",
    "device_name": "BoardLeaf1",
    "vendor": "huawei",
    "command_executed": "display ip routing-table",
    "result": "<BoardLeaf1> display ip routing-table\n..."
}
```

**Command Syntax Error (422):**
```json
{
    "status": "execution_failed",
    "device_name": "BoardLeaf1",
    "vendor": "huawei",
    "command_executed": "display ip rout",
    "result": "<BoardLeaf1> display ip rout\n                              ^\nError: Incomplete command found at '^' position."
}
```

**Device Not Found (404):**
```json
{
    "error": "Device 'UnknownDevice' not found"
}
```

---

## Participant Guide

### Environment Requirements

- Participants run Agent **locally** (Phase 1 / Phase 2)
- Agent calls the remote Agent Tool Server via HTTP
- No need to deploy the server locally (but a fallback option is provided)

### Model Rules

1. **Base Model:** The entire competition (Phase 1 / 2 / 3) uses **Qwen3.5-35B-A3B** as the base model
2. **Fine-tuning Allowed:** Participants may fine-tune Qwen3.5-35B-A3B (LoRA, full fine-tuning, etc.)
3. **No Replacement:** Replacing it with a different architecture or parameter scale is not allowed; final inference must be based on Qwen3.5-35B-A3B
4. **Phase 3 Submission:** For Phase 3, the organizer deploys the base model on GPU instances; participants only need to submit their fine-tuned weights

### API Call Rules

1. **Sequential Calls:** When solving a single problem, the Agent must call tools sequentially; no concurrent calls within a problem
2. **Concurrency Limit:** Each participant may run at most 2 tasks simultaneously (2 problems in parallel)
3. **Daily Quota:** Max 1,000 API calls per day (Phase 1 only; Phase 2 and Phase 3 are not subject to this limit)
4. **Authentication:** Every request must include the Authorization header

### Local Server Deployment

If server access issues occur, participants may deploy the Agent Tool Server locally:

1. First, unzip `devices_outputs.zip` inside the same directory
2. Then, run `python server.py` to deploy the local server.
3. An example agent workflow is provide in `agent/` folder.

After local deployment, change the Agent's target URL to `http://localhost:7860/api/agent/execute`; no Token required.

---

## Evaluation Metrics & Scoring

Each phase uses different evaluation criteria, progressively increasing in rigor:

### Scoring by Phase

| Phase | Primary Metric | Secondary Metric | Description |
|-------|---------------|-----------------|-------------|
| **Phase 1** | Accuracy | — | Scored by accuracy only |
| **Phase 2** | Accuracy | API Call Count | Accuracy first; ties broken by fewer API calls on correct problems |
| **Phase 3** | Accuracy + Speed | — | Correctness and time-based scoring (see table below) |

### Phase 3: Detailed Scoring Standards

- **Pass@1 (Consistency Metric):** Rewards agents with high success rates across 4 independent trials to ensure solution robustness.
- **TTS (Time To Solve):** Measures efficiency in pinpointing and fixing faults via logical deduction.
- **Execution Guardrail:** A strict 15-minute cutoff is implemented to prevent infinite loops and resource exhaustion.

Points are awarded only if the task is completed correctly within the allotted time. We will select the fastest solution in 4 generations. The faster the resolution, the higher the score:

| Answering time            | Discount |
| ------------------------- | -------- |
| `< 5 minutes`             | 100%     |
| `5 minutes  - 10 minutes` | 80%      |
| `10 minutes - 15 minutes` | 60%      |
| `> 15 minutes`            | 0%       |

---

## Quick Start: Running the Agent with OpenClaw

The `agent/` directory provides a ready-to-use agent solution based on **OpenClaw** (an open-source agentic framework). By combining the pre-configured skills, OpenClaw configuration files, and the batch evaluation script, participants can quickly launch an agent to solve CTBench problems locally.

### Prerequisites

1. **Clone and install OpenClaw** from its open-source repository, and ensure it runs locally (refer to the OpenClaw official documentation for installation steps).
2. **Python 3.8+** and **Node.js** installed.
3. **Agent Tool Server** running locally at `http://127.0.0.1:7860` (or the remote server with a valid Token).

### Directory Structure

```
agent/
├── openclaw_config/          # OpenClaw configuration files
│   ├── IDENTITY.md           # Agent identity definition (name, persona)
│   ├── SOUL.md               # Code of conduct & core principles
│   ├── USER.md               # Competition scenario & requirements
│   ├── AGENTS.md             # Agent coordination settings
│   └── TOOLS.md              # Available tools & NOC API conventions
├── skills/                   # Skill definitions for the agent
│   ├── infra_maintenance/    # Infrastructure maintenance (config/log/alarm/memory/LLDP)
│   ├── l2_link/              # Layer 2 link O&M (interface/VLAN/MAC/STP)
│   ├── l3_route/             # Layer 3 routing (IP/ARP/OSPF/BGP)
│   └── adv_tunnel/           # Advanced tunnels (VXLAN/VRRP/BFD/DHCP/SRv6)
├── evaluate_openclaw.py      # Batch evaluation script
├── evaluate_openclaw_guideline.md  # Detailed usage guide for the evaluation script
└── requirements.txt          # Python dependencies
```

### Configuration

1. **Copy the `openclaw_config/` files** into your local OpenClaw project's configuration directory (or symlink them) so that OpenClaw loads the agent identity, tools, and skills at startup.

2. **Copy the `skills/` directory** into your local OpenClaw project's skills directory so that the four network O&M skills (`infra_maintenance`, `l2_link`, `l3_route`, `adv_tunnel`) are available to the agent.

3. **Edit `evaluate_openclaw.py`** and set the following paths at the top of the file:

   ```python
   # Set to the absolute path of your local OpenClaw project directory
   OPENCLAW_DIR = r"C:\path\to\your\openclaw"

   # Set to the absolute path where OpenClaw stores session logs
   OPENCLAW_SESSION_DIR = r"C:\Users\YourUser\.openclaw\agents\main\sessions"
   ```

### Running the Agent

```bash
# Install Python dependencies
pip install -r agent/requirements.txt

# Run all questions from the input JSON
python agent/evaluate_openclaw.py -i data/Phase_1/test.json

# Run specific questions only
python agent/evaluate_openclaw.py -i data/Phase_1/test.json --questions 1,2,5

# Run with concurrency (max 2 for competition compliance)
python agent/evaluate_openclaw.py -i data/Phase_1/test.json --concurrency 2

# Resume from an interrupted run
python agent/evaluate_openclaw.py -i data/Phase_1/test.json --resume
```

### How It Works

1. **`evaluate_openclaw.py`** loads questions from the input JSON file, then invokes the locally running OpenClaw agent for each question.
2. The OpenClaw agent, guided by `openclaw_config/` (identity, tools, and behavioral rules), uses the four **skills** to collect device data via the API (`http://127.0.0.1:7860/api/agent/execute`).
3. The agent analyzes the collected data and produces a final answer.
4. The script extracts the answer from the OpenClaw session log and writes results to `agent/eval_results/result.csv`.

### Output

Results are saved under `agent/eval_results/`:

| File | Description |
|------|-------------|
| `result.csv` | Final answers (`id`, `prediction`) — the file to submit |
| `eval_detail.jsonl` | Detailed execution logs per question |
| `progress.json` | Progress tracking for the `--resume` feature |

For more details on the evaluation script, see [`agent/evaluate_openclaw_guideline.md`](agent/evaluate_openclaw_guideline.md).