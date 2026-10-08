#!/usr/bin/env bash
# Kensho Cron Wrapper — skip-if-running + exponential backoff
# Usage: cron_wrapper.sh <job_id> <command> [args...]

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <job_id> <command> [args...]" >&2
  exit 1
fi

JOB_ID="$1"
shift
CMD=("$@")

# State directory for PID files and backoff state
STATE_DIR="$HOME/.hermes/state"
mkdir -p "$STATE_DIR"
PID_FILE="$STATE_DIR/${JOB_ID}.pid"
BACKOFF_FILE="$STATE_DIR/${JOB_ID}.backoff"

# Skip-if-running: check if PID file exists and process is alive
if [[ -f "$PID_FILE" ]]; then
  PID=$(cat "$PID_FILE")
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $JOB_ID: skip-if-running (PID $PID active)" >&2
    exit 0
  fi
fi

# Write our PID
echo "$$" > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

# Read backoff state
FAILURE_COUNT=0
NEXT_ALLOWED=0
if [[ -f "$BACKOFF_FILE" ]]; then
  if IFS=: read -r failure_count next_allowed < "$BACKOFF_FILE"; then
    FAILURE_COUNT="$failure_count"
    NEXT_ALLOWED="$next_allowed"
  fi
fi

# Check backoff period
NOW=$(date +%s)
if [[ $NOW -lt $NEXT_ALLOWED ]]; then
  BACKOFF_SECONDS=$((NEXT_ALLOWED - NOW))
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $JOB_ID: exponential backoff (${FAILURE_COUNT} failures, wait ${BACKOFF_SECONDS}s)" >&2
  rm -f "$PID_FILE"
  exit 0
fi

# Execute
echo "[$(date +'%Y-%m-%d %H:%M:%S')] $JOB_ID: starting (attempt $((FAILURE_COUNT + 1)))" >&2
if "${CMD[@]}"; then
  echo "0:0" > "$BACKOFF_FILE"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $JOB_ID: completed successfully" >&2
  exit 0
else
  NEW_FAILURE_COUNT=$((FAILURE_COUNT + 1))
  BASE_DELAY=30
  DELAY=$((BASE_DELAY * (2 ** FAILURE_COUNT)))
  if [[ $DELAY -gt 3600 ]]; then DELAY=3600; fi
  NEW_NEXT_ALLOWED=$((NOW + DELAY))
  echo "${NEW_FAILURE_COUNT}:${NEW_NEXT_ALLOWED}" > "$BACKOFF_FILE"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $JOB_ID: failed (failure $NEW_FAILURE_COUNT, retry in ${DELAY}s)" >&2
  rm -f "$PID_FILE"
  exit 1
fi
