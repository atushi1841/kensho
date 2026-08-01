"""
Kensho PID Lock — 多重起動防止の汎用ロック (DEPRECATED)
"""

# DEPRECATION: このPIDロックは kensho-auto-apply.sh の flock 機構に代替されています。
from __future__ import annotations

import atexit
import os
import traceback as _tb
from pathlib import Path

import psutil

LOCK_BASE: Path = Path(__file__).resolve().parent.parent.parent / "data" / "locks"


def acquire_pid_lock(lock_name: str) -> Path | None:
    """
    PIDロックを取得する。
    既存プロセスが稼働中なら None を返し、新規ロックが取れたら Path を返す。
    """
    LOCK_BASE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_BASE.mkdir(exist_ok=True)
    lock_path: Path = LOCK_BASE / f"{lock_name}.pid"

    if lock_path.exists():
        try:
            old_pid: int = int(lock_path.read_text().strip())
            if psutil.pid_exists(old_pid):
                print(f"[LOCK] 別プロセス実行中 (PID {old_pid}) → 終了", flush=True)
                return None
        except Exception:
            print(f"[LOCK] PIDロック読み込み失敗: {_tb.format_exc()[-100:]}", flush=True)
        try:
            lock_path.unlink()
        except Exception:
            pass

    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(_cleanup_lock, lock_path)
    return lock_path


def _cleanup_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass
