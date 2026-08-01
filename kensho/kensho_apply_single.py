#!/usr/bin/env python3
"""Kensho Single Apply — 手動CLI: 1垢の応募を実行（ForceBindIP不要、orchestratorは直接呼び出し）"""

from __future__ import annotations

import os
import signal
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kensho.core.encoding import guard_stdio

guard_stdio()
from kensho.application.applier import apply_for_account  # noqa: E402


def _signal_handler(signum: int, frame) -> None:
    """Gracefully shut down on SIGTERM/SIGINT."""
    print(f"\n[KILL] Received signal {signum}, shutting down gracefully...", flush=True)
    sys.exit(128 + signum)


def _check_crash_history() -> bool:
    """過去10分以内に2回以上のクラッシュがある場合は実行を拒否してTrueを返す。"""
    import datetime as dt
    import json
    from pathlib import Path

    crash_file = Path(__file__).parent / "data" / "crash_history.json"
    crash_file.parent.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now()
    recent_crashes = []

    # 既存のクラッシュ履歴を読み込み、10分以上前のものは削除
    if crash_file.exists():
        try:
            history = json.loads(crash_file.read_text(encoding="utf-8"))
            for ts in history:
                try:
                    crash_time = dt.datetime.fromisoformat(ts)
                    if (now - crash_time).total_seconds() < 600:  # 10分
                        recent_crashes.append(ts)
                except Exception:
                    pass
        except Exception:
            recent_crashes = []

    # 今回の実行自体もクラッシュとして記録（正常終了時に削除される）
    recent_crashes.append(now.isoformat())
    crash_file.write_text(json.dumps(recent_crashes, ensure_ascii=False), encoding="utf-8")

    if len(recent_crashes) > 2:  # 10分以内に3回以上のクラッシュ/実行
        print(
            f"\n[CRASH-LOOP] ⚠ 過去10分以内に{len(recent_crashes)}回のクラッシュを検出。\n"
            f"  クラッシュループ防止のため、実行を中断します。\n"
            f"  原因を確認の上、手動で data/crash_history.json を削除して再試行してください。\n",
            flush=True,
        )
        return True
    return False


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # クラッシュループ検知
    if _check_crash_history():
        sys.exit(2)

    from argparse import ArgumentParser

    _p = ArgumentParser(description="Kensho 単一アカウント応募（CLI）")
    _p.add_argument("account", help="アカウントキー (例: atushi16)")
    _p.add_argument("max_n", type=int, nargs="?", default=10, help="最大処理件数（省略時10）")
    _p.add_argument("--dry-run", action="store_true", help="実際に応募せずログのみ")
    _args = _p.parse_args()

    try:
        succ, err = apply_for_account(_args.account, _args.max_n, dry_run=_args.dry_run)
        print(f"\nRESULT: {succ} success, {err} errors")
        sys.exit(1 if err > 0 else 0)
    finally:
        # 正常終了時はクラッシュ履歴をクリア
        import json as _json
        from pathlib import Path as _Path

        _cf = _Path(__file__).parent / "data" / "crash_history.json"
        if _cf.exists():
            _cf.write_text(_json.dumps([]), encoding="utf-8")
