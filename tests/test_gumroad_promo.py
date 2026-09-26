"""Tests for scripts/gumroad_promo_weekly.py + scripts/gumroad_promo_kpi.py (t_3848cbde).

販促週次投稿の dedup/文言選択、views 前日比評価、売上API失敗時フォールバックを検証。
ネットワーク・X投稿は mock（実投稿はしない）。
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gumroad_promo_kpi as kpi
import gumroad_promo_weekly as promo

# ── 週次投稿: week_key / dedup ─────────────────────────────────────────────


def test_week_key_iso_format() -> None:
    assert promo.week_key(date(2026, 9, 28)) == "2026-W40"
    assert promo.week_key(date(2026, 9, 26)) == "2026-W39"


def test_pick_text_returns_rotation_within_limit() -> None:
    text, reason = promo.pick_text(date(2026, 9, 28), {})
    assert text is not None
    assert reason == ""
    assert len(text) <= 280
    assert promo.PAID_DATASET_URL in text or promo.FREE_SAMPLE_URL in text or promo.WEEKLY_REPORT_URL in text


def test_pick_text_slot_a_and_b_differ_in_same_week() -> None:
    """週2投稿（t_e6968f4f）: 同週の slot a/b は異なる文言（BOT検知回避）。"""
    ta, _ = promo.pick_text(date(2026, 9, 28), {}, slot="a")
    tb, _ = promo.pick_text(date(2026, 9, 28), {}, slot="b")
    assert ta is not None and tb is not None
    assert ta != tb


def test_pick_text_skips_when_week_slot_already_posted() -> None:
    state = {"posted_weeks": {"2026-W39": {"a": {"tweet_id": "123"}}}}
    text, reason = promo.pick_text(date(2026, 9, 26), state, slot="a")
    assert text is None
    assert "投稿済み" in reason
    assert "2026-W39" in reason


def test_pick_text_slot_b_allows_second_post_in_same_week() -> None:
    """slot a は投稿済みでも slot b は未投稿 → b は投稿可能（週2投稿の根拠）。"""
    state = {"posted_weeks": {"2026-W39": {"a": {"tweet_id": "123"}}}}
    text, reason = promo.pick_text(date(2026, 9, 26), state, slot="b")
    assert text is not None
    assert reason == ""


def test_pick_text_force_bypasses_slot_dedup() -> None:
    state = {"posted_weeks": {"2026-W39": {"a": {"tweet_id": "123"}}}}
    text, _ = promo.pick_text(date(2026, 9, 26), state, slot="a", force=True)
    assert text is not None


def test_pick_text_legacy_flat_state_is_slot_a_compatible() -> None:
    """旧 t_3848cbde 平構造（スロットなし）も slot=a として互換。"""
    state = {"posted_weeks": {"2026-W39": {"tweet_id": "123", "text": "x"}}}
    text, reason = promo.pick_text(date(2026, 9, 26), state, slot="a")
    assert text is None
    assert "投稿済み" in reason


def test_weekly_tweets_rotation_covers_all_entries() -> None:
    # 全文言が 280 字以内・商品リンクのプレースホルダーを含む（X の文字数制限・販促リンク必須）
    # utm 付与後の展開は pick_text で行われる
    for t in promo.WEEKLY_TWEETS:
        assert len(t) <= 280
        assert "{free}" in t or "{paid}" in t or "{report}" in t


def test_weekly_tweets_count_doubled() -> None:
    """週1→週2拡大（t_e6968f4f）: 16種 = 旧8種 + 新增8種。"""
    assert len(promo.WEEKLY_TWEETS) == 16
    assert len(promo.SLOTS) == 2
    assert set(promo.SLOTS) == {"a", "b"}


def test_slot_index_is_deterministic_and_distinct() -> None:
    """週×スロットで独立文言。同一週の a/b は異なる idx。"""
    ia = promo._slot_index(40, "a")
    ib = promo._slot_index(40, "b")
    assert ia != ib
    assert 0 <= ia < len(promo.WEEKLY_TWEETS)
    assert 0 <= ib < len(promo.WEEKLY_TWEETS)
    # 同スロットは決定論的
    assert promo._slot_index(40, "a") == ia


def test_record_xpost_state_appends_without_clobber(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xstate = tmp_path / "gumroad_x_post_state.json"
    xstate.write_text(json.dumps({"posted": {"2026-09-11": {"tweet_id": "old"}}}), encoding="utf-8")
    monkeypatch.setattr(promo, "XPOST_STATE_FILE", xstate)

    promo.record_xpost_state(date(2026, 9, 26), "new123", "hello", slot="b")

    data = json.loads(xstate.read_text(encoding="utf-8"))
    assert "2026-09-11" in data["posted"], "既存投稿記録は保持される"
    assert data["posted"]["2026-09-26"]["tweet_id"] == "new123"
    assert data["posted"]["2026-09-26"]["source"] == "gumroad_promo_weekly"
    assert data["posted"]["2026-09-26"]["slot"] == "b"


# ── KPI: views 前日比 ───────────────────────────────────────────────────────


def test_views_dod_growth_meets_target() -> None:
    hist = {"2026-09-26": {"views": 12}, "2026-09-25": {"views": 10}}
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["pct"] == 20.0
    assert out["meets_target"] is True


def test_views_dod_decline_fails_target() -> None:
    hist = {"2026-09-26": {"views": 5}, "2026-09-25": {"views": 10}}
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["pct"] == -50.0
    assert out["meets_target"] is False


def test_views_dod_zero_to_zero_is_flat() -> None:
    hist = {"2026-09-26": {"views": 0}, "2026-09-25": {"views": 0}}
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["pct"] is None
    assert out["meets_target"] is False


def test_views_dod_zero_to_positive_is_met() -> None:
    hist = {"2026-09-26": {"views": 1}, "2026-09-25": {"views": 0}}
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["meets_target"] is True


def test_views_dod_missing_prev_is_unknown() -> None:
    out = kpi.views_dod({"2026-09-26": {"views": 3}}, date(2026, 9, 26))
    assert out["pct"] is None
    assert out["meets_target"] is None


def test_views_dod_reads_twitter_referrer() -> None:
    hist = {
        "2026-09-26": {"views": 5, "referrers": {"Twitter": 3}},
        "2026-09-25": {"views": 4},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 3


def test_views_dod_fuzzy_twitter_referrer_t_co() -> None:
    # t.co キーでも検出（t_b8ec048a: 柔軟マッチ）
    hist = {
        "2026-09-26": {"views": 5, "referrers": {"https://t.co/abc123": 2}},
        "2026-09-25": {"views": 4},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 2
    assert "https://t.co/abc123" in out["twitter_referrers"]


def test_views_dod_fuzzy_twitter_referrer_twitter_com() -> None:
    # twitter.com キーでも検出
    hist = {
        "2026-09-26": {"views": 5, "referrers": {"twitter.com": 2}},
        "2026-09-25": {"views": 4},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 2


def test_views_dod_utm_source_twitter() -> None:
    # utm_source=twitter を含むキーでも検出（utm 計測経路で独立判定）
    hist = {
        "2026-09-26": {"views": 5, "referrers": {"https://t.co/xyz?utm_source=twitter": 3}},
        "2026-09-25": {"views": 4},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 3


def test_views_dod_missing_twitter_referrer_returns_zero() -> None:
    # Twitter キーが存在しない（例: Direct, email, IM のみ）場合は 0 を返す（t_b8ec048a）
    # None ではなく 0 ＝「X 販促経由流入=0」の明示的記録
    hist = {
        "2026-09-26": {"views": 1, "referrers": {"Direct, email, IM": 1}},
        "2026-09-25": {"views": 1},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 0
    assert out["twitter_referrers"] == []


def test_views_dod_xcom_referrer() -> None:
    # x.com キーでも検出
    hist = {
        "2026-09-26": {"views": 5, "referrers": {"x.com": 2}},
        "2026-09-25": {"views": 4},
    }
    out = kpi.views_dod(hist, date(2026, 9, 26))
    assert out["twitter_views"] == 2


# ── KPI: 売上判定 / フォールバック ─────────────────────────────────────────


def test_evaluate_sales_target_met() -> None:
    ev = kpi.evaluate({"ok": True, "week": 1}, {"meets_target": True})
    assert ev["sales_meets_target"] is True
    assert ev["views_meets_target"] is True


def test_evaluate_sales_target_not_met_when_zero() -> None:
    ev = kpi.evaluate({"ok": True, "week": 0}, {"meets_target": None})
    assert ev["sales_meets_target"] is False
    assert ev["views_meets_target"] is None


def test_evaluate_sales_unknown_when_api_failed() -> None:
    ev = kpi.evaluate({"ok": False, "error": "timeout"}, {"meets_target": False})
    assert ev["sales_meets_target"] is None
    assert ev["sales_week_count"] is None


def test_api_sales_count_empty_token_fails_cleanly() -> None:
    out = kpi.api_sales_count("")
    assert out["ok"] is False
    assert "TOKEN" in out["error"]


def test_dashboard_fallback_reads_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "gumroad_state.json"
    state.write_text(
        json.dumps({"total_sales": 0, "login_ok": True, "last_success_at": "2026-09-25T13:19:41"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(kpi, "DASHBOARD_STATE", state)
    out = kpi.dashboard_sales_fallback()
    assert out["ok"] is True
    assert out["login_ok"] is True
    assert out["total_sales"] == 0


def test_dashboard_fallback_missing_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kpi, "DASHBOARD_STATE", tmp_path / "missing.json")
    out = kpi.dashboard_sales_fallback()
    assert out["ok"] is False


def test_load_env_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUMROAD_TOKEN", "tok_env")
    assert kpi.load_env_token() == "tok_env"
