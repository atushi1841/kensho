"""Functions for applying browser operations (placeholder)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _save_session_cookies(ctx: Any, account_key: str, session_path: Path) -> None:
    """ブラウザコンテキストのstorage_stateをJSONファイルに保存する。

    保存中にエラーが発生した場合は無視する（握りつぶす）。

    Args:
        ctx: Playwright BrowserContext
        account_key: アカウントキー（ログなどに利用）
        session_path: 保存先ファイルパス
    """
    try:
        data = ctx.storage_state()
        session_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    except Exception:
        pass
