"""
Kensho PID Lock — 多重起動防止 + ハング(stale)検出付き汎用ロック
"""

from __future__ import annotations

import atexit
import os
import time
import traceback as _tb
from pathlib import Path

import psutil

LOCK_BASE: Path = Path(__file__).resolve().parent.parent.parent / "data" / "locks"

# ロックがこの秒数以上、握ったまま進捗(開始時刻基準)が無ければハングとみなすデフォルト
DEFAULT_MAX_STALE_SECONDS: int = 3600  # 1時間


def acquire_pid_lock(lock_name: str, max_stale_seconds: int = DEFAULT_MAX_STALE_SECONDS) -> Path | None:
    """
    PIDロックを取得する。

    - 既存プロセスが稼働中 → None（ブロック）
    - 既存プロセスが死んでいる → ロックを再利用
    - 既存プロセスが生きているがハング(開始から max_stale_seconds 超過)している
      → 旧プロセスを kill して引き継ぐ（デッドロック放置による全体停止を防ぐ）

    ロックファイル書式:
        1行目: pid
        2行目: 開始 epoch 秒
    """
    LOCK_BASE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_BASE.mkdir(exist_ok=True)
    lock_path: Path = LOCK_BASE / f"{lock_name}.pid"

    if lock_path.exists():
        old_pid: int | None = None
        start_ts: float | None = None
        try:
            lines = lock_path.read_text(encoding="utf-8").strip().splitlines()
            old_pid = int(lines[0].strip())
            if len(lines) >= 2 and lines[1].strip().replace(".", "", 1).isdigit():
                start_ts = float(lines[1].strip())
        except Exception:
            print(f"[LOCK] PIDロック読み込み失敗: {_tb.format_exc()[-100:]}", flush=True)

        if old_pid is not None:
            if not _pid_alive(old_pid):
                # プロセスは既に死んでいる → 引き継ぐ
                print(f"[LOCK] 前回PID {old_pid} は終了済み → ロック再利用", flush=True)
                lock_path.unlink(missing_ok=True)
            elif _is_stale(old_pid, start_ts, max_stale_seconds) and _is_our_worker(old_pid, lock_name):
                # ハング(デッドロック)は生存しているが進捗が無い → 回収
                _kill_tree(old_pid)
                print(
                    f"[LOCK] 前回PID {old_pid} がハング(>={max_stale_seconds}s) → killして引き継ぎ",
                    flush=True,
                )
                lock_path.unlink(missing_ok=True)
            else:
                print(f"[LOCK] 別プロセス実行中 (PID {old_pid}) → 終了", flush=True)
                return None

    lock_path.write_text(f"{os.getpid()}\n{time.time()}\n", encoding="utf-8")
    atexit.register(_cleanup_lock, lock_path)
    return lock_path


def _is_stale(old_pid: int, start_ts: float | None, max_stale_seconds: int) -> bool:
    """開始時刻から max_stale_seconds 以上経過していればハングとみなす。"""
    if start_ts is None:
        return False  # 開始時刻不明(旧形式)は保守的にブロック継続
    return (time.time() - start_ts) > max_stale_seconds


def _pid_alive(pid: int) -> bool:
    """psutil.pid_exists の安全ラッパー。

    psutil 5.9.8 の既知バグ: WSL の /proc がトリガーで pid_exists が
    `TypeError: startswith first arg must be str or a tuple of str, not bytes`
    を時折投げる（バイト/文字列混在ディレクトリ走査）。単独呼び出しでは
    再現せず、大量プロセス走査時に出るため実運用で落ちる。

    クラッシュさせず、確認不能な場合は「生存している」とみなして
    多重起動ブロックを維持する（安全側に倒す）。ロックが取れないだけで
    応募は次のサイクルで再試行されるため、過度に警戒する必要はない。
    """
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return True  # 確認不能 → 生存扱い（ブロック継続、安全側）


def _is_our_worker(old_pid: int, lock_name: str) -> bool:
    """そのPIDが本当に該当ワーカー(orchestrator等)かを確認（PID再利用対策）。"""
    try:
        p = psutil.Process(old_pid)
        cmdline = " ".join(p.cmdline() or [])
        return lock_name in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _kill_tree(old_pid: int) -> None:
    """プロセスの子孫を先に殺し、最後に親を殺す。存続されても無視。"""
    try:
        parent = psutil.Process(old_pid)
        kids = parent.children(recursive=True)
        for child in kids:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def _cleanup_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass
