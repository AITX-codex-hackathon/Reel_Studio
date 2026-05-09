#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON="$ROOT_DIR/venv/bin/python"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  local status=$?

  trap - EXIT INT TERM

  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  exit "$status"
}

is_running_job() {
  local pid="$1"
  local running_pid

  for running_pid in $(jobs -pr); do
    if [[ "$running_pid" == "$pid" ]]; then
      return 0
    fi
  done

  return 1
}

trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
  echo "Could not find the project venv at $ROOT_DIR/venv."
  echo "Create it first, then install backend dependencies:"
  echo "  /opt/homebrew/bin/python3.11 -m venv venv"
  echo "  venv/bin/python -m pip install './backend[audio,dev]'"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  npm --prefix "$FRONTEND_DIR" install
fi

echo "Starting backend on http://localhost:$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  "$PYTHON" -m uvicorn main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT"
npm --prefix "$FRONTEND_DIR" run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo
echo "Both servers are running. Press Ctrl+C to stop."

while true; do
  if ! is_running_job "$BACKEND_PID"; then
    wait "$BACKEND_PID"
    exit $?
  fi

  if ! is_running_job "$FRONTEND_PID"; then
    wait "$FRONTEND_PID"
    exit $?
  fi

  sleep 1
done
