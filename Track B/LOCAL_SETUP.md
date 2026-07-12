# Track B — Local Setup (No OpenClaw Required)

Run Track B with **`main.py`** — a self-contained Python agent like Track A. You do **not** need the OpenClaw GitHub repo unless you want the optional reference agent in `agent/`.

## What you need

| Component | Required? | Notes |
|-----------|-----------|--------|
| Python 3.8+ venv | Yes | Same as Track A |
| `devices_outputs.zip` | Yes (local server) | Unzip in `Track B/` — download full file from HuggingFace if the repo copy is an LFS pointer |
| `server.py` | Yes | CLI simulation sandbox |
| `main.py` | Yes | Standalone agent (this guide) |
| LLM API key | Yes | Token Factory, OpenRouter, or local vLLM |
| OpenClaw | **No** | Optional reference only |

---

## Step 1: Python environment

```bash
cd ~/telco-agentic-study-o.e
source .venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate

cd "Track B"
pip install -r requirements.txt
```

---

## Step 2: Unzip device data (one-time)

```bash
cd ~/telco-agentic-study-o.e/"Track B"
unzip -o devices_outputs.zip
```

You should get a `devices_outputs/` folder with per-question device CLI outputs. If unzip fails with "cannot find zipfile directory", re-download the dataset from HuggingFace — the git copy may only contain an LFS pointer.

---

## Step 3: Start the tool server

**Terminal 1** (leave running):

```bash
source .venv/bin/activate
cd ~/telco-agentic-study-o.e/"Track B"
python server.py
```

Server listens on **`http://localhost:7860`**.

### Smoke-test (no LLM needed)

```bash
curl -s http://localhost:7860/api/agent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "Gamma-Aegis-01",
    "command": "display interface brief",
    "question_number": 1
  }' | python3 -m json.tool
```

Expect `"status": "success"` and CLI output in `"result"`.

---

## Step 4: Set your LLM API key

Same pattern as Track A. **Do not hardcode keys in source.**

```bash
export NEBIUS_API_KEY="your-token-factory-key"
# or
export AGENT_API_KEY="your-openrouter-key"
```

List models your Token Factory account can use:

```bash
curl -s https://api.tokenfactory.nebius.com/v1/models \
  -H "Authorization: Bearer $NEBIUS_API_KEY" | python3 -c "
import sys, json
for m in json.load(sys.stdin).get('data', []):
    print(m['id'])
"
```

Pick a model from that list (e.g. `Qwen/Qwen3-30B-A3B-Instruct-2507`). The competition model `Qwen3.5-35B-A3B` may not be on Token Factory.

---

## Step 5: Run the agent

**Terminal 2:**

```bash
source .venv/bin/activate
cd ~/telco-agentic-study-o.e/"Track B"

# Smoke test — 1 problem
python main.py \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1 \
  --verbose
```

### All Phase 1 questions

```bash
python main.py \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --input_json data/Phase_1/test.json
```

### Output

| File | Contents |
|------|----------|
| `results/result.csv` | `scenario_id`, `prediction` |
| `results/results.json` | Full run traces per scenario |
| `log.log` | Execution log |

---

## CLI reference

| Flag | Default | Purpose |
|------|---------|---------|
| `--input_json` | `data/Phase_1/test.json` | Questions file |
| `--server_url` | `http://localhost:7860` | Tool server base URL |
| `--tool_token` | env `ZINDI_TOKEN` | Bearer token for **remote** tool server only |
| `--model_url` | OpenRouter | LLM API base URL |
| `--model_name` | `qwen/qwen3.5-35b-a3b` | LLM model ID |
| `--api_key` | env vars | LLM key (overrides env) |
| `--max_samples` | all | Limit number of problems |
| `--max_iterations` | 15 | Max tool-calling rounds per problem |
| `--verbose` | off | Print tool calls and API errors |

### API key priority (`main.py`)

1. `--api_key` CLI flag
2. `NEBIUS_API_KEY` environment variable
3. `AGENT_API_KEY` environment variable

### Tool server auth

- **Local** (`python server.py`): no token needed
- **Remote** (124.71.227.61 / 120.46.145.77):

```bash
export ZINDI_TOKEN="your-zindi-bearer-token"

python main.py \
  --server_url http://124.71.227.61 \
  --tool_token "$ZINDI_TOKEN" \
  ...
```

---

## Remote tool server (optional)

Instead of local `server.py`:

| Region | Host |
|--------|------|
| Hong Kong / others | `124.71.227.61` |
| China | `120.46.145.77` |

Use `--server_url http://124.71.227.61` and `--tool_token "$ZINDI_TOKEN"`.

Phase 1 limits: 1,000 API calls/day, max 2 problems in parallel, sequential CLI calls per problem.

---

## OpenClaw (optional alternative)

The `agent/` folder is an **optional** OpenClaw-based reference agent. It requires:

- Cloning [OpenClaw](https://github.com/openclaw/openclaw) separately
- Node.js
- Copying `agent/openclaw_config/` and `agent/skills/` into OpenClaw
- Running `agent/evaluate_openclaw.py`

Use **`main.py`** if you want everything in this repo without extra dependencies.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate venv: `source .venv/bin/activate` |
| Server starts but commands return 404 | Run `unzip devices_outputs.zip` |
| LLM 401 | Wrong key or wrong `--model_url` for your provider |
| LLM 404 | Model not in your `/v1/models` list — pick one that is |
| Empty answers | Run with `--verbose`, check `log.log` for LLM errors |
| unzip fails | Re-download full `devices_outputs.zip` from HuggingFace |

---

## Quick copy-paste (local + Token Factory)

```bash
# Terminal 1
cd ~/telco-agentic-study-o.e && source .venv/bin/activate
cd "Track B" && unzip -o devices_outputs.zip && python server.py

# Terminal 2
cd ~/telco-agentic-study-o.e && source .venv/bin/activate
export NEBIUS_API_KEY="your-key"
cd "Track B"
python main.py \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1 \
  --verbose
```
