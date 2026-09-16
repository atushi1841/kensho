"""kensho_winrate_analysis.py のフェイクDB/フェイクJSON突合テスト（t_8bf52d53）."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.kensho_winrate_analysis import (  # noqa: E402
    _time_window_pick,
    _within_h48,
    aggregate,
    apply_lag_bucket,
    default_week,
    extract_tweet_ids,
    iso_week_bounds,
    load_campaigns,
    load_wins,
    main,
    match_wins,
    parse_dt,
    tweet_id_to_time_ms,
)


def _campaign_item(tweet_id: str, handle: str, source: str, applied: dict) -> dict:
    return {
        "x_url": f"https://x.com/{handle}/status/{tweet_id}",
        "detail_url": "/detail/abc123.html",
        "source": source,
        "applied": applied,
        "prize_score": {"items": ["Amazonギフト券"]},
        "prize_rank": 2,
    }


def _win(sender: str, text: str, acct: str = "atushi16", t: str = "2026-09-14 10:00") -> dict:
    return {
        "sender": sender,
        "message_text": text,
        "message_time": t,
        "account_key": acct,
    }


def _write_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    collected = {
        "timestamp": "2026-09-16T00:00:00",
        "collected": [
            _campaign_item("2000000000000000001", "campA", "knshow", {"atushi16": "2026-09-01T08:00:00Z"}),
            _campaign_item(
                "2000000000000000002",
                "campB",
                "kenshouclub",
                {"atushi16": "2026-09-02T09:00:00Z", "kudou": "2026-09-02T10:00:00Z"},
            ),
            _campaign_item("2000000000000000003", "campC", "twscrape", {}),
        ],
    }
    wins = {
        "atushi16": [
            # tweet_id完全一致（本文引用）
            _win("@campA", "当選です https://x.com/campA/status/2000000000000000001?s=20"),
            # handle一致フォールバック（本文にステータスリンクなし）
            _win("@campB", "厳正な抽選の結果、当選されました。"),
            # 収集履歴外 = unmatched
            _win("@unknown acct", "当選おめでとうございます"),
        ],
        "kudou": [
            # handle+垢一致（appliedにkudouあり）
            _win("@campB", "当選通知です", acct="kudou"),
        ],
    }
    cp = tmp_path / "collected.json"
    wp = tmp_path / "dm_wins.json"
    cp.write_text(json.dumps(collected, ensure_ascii=False), encoding="utf-8")
    wp.write_text(json.dumps(wins, ensure_ascii=False), encoding="utf-8")
    return cp, wp


def test_tweet_id_and_handle_matching(tmp_path: Path) -> None:
    cp, wp = _write_fixtures(tmp_path)
    campaigns = load_campaigns([str(cp)])
    wins = load_wins(str(wp))
    matched, unmatched = match_wins(wins, campaigns)
    assert len(matched) == 4
    assert len(unmatched) == 0
    keys = {m["key"] for m in matched}
    assert keys == {"tweet_id", "handle"}
    # unmatched率の分母は全当選件数
    stats = aggregate(campaigns, matched, unmatched)
    assert stats["total_wins"] == 4
    assert stats["unmatched"] == 0


def test_source_aggregation_rates(tmp_path: Path) -> None:
    cp, wp = _write_fixtures(tmp_path)
    campaigns = load_campaigns([str(cp)])
    wins = load_wins(str(wp))
    matched, unmatched = match_wins(wins, campaigns)
    stats = aggregate(campaigns, matched, unmatched)
    # 応募数: campA(1)+campB(2)+campC(0) → source別
    assert stats["applies_by_source"]["knshow"] == 1
    assert stats["applies_by_source"]["kenshouclub"] == 2
    assert stats["wins_by_source"]["knshow"] == 1
    assert stats["wins_by_source"]["kenshouclub"] == 2
    # ケタ違いの当選率が算出可能（campA垢=1/1、campB垢別）
    assert stats["matched"] == 4


def test_handle_match_prefers_applied_account(tmp_path: Path) -> None:
    cp, wp = _write_fixtures(tmp_path)
    campaigns = load_campaigns([str(cp)])
    wins = load_wins(str(wp))
    matched, _ = match_wins(wins, campaigns)
    kudou = [m for m in matched if m["win"]["account_key"] == "kudou"]
    assert len(kudou) == 1
    assert kudou[0]["campaign"]["handle"] == "campb"
    assert "kudou" in kudou[0]["campaign"]["applied"]


def test_lag_bucket_instant_win() -> None:
    win = _win("@campA", "x", t="2026-09-14 10:00")
    tid = "2089544551199617296"  # 実dm_winsのID（2026-08-18頃）
    camp = {
        "tweet_id": tid,
        "applied": {"atushi16": "2026-08-18T11:00:00+09:00"},
        "source": "knshow",
    }
    ms = tweet_id_to_time_ms(tid)
    assert ms is not None
    # 実データで投稿→応募の遅延帯を分類できること
    assert apply_lag_bucket(win, camp) in {"<1h", "<24h", "<7d", ">=7d", "負値(要調査)", "不明"}


def test_parse_dt_naive_is_jst() -> None:
    dt = parse_dt("2026-09-14 10:00")
    assert dt is not None
    offset = dt.utcoffset()
    assert dt.hour == 10 and offset is not None
    assert offset.total_seconds() == 9 * 3600
    dt2 = parse_dt("2026-09-14T10:00:00Z")
    assert dt2 is not None and dt2.hour == 19  # UTC→JST


def test_week_bounds_and_default_week() -> None:
    b = iso_week_bounds("2026W38")
    assert b is not None
    assert b[0].isoweekday() == 1 and b[1] - b[0] == timedelta(days=7)
    assert iso_week_bounds("2026-38") is None
    assert default_week(date(2026, 9, 16)) == "2026W38"


def test_extract_tweet_ids() -> None:
    ids = extract_tweet_ids(
        "a https://x.com/foo/status/1234567890123456789?s=20 b twitter.com/bar/statuses/987654321098765432"
    )
    assert ids == {"1234567890123456789", "987654321098765432"}


def test_main_cli_end_to_end(tmp_path: Path) -> None:
    cp, wp = _write_fixtures(tmp_path)
    out = tmp_path / "winrate-2026W38.md"
    rc = main([
        "--week",
        "2026W38",
        "--project-dir",
        str(tmp_path),
        "--collected",
        str(cp),
        "--wins",
        str(wp),
        "--out",
        str(out),
    ])
    assert rc == 0
    md = out.read_text(encoding="utf-8")
    assert "# 当選率源別レポート 2026W38" in md
    assert "unmatched" in md
    assert "| knshow | 1 | 1 | 100.00% |" in md


def test_time_window_pick_prefers_nearby_campaign(tmp_path: Path) -> None:
    """同handle複数候補から、当該垢の応募時刻が win 通知時刻の±48h内にある案件を選ぶ（critic v167）。"""
    # win 通知 2026-09-10 12:00。campA は応募が同日（窓内）、campB は一週間前（窓外）。
    near = {"applied": {"atushi16": "2026-09-10T11:00:00Z"}, "tweet_id": "111"}
    far = {"applied": {"atushi16": "2026-09-03T12:00:00Z"}, "tweet_id": "222"}
    win_time = parse_dt("2026-09-10 12:00")
    assert win_time is not None
    picked = _time_window_pick([near, far], "atushi16", win_time)
    assert picked == near
    # 窓内候補が無ければ None → 呼び出し側フォールバックへ
    assert _time_window_pick([far], "atushi16", win_time) is None
    # 時刻不明 win は None
    assert _time_window_pick([near], "atushi16", None) is None


def test_within_h48() -> None:
    a = parse_dt("2026-09-10 12:00")
    b = parse_dt("2026-09-09 13:00")  # 23h差 → 窓内
    c = parse_dt("2026-09-08 12:00")  # 48h差ちょうど → 窓内
    d = parse_dt("2026-09-08 11:00")  # 49h差 → 窓外
    assert a is not None and b is not None and c is not None and d is not None
    assert _within_h48(a, b) is True
    assert _within_h48(a, c) is True
    assert _within_h48(a, d) is False


def test_load_campaigns_prefers_dedicated_tweet_id(tmp_path: Path) -> None:
    """collected アイテムが専用 tweet_id フィールドを持つ場合は x_url 抽出より優先（critic v167）。"""
    cp = tmp_path / "collected.json"
    cp.write_text(
        json.dumps({
            "collected": [
                {
                    "x_url": "https://x.com/h/status/999000111222333444",
                    "detail_url": "/detail/zzz.html",
                    "tweet_id": "999000111222333445",
                    "source": "knshow",
                    "applied": {"atushi16": "2026-09-01T08:00:00Z"},
                },
                # tweet_id 欠損 → x_url の status セグメントへフォールバック
                {
                    "x_url": "https://x.com/h2/status/123456789012345678",
                    "detail_url": "/detail/yyy.html",
                    "tweet_id": None,
                    "source": "twscrape",
                    "applied": {},
                },
            ]
        }),
        encoding="utf-8",
    )
    camps = load_campaigns([str(cp)])
    values = list(camps.values())
    by_x = {c["handle"]: c for c in values}
    assert by_x["h"]["tweet_id"] == "999000111222333445"  # 専用フィールド優先
    assert by_x["h2"]["tweet_id"] == "123456789012345678"  # フォールバック


def test_handle_match_uses_time_window_over_latest(tmp_path: Path) -> None:
    """win 通知時刻±48h内の応募を持つ案件を、同handle候補から選ぶ（最新応募でなく）。"""
    cp = tmp_path / "collected.json"
    # 同handle 'shopX' の2案件：candA は応募時刻が win と近い（窓内）、candB は遠い
    cp.write_text(
        json.dumps({
            "collected": [
                {
                    "x_url": "https://x.com/shopX/status/111111111111111111",
                    "detail_url": "/detail/a.html",
                    "tweet_id": "111111111111111111",
                    "source": "knshow",
                    "applied": {"atushi16": "2026-09-10T11:00:00Z"},
                },
                {
                    "x_url": "https://x.com/shopX/status/200000000000000000",
                    "detail_url": "/detail/b.html",
                    "tweet_id": "200000000000000000",
                    "source": "twscrape",
                    "applied": {"atushi16": "2026-08-01T12:00:00Z"},
                },
            ]
        }),
        encoding="utf-8",
    )
    wp = tmp_path / "dm_wins.json"
    wp.write_text(
        json.dumps({
            "atushi16": [_win("@shopX", "当選", t="2026-09-10 12:00")],
        }),
        encoding="utf-8",
    )
    matched, _ = match_wins(load_wins(str(wp)), load_campaigns([str(cp)]))
    assert len(matched) == 1
    # 時刻窓で candA (tweet_id=111111111111111111) が選ばれる
    assert matched[0]["campaign"]["tweet_id"] == "111111111111111111"
    assert matched[0]["key"] == "handle"  # handle 起点の照合のまま
