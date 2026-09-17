"""tests/test_apply_success_rate.py — 計測源一本化（auto log 完了行集計, t_9f37e5e3）."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import apply_success_rate as sr  # noqa: E402


def _write_auto_log(tmp_path: Path, name: str, lines: list[str]) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_aggregates_completion_lines(tmp_path: Path) -> None:
    _write_auto_log(
        tmp_path,
        "auto_20260915.log",
        [
            "[OK] 完了: 15成功 / 0エラー",
            "2026-09-15 09:00:00.000 | INFO | _   完了: 15成功/0エラー（1秒）",
            "[OK] 完了: 4成功 / 1エラー",
            "[OK] 完了: 0成功 / 2エラー",
            "2026-09-15 12:00:00.000 | INFO | _   完了: 0成功/0エラー（1秒）",
        ],
    )
    ok, err, lines = sr.summarize_date("2026-09-15", log_dir=str(tmp_path))
    assert (ok, err, lines) == (19, 3, 3)  # 15+4+0 / 0+1+2 / 完了行3


def test_empty_day_returns_zeros(tmp_path: Path) -> None:
    _write_auto_log(tmp_path, "auto_20260916.log", ["処理待ちのバッチなし"])
    ok, err, lines = sr.summarize_date("20260916", log_dir=str(tmp_path))
    assert (ok, err, lines) == (0, 0, 0)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sr.summarize_date("20260101", log_dir=str(tmp_path))


def test_format_rate() -> None:
    assert sr.format_rate(223, 3) == "成功 223 件 / エラー 3 件 / 成功率 98.7%"
    assert sr.format_rate(0, 0) == "成功 0 件 / エラー 0 件 / 成功率 0.0%"


def test_regex_matches_production_line(tmp_path: Path) -> None:
    _write_auto_log(
        tmp_path,
        "auto_20260915.log",
        ["[OK] 完了: 15成功 / 0エラー"],
    )
    ok, err, lines = sr.summarize_date("20260915", log_dir=str(tmp_path))
    assert (ok, err, lines) == (15, 0, 1)
