"""
Tests for scripts/apify_seo_apply.py — SEO audit findings batch-apply (t_15af8300 / critic v14-C)

ネットワーク不使用: fixture ベースの actor / finding データで
merge_* 関数と build_update_payload を検証する。
HTTP呼び出しはモックで検証。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_seo_apply as apply_mod


def _actor(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "test_id_001",
        "name": "japan-foo-market-scraper",
        "title": "Japan Foo Market Scraper",
        "description": "Scrapes Japan foo market prices.",
        "seoTitle": "",
        "seoDescription": "",
        "categories": ["ECOMMERCE"],
        "isPublic": True,
        "modifiedAt": "2026-09-01T00:00:00.000Z",
    }
    base.update(overrides)
    return base


def _finding(**overrides: Any) -> apply_mod.Finding:
    base: dict[str, Any] = {
        "actor": "japan-foo-market-scraper",
        "issue": "missing_categories",
        "field": "categories",
        "current": "ECOMMERCE",
        "suggested": "追加候補: AUTOMATION(競合2件), DEVELOPER_TOOLS(競合2件)",
        "evidence": "test evidence",
    }
    base.update(overrides)
    return apply_mod.Finding(**base)


# --- merge_categories ---


def test_merge_categories_appends_only_new_valid():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(suggested="追加候補: AUTOMATION(競合2件), DEVELOPER_TOOLS(競合2件)")
    cats, ch = apply_mod.merge_categories(a, f)
    assert "AUTOMATION" in cats
    assert "DEVELOPER_TOOLS" in cats
    assert "ECOMMERCE" in cats
    assert ch == ["categories"]


def test_merge_categories_skips_existing():
    a = _actor(categories=["ECOMMERCE", "AUTOMATION"])
    f = _finding(suggested="追加候補: AUTOMATION(競合2件), DEVELOPER_TOOLS(競合2件)")
    cats, ch = apply_mod.merge_categories(a, f)
    # AUTOMATION は既存なので追加されない、DEVELOPER_TOOLS だけ追加
    assert cats.count("AUTOMATION") == 1
    assert "DEVELOPER_TOOLS" in cats
    assert ch == ["categories"]


def test_merge_categories_no_valid_returns_empty_change():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(suggested="追加候補: NOT_A_VALID_CATEGORY(競合2件)")
    cats, ch = apply_mod.merge_categories(a, f)
    assert cats == ["ECOMMERCE"]
    assert ch == []


def test_merge_categories_no_candidate_keyword_returns_empty():
    a = _actor()
    f = _finding(suggested="何か別の提案")
    cats, ch = apply_mod.merge_categories(a, f)
    assert ch == []


def test_merge_categories_caps_at_3():
    """Apify API の実制限: 3つまで。4つ目を追加しようとしてもスキップ。"""
    a = _actor(categories=["ECOMMERCE", "AUTOMATION"])  # 既に2つ
    f = _finding(suggested="追加候補: LEAD_GENERATION(競合1件), DEVELOPER_TOOLS(競合1件), MCP_SERVERS(競合1件)")
    cats, ch = apply_mod.merge_categories(a, f)
    # 2つ → 3つまでしか追加できない（ECOMMERCE, AUTOMATION, +1つだけ）
    assert len(cats) == 3
    assert "ECOMMERCE" in cats
    assert "AUTOMATION" in cats
    # 3つ目: 候補順で LEAD_GENERATION が先頭なので追加される
    # DEVELOPER_TOOLS と MCP_SERVERS は上限到達でスキップ
    assert ch == ["categories"]


def test_merge_categories_already_3_no_change():
    a = _actor(categories=["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"])
    f = _finding(suggested="追加候補: LEAD_GENERATION(競合1件)")
    cats, ch = apply_mod.merge_categories(a, f)
    # 既に3つなので何も追加しない
    assert cats == ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"]
    assert ch == []


# --- merge_title ---


def test_merge_title_adds_missing_keywords():
    a = _actor(title="Japan Foo Market Scraper")
    f = _finding(
        issue="title_keyword_gap",
        field="title",
        suggested="タイトルへ追加: collectibles(競合3件), marketplace(競合2件)",
    )
    new_title, ch = apply_mod.merge_title(a, f)
    assert "collectibles" in new_title
    assert "marketplace" in new_title
    assert ch == ["title"]


def test_merge_title_skips_existing_keywords():
    a = _actor(title="Japan Foo Market collectibles Scraper")
    f = _finding(
        issue="title_keyword_gap",
        suggested="タイトルへ追加: collectibles(競合3件), marketplace(競合2件)",
    )
    new_title, ch = apply_mod.merge_title(a, f)
    # collectibles は既存、marketplace だけ追加
    assert "marketplace" in new_title
    # 元のtitleに含まれる collectibles の重複は1個のまま
    assert new_title.count("collectibles") == 1
    assert ch == ["title"]


def test_merge_title_truncates_to_63():
    long_suffix = " ".join(f"keyword{i}" for i in range(20))
    a = _actor(title="Short")
    f = _finding(
        issue="title_keyword_gap",
        suggested=f"タイトルへ追加: {long_suffix}",
    )
    new_title, ch = apply_mod.merge_title(a, f)
    assert len(new_title) <= 63
    assert ch == ["title"]


# --- merge_description ---


def test_merge_description_short_extends_with_suffix():
    a = _actor(description="Short desc.")
    f = _finding(
        issue="short_description",
        field="description",
        suggested="競合中央値 274字以上に拡張（最大 294字）",
    )
    new_desc, ch = apply_mod.merge_description(a, f)
    assert "Updated for better discoverability" in new_desc
    assert ch == ["description"]


def test_merge_description_missing_keywords_appends():
    a = _actor(description="Scrapes prices.")
    f = _finding(
        issue="missing_keywords",
        field="description",
        suggested="説明/タイトルに追加: api(競合2件), clean(競合2件)",
    )
    new_desc, ch = apply_mod.merge_description(a, f)
    assert "api" in new_desc
    assert "clean" in new_desc
    assert ch == ["description"]


def test_merge_description_truncates_to_512():
    a = _actor(description="X")
    f = _finding(
        issue="missing_keywords",
        suggested="説明/タイトルに追加: " + ",".join(f"kw{i}" for i in range(50)),
    )
    new_desc, ch = apply_mod.merge_description(a, f)
    assert len(new_desc) <= 512
    assert ch == ["description"]


# --- merge_seo_fields ---


def test_merge_seo_fields_fills_seo_title_from_title():
    a = _actor(title="Japan Foo Bar Baz", seoTitle="")
    f = _finding(issue="seo_title_missing", field="seoTitle", suggested="")
    out, ch = apply_mod.merge_seo_fields(a, f)
    assert "seoTitle" in out
    assert out["seoTitle"] == "Japan Foo Bar Baz"[:60]
    assert "seoTitle" in ch


def test_merge_seo_fields_fills_seo_description_from_description():
    a = _actor(description="Long enough description text here.", seoDescription="")
    f = _finding(issue="seo_description_missing", field="seoDescription", suggested="")
    out, ch = apply_mod.merge_seo_fields(a, f)
    assert "seoDescription" in out
    assert out["seoDescription"] == "Long enough description text here."[:160]
    assert "seoDescription" in ch


def test_merge_seo_fields_does_not_overwrite_existing():
    a = _actor(seoTitle="Existing", seoDescription="Existing desc")
    f = _finding(issue="seo_title_missing", suggested="")
    out, ch = apply_mod.merge_seo_fields(a, f)
    # 既存値があるなら上書きしない
    assert "seoTitle" not in out
    assert ch == []


# --- build_update_payload ---


def test_build_payload_missing_categories():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(issue="missing_categories", suggested="追加候補: AUTOMATION(競合2件)")
    payload, changed = apply_mod.build_update_payload(a, f)
    # build_update_payload 自体は isPublic を付与しない（apply_one で付与する）
    assert "categories" in payload
    assert "AUTOMATION" in payload["categories"]
    assert "isPublic" not in payload
    assert "categories" in changed


def test_build_payload_short_description():
    a = _actor(description="Short.")
    f = _finding(issue="short_description", suggested="競合中央値 274字以上に拡張")
    payload, changed = apply_mod.build_update_payload(a, f)
    assert "description" in payload
    assert "Updated for better discoverability" in payload["description"]


def test_build_payload_seo_title_missing():
    a = _actor(seoTitle="")
    f = _finding(issue="seo_title_missing", suggested="")
    payload, changed = apply_mod.build_update_payload(a, f)
    assert "seoTitle" in payload
    assert payload["seoTitle"]  # 空ではない


def test_build_payload_no_change_returns_empty():
    a = _actor()
    f = _finding(issue="missing_categories", suggested="追加候補: NOT_A_VALID_CATEGORY(競合2件)")
    payload, changed = apply_mod.build_update_payload(a, f)
    # isPublic は build_update_payload 段階では付与しない（apply_one で付与）
    assert "categories" not in payload
    assert changed == []


def test_build_payload_discovery_gap_falls_back_to_description():
    a = _actor(description="Original desc.")
    f = _finding(issue="discovery_gap", suggested="", field="actor")
    payload, changed = apply_mod.build_update_payload(a, f)
    # suggestedに「追加」/「追加候補」が無いので他経路で何も変わらず、fallbackでdescriptionに追記
    assert "description" in payload
    assert "Updated for better discoverability" in payload["description"]
    assert "description" in changed


# --- load_findings のフィルタ ---


def test_load_findings_skips_no_competitor_data(tmp_path: Path):
    import csv as _csv

    p = tmp_path / "test.csv"
    with p.open("w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["actor", "issue", "field", "current", "suggested", "evidence"])
        w.writeheader()
        w.writerow({
            "actor": "a",
            "issue": "no_competitor_data",
            "field": "",
            "current": "",
            "suggested": "",
            "evidence": "",
        })
        w.writerow({
            "actor": "a",
            "issue": "missing_categories",
            "field": "categories",
            "current": "ECOMMERCE",
            "suggested": "追加候補: AUTOMATION(競合2件)",
            "evidence": "",
        })
    findings = apply_mod.load_findings(p, limit=None, impacts=None)
    # no_competitor_data はデフォルト skip
    assert len(findings) == 1
    assert findings[0].issue == "missing_categories"


def test_load_findings_impact_filter(tmp_path: Path):
    import csv as _csv

    p = tmp_path / "test.csv"
    with p.open("w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["actor", "issue", "field", "current", "suggested", "evidence"])
        w.writeheader()
        w.writerow({
            "actor": "a",
            "issue": "discovery_gap",
            "field": "",
            "current": "",
            "suggested": "",
            "evidence": "",
        })
        w.writerow({
            "actor": "a",
            "issue": "short_description",
            "field": "description",
            "current": "x",
            "suggested": "拡張",
            "evidence": "",
        })
        w.writerow({
            "actor": "a",
            "issue": "missing_categories",
            "field": "categories",
            "current": "ECOMMERCE",
            "suggested": "追加候補: AUTOMATION(競合2件)",
            "evidence": "",
        })
    findings = apply_mod.load_findings(p, limit=None, impacts={"discovery_gap"})
    assert len(findings) == 1
    assert findings[0].issue == "discovery_gap"


def test_load_findings_impact_order():
    """impact_rank で正しくソートされるか。"""
    p = Path("/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-audit-2026-09-04.csv")
    if not p.exists():
        return  # CSVが無ければskip（CI環境用）
    findings = apply_mod.load_findings(p, limit=10, impacts=None)
    ranks = [f.impact_rank for f in findings]
    assert ranks == sorted(ranks)
    assert findings[0].impact_rank == 0  # discovery_gap が最初


# --- apply_one の HTTP モックテスト ---


def test_apply_one_success():
    a = _actor(id="test123", categories=["ECOMMERCE"])
    f = _finding(issue="missing_categories", suggested="追加候補: AUTOMATION(競合2件)")
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        with patch.object(
            apply_mod,
            "_api_put",
            return_value=(
                200,
                {
                    "data": {**a, "categories": ["ECOMMERCE", "AUTOMATION"], "modifiedAt": "2026-09-04T11:00:00Z"},
                },
            ),
        ) as mock_put:
            r = apply_mod.apply_one(f, "test123", "tok", cache)
    assert r.ok
    assert r.status_code == 200
    assert "categories" in r.fields_changed
    assert mock_put.called
    # isPublic 維持の確認
    call_args = mock_put.call_args
    payload = call_args[0][2]
    assert payload["isPublic"] is True


def test_apply_one_get_failure():
    f = _finding()
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(404, {"error": "Not found"})):
        r = apply_mod.apply_one(f, "test123", "tok", cache)
    assert not r.ok
    assert r.status_code == 404


def test_apply_one_put_failure():
    a = _actor(id="test123", categories=["ECOMMERCE"])
    f = _finding(issue="missing_categories", suggested="追加候補: AUTOMATION(競合2件)")
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        with patch.object(apply_mod, "_api_put", return_value=(400, {"error": {"message": "bad"}})):
            r = apply_mod.apply_one(f, "test123", "tok", cache)
    assert not r.ok
    assert r.status_code == 400


def test_apply_one_no_change_proposed():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(issue="missing_categories", suggested="追加候補: NOT_VALID")
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        r = apply_mod.apply_one(f, "test123", "tok", cache)
    assert not r.ok
    assert "no change proposed" in r.error


# --- v15-A bulk templating tests ---


def test_group_findings_by_actor():
    f1 = _finding(actor="actor-a", issue="short_description", impact_rank=1)
    f2 = _finding(actor="actor-a", issue="missing_keywords", impact_rank=3)
    f3 = _finding(actor="actor-b", issue="missing_categories", impact_rank=2)
    g = apply_mod.group_findings_by_actor([f1, f3, f2])
    assert set(g.keys()) == {"actor-a", "actor-b"}
    assert [f.issue for f in g["actor-a"]] == ["short_description", "missing_keywords"]
    assert [f.issue for f in g["actor-b"]] == ["missing_categories"]


def test_group_findings_by_actor_empty():
    assert apply_mod.group_findings_by_actor([]) == {}


def test_merge_actor_payload_combines_changes():
    """複数 finding を 1 actor に集約したとき payload が合体する."""
    a = _actor(
        title="Old Title",
        description="Old desc.",
        categories=["ECOMMERCE"],
    )
    f1 = _finding(issue="short_description", suggested="競合中央値 274字以上に拡張（最大 294字）", impact_rank=1)
    f2 = _finding(
        issue="missing_categories", suggested="追加候補: AUTOMATION(競合2件), DEVELOPER_TOOLS(競合2件)", impact_rank=2
    )
    payload, changed, applied = apply_mod.merge_actor_payload(a, [f1, f2])
    assert "description" in changed
    assert "categories" in changed
    assert "short_description" in applied
    assert "missing_categories" in applied
    assert len(applied) == 2


def test_merge_actor_payload_no_change():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(issue="missing_categories", suggested="追加候補: NOT_VALID_CATEGORY")
    payload, changed, applied = apply_mod.merge_actor_payload(a, [f])
    assert payload == {}
    assert changed == []
    assert applied == []


def test_merge_actor_payload_chained_title_updates():
    """同じ title に2回 update が走っても virtual_actor で累積する."""
    a = _actor(title="Base", description="Base desc.")
    f1 = _finding(issue="title_keyword_gap", suggested="タイトルへ追加: collectibles(競合3件)", impact_rank=4)
    f2 = _finding(issue="title_keyword_gap", suggested="タイトルへ追加: sold(競合2件)", impact_rank=4)
    payload, changed, applied = apply_mod.merge_actor_payload(a, [f1, f2])
    assert "title" in changed
    assert "collectibles" in payload["title"]
    assert "sold" in payload["title"]


def test_apply_bulk_one_merges_multiple_findings():
    """1 actor に複数 finding → 1 GET + 1 PUT で 複数 ApplyResult が返る."""
    a = _actor(
        id="actX1",
        title="Old",
        description="Old desc.",
        categories=["ECOMMERCE"],
    )
    f1 = _finding(
        actor="actor-x", issue="short_description", suggested="競合中央値 274字以上に拡張（最大 294字）", impact_rank=1
    )
    f2 = _finding(actor="actor-x", issue="missing_categories", suggested="追加候補: AUTOMATION(競合2件)", impact_rank=2)
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        with patch.object(
            apply_mod, "_api_put", return_value=(200, {"data": {**a, "categories": ["ECOMMERCE", "AUTOMATION"]}})
        ) as mock_put:
            results = apply_mod.apply_bulk_one("actor-x", "actX1", [f1, f2], "tok", cache)
    assert mock_put.call_count == 1  # 1 PUT にまとめられている
    assert len(results) == 2
    assert all(r.ok for r in results)
    assert {r.issue for r in results} == {"short_description", "missing_categories"}


def test_apply_bulk_one_no_op_returns_single_ng():
    a = _actor(categories=["ECOMMERCE"])
    f = _finding(actor="actor-x", issue="missing_categories", suggested="追加候補: NOT_VALID")
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        results = apply_mod.apply_bulk_one("actor-x", "actX1", [f], "tok", cache)
    assert len(results) == 1
    assert not results[0].ok
    assert "no change proposed" in results[0].error


def test_apply_bulk_one_put_failure_consolidates():
    a = _actor(id="actX1", title="T", description="D", categories=["ECOMMERCE"])
    f1 = _finding(actor="actor-x", issue="short_description", impact_rank=1)
    f2 = _finding(
        actor="actor-x", issue="missing_keywords", suggested="説明/タイトルに追加: foo(競合2件)", impact_rank=3
    )
    cache: dict[str, Any] = {}
    with patch.object(apply_mod, "_api_get", return_value=(200, {"data": a})):
        with patch.object(apply_mod, "_api_put", return_value=(400, {"error": "bad"})):
            results = apply_mod.apply_bulk_one("actor-x", "actX1", [f1, f2], "tok", cache)
    assert len(results) == 1  # 集約されて 1 件
    assert not results[0].ok
    assert results[0].status_code == 400
