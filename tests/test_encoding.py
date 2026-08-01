"""
Tests for core/encoding.py — cp932ガード共通ユーティリティ
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.core.encoding import cp932_safe, guard_stdio


class TestGuardStdio:
    """guard_stdio: UTF-8強制"""

    def test_sets_env_var(self) -> None:
        """PYTHONIOENCODING が設定される"""
        guard_stdio()
        assert "utf-8" in __import__("os").environ.get("PYTHONIOENCODING", "")

    def test_is_callable(self) -> None:
        """例外を投げずに実行できる"""
        guard_stdio()  # 2回目もOK


class TestCp932Safe:
    """cp932_safe: 絵文字除去・日本語維持"""

    def test_plain_japanese(self) -> None:
        """日本語テキストはそのまま"""
        text: str = "文字化けが直ってないので直して欲しい"
        result: str = cp932_safe(text)
        assert result == text
        result.encode("cp932")  # cp932でエンコード可能

    def test_emoji_replaced(self) -> None:
        """絵文字が安全なASCIIに置き換わる"""
        result: str = cp932_safe("✅ 完了")
        assert "[OK]" in result
        result.encode("cp932")

    def test_all_cp932_safe(self) -> None:
        """変換結果が常にcp932でエンコード可能"""
        cases: list[str] = [
            "✅ 🔄 💾 ☕ ⚠️ ❗ ℹ️ ⏸️ ➕ ➖",
            "文字化けテスト 💯",
            "普通のテキストのみ",
            "",
            "半角英数123abc!@#",
        ]
        for c in cases:
            safe: str = cp932_safe(c)
            safe.encode("cp932")  # 例外を投げない
