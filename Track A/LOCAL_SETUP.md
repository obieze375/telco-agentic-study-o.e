# Track A — Local Setup & Script Changes

This document describes how to run Track A locally, including changes made to `main.py` for API authentication and LLM provider configuration.

## 1. Python environment (Kali / Debian)

System Python on Kali is externally managed (PEP 668). Use a virtual environment:

```bash
cd ~/telco-agentic-study-o.e
python3 -m venv .venv
source .venv/bin/activate

cd "Track A"
pip install -r requirements.txt
```

## 2. Start the tool server

In one terminal:

```bash
source .venv/bin/activate
cd "Track A"
python server.py
```

The server listens on `http://localhost:7860` by default.

## 3. Changes made to `main.py`

### 3.1 Removed hardcoded API key

**Before:** `main.py` overwrote any environment variable on every run:

```python
os.environ['AGENT_API_KEY'] = 'sk-XXXXXXXXXXXXX'
API_KEY = os.environ.get("AGENT_API_KEY", "dummy")
```

This meant `export NEBIUS_API_KEY=...` in the shell had no effect.

**After:** Keys are resolved at runtime via `resolve_api_key()` with a clear priority order. No secrets are stored in source code.

### 3.2 Added `resolve_api_key()` function

```python
def resolve_api_key(cli_key: Optional[str] = None) -> str:
    if cli_key:
        return cli_key
    return os.environ.get("NEBIUS_API_KEY") or os.environ.get("AGENT_API_KEY") or "dummy"
```

### 3.3 Added `--api_key` CLI flag

You can pass the LLM API key on the command line without editing the script:

```bash
python main.py --api_key "$NEBIUS_API_KEY" ...
```

### 3.4 API key passed explicitly to `AgentsRunner`

The OpenAI-compatible client now receives `api_key` as a constructor argument instead of reading a module-level global.

### 3.5 Updated `requirements.txt`

Added runtime dependencies that were missing from the original file:

- `uvicorn` — required by `server.py`
- `httpx` — used by the OpenAI client in `main.py`
- `requests` — used by `main.py`

---

## 4. How to pass the API token

The script talks to **two** different services. Use the correct credential for each:

| Service | Purpose | Credential |
|---------|---------|------------|
| **LLM API** (Token Factory, OpenRouter, local vLLM) | Model inference / tool calling | `NEBIUS_API_KEY`, `AGENT_API_KEY`, or `--api_key` |
| **Tool server** (`server.py` or remote) | 5G simulation tools | Zindi Bearer token in `Environment._headers()` (remote only) |

For **local** `server.py`, no tool-server token is required.

### Option A — Environment variable (recommended)

**Nebius Token Factory:**

```bash
export NEBIUS_API_KEY="your-token-factory-key"

python main.py \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1
```

**OpenRouter:**

```bash
export AGENT_API_KEY="your-openrouter-key"

python main.py \
  --server_url http://localhost:7860 \
  --model_url https://openrouter.ai/api/v1 \
  --model_name qwen/qwen3.5-35b-a3b \
  --max_samples 1
```

`NEBIUS_API_KEY` takes priority over `AGENT_API_KEY` when both are set.

### Option B — CLI flag

```bash
python main.py \
  --api_key "$NEBIUS_API_KEY" \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1
```

`--api_key` overrides both environment variables.

### Option C — Local vLLM (no real key needed)

```bash
export AGENT_API_KEY="not-needed"

python main.py \
  --server_url http://localhost:7860 \
  --model_url http://localhost:8000/v1 \
  --model_name Qwen3.5-35B-A3B \
  --max_samples 1
```

---

## 5. LLM provider configuration

`main.py` defaults to OpenRouter. For **Nebius Token Factory**, override both URL and model:

```bash
--model_url https://api.tokenfactory.nebius.com/v1
--model_name <model-id-from-your-account>
```

### List models available on your Token Factory account

```bash
curl -s https://api.tokenfactory.nebius.com/v1/models \
  -H "Authorization: Bearer $NEBIUS_API_KEY" | python3 -m json.tool
```

Only use model IDs that appear in the `"data"` list. Requesting a model not in that list returns **HTTP 404**.

### Common errors

| HTTP status | Cause | Fix |
|-------------|-------|-----|
| **401** | Wrong API key, or Token Factory key sent to OpenRouter URL | Match key to `--model_url` |
| **404** | Model ID not in your `/v1/models` list | Pick a model from the list command above |

### Competition model note

The competition requires **Qwen3.5-35B-A3B**. Nebius Token Factory may not host that exact model. Use Token Factory for development (e.g. `Qwen/Qwen3-30B-A3B-Instruct-2507`) and deploy the competition model locally via vLLM for final submissions.

---

## 6. Full run example (Token Factory + local server)

**Terminal 1 — tool server:**

```bash
source .venv/bin/activate
cd "Track A"
python server.py
```

**Terminal 2 — agent:**

```bash
source .venv/bin/activate
cd "Track A"
export NEBIUS_API_KEY="your-token-factory-key"

python main.py \
  --server_url http://localhost:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1 \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1 \
  --verbose
```

Output is written to `results/result.csv`.

---

## 7. Verify API key before running the agent

```bash
curl -s https://api.tokenfactory.nebius.com/v1/chat/completions \
  -H "Authorization: Bearer $NEBIUS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_tokens": 10
  }'
```

A JSON response with `"choices"` means the key and model are correct.
