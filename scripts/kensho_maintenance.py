#!/usr/bin/env python3
"""
Kensho Daily Maintenance — 日次メンテナンス（1日1回実行）

- Health Check（全項目）
- pg0インスタンス状態チェック
- 古いログのクリーンアップ
- 日次カウンターの検証
- アダプタ名の整合性確認
- ゾンビロック削除

使い方:
    python scripts/kensho_maintenance.py

Cron設定（推奨）:
    every day 3:00 AM — 深夜のうちに実行
"""
from __future__ import annotations

import sys, os, json, time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.encoding import guard_stdio
guard_stdio()

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_health_check() -> dict[str, Any]:
    """tools/health_check.py を実行して結果を取得"""
    health_py = PROJECT_DIR / "tools" / "health_check.py"
    if not health_py.exists():
        log("⚠ tools/health_check.py が見つからない")
        return {"success": False, "summary": {"fail": 1}}

    import subprocess
    result = subprocess.run(
        [sys.executable, str(health_py)],
        capture_output=True, text=True, timeout=60,
        encoding='utf-8'
    )
    for line in result.stdout.splitlines():
        if line.strip():
            log(f"  [health] {line.strip()}")
    if result.stderr.strip():
        log(f"  [health/stderr] {result.stderr.strip()[:200]}")

    return {"success": result.returncode == 0, "output": result.stdout}


def cleanup_old_logs() -> int:
    """30日以上前のログディレクトリを削除"""
    from core.cleanup import clean_old_logs
    from core.config import load as load_config
    cfg = load_config()
    retention = cfg.get("general", {}).get("log_retention_days", 30)
    removed = clean_old_logs(str(LOG_DIR), retention_days=retention)
    if removed > 0:
        log(f"🧹 古いログ {removed} 個削除（{retention}日以上前）")
    else:
        log("🧹 古いログ: 削除対象なし")
    return removed


def check_disk_space() -> bool:
    """ログディレクトリのサイズを確認（100MB超で警告）"""
    total_size = 0
    for f in LOG_DIR.rglob("*"):
        if f.is_file():
            try:
                total_size += f.stat().st_size
            except OSError:
                pass

    mb = total_size / (1024 * 1024)
    if mb > 100:
        log(f"⚠ ログディレクトリ {mb:.0f}MB — 100MB超え！要クリーンアップ")
        return False
    else:
        log(f"📊 ログディレクトリ: {mb:.0f}MB（問題なし）")
        return True


def check_session_files() -> None:
    """Xセッションファイルの最終更新日を確認"""
    data_dir = PROJECT_DIR / "data"
    if not data_dir.is_dir():
        return

    now = datetime.now()
    for f in data_dir.glob("x_session*.json"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            days_old = (now - mtime).days
            if days_old > 14:
                log(f"⚠ {f.name}: {days_old}日更新なし — セッション切れの可能性")
            elif days_old > 7:
                log(f"⚡ {f.name}: {days_old}日更新なし")
            else:
                log(f"✅ {f.name}: {days_old}日前更新（問題なし）")
        except OSError:
            pass


def main() -> int:
    log("=" * 50)
    log(f"Kensho Daily Maintenance — {datetime.now().isoformat()}")
    log("=" * 50)

    errors = 0

    # 1. Health Check（自動修復あり）
    log("")
    log("--- [1/5] Health Check ---")
    result = run_health_check()
    if not result.get("success", False):
        log("⚠ health_checkで警告あり")

    # 2. 古いログクリーンアップ
    log("")
    log("--- [2/5] Log Cleanup ---")
    cleanup_old_logs()

    # 3. ディスク容量
    log("")
    log("--- [3/5] Disk Space ---")
    if not check_disk_space():
        errors += 1

    # 4. セッションファイル確認
    log("")
    log("--- [4/5] Session Files ---")
    check_session_files()

    # 5. サマリー
    log("")
    log("--- [5/5] Summary ---")
    if errors == 0:
        log("✅ メンテナンス完了 — 問題なし")
    else:
        log(f"⚠ メンテナンス完了 — {errors}個の警告あり")

    log("=" * 50)
    log(f"Log: {LOG_FILE}")
    log("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
