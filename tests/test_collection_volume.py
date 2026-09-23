"""tests/test_collection_volume.py — 収集ボリューム指標の単体テスト。

対象: kensho/core/collection_volume.py（2026-09-23 追加）
「本日収集実績」の手書き値問題（ダッシュボード再生成で消える／222固定化）の
恒久対策として、集計の正しさをここで固定する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kensho.core import collection_volume


def _make_project(tmp_path: Path, logs: dict[str, str], collected: Any = None) -> Path:
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    for name, body in logs.items():
        (tmp_path / "logs" / name).write_text(body, encoding="utf-8")
    (tmp_path / "data").mkdir(exist_ok=True)
    if collected is not None:
        (tmp_path / "data" / "collected.json").write_text(
            json.dumps(collected, ensure_ascii=False), encoding="utf-8"
        )
    return tmp_path


def test_today_counts_unique_x_urls_across_runs(tmp_path: Path) -> None:
    """複数runの重複URLは1件に丸め、当日ユニーク数を返す。"""
    project = _make_project(
        tmp_path,
        {
            "collect_20260923_090001.log": (
                "    ✅ https://x.com/aaa/status/111...\n"
                "    ✅ https://x.com/bbb/status/222...\n"
            ),
            "collect_20260923_130001.log": (
                "    ✅ https://x.com/aaa/status/111...\n"
                "    ✅ https://x.com/ccc/status/333...\n"
            ),
        },
    )
    assert collection_volume.count_today_collected(project, day="2026-09-23") == 3


def test_other_days_and_non_status_urls_are_ignored(tmp_path: Path) -> None:
    """別日のログ・プロフィールURL・走査ログ行は計上しない。"""
    project = _make_project(
        tmp_path,
        {
            "collect_20260922_090001.log": "    ✅ https://x.com/old/status/999...\n",
            "collect_20260923_090001.log": (
                "  [KCLUB] ページ6: 記事走査26件（収集件数ではない）\n"
                "    ✅ https://x.com/ddd\n"
                "    ✅ https://example.com/status/123456\n"
                "    ✅ https://x.com/eee/status/444...\n"
            ),
        },
    )
    assert collection_volume.count_today_collected(project, day="2026-09-23") == 1


def test_twitter_com_urls_counted_and_empty_run_is_zero(tmp_path: Path) -> None:
    """twitter.com表記も同一視し、収集0件run（URL行なし）は加算されない。"""
    project = _make_project(
        tmp_path,
        {
            "collect_20260923_100001.log": "  [収集] TypeError: 収集停止\n",
            "collect_20260923_120001.log": "    ✅ https://twitter.com/fff/status/555...\n",
        },
    )
    assert collection_volume.count_today_collected(project, day="2026-09-23") == 1
    assert collection_volume.count_today_runs(project, day="2026-09-23") == 2


def test_total_from_collected_json_variants(tmp_path: Path) -> None:
    """dict(collected)形式・list形式・欠落のすべてで破綻しない。"""
    project = _make_project(tmp_path, {}, collected={"collected": [{"x_url": "a"}, {"x_url": "b"}]})
    assert collection_volume.count_total_collected(project) == 2

    project2 = _make_project(tmp_path / "p2", {}, collected=[{"x_url": "a"}])
    assert collection_volume.count_total_collected(project2) == 1

    project3 = _make_project(tmp_path / "p3", {})
    assert collection_volume.count_total_collected(project3) == 0


def test_volume_stats_keys_and_source(tmp_path: Path) -> None:
    """統計dictの必須キーと出典表記を固定する。"""
    project = _make_project(
        tmp_path,
        {"collect_20260923_210002.log": "    ✅ https://x.com/ggg/status/666...\n"},
        collected={"collected": [{"x_url": "a"}, {"x_url": "b"}, {"x_url": "c"}]},
    )
    stats = collection_volume.volume_stats(project, day="2026-09-23")
    assert stats["collected_today"] == 1
    assert stats["collected_total"] == 3
    assert stats["collected_today_date"] == "2026-09-23"
    assert stats["collected_today_runs"] == 1
    assert stats["collected_today_source"] == "logs/collect_20260923_*.log"


def test_missing_project_dir_returns_zero(tmp_path: Path) -> None:
    """ログ/データが存在しないディレクトリでも例外を出さず0を返す。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    stats = collection_volume.volume_stats(empty, day="2026-09-23")
    assert stats["collected_today"] == 0
    assert stats["collected_total"] == 0
