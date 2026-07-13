#!/bin/sh
set -e

case "$1" in
  server)
    exec python server.py
    ;;
  agent)
    shift
    exec python main.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
