#!/usr/bin/env python3
"""Kanban AIチームの日次サマリーを Telegram に送る。

kanban_report.py の集計をそのまま通知本文にする（前日=JST）。
ネイティブcrontab から呼ばれる想定。送信本文が空なら何もしない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    # 前日(JST)の集計
    res = subprocess.run(
        [sys.executable, str(ROOT / "kensho" / "tools" / "kanban_report.py")],
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
    )
    body = (res.stdout or "").strip()
    if not body:
        print("[kanban-daily] 集計結果が空のため送信スキップ")
        return 0

    try:
        from kensho.utils.notify import send_notification
    except Exception as e:
        print(f"[kanban-daily] notify import失敗: {e}")
        return 1

    ok = send_notification("daily_report", body)
    print(f"[kanban-daily] 送信{'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
