#!/usr/bin/env bash
set -u
cd /mnt/d/Project2/kensho
PY=/home/atushi/.hermes/hermes-agent/venv/bin/python3
timeout 240 $PY -m scripts.camera_monitor --limit 2 2>&1 | tail -30
echo "rc=$?"