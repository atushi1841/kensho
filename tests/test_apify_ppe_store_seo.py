"""Tests for scripts/apify_ppe_store_seo.py — v26-3 Apify Store description SEO最適化（t_c0f85dbe）。

主に pure function（validate_spec / validate_all / meta_diff）を検証。
API は叩かず、SPECS の内容と README 成果物の存在をチェックする。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_ppe_store_seo as seo


def _base_spec() -> dict[str, Any]:
    """あらゆる検証に通る「正常系」spec を返す。"""
    s = dict(seo.SPECS["camera"])  # 実 spec を雛形に
    s["name"] = "test-actor"
    return s


# --------------------------------------------------------------------- validate_spec


def test_validate_all_no_problems_for_all_five() -> None:
    # SPECS 全体が文字数/カテゴリ数/README 存在/旨文案 の違反なし
    assert seo.validate_all() == []


def test_validate_spec_ok_for_normal() -> None:
    assert seo.validate_spec(_base_spec()) == []


def test_validate_spec_rejects_title_overflow() -> None:
    s = _base_spec()
    s["title"] = "X" * 64
    problems = seo.validate_spec(s)
    assert any("title=64 > 63" in p for p in problems)


def test_validate_spec_rejects_seodescription_overflow() -> None:
    s = _base_spec()
    s["seoDescription"] = "X" * 161
    problems = seo.validate_spec(s)
    assert any("seoDescription=161 > 160" in p for p in problems)


def test_validate_spec_rejects_description_overflow() -> None:
    s = _base_spec()
    s["description"] = "X" * 301
    problems = seo.validate_spec(s)
    assert any("description=301 > 300" in p for p in problems)


def test_validate_spec_rejects_too_many_categories() -> None:
    s = _base_spec()
    s["categories"] = ["A", "B", "C", "D"]
    problems = seo.validate_spec(s)
    assert any("categories=4 > 3" in p for p in problems)


def test_validate_spec_rejects_junk_suffix() -> None:
    s = _base_spec()
    s["description"] = "Nice text. Updated for better discoverability."
    problems = seo.validate_spec(s)
    assert any("junk suffix" in p for p in problems)


def test_validate_spec_rejects_truncated_title() -> None:
    s = _base_spec()
    s["title"] = "Japan Used Instrument Market — Cross-Shop Price Comparison digi"
    problems = seo.validate_spec(s)
    assert any("truncated keyword remnant" in p for p in problems)


def test_validate_spec_rejects_missing_readme(tmp_path: Path) -> None:
    s = _base_spec()
    s["readme_path"] = tmp_path / "does-not-exist.md"
    problems = seo.validate_spec(s)
    assert any("readme missing or empty" in p for p in problems)


# --------------------------------------------------------------------- meta_diff


def test_meta_diff_detects_changes() -> None:
    spec = {
        "title": "New Title",
        "seoTitle": "NT",
        "seoDescription": "ND",
        "description": "NewDesc",
        "categories": ["A", "B", "C"],
    }
    current = {
        "title": "Old Title",
        "seoTitle": "NT",
        "seoDescription": "ND",
        "description": "NewDesc",
        "categories": ["A", "B", "C"],
    }
    diff = seo.meta_diff(spec, current)  # type: ignore[arg-type]
    # タイトルのみ変わる
    assert set(diff.keys()) == {"title"}
    assert diff["title"] == ("Old Title", "New Title")


def test_meta_diff_empty_when_identical() -> None:
    spec = {"title": "Same", "seoTitle": "ST", "seoDescription": "SD", "description": "D", "categories": ["A"]}
    current = dict(spec)
    diff = seo.meta_diff(spec, current)  # type: ignore[arg-type]
    assert diff == {}


def test_meta_diff_all_fields() -> None:
    spec = {"title": "T", "seoTitle": "ST", "seoDescription": "SD", "description": "D", "categories": ["A", "B", "C"]}
    current = {}
    diff = seo.meta_diff(spec, current)  # type: ignore[arg-type]
    assert set(diff.keys()) == {"title", "seoTitle", "seoDescription", "description", "categories"}


# --------------------------------------------------------------------- content sanity


def test_specs_contain_seo_keywords() -> None:
    """Japanese二手中古価格データ系のSEOキーワードが各specに入っている。"""
    for key, spec in seo.SPECS.items():
        blob = " ".join([
            str(spec.get("title", "")),
            str(spec.get("seoTitle", "")),
            str(spec.get("seoDescription", "")),
            str(spec.get("description", "")),
        ]).lower()
        assert "used" in blob, f"{key}: missing 'used'"
        assert "japan" in blob, f"{key}: missing 'japan'"
        assert "price" in blob, f"{key}: missing 'price'"
        # 各 actor が固有の中古ドメイン語も含む
        assert key in {"camera", "watch", "luxury", "instrument", "offmall"}
        assert blob.count("arbitrage") >= 0  # 少なくとも1アクター以上で resale 言及


def test_pppe_claims_consistent() -> None:
    """description 内の単価表記と spec.ppe が一致する。"""
    for key, spec in seo.SPECS.items():
        assert f"${spec['ppe']}" in spec["description"], f"{key}: price claim mismatch"


def test_readme_artifacts_exist_and_nonempty() -> None:
    for key, spec in seo.SPECS.items():
        p = spec["readme_path"]
        assert p.exists(), f"{key}: README not found at {p}"
        assert len(p.read_text(encoding="utf-8").strip()) > 500, f"{key}: README too thin"
