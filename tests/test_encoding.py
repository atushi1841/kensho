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

    def test_emoji_codepoint_notation(self) -> None:
        """マップ外の絵文字は [U+XXXX] 表記になる"""
        assert cp932_safe("🎁") == "[U+1F381]"
        assert cp932_safe("👍") == "[U+1F44D]"
        assert cp932_safe("\U0001f4be") == "[U+1F4BE]"  # 💾

    def test_variation_selector(self) -> None:
        """異体字セレクタ（U+FE0F）は [U+FE0F] に置換される"""
        assert cp932_safe("\ufe0f") == "[U+FE0F]"

    def test_longest_match_priority(self) -> None:
        """⚠️（⚠+VS16）は変換マップ優先で [!] になる（単体の⚠は絵文字範囲外で除去）"""
        assert cp932_safe("⚠️") == "[!]"
        assert cp932_safe("⚠") == ""

    def test_unencodable_non_emoji_removed(self) -> None:
        """絵文字範囲外のcp932非対応文字（é, ½）は除去される"""
        assert cp932_safe("café") == "caf"
        assert cp932_safe("½") == ""

    def test_cp932_encodable_symbols_preserved(self) -> None:
        """cp932に含まれる記号（①, Ⅴ, Ж）はそのまま維持される"""
        for ch in ("①", "Ⅴ", "Ж"):
            assert cp932_safe(ch) == ch

    def test_mixed_text(self) -> None:
        """日本語文中の絵文字だけが置換される"""
        assert cp932_safe("在庫✅あり") == "在庫[OK]あり"

    def test_result_always_encodable(self) -> None:
        """混在テキストの変換結果も必ずcp932でエンコード可能"""
        mixed: str = "懸賞🎁当選❗café☕‼️"
        cp932_safe(mixed).encode("cp932")  # 例外を投げない
