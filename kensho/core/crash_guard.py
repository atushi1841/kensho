"""
Kensho Crash Guard — 異常終了検出・状態保存・クラッシュダンプ

使い方:
  from kensho.core.crash_guard import CrashGuard

  guard = CrashGuard()
  guard.update('step', 'apply', account='atushi16', item=5, total=15, url='https://x.com/...')

動作:
  - 1秒おきに heartbeat を data/orchestrator_heartbeat.json に書き込む
  - atexit ハンドラで「正常終了しなかった」場合に crash_snapshot を保存
  - SIGTERM をキャッチして heartbeat を即座に書き込んで終了
  - main() 終了時に mark_done() で heartbeat をクリア
"""

from __future__ import annotations

import atexit
import json
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any

# ── パス設定 ──
PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
HEARTBEAT_FILE = os.path.join(PROJECT_DIR, "data", "orchestrator_heartbeat.json")
CRASH_DIR = os.path.join(PROJECT_DIR, "data", "crash_reports")
os.makedirs(CRASH_DIR, exist_ok=True)
os.makedirs(os.path.dirname(HEARTBEAT_FILE), exist_ok=True)


class CrashGuard:
    """異常終了検出ガード

    heartbeat に常に「今何をしているか」を書き続ける。
    次回起動時に heartbeat が 'done' 以外で残っていれば =
    前回異常終了した証拠。
    """

    def __init__(self, heartbeat_interval: float = 1.0) -> None:
        self._state: dict[str, Any] = {
            "step": "init",
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "account": "",
            "item": 0,
            "total": 0,
            "url": "",
            "message": "",
            "done": False,
        }
        self._interval = heartbeat_interval
        self._lock = threading.Lock()
        self._stopped = False

        # ── atexit: 正常終了しなかったらクラッシュダンプを保存 ──
        atexit.register(self._on_exit)

        # ── SIGTERM ハンドラ (taskkill等で呼ばれる) ──
        try:
            signal.signal(signal.SIGTERM, self._handle_sigterm)
        except (ValueError, OSError):
            pass  # 非メインスレッドでは登録できない

        # ── ハートビートスレッド開始 ──
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def update(
        self,
        step: str,
        message: str = "",
        *,
        account: str = "",
        item: int = 0,
        total: int = 0,
        url: str = "",
    ) -> None:
        """現在の状態を更新（直ちにファイルに反映）"""
        with self._lock:
            self._state["step"] = step
            self._state["message"] = message
            self._state["account"] = account
            self._state["item"] = item
            self._state["total"] = total
            self._state["url"] = url
            self._state["updated_at"] = datetime.now().isoformat()
        self._flush()

    def mark_done(self) -> None:
        """正常終了時に呼ぶ → heartbeat を done に設定"""
        with self._lock:
            self._state["done"] = True
            self._state["step"] = "done"
            self._state["message"] = "正常終了"
            self._state["updated_at"] = datetime.now().isoformat()
        self._flush()
        self._stopped = True

    def _flush(self) -> None:
        """状態をファイルに書き込む"""
        try:
            with self._lock:
                data = dict(self._state)
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 書き込み失敗は無視（クラッシュ中はどうせ読めない）

    def _heartbeat_loop(self) -> None:
        """定期的に heartbeat を更新"""
        while not self._stopped:
            self._flush()
            time.sleep(self._interval)

    def _on_exit(self) -> None:
        """atexit: プロセス終了時に呼ばれる"""
        if self._stopped:
            # mark_done() が呼ばれていたら何もしない
            return
        if self._state.get("done"):
            return
        # 正常終了しなかった → クラッシュダンプ保存
        self._save_crash_dump()

    def _handle_sigterm(self, signum: int, frame: Any) -> None:
        """SIGTERM 受信時: 状態を書き込んで終了"""
        self._state["step"] = "sigterm"
        self._state["message"] = f"SIGTERM受信 (signal={signum})"
        self._state["updated_at"] = datetime.now().isoformat()
        self._flush()
        self._save_crash_dump()
        sys.exit(128 + signum)

    def _save_crash_dump(self) -> None:
        """クラッシュダンプファイルを保存"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            # スレッドダンプも収集
            frames = []
            try:
                import threading as _thr

                for t in _thr.enumerate():
                    frames.append({
                        "thread": t.name,
                        "is_alive": t.is_alive(),
                        "daemon": t.daemon,
                    })
            except Exception:
                pass

            dump = {
                "crash_time": ts,
                "pid": os.getpid(),
                "heartbeat": dict(self._state),
                "threads": frames,
                "traceback": traceback.format_exc() if sys.exc_info()[0] else "",
            }
            path = os.path.join(CRASH_DIR, f"crash_{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ── 簡易関数インターフェース ──
_guard: CrashGuard | None = None


def start() -> CrashGuard:
    """CrashGuard を開始する（main()の先頭で1回呼ぶ）"""
    global _guard
    if _guard is None:
        _guard = CrashGuard()
    return _guard


def get() -> CrashGuard | None:
    """現在の CrashGuard インスタンスを取得"""
    return _guard


def _pid_is_alive(pid: int) -> bool:
    """pid が生存しているかを確認（並列実行の進行中判定用）"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 存在するが権限不足 → 実行中とみなす
    except OSError:
        return False


def check_previous_crash() -> dict[str, Any] | None:
    """前回のクラッシュ状態を確認（次回起動時に呼ぶ）"""
    try:
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, encoding="utf-8") as f:
                hb = json.load(f)
            if not hb.get("done", False):
                # 並列実行中: 別垢プロセスの最後のが done:False でも、
                # その pid がまだ生存していれば「進行中」であり異常終了ではない。
                # 真に前回プロセスが終了(or死亡)していた場合のみクラッシュとみなす。
                pid = hb.get("pid")
                if isinstance(pid, int) and _pid_is_alive(pid):
                    return None
                return dict(hb)
    except Exception:
        pass
    return None


def list_crash_reports(limit: int = 5) -> list[dict[str, Any]]:
    """保存されたクラッシュレポート一覧"""
    if not os.path.isdir(CRASH_DIR):
        return []
    reports = []
    for fname in sorted(os.listdir(CRASH_DIR), reverse=True)[:limit]:
        if fname.endswith(".json"):
            try:
                with open(os.path.join(CRASH_DIR, fname), encoding="utf-8") as f:
                    reports.append(json.load(f))
            except Exception:
                reports.append({"file": fname, "error": "read failed"})
    return reports
