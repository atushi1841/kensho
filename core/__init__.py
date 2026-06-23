"""
Kensho Core — 共通モジュール
"""
from __future__ import annotations

from core.config import load as load_config
from core.encoding import guard_stdio, hide_console
from core.logger import LogWriter, make_path, write_daily_summary
from core.notifier import notify_error, notify_warning
from core.cleanup import kill_zombies, clean_old_logs
