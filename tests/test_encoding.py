"""
Tests for core/encoding.py — cp932ガード共通ユーティリティ
"""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.encoding import guard_stdio, hide_console


class TestGuardStdio:
    """guard_stdio: UTF-8強制"""

    def test_sets_env_var(self) -> None:
        """PYTHONIOENCODING が設定される"""
        guard_stdio()
        assert 'utf-8' in __import__('os').environ.get('PYTHONIOENCODING', '')

    def test_is_callable(self) -> None:
        """例外を投げずに実行できる"""
        guard_stdio()  # 2回目もOK


class TestHideConsole:
    """hide_console: 例外を投げない"""

    def test_does_not_crash(self) -> None:
        """常に例外なく実行できる"""
        hide_console()
