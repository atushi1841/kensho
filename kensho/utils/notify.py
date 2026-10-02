"""
Kensho Notification — 通知送信モジュール
v1.0: Telegram / 標準出力 への通知送信に対応

使い方:
    send_notification("dm_win", "🎉 @atushi16 が当選！", account_key="atushi16")
"""

from __future__ import annotations

import os
import logging
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv

    # cron実行時はcwdが不定なので、プロジェクトルートの.envを明示的に読む
    _ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
    else:
        load_dotenv()
except Exception:
    pass

log = logging.getLogger(__name__)


def _resolve_env(val: str) -> str:
    """${VAR} や $VAR を環境変数で置換（未設定なら空文字）"""
    if not isinstance(val, str):
        return val
    import re
    def repl(m):
        var = m.group(1) or m.group(2)
        return os.environ.get(var, "")
    # ${VAR} と $VAR の両対応
    return re.sub(r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)', repl, val)


def _load_config() -> dict:
    """config.yaml の telegram セクションを読み込む（環境変数展開込み）"""
    cfg_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if not cfg_path.exists():
        return {"enabled": False}
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    tg = raw.get("telegram", {}) or {}
    # token / chat_id の環境変数展開
    if "token" in tg:
        tg["token"] = _resolve_env(tg["token"])
    if "chat_id" in tg:
        tg["chat_id"] = _resolve_env(tg["chat_id"])
    return tg


def send_telegram(message: str, token: str | None = None, chat_id: str | None = None) -> bool:
    """Telegram Bot API でメッセージを送信（依存ライブラリ不要）"""
    cfg = _load_config()
    token = token or cfg.get("token", "")
    chat_id = chat_id or cfg.get("chat_id", "")

    if not token or not chat_id:
        log.warning("[通知] Telegram token/chat_id 未設定。通知スキップ")
        return False

    text = urllib.parse.quote_plus(message[:4096])  # Telegram上限
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}&parse_mode=HTML"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        log.warning(f"[通知] Telegram送信失敗: {e}")
        return False


def send_notification(event: str, message: str, *, account_key: str | None = None) -> bool:
    """イベントに応じて通知を送信

    Args:
        event: 通知イベント種別 (dm_win, error, daily_report)
        message: 送信内容
        account_key: 関連アカウント

    Returns:
        送信成否
    """
    cfg = _load_config()
    if not cfg.get("enabled", False):
        return False

    notify_on = cfg.get("notify_on", ["dm_win"])
    if event not in notify_on:
        return False

    # アカウント情報をヘッダーに付加
    header = "🤖 Kensho 通知"
    if account_key:
        header += f" (@{account_key})"
    full_msg = f"<b>{header}</b>\n{message}"

    ok = send_telegram(full_msg)
    if ok:
        log.info(f"[通知] {event}: {message[:60]}... → Telegram送信OK")
    else:
        log.warning(f"[通知] {event}: {message[:60]}... → 送信失敗")

    # Telegram未設定時は常にstdoutに出力
    print(f"[通知/{event}] {message}")
    return ok


# ── DM当選通知のショートカット ──
def notify_dm_win(account_key: str, sender: str, text: str) -> bool:
    """DM当選検出時の通知"""
    msg = f"🎉 <b>DM当選検出</b>\nアカウント: @{account_key}\n送信者: {sender}\n内容: {text[:200]}"
    return send_notification("dm_win", msg, account_key=account_key)


def notify_running(account_key: str, item_count: int) -> bool:
    """応募実行通知"""
    msg = f"🔄 応募開始: @{account_key} ({item_count}件)"
    return send_notification("running", msg, account_key=account_key)


# CLIテスト用
if __name__ == "__main__":
    print("[通知] Telegram設定確認中...")
    cfg = _load_config()
    if cfg.get("enabled"):
        print(f"  Token: {cfg.get('token', '')[:8]}...")
        print(f"  ChatID: {cfg.get('chat_id', '')}")
        send_telegram("🤖 Kensho通知テスト")
    else:
        print("  Telegram未設定 (config.yaml > telegram.enabled = false)")
