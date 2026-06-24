"""Kensho Encoding — cp932ガード共通ユーティリティ

WindowsのタスクスケジューラーやForceBindIP経由で
標準出力がcp932に化ける問題に対処する。

エクスポート:
  guard_stdio()      — stdout/stderr/コンソールCPをUTF-8に強制
  cp932_safe(msg)    — cp932端末で安全に印刷できる文字列に変換
  hide_console()     — コンソール窓を隠す（pythonw.exe代替）
"""
from __future__ import annotations

import sys, os, re as _re


def _set_console_utf8() -> None:
    """WindowsコンソールのコードページをUTF-8(65001)に設定。
    chcp 65001 相当をWin32 APIで実行。
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        # STD_OUTPUT_HANDLE = -11, STD_ERROR_HANDLE = -12
        kernel32 = ctypes.windll.kernel32
        # CP_UTF8 = 65001
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def guard_stdio() -> None:
    """
    標準出力・標準エラー出力を UTF-8 に固定。
    タスクスケジューラー・ForceBindIP経由で実行しても
    絵文字や日本語が正しく出力される。
    """
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    _set_console_utf8()

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


def cp932_safe(text: str) -> str:
    """cp932端末で安全に印刷できる文字列に変換。

    絵文字やcp932に無い記号をASCII記述に置き換える。
    日本語（ひらがな・カタカナ・漢字）はそのまま維持。
    """
    try:
        text.encode('cp932')
        return text  # 問題なし
    except UnicodeEncodeError:
        pass

    # 変換マップ（頻出絵文字 → ASCII代替） — 長いキー順（貪欲マッチ）
    _EMOJI_MAP: list[tuple[str, str]] = [
        ('\u26a0\ufe0f', '[!]'),     # ⚠️
        ('\u2139\ufe0f', '[i]'),     # ℹ️
        ('\u23f8\ufe0f', '[PAUSE]'), # ⏸️
        ('\u2705', '[OK]'),          # ✅
        ('\u274c', '[NG]'),          # ❌
        ('\u2757', '[!!]'),          # ❗
        ('\u2615', '[TEA]'),         # ☕
        ('\u2795', '[+]'),           # ➕
    ]

    result: list[str] = []
    i: int = 0
    while i < len(text):
        # 複数文字の変換マップを先にチェック
        matched: bool = False
        for raw, replacement in _EMOJI_MAP:
            if text[i:i + len(raw)] == raw:
                result.append(replacement)
                i += len(raw)
                matched = True
                break
        if matched:
            continue

        ch: str = text[i]
        cp: int = ord(ch)

        # cp932に含まれる文字はそのまま
        try:
            ch.encode('cp932')
            result.append(ch)
            i += 1
            continue
        except UnicodeEncodeError:
            pass

        # 絵文字範囲 → [U+XXXX]
        if (0x1F000 <= cp <= 0x1FFFF or       # 😀🎁💾
            0x2700 <= cp <= 0x27BF or          # Dingbats
            0xFE00 <= cp <= 0xFE0F or          # Variation selectors
            cp == 0x200D):                     # ZWJ
            result.append(f'[U+{cp:04X}]')
        else:
            # それ以外 → 除去
            result.append('')
        i += 1

    return ''.join(result)
