"""
Kensho Session Monitor — auth_token/ct0 有効期限監視
各アカウントのセッションファイルを読み込み、期限切れを事前警告
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# 警告を出す残り日数
WARN_DAYS: int = 14
# ct0の標準有効期間（秒） — 推定1年
CT0_MAX_AGE: float = 365 * 24 * 3600

BASE: Path = Path(__file__).parent.parent
DATA_DIR: Path = BASE / "data"


def check_session(account_key: str, session_path: str) -> dict[str, Any]:
    """1アカウントのセッションをチェック"""
    result: dict[str, Any] = {
        "account": account_key,
        "status": "OK",
        "warnings": [],
        "auth_token": "",
        "ct0": "",
    }

    full_path: Path = BASE / session_path
    if not full_path.exists():
        result["status"] = "ERROR"
        result["warnings"].append(f"セッションファイルなし: {session_path}")
        return result

    try:
        with open(full_path, encoding="utf-8") as f:
            session: dict[str, Any] = json.load(f)

        cookies: list[dict[str, Any]] = session.get("cookies", [])
        now: float = datetime.now().timestamp()

        for c in cookies:
            name: str = c.get("name", "")
            value: str = c.get("value", "")

            if name == "auth_token":
                result["auth_token"] = f"{value[:8]}...{value[-4:]}"
                # auth_token は無期限だが存在確認のみ
                if not value or len(value) < 10:
                    result["status"] = "WARN"
                    result["warnings"].append("auth_token が不正または短すぎる")

            elif name == "ct0":
                result["ct0"] = f"{value[:8]}...{value[-4:]}"
                # ct0 の有効期限はファイル作成日から推定
                if full_path.stat().st_mtime:
                    age_days: float = (now - full_path.stat().st_mtime) / 86400
                    remaining_days: float = 365 - age_days
                    if remaining_days < WARN_DAYS:
                        result["status"] = "WARN"
                        result["warnings"].append(
                            f"ct0 有効期限まであと{remaining_days:.0f}日 （{WARN_DAYS}日を切ったら再取得推奨）"
                        )
                    else:
                        result["warnings"].append(f"ct0 残り{remaining_days:.0f}日（問題なし）")

    except Exception as e:
        result["status"] = "ERROR"
        result["warnings"].append(f"読み込みエラー: {e}")

    return result


def main() -> None:
    """メイン"""
    config_path: Path = BASE / "config.yaml"
    if not config_path.exists():
        print("[SessionMonitor] config.yaml が見つかりません")
        return

    import yaml

    with open(config_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    print(f"[SessionMonitor] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_ok: bool = True
    for acct in cfg.get("accounts", []):
        key: str = acct["key"]
        session_file: str = acct["session"]
        result: dict[str, Any] = check_session(key, session_file)

        icon: str = "✅" if result["status"] == "OK" else "⚠️" if result["status"] == "WARN" else "❌"
        print(f"  {icon} {key} ({result['status']})")
        print(f"    auth_token: {result['auth_token']}")
        print(f"    ct0:        {result['ct0']}")
        for w in result["warnings"]:
            print(f"    {w}")
        if result["status"] != "OK":
            all_ok = False
        print()

    if all_ok:
        print("  全アカウント正常です ✅")
    else:
        print("  ⚠️ 警告のあるアカウントはセッション再取得を検討してください")

    # Windowsトースト通知（警告がある場合）
    if not all_ok:
        try:
            from kensho.core.notifier import notify

            notify("Kensho Session Monitor", "一部のアカウントでセッションの期限が近づいています")
        except Exception:
            pass


if __name__ == "__main__":
    main()
