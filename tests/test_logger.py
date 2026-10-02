"""
Tests for core/logger.py — ログ出力・日次サマリー生成
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from kensho.core.logger import LogWriter, ensure_dirs, make_path, write_daily_summary


def _patch_log_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """LOGS_DIR / SUMMARY_DIR をtmp_path配下に差し替え（実logs/ディレクトリを触らない）"""
    logs_dir = tmp_path / "logs"
    summary_dir = logs_dir / "summary"
    monkeypatch.setattr("kensho.core.logger.LOGS_DIR", logs_dir)
    monkeypatch.setattr("kensho.core.logger.SUMMARY_DIR", summary_dir)
    return logs_dir, summary_dir


class TestEnsureDirs:
    """ensure_dirs: 日付フォルダ作成"""

    def test_creates_today_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """今日の日付ディレクトリとsummaryディレクトリを作成する"""
        logs_dir, summary_dir = _patch_log_dirs(monkeypatch, tmp_path)
        day_dir: Path = ensure_dirs()
        assert day_dir == logs_dir / datetime.now().strftime("%Y-%m-%d")
        assert day_dir.exists()
        assert summary_dir.exists()

    def test_idempotent(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """2回呼んでも同じパスを返し、エラーにならない"""
        _patch_log_dirs(monkeypatch, tmp_path)
        first: Path = ensure_dirs()
        second: Path = ensure_dirs()
        assert first == second


class TestMakePath:
    """make_path: ログファイルパス生成（例: logs/2026-06-18/apply_kudou_153000.log）"""

    def test_default_suffix_log(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """デフォルト拡張子は.logで、<prefix>_<HHMMSS>.log形式"""
        logs_dir, _ = _patch_log_dirs(monkeypatch, tmp_path)
        p: Path = make_path("apply_kudou")
        assert p.parent == logs_dir / datetime.now().strftime("%Y-%m-%d")
        assert re.fullmatch(r"apply_kudou_\d{6}\.log", p.name)

    def test_custom_suffix(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """suffix指定で拡張子が変わる"""
        _patch_log_dirs(monkeypatch, tmp_path)
        p: Path = make_path("collect", suffix="json")
        assert re.fullmatch(r"collect_\d{6}\.json", p.name)


class TestLogWriter:
    """LogWriter: ファイル＋出力への同時書き込み"""

    def test_write_creates_log_file(self, tmp_path: Path) -> None:
        """write()でファイルが作られ、[HH:MM:SS]メッセージ形式で書き込まれる"""
        log_path = tmp_path / "writer_test.log"
        writer = LogWriter(log_path, echo=False)
        try:
            writer.write("書き込みテストメッセージ")
        finally:
            writer.close()
        content = log_path.read_text(encoding="utf-8")
        assert "書き込みテストメッセージ" in content
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", content)

    def test_context_manager_closes(self, tmp_path: Path) -> None:
        """withブロックを抜けるとsinkが解放され、メッセージがファイルに残る"""
        log_path = tmp_path / "context_test.log"
        with LogWriter(log_path, echo=False) as writer:
            writer.write("コンテキストマネージャ経由のメッセージ")
        assert "コンテキストマネージャ経由のメッセージ" in log_path.read_text(encoding="utf-8")


class TestWriteDailySummary:
    """write_daily_summary: 日次サマリーMarkdown生成"""

    def test_returns_none_when_no_day_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """当日のログディレクトリが存在しない場合はNoneを返す"""
        _patch_log_dirs(monkeypatch, tmp_path)
        assert write_daily_summary() is None

    def test_generates_markdown_summary(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """ログファイル一覧がMarkdownテーブルでサマリーに出力される"""
        logs_dir, summary_dir = _patch_log_dirs(monkeypatch, tmp_path)
        day_dir: Path = ensure_dirs()
        (day_dir / "collect_090000.log").write_text("dummy", encoding="utf-8")
        (day_dir / "apply_153000.log").write_text("dummy", encoding="utf-8")

        out: Path | None = write_daily_summary()
        assert out is not None
        assert out == summary_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"

        text = out.read_text(encoding="utf-8")
        assert f"# 📊 Kensho 日次サマリー {day_dir.name}" in text
        assert "| 09:00:00 | collect | `collect_090000.log` |" in text
        assert "| 15:30:00 | apply | `apply_153000.log` |" in text

    def test_rows_sorted_by_filename(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """ログ行はファイル名順（=時刻順）に並ぶ"""
        _patch_log_dirs(monkeypatch, tmp_path)
        day_dir: Path = ensure_dirs()
        (day_dir / "apply_100000.log").write_text("b", encoding="utf-8")
        (day_dir / "apply_090000.log").write_text("a", encoding="utf-8")

        out = write_daily_summary()
        assert out is not None
        text = out.read_text(encoding="utf-8")
        assert text.index("apply_090000.log") < text.index("apply_100000.log")

    def test_multi_underscore_name_parsed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """prefixに_を含むファイル（apply_kudou_153000）も種別・時刻が正しく分解される"""
        _patch_log_dirs(monkeypatch, tmp_path)
        day_dir: Path = ensure_dirs()
        (day_dir / "apply_kudou_153000.log").write_text("x", encoding="utf-8")

        out = write_daily_summary()
        assert out is not None
        assert "| 15:30:00 | apply | `apply_kudou_153000.log` |" in out.read_text(encoding="utf-8")

    def test_ignores_non_log_files(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """.log以外のファイルはサマリー対象外"""
        _patch_log_dirs(monkeypatch, tmp_path)
        day_dir: Path = ensure_dirs()
        (day_dir / "note.txt").write_text("not a log", encoding="utf-8")
        (day_dir / "apply_120000.log").write_text("log", encoding="utf-8")

        out = write_daily_summary()
        assert out is not None
        text = out.read_text(encoding="utf-8")
        assert "note.txt" not in text
        assert "| 12:00:00 | apply | `apply_120000.log` |" in text
