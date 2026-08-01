"""
Kensho Notifier — Windows Toast / Discord Webhook / Linux Log 通知
v2.1: Linux対応（WSL2ではトースト非対応 → ファイルログ）
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import urllib.request
from typing import Any

from kensho.core.encoding import guard_stdio

guard_stdio()

_NOTIFIER_LOG_DIR: str = ""


def _set_notifier_log_dir(log_dir: str) -> None:
    """ログ出力先を設定"""
    global _NOTIFIER_LOG_DIR
    _NOTIFIER_LOG_DIR = log_dir


def _write_notifier_log(title: str, message: str) -> None:
    """Linux用: ファイルログに通知を書き込む"""
    if not _NOTIFIER_LOG_DIR:
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    today = time.strftime("%Y-%m-%d")
    logfile = os.path.join(_NOTIFIER_LOG_DIR, today, "notifier.log")
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{title}] {message}\n")
    except Exception:
        pass


def send_windows_toast(title: str, message: str) -> bool:
    """Windowsトースト通知を表示（Linuxではファイルログ）"""
    if platform.system() == "Linux":
        # WSL2 はデスクトップ通知不可 → ファイルログ
        _write_notifier_log("NOTIFY", f"{title}: {message}")
        return True

    safe_title = title.replace('"', '`"').replace("'", "`'")
    safe_msg = message.replace('"', '`"').replace("'", "`'")[:80]
    ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode("{safe_title}")) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode("{safe_msg}")) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Kensho").Show($toast)
'''
    try:
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def send_discord(message: str, webhook_url: str = "") -> bool:
    """
    Discord Webhook にメッセージを送信。
    webhook_url が空なら何もしない。
    """
    if not webhook_url:
        return False

    payload = {
        "content": message,
        "username": "Kensho",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status: int = resp.status
            return status == 204
    except Exception as e:
        print(f"[Notifier] Discord送信失敗: {e}", flush=True)
        return False


def notify_error(title: str, details: str, log_path: str = "", cfg: dict[str, Any] | None = None) -> bool:
    """
    エラー通知を送信（Windows Toast + Discord / Linux Log + Discord）。
    cfg が None なら何もしない。
    """
    toast = False
    discord = False

    if cfg:
        if cfg.get("notify", {}).get("windows_toast", False):
            toast = send_windows_toast("🚨 Kensho - " + title, details[:80])

        webhook = cfg.get("notify", {}).get("discord_webhook", "")
        if webhook:
            msg = f"🚨 **{title}**\\n```\\n{details[:1500]}```"
            if log_path:
                msg += f"\\n📄 ログ: `{log_path}`"
            discord = send_discord(msg, webhook)

    return toast or discord


def notify_warning(title: str, details: str, log_path: str = "", cfg: dict[str, Any] | None = None) -> bool:
    """警告通知（エラーより軽度）"""
    toast = False
    discord = False

    if cfg:
        if cfg.get("notify", {}).get("windows_toast", False):
            toast = send_windows_toast("⚠️ Kensho - " + title, details[:80])

        webhook = cfg.get("notify", {}).get("discord_webhook", "")
        if webhook:
            msg = f"[!] **{title}**\\n```\\n{details[:1500]}```"
            if log_path:
                msg += f"\\n📄 ログ: `{log_path}`"
            discord = send_discord(msg, webhook)

    return toast or discord
