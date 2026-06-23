"""
Kensho Encoding — cp932ガード共通ユーティリティ
WindowsのタスクスケジューラーやForceBindIP経由で
標準出力がcp932に化ける問題に対処する。
"""
from __future__ import annotations

import sys, os


def guard_stdio() -> None:
    """
    標準出力・標準エラー出力を UTF-8 に固定。
    タスクスケジューラー・ForceBindIP経由で実行しても
    絵文字や日本語が正しく出力される。
    """
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
            sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)  # type: ignore[union-attr]
        except Exception:
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except Exception:
                pass


def hide_console() -> None:
    """Windowsコンソール窓を隠す（pythonw.exeが無い場合の保険）"""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass
