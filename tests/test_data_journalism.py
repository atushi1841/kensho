"""kensho_data_journalism.py の傾向抽出テスト（t_0b949bda）.

実データには依存せず、フェイクの collected / dm_wins から
「抽出→集計→テンプレート描画→出力」の全経路を検証する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.kensho_data_journalism import (  # noqa: E402
    _PLACEHOLDER_RE,
    Campaign,
    analyze,
    band_of,
    build_blog_sections,
    build_sections,
    classify_category,
    discover_snapshot_files,
    extract_keywords,
    extract_value_from_text,
    iso_week_label,
    keyword_stats,
    load_campaigns,
    load_wins,
    main,
    match_wins_local,
    parse_deadline,
    render_template,
    stats_fingerprint,
    week_window,
    wins_block,
)

TWEET_A = "2080000000000000001"
TWEET_B = "2080000000000000002"
TWEET_C = "2080000000000000003"


def _item(
    tweet_id: str,
    handle: str = "campA",
    *,
    text: str = "",
    seats: int = 5,
    value: int = 0,
    items: list[str] | None = None,
    deadline: str = "2026-09-30",
    applied: dict[str, str | None] | None = None,
    route: str = "X",
    source: str = "knshow",
) -> dict:
    return {
        "detail_url": f"/detail/{tweet_id}.html",
        "x_url": f"https://x.com/{handle}/status/{tweet_id}",
        "source": source,
        "deadline": deadline,
        "winner_count": seats,
        "prize_score": {"estimated_value_jpy": value, "items": items or [], "priority": 2.5},
        "applied": applied if applied is not None else {"accA": "2026-09-21T00:00:00Z"},
        "tweet_text": text,
        "tweet_id": tweet_id,
        "導線": route,
    }


def _write_project(tmp_path: Path, collected: object, wins: dict | None = None) -> Path:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "collected_today.json").write_text(
        json.dumps(collected, ensure_ascii=False), encoding="utf-8"
    )
    if wins is not None:
        (tmp_path / "data" / "dm_wins.json").write_text(json.dumps(wins, ensure_ascii=False), encoding="utf-8")
    tpl_dir = tmp_path / "reports" / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    repo_tpl = Path(__file__).resolve().parents[1] / "reports" / "templates"
    (tpl_dir / "data-journalism-report.md").write_text(
        (repo_tpl / "data-journalism-report.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tpl_dir / "data-journalism-blog.md").write_text(
        (repo_tpl / "data-journalism-blog.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


# ── 正規化・抽出 ──────────────────────────────────────────────────────
def test_parse_deadline_formats() -> None:
    assert parse_deadline("2026-09-30") is not None
    assert parse_deadline("2026年9月30日") is not None
    assert parse_deadline("9/30") is not None
    assert parse_deadline("") is None
    assert parse_deadline("未定") is None


def test_extract_value_from_text_prefers_yen_bun() -> None:
    assert extract_value_from_text("Amazonギフトカード1,000円分が30名様に当たる") == 1000
    assert extract_value_from_text("100名さまに500円相当のデジタルコード") == 500
    assert extract_value_from_text("応募は9月30日まで") == 0
    # 100円未満・300万円超は誤検出として捨てる
    assert extract_value_from_text("送料50円") == 0
    assert extract_value_from_text("総額50,000,000円の看板企画") == 0


def test_extract_keywords_drops_boilerplate_and_digits() -> None:
    camp = Campaign(
        key="k",
        tweet_text="応募方法: フォロー＆リポスト #VRChat 9月30日 1,000円分のAmazonギフトカード プレゼント",
    )
    kws = extract_keywords(camp)
    assert "#VRChat" in kws
    assert "応募方法" not in kws
    assert "プレゼント" not in kws
    assert all(not k.isdigit() for k in kws)
    # 同一案件内の重複は1回だけ（DFで数えるため）
    assert len(kws) == len(set(kws))


def test_extract_keywords_normalizes_entities_and_width() -> None:
    camp = Campaign(key="k", tweet_text="＃鬼滅の刃 ＆amp; #煉獄さん キャンペーン")
    kws = extract_keywords(camp)
    assert "#鬼滅の刃" in kws
    assert "#煉獄さん" in kws


def test_classify_category_from_text() -> None:
    assert classify_category(Campaign(key="k", tweet_text="Switch2が当たる")) == "ゲーム機・ゲームソフト"
    assert classify_category(Campaign(key="k", tweet_text="Amazonギフトカード1,000円分")) == "Amazonギフト券"
    assert classify_category(Campaign(key="k", tweet_text="兵庫県産トマト（7,000円相当）をプレゼント")) == "食品・飲料"
    assert classify_category(Campaign(key="k", tweet_text="抱き枕カバーを抽選で1名様")) == "グッズ・ノベルティ"
    assert classify_category(Campaign(key="k", tweet_text="謎の企画")) == "分類不能・情報欠損"
    # prize_score の items が優先シグナル
    assert classify_category(Campaign(key="k", prize_items=["Amazonギフト券"])) == "Amazonギフト券"


def test_band_of() -> None:
    from scripts.kensho_data_journalism import _WINCOUNT_BANDS

    assert band_of(1, _WINCOUNT_BANDS) == "1名（最難関）"
    assert band_of(0, _WINCOUNT_BANDS) == "枠数不明・記載なし"
    assert band_of(500, _WINCOUNT_BANDS) == "101名以上（大量枠）"


def test_iso_week_and_window() -> None:
    from datetime import date

    assert iso_week_label(date(2026, 9, 23)) == "2026W39"
    window = week_window("2026W39")
    assert window is not None
    assert window[0].strftime("%Y-%m-%d") == "2026-09-21"
    assert week_window("bad") is None


# ── ローダ ────────────────────────────────────────────────────────────
def test_load_campaigns_merges_and_unions_applied(tmp_path: Path) -> None:
    old = [_item(TWEET_A, text="Amazonギフト券1,000円分", applied={"accA": "2026-09-01T00:00:00Z"})]
    new = [_item(TWEET_A, text="Amazonギフト券1,000円分", applied={"accB": "2026-09-02T00:00:00Z"})]
    (tmp_path / "a.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"collected": new}, ensure_ascii=False), encoding="utf-8")
    camps = load_campaigns([str(tmp_path / "a.json"), str(tmp_path / "b.json")])
    assert len(camps) == 1
    camp = camps[TWEET_A]
    assert set(camp.applied) == {"accA", "accB"}
    # prize_score が 0 なので本文の「◯円分」から推定される
    assert camp.estimated_value_jpy == 1000
    assert camp.value_source == "text"


def test_load_campaigns_prefers_prize_score_value(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps([_item(TWEET_B, value=3000, text="500円分")], ensure_ascii=False), encoding="utf-8")
    camps = load_campaigns([str(p)])
    assert camps[TWEET_B].estimated_value_jpy == 3000
    assert camps[TWEET_B].value_source == "prize_score"


def test_discover_snapshot_files_includes_history(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "collected_today.json").write_text("[]", encoding="utf-8")
    hdir = tmp_path / "data" / "collected_history"
    hdir.mkdir()
    (hdir / "collected_20260921.json").write_text("[]", encoding="utf-8")
    paths = discover_snapshot_files(str(tmp_path))
    assert any("collected_today.json" in p for p in paths)
    assert any("collected_history" in p for p in paths)


def test_load_wins_flattens(tmp_path: Path) -> None:
    p = tmp_path / "dm_wins.json"
    p.write_text(json.dumps({"accA": [{"sender": "@campA", "message_text": "当選"}], "accB": []}), encoding="utf-8")
    wins = load_wins(str(p))
    assert len(wins) == 1
    assert wins[0]["account_key"] == "accA"


# ── 突合 ──────────────────────────────────────────────────────────────
def test_match_wins_local_by_tweet_id_and_handle() -> None:
    camps = {
        TWEET_A: Campaign(key=TWEET_A, tweet_id=TWEET_A, handle="campa", applied={"accA": "t"}),
        TWEET_B: Campaign(key=TWEET_B, tweet_id=TWEET_B, handle="campb", applied={"accA": "t"}),
    }
    wins = [
        {"account_key": "accA", "sender": "@other", "message_text": f"ご当選 https://x.com/campa/status/{TWEET_A}"},
        {"account_key": "accA", "sender": "@campb", "message_text": "ご当選おめでとうございます"},
    ]
    matched, unmatched = match_wins_local(wins, camps)
    assert len(matched) == 2
    assert not unmatched
    assert {m["key"] for m in matched} == {"tweet_id", "handle"}


def test_match_wins_local_unmatched() -> None:
    matched, unmatched = match_wins_local(
        [{"account_key": "accZ", "sender": "@nobody", "message_text": "当選"}], {}
    )
    assert matched == []
    assert len(unmatched) == 1


# ── 集計 ──────────────────────────────────────────────────────────────
def _fixture_campaigns() -> dict[str, Campaign]:
    return {
        TWEET_A: Campaign(
            key=TWEET_A, tweet_id=TWEET_A, handle="campa", source="knshow", deadline="2026-09-30",
            winner_count=100, estimated_value_jpy=1000, value_source="text", route="X",
            tweet_text="#VRChat 衣装プレゼント Amazonギフト券1,000円分",
            applied={"accA": "t1", "accB": "t2"},
        ),
        TWEET_B: Campaign(
            key=TWEET_B, tweet_id=TWEET_B, handle="campb", source="kenshouclub", deadline="2026-09-25",
            winner_count=1, estimated_value_jpy=0, route="LINE",
            tweet_text="#VRChat ぬいぐるみ1名様",
            applied={"accA": "t1"},
        ),
        TWEET_C: Campaign(
            key=TWEET_C, tweet_id=TWEET_C, handle="campc", source="twscrape", deadline="",
            winner_count=0, route="未判定", tweet_text="豪華賞品が当たる",
            applied={},
        ),
    }


def test_keyword_stats_lift_sign() -> None:
    camps = _fixture_campaigns()
    rows = {r["keyword"]: r for r in keyword_stats(camps, top_n=50, min_df=2)}
    assert "#VRChat" in rows
    # #VRChat は応募が厚い2案件に含まれる → 全体平均より応募率が高い
    assert rows["#VRChat"]["campaigns"] == 2
    assert rows["#VRChat"]["lift"] > 0
    # min_df を上げると 2 件しか出ていない語は消える
    assert "#VRChat" not in {r["keyword"] for r in keyword_stats(camps, top_n=50, min_df=3)}


def test_analyze_aggregates() -> None:
    camps = _fixture_campaigns()
    wins = [
        {"account_key": "accA", "sender": "@campa", "message_text": f"https://x.com/campa/status/{TWEET_A}"},
    ]
    stats = analyze(camps, wins, None, wins_stats=wins_block(camps, wins))
    assert stats["total_campaigns"] == 3
    assert stats["total_entries"] == 3
    assert stats["total_seats"] == 101
    assert stats["total_estimated_value_jpy"] == 1000
    assert stats["wins"]["matched"] == 1
    assert stats["wins"]["by_category"]
    assert stats["by_route"]["X"] == 1
    assert stats["category_unclassified"] == 1
    # 未応募案件（accB 未応募の案件がある）が機会損失リストに出る
    assert any(m["missing"] >= 1 for m in stats["missed"])


def test_analyze_win_rates_use_full_period_entries() -> None:
    camps = _fixture_campaigns()
    wins = [{"account_key": "accA", "sender": "@campa", "message_text": f"https://x.com/campa/status/{TWEET_A}"}]
    stats = analyze(camps, wins, None, wins_stats=wins_block(camps, wins))
    block = stats["wins"]
    assert block["entries_total"] == 3
    assert sum(block["entries_by_category"].values()) == 3
    assert block["matched_keys"].get("tweet_id") == 1


def test_analyze_wow_delta() -> None:
    cur = {TWEET_A: _fixture_campaigns()[TWEET_A]}
    prev = _fixture_campaigns()
    stats = analyze(cur, [], prev, wins_stats=wins_block(cur, []))
    wow = stats["wow"]
    assert wow is not None
    assert wow["prev_size"] == 3
    assert wow["disappeared"] == 2


def test_fingerprint_is_stable() -> None:
    camps = _fixture_campaigns()
    s1 = analyze(camps, [], None)
    s2 = analyze(camps, [], None)
    assert stats_fingerprint(s1) == stats_fingerprint(s2)


def test_wow_new_sample_is_deterministically_sorted() -> None:
    """前週比の「新規案件の例」はキー降順で固定する（t_0b949bda 再現性回帰）.

    set の反復順はプロセスごとのハッシュ乱数に依存するため、`list(new)[:5]` に戻すと
    同一入力でも fingerprint が揺れる（レポート本文の数値は同じなのに統計ダイジェストが変わる）。
    """
    prev = {TWEET_A: Campaign(key=TWEET_A, tweet_id=TWEET_A, tweet_text="既存案件")}
    new_ids = [
        "2080000000000000005",
        "2080000000000000006",
        "2080000000000000007",
        "2080000000000000008",
        "2080000000000000009",
        "2080000000000000010",
    ]
    cur = {**prev, **{i: Campaign(key=i, tweet_id=i, tweet_text=f"新規{i}") for i in new_ids}}
    wow = analyze(cur, [], prev)["wow"]
    assert wow is not None
    assert wow["new_campaigns"] == 6
    assert wow["new_sample"] == [f"新規{i}" for i in sorted(new_ids, reverse=True)[:5]]
    # 同条件を再計算しても同一（候補順が固定されている）
    assert analyze(cur, [], prev)["wow"]["new_sample"] == wow["new_sample"]


# ── 描画 ──────────────────────────────────────────────────────────────
def test_render_template_raises_on_missing_placeholder() -> None:
    with pytest.raises(KeyError):
        render_template("hello {{MISSING_TOKEN}}", {})


def test_build_sections_uses_real_numbers() -> None:
    camps = _fixture_campaigns()
    # min_df=2: フィクスチャの #VRChat は2案件にしか出ないため、既定(min_df=3)では
    # ノイズ除外で表が空になる。ここでは「統計に入っている語が実際に表へ出る」ことを見る。
    stats = analyze(camps, [], None, min_df=2)
    sections = build_sections(stats)
    assert "3" in sections["SUMMARY_BULLETS"]
    assert "#VRChat" in sections["KEYWORD_TABLE"]
    assert "機会損失" not in sections["MISSED_TABLE"]  # 見出しではなく表本体
    blog = build_blog_sections({**stats, "week_label": "2026W39"})
    assert "2026W39" in blog["BODY"]


def test_report_template_placeholders_are_all_supplied() -> None:
    repo = Path(__file__).resolve().parents[1]
    tpl = (repo / "reports" / "templates" / "data-journalism-report.md").read_text(encoding="utf-8")
    blog_tpl = (repo / "reports" / "templates" / "data-journalism-blog.md").read_text(encoding="utf-8")
    camps = _fixture_campaigns()
    stats = {**analyze(camps, [], None), "week_label": "2026W39"}
    values = build_sections(stats)
    values.update({t: "" for t in _PLACEHOLDER_RE.findall(tpl)})
    values.update({**build_blog_sections(stats), "TITLE": "t", "FRONT_MATTER": "f", "FOOTER": "x"})
    # テンプレ側のトークンが全て補給されていれば KeyError は出ない
    render_template(tpl, values)
    render_template(blog_tpl, values)


# ── エンドツーエンド ──────────────────────────────────────────────────
def test_main_end_to_end_writes_report_stats_and_drafts(tmp_path: Path) -> None:
    collected = [
        _item(TWEET_A, text="VRChat 衣装 #VRChat Amazonギフト券1,000円分", seats=100),
        _item(TWEET_B, handle="campB", text="ぬいぐるみ 1名様", seats=1, applied={}),
        _item(TWEET_C, handle="campC", text="旅行ペアチケット", seats=2, deadline="9/30"),
    ]
    wins = {"accA": [{"sender": "@campA", "message_text": f"当選 https://x.com/campA/status/{TWEET_A}"}]}
    pd = _write_project(tmp_path, collected, wins)

    rc = main(["--project-dir", str(pd), "--week", "2026W39", "--quiet"])
    assert rc == 0

    report = pd / "reports" / "journalism" / "2026W39.md"
    stats_path = pd / "reports" / "journalism" / "2026W39.json"
    devto = pd / "reports" / "journalism" / "drafts" / "devto-2026W39.md"
    qiita = pd / "reports" / "journalism" / "drafts" / "qiita-2026W39.md"
    for p in (report, stats_path, devto, qiita):
        assert p.exists(), p
    body = report.read_text(encoding="utf-8")
    assert "2026W39" in body
    assert "{{" not in body  # 未置換のプレースホルダが残っていない
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats["wins"]["matched"] == 1
    assert stats["fingerprint"]
    # dev.to は published:false / Qiita は private:true の front matter
    assert "published: false" in devto.read_text(encoding="utf-8")
    assert "private: true" in qiita.read_text(encoding="utf-8")


def test_main_is_deterministic_across_runs(tmp_path: Path) -> None:
    collected = [_item(TWEET_A, text="#VRChat Amazonギフト券1,000円分")]
    pd = _write_project(tmp_path, collected, {})
    assert main(["--project-dir", str(pd), "--week", "2026W39", "--quiet"]) == 0
    first = json.loads((pd / "reports" / "journalism" / "2026W39.json").read_text(encoding="utf-8"))
    assert main(["--project-dir", str(pd), "--week", "2026W39", "--quiet"]) == 0
    second = json.loads((pd / "reports" / "journalism" / "2026W39.json").read_text(encoding="utf-8"))
    assert first["fingerprint"] == second["fingerprint"]


def test_main_snapshot_creates_history(tmp_path: Path) -> None:
    pd = _write_project(tmp_path, [_item(TWEET_A, text="テスト")], {})
    assert main(["--project-dir", str(pd), "--week", "2026W39", "--snapshot", "--quiet"]) == 0
    hist = list((pd / "data" / "collected_history").glob("*.json"))
    assert len(hist) == 1


def test_main_no_wins_skips_matching(tmp_path: Path) -> None:
    wins = {"accA": [{"sender": "@campA", "message_text": f"status/{TWEET_A}"}]}
    pd = _write_project(tmp_path, [_item(TWEET_A, text="景品")], wins)
    assert main(["--project-dir", str(pd), "--week", "2026W39", "--no-wins", "--quiet"]) == 0
    stats = json.loads((pd / "reports" / "journalism" / "2026W39.json").read_text(encoding="utf-8"))
    assert stats["wins"]["total"] == 0


def test_main_check_template_ok(tmp_path: Path) -> None:
    pd = _write_project(tmp_path, [], {})
    assert main(["--project-dir", str(pd), "--check-template"]) == 0


def test_main_missing_data_returns_1(tmp_path: Path) -> None:
    pd = _write_project(tmp_path, [], {})
    (pd / "data" / "collected_today.json").unlink()
    assert main(["--project-dir", str(pd), "--week", "2026W39", "--quiet"]) == 1
