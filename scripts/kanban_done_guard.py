#!/usr/bin/env python3
"""kensho repo 内からの done guard 呼出wrapper（t_974844f8 対応）.

card body の検証コマンド `bash scripts/kanban_done_guard.py <task_id>` が
repo 内で解决できるように、実体は profiles/kensho-sweeps の-guard を委譲する。
"""
import os
import subprocess
import sys

REAL = "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py"
if not os.path.exists(REAL):
    sys.stderr.write(f"guard 実体不在: {REAL}\n")
    sys.exit(127)

rc = subprocess.call([sys.executable, REAL] + sys.argv[1:])
sys.exit(rc)