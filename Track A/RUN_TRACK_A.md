# How to Run Track A

This guide assumes you are running Track A from the local project checkout and using your Nebius API key from `Track A/.env`.

## 1. Start the local tools server

Open Terminal 1:

```bash
cd "/Users/vic/Telco-Troubleshooting-Agentic-Challenge/Track A"
source .venv/bin/activate
DATA_SPLIT=train python server.py
```

Leave this terminal running.

Use `DATA_SPLIT=train` when you want labelled results and local accuracy.

Use this instead for the test split:

```bash
DATA_SPLIT=test python server.py
```

## 2. Run the current agent architecture

Open Terminal 2:

```bash
cd "/Users/vic/Telco-Troubleshooting-Agentic-Challenge/Track A"
source .venv/bin/activate
```

Run the current `investigator_decision` architecture:

```bash
python main.py \
  --server_url http://127.0.0.1:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1/ \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 10 \
  --save_dir ./results/new-run-train-10 \
  --log_file ./results/new-run-train-10.log \
  --architecture investigator_decision \
  --verbose
```

## 3. Check outputs

After the run finishes, inspect:

```text
Track A/results/new-run-train-10/results.json
Track A/results/new-run-train-10/result.csv
Track A/results/new-run-train-10.log
```

Quick terminal check:

```bash
cat ./results/new-run-train-10/result.csv
```

## 4. Run one sample for smoke testing

Use this when you only want to confirm the system works:

```bash
python main.py \
  --server_url http://127.0.0.1:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1/ \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 1 \
  --save_dir ./results/smoke-test \
  --log_file ./results/smoke-test.log \
  --architecture investigator_decision \
  --verbose
```

## 5. Run the old baseline if needed

The baseline is still available:

```bash
python main.py \
  --server_url http://127.0.0.1:7860 \
  --model_url https://api.tokenfactory.nebius.com/v1/ \
  --model_name Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max_samples 10 \
  --save_dir ./results/baseline-rerun-10 \
  --log_file ./results/baseline-rerun-10.log \
  --architecture baseline \
  --verbose
```

## Important notes

- Make sure `Track A/.env` contains:

```bash
NEBIUS_API_KEY=your_key_here
```

- Do not close Terminal 1 while Terminal 2 is running.
- Current default `--max_iterations` is `15`, so you do not need to pass it unless you want a different value.
- Use a new `--save_dir` for every experiment so you do not overwrite previous results.
