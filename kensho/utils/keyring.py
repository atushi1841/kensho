"""
Kensho Keyring — Xセッション認証情報の安全な保存・取得
Windows Credential Manager 経由で保管（平文JSONからの脱却）。

使い方:
  from kensho.utils.keyring import save_session, load_session
  save_session('atushi16', {'auth_token': 'xxx', 'ct0': 'yyy'})
  data = load_session('atushi16')
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import keyring

SERVICE_NAME: str = "kensho-sweeps"
SESSION_FILE_DIR: Path = Path(__file__).parent.parent.parent / "data"


def _get_session_path(account_key: str) -> Path:
    """ファイルフォールバック用のパス"""
    name: str = {
        "atushi16": "x_session.json",
        "kudou": "x_session_kudou.json",
        "atushi1840": "x_session_b.json",
        "zin20120731": "x_session_c.json",
        "inobase1-4": "x_session_inobase1-4.json",
    }.get(account_key, f"x_session_{account_key}.json")
    return SESSION_FILE_DIR / name


def save_session(account_key: str, data: dict[str, Any]) -> bool:
    """
    セッションデータを Credential Manager に安全に保存。
    フォールバック: 従来のJSONファイルにも書き込む（互換性維持）。
    """
    try:
        serialized: str = json.dumps(data, ensure_ascii=False)
        keyring.set_password(SERVICE_NAME, account_key, serialized)
        # 同時にファイルにも書く（Fallback + 手動編集用）
        path = _get_session_path(account_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[KEYRING] 保存失敗（ファイルフォールバック）: {e}", flush=True)
        return False


def load_session(account_key: str) -> dict[str, Any] | None:
    """
    Credential Manager からセッションデータを読み込む。
    失敗時は従来のJSONファイルからフォールバック。
    """
    try:
        stored: str | None = keyring.get_password(SERVICE_NAME, account_key)
        if stored:
            return json.loads(stored)  # type: ignore[no-any-return]
    except Exception:
        pass

    # ファイルフォールバック
    path = _get_session_path(account_key)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            pass
    return None


def delete_session(account_key: str) -> bool:
    """Credential Manager + ファイルから削除"""
    try:
        keyring.delete_password(SERVICE_NAME, account_key)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        pass
    path = _get_session_path(account_key)
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    return True


def migrate_file_to_keyring(account_key: str) -> bool:
    """既存のJSONファイルから Credential Manager に移行"""
    data = load_session(account_key)
    if data:
        return save_session(account_key, data)
    return False


def migrate_all() -> list[str]:
    """全アカウントをファイル→Credential Managerに移行"""
    results: list[str] = []
    for acct in ["atushi16", "kudou", "atushi1840", "zin20120731", "inobase1-4"]:
        if migrate_file_to_keyring(acct):
            results.append(f"✅ {acct}")
        else:
            results.append(f"❌ {acct}（ファイルなし or 移行失敗）")
    return results
