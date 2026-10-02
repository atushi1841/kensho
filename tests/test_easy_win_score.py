"""Tests for 当選易度スコア easy_win_score（t_c1889d30）.

winner_count（口数）と prize_score.priority（賞品優先度）を各々 [0,1] に正規化して
等重合成した 0-100 の当選易度スコアを、data/collected_today.json の全件付与と
デイリーレポートの TOP50 表示に使う。

安全側の保証:
  - 計算不能（winner_count 欠落・0・不正）は score=0.0 を付与し、TOP50 からは分離
  - スコアは表示・可視化のみ。応募バッチ配分・応募ロジック（applier）には未反映
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from kensho.scraping.pathway_classifier import (
    PATHWAY_KEY,
    build_non_x_report_md,
    easy_win_ranking,
    easy_win_top_md,
    label_counts,
)
from kensho.scraping.scorer import (
    EASY_WIN_SCORE_KEY,
    attach_easy_win_scores,
    compute_easy_win_score,
    normalize_prize_score,
    normalize_winner_count,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKFILL_SCRIPT = PROJECT_DIR / "scripts" / "backfill_easy_win_score.py"
COLLECTED_TODAY = PROJECT_DIR / "data" / "collected_today.json"


def _item(winner_count: object, priority: object = 2.0, **extra: object) -> dict[str, Any]:
    """winner_count / prize_score.priority を持つテスト用アイテム。"""
    item: dict[str, Any] = {
        "x_url": str(extra.pop("x_url", "https://x.com/i/web/status/1")),
        PATHWAY_KEY: "X",
    }
    item.update(extra)
    if winner_count is not ...:
        item["winner_count"] = winner_count
    if priority is not ...:
        item["prize_score"] = {"priority": priority, "prize_type": "物"}
    return item


# ── normalize_winner_count ──────────────────────────────────────────


def test_normalize_winner_count_log_scale() -> None:
    """log1p スケール + 上限1000クリップ。欠落・0・不正は 0.0（計算不能）。"""
    assert normalize_winner_count(1000) == 1.0
    assert normalize_winner_count(9999) == 1.0
    assert normalize_winner_count(0) == 0.0
    assert normalize_winner_count(None) == 0.0
    assert normalize_winner_count(-3) == 0.0
    assert normalize_winner_count("abc") == 0.0
    assert normalize_winner_count(float("nan")) == 0.0
    assert normalize_winner_count(float("inf")) == 0.0
    # 数値文字列は受理（収集側が文字列で返す場合あり）
    assert normalize_winner_count("3") == pytest.approx(math.log1p(3) / math.log1p(1000))
    # 単調増加（多いほど当選しやすい）
    assert normalize_winner_count(1) < normalize_winner_count(10) < normalize_winner_count(100)


def test_normalize_prize_score_bounds() -> None:
    """priority 1.0=通常→0.0 / 3.0=満点→1.0、範囲外はクリップ。"""
    assert normalize_prize_score({"priority": 1.0}) == 0.0
    assert normalize_prize_score({"priority": 3.0}) == 1.0
    assert normalize_prize_score({"priority": 2.5}) == 0.75
    assert normalize_prize_score({"priority": 4.0}) == 1.0
    assert normalize_prize_score({"priority": 0.5}) == 0.0
    # 欠落・非dict・不正は「評価なし=通常扱い」でボーナス0
    assert normalize_prize_score(None) == 0.0
    assert normalize_prize_score({}) == 0.0
    assert normalize_prize_score({"priority": "x"}) == 0.0


# ── compute_easy_win_score ──────────────────────────────────────────


def test_compute_easy_win_score_known_value() -> None:
    """wc=3 / priority=2.5 → 100*(0.5*log1p正規化 + 0.5*0.75) = 47.5。"""
    got = compute_easy_win_score(_item(3, 2.5))
    assert got == pytest.approx(47.5, abs=0.05)
    assert got == round(got, 1)


@pytest.mark.parametrize(
    "item",
    [
        _item(None),
        _item(0),
        _item(None, priority=...),
        {"winner_count": "abc"},
        {"winner_count": -1},
        {"winner_count": float("nan")},
    ],
    ids=["missing-wc", "wc-zero", "no-prize-key", "wc-string", "wc-negative", "wc-nan"],
)
def test_compute_easy_win_score_uncomputable_is_zero(item: dict[str, Any]) -> None:
    """winner_count 欠落・0・不正 = 計算不能 → 0.0 を返す（TOP50 から分離される）。"""
    assert compute_easy_win_score(item) == 0.0


def test_compute_easy_win_score_monotonic_and_in_range() -> None:
    """同一賞品なら口数が多いほど高く、同一口数なら優先度が高いほど高い。0-100 に収まる。"""
    samples = [
        _item(wc, pr)
        for wc in (1, 2, 3, 5, 10, 30, 100, 300, 1000)
        for pr in (1.0, 2.0, 2.5, 3.0)
    ]
    scores = [compute_easy_win_score(it) for it in samples]
    assert all(0.0 <= s <= 100.0 for s in scores)
    # 口数の単調性（優先度を固定）
    by_wc = [compute_easy_win_score(_item(wc, 3.0)) for wc in (1, 10, 100, 1000)]
    assert by_wc == sorted(by_wc) and len(set(by_wc)) == 4
    # 優先度の単調性（口数を固定）
    by_pr = [compute_easy_win_score(_item(10, pr)) for pr in (1.0, 2.0, 3.0)]
    assert by_pr == sorted(by_pr) and len(set(by_pr)) == 3


# ── ranking / レポート表示 ──────────────────────────────────────────


def test_easy_win_ranking_sorts_desc_and_separates_uncomputable() -> None:
    """計算可能な案件のみをスコア降順 TOP n にし、計算不能は別リストで返す。"""
    items = [
        _item(10, 3.0, x_url="https://x.com/i/web/status/hi"),
        _item(2, 1.5, x_url="https://x.com/i/web/status/lo"),
        _item(0, 3.0, x_url="https://x.com/i/web/status/zero"),  # 計算不能
        {EASY_WIN_SCORE_KEY: 0.0, "x_url": "https://x.com/i/web/status/noscore"},  # 未付与扱い
    ]
    for it in items:
        it.setdefault(EASY_WIN_SCORE_KEY, compute_easy_win_score(it))
    top, bad = easy_win_ranking(items, n=50)
    assert [it["x_url"] for it in top] == [
        "https://x.com/i/web/status/hi",
        "https://x.com/i/web/status/lo",
    ]
    assert {it["x_url"] for it in bad} == {
        "https://x.com/i/web/status/zero",
        "https://x.com/i/web/status/noscore",
    }
    # n での切り詰め
    top1, _bad1 = easy_win_ranking(items, n=1)
    assert len(top1) == 1
    assert top1[0]["x_url"] == "https://x.com/i/web/status/hi"


def test_easy_win_top_md_shows_top50_and_uncomputable_section() -> None:
    """TOP50 表に計算可能な案件だけを出し、計算不能は件数のみで分離する。"""
    items = [
        _item(50, 3.0, x_url="https://x.com/i/web/status/a", deadline="2026-10-01 12:00"),
        _item(5, 2.0, x_url="https://x.com/i/web/status/b"),
        _item(0, 3.0, x_url="https://x.com/i/web/status/c"),  # 計算不能
    ]
    for it in items:
        it[EASY_WIN_SCORE_KEY] = compute_easy_win_score(it)
    md = easy_win_top_md(items)
    assert "当選易度 TOP50（easy_win_score 高得点順）" in md
    assert "| 1 | " in md and "| 2 | " in md
    assert "https://x.com/i/web/status/a" in md
    assert "計算不能（winner_count 欠落・0）: 1件" in md
    # 計算不能は TOP50 表に出さない（分離）
    assert "https://x.com/i/web/status/c" not in md
    # 表示のみである明示
    assert "応募ロジックには未反映" in md


def test_easy_win_top_md_rows_are_descending() -> None:
    """TOP 表は easy_win_score の降順に並ぶ。"""
    items = [_item(wc, 2.0, x_url=f"https://x.com/i/web/status/{wc}") for wc in (1, 100, 10, 300, 3)]
    for it in items:
        it[EASY_WIN_SCORE_KEY] = compute_easy_win_score(it)
    md = easy_win_top_md(items)
    rows = [ln for ln in md.splitlines() if ln.startswith("| ") and ln.split("|")[1].strip().isdigit()]
    assert len(rows) == 5
    values = [float(r.split("|")[2].strip()) for r in rows]
    assert values == sorted(values, reverse=True)


def test_build_non_x_report_md_contains_top50_section() -> None:
    """デイリーレポート本体に当選易度 TOP50 セクションが入る（既存セクションも維持）。"""
    items = [
        _item(20, 3.0, x_url="https://x.com/i/web/status/x"),
        {"導線": "Web応募", "x_url": "https://example.com/n", PATHWAY_KEY: "Web応募"},
    ]
    for it in items:
        it[EASY_WIN_SCORE_KEY] = compute_easy_win_score(it)
    md = build_non_x_report_md(items, label_counts(items), "20260930")
    assert "## 当選易度 TOP50（easy_win_score 高得点順）" in md
    assert "## 導入ラベル別件数" in md
    assert "## 手動・要確認リスト（自動応募対象外）" in md


def test_attach_easy_win_scores_inplace_and_idempotent() -> None:
    """collector / backfill 共通の付与ヘルパー: 全件インプレース付与・件数返却・冪等。"""
    items = [
        _item(10, 2.0, x_url="https://x.com/i/web/status/1"),
        _item(0, 3.0, x_url="https://x.com/i/web/status/2"),
        _item(None, priority=..., x_url="https://x.com/i/web/status/3"),
    ]
    order_before = [it["x_url"] for it in items]

    counts = attach_easy_win_scores(items)
    assert counts == (1, 2)  # (計算可能, 計算不能)
    assert all(EASY_WIN_SCORE_KEY in it for it in items)  # 全件に付与
    assert [it["x_url"] for it in items] == order_before  # 並べ替えない
    first_scores = [it[EASY_WIN_SCORE_KEY] for it in items]

    assert attach_easy_win_scores(items) == counts  # 冪等
    assert [it[EASY_WIN_SCORE_KEY] for it in items] == first_scores


# ── 収集データへの付与（受け入れ条件 (a)(b)）────────────────────────


def test_collected_today_has_easy_win_score() -> None:
    """data/collected_today.json の各エントリに easy_win_score が付与済み（0-100）。"""
    if not COLLECTED_TODAY.exists():
        pytest.skip("data/collected_today.json が存在しない")
    data = json.loads(COLLECTED_TODAY.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        pytest.skip("data/collected_today.json が空")
    with_key = [it for it in data if EASY_WIN_SCORE_KEY in it]
    assert with_key, f"easy_win_score 付きエントリが 0 件（全{len(data)}件）"
    assert len(with_key) > 0
    for it in with_key:
        s = it[EASY_WIN_SCORE_KEY]
        assert isinstance(s, (int, float)) and 0.0 <= float(s) <= 100.0
    # 計算不能（0点）と計算可能な件数が一致し合う（TOP50 に切り詰めない全件ランクで突合）
    bad = [it for it in data if float(it.get(EASY_WIN_SCORE_KEY, -1)) <= 0.0]
    top, uncomputable = easy_win_ranking(data, n=len(data))
    assert len(top) + len(uncomputable) == len(data)
    assert len(uncomputable) == len(bad)
    assert top, "計算可能な案件が0件"


def test_backfill_script_dry_run() -> None:
    """backfill スクリプトは --dry-run で書き込まずに検算のみ終了する（exit 0）。"""
    if not COLLECTED_TODAY.exists() or not BACKFILL_SCRIPT.exists():
        pytest.skip("data/collected_today.json または backfill スクリプトが存在しない")
    before = COLLECTED_TODAY.stat().st_mtime_ns
    proc = subprocess.run(
        [sys.executable, str(BACKFILL_SCRIPT), "--dry-run"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout[-2000:]} stderr={proc.stderr[-2000:]}"
    assert "TOP5" in proc.stdout
    assert COLLECTED_TODAY.stat().st_mtime_ns == before, "dry-run なのにファイルが書き換わった"
