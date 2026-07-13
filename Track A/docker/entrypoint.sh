#!/bin/sh
set -e

case "$1" in
  server)
    exec python server.py
    ;;
  agent)
    shift
    exec python main.py \
      --server_url "${SERVER_URL:-http://server:7860}" \
      --model_url "${MODEL_URL:-https://api.tokenfactory.nebius.com/v1}" \
      --model_name "${MODEL_NAME:-Qwen/Qwen3-30B-A3B-Instruct-2507}" \
      --architecture "${ARCHITECTURE:-investigator_decision}" \
      --max_samples "${MAX_SAMPLES:-10}" \
      --max_iterations "${MAX_ITERATIONS:-15}" \
      --save_dir "${SAVE_DIR:-/app/results/run}" \
      --log_file "${LOG_FILE:-/app/results/run.log}" \
      --verbose \
      "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
