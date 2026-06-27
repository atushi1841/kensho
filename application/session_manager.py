"""
Kensho Session Manager — セッションファイルの管理・監視
v3.4: keyring対応（Credential Manager優先、ファイルフォールバック）
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from utils.keyring import load_session


def get_session_data(account_key: str) -> dict[str, Any] | None:
    """
    アカウントのセッションデータを取得。
    優先順位: Credential Manager → 従来のセッションファイル
    """
    return load_session(account_key)

def check_sessions(cfg: dict[str, Any], log: Any = None) -> list[tuple[str, str, float]]:
    """
    全アカウントのセッションファイルの最終更新日時を確認。
    閾値を超えているものがあれば警告をログに記録。

    戻り値: list of (account_key, display_name, days_since_update)
    """
    project_dir = Path(cfg['general']['project_dir'])
    warn_days = cfg['general'].get('session_warn_days', 3)
    warnings: list[tuple[str, str, float]] = []

    now = time.time()

    for acct in cfg.get('accounts', []):
        key = acct['key']
        display = acct.get('display', key)
        session_rel = acct['session']
        session_path = project_dir / session_rel

        if not session_path.exists():
            warnings.append((key, display, -1))  # -1 = ファイルなし
            if log:
                log.write(f"[!] Session: {display} セッションファイルなし: {session_rel}")
            continue

        mtime = os.path.getmtime(session_path)
        days = (now - mtime) / 86400

        # アカウント別の閾値（あれば）
        acct_warn = acct.get('session_max_age_days', warn_days)

        if days > acct_warn:
            warnings.append((key, display, round(days, 1)))
            if log:
                log.write(
                    f"[!] Session: {display} のセッションが {days:.0f}日間未更新"
                    f"（閾値: {acct_warn}日）"
                )
        else:
            if log:
                log.write(f"[OK] Session: {display} OK（最終更新: {days:.0f}日前）")

    return warnings
