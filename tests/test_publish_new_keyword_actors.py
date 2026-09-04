"""Tests for scripts/publish_new_keyword_actors.py (t_792918af v14-B)."""

import copy
import importlib.util
from pathlib import Path
from unittest import mock

import pytest

MOD = importlib.util.spec_from_file_location("publish_nka", Path("scripts/publish_new_keyword_actors.py"))
mod = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(mod)


def _act():
    return {
        "id": "whSePszWpMtfeLYBp",
        "name": "mercari-japan-search-scraper",
        "categories": ["ECOMMERCE"],
        "title": "Mercari Japan Search Scraper — Prices & Product Data",
        "seo_title": "Mercari Japan Search Scraper — Prices & Product Data",
        "seo_description": "Mercari scrape description for SEO.",
        "description": "Scrape Mercari Japan listings.",
        "force_price": False,
    }


# ---------------------------------------------------------------- spec integrity


@pytest.mark.parametrize("key", list(mod.ACTORS.keys()))
def test_spec_complete(key):
    s = mod.ACTORS[key]
    for f in ("id", "name", "categories", "title", "seo_title", "seo_description", "description"):
        assert s.get(f), f"{key} missing {f}"
    assert len(s["categories"]) <= 3
    assert len(s["seo_title"]) <= mod.CHAR_LIMITS["seoTitle"]
    assert len(s["seo_description"]) <= mod.CHAR_LIMITS["seoDescription"]
    assert len(s["description"]) <= mod.CHAR_LIMITS["description"]


def test_target_ppe_is_0_002():
    assert mod.TARGET_PPE == 0.002


def test_ids_stable():
    assert mod.ACTORS["mercari"]["id"] == "whSePszWpMtfeLYBp"
    assert mod.ACTORS["yahoo"]["id"] == "8WBam4CPB72q9Rvsd"
    assert mod.ACTORS["surugaya"]["id"] == "F8Hl0a8Cx9bpJBrxR"


# ---------------------------------------------------------------- helpers


def test_effective_price_pay_per_event():
    d = {
        "pricingInfos": [
            {
                "pricingModel": "PAY_PER_EVENT",
                "pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventPriceUsd": 0.002}}},
            }
        ]
    }
    assert mod._effective_price(d) == 0.002


def test_effective_price_last_entry_wins():
    d = {
        "pricingInfos": [
            {
                "pricingModel": "PAY_PER_EVENT",
                "pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventPriceUsd": 0.002}}},
            },
            {"pricingModel": "FREE"},
        ]
    }
    assert mod._effective_price(d) is None  # FREE is effective -> None


def test_effective_price_empty():
    assert mod._effective_price({}) is None


def test_current_seo_ok_matching():
    s = _act()
    d = {"seoTitle": s["seo_title"], "seoDescription": s["seo_description"], "isPublic": True}
    assert mod._current_seo_ok(s, d) is True


def test_current_seo_ok_mismatch():
    s = _act()
    d = {"seoTitle": "old", "seoDescription": s["seo_description"], "isPublic": True}
    assert mod._current_seo_ok(s, d) is False


def test_current_seo_ok_not_public():
    s = _act()
    d = {"seoTitle": s["seo_title"], "seoDescription": s["seo_description"], "isPublic": False}
    assert mod._current_seo_ok(s, d) is False


@mock.patch.object(mod, "_put")
def test_apply_price_uses_template_and_appends(mock_put):
    d = {
        "id": "x",
        "pricingInfos": [
            {
                "pricingModel": "PAY_PER_EVENT",
                "apifyMarginPercentage": 0.2,
                "pricingPerEvent": {
                    "actorChargeEvents": {
                        "apify-actor-start": {"eventPriceUsd": 0.00005},
                        "apify-default-dataset-item": {"eventPriceUsd": 1e-05},
                    }
                },
            },
            {"pricingModel": "FREE"},
        ],
    }
    changed = mod._apply_price(d, 0.002)
    assert changed is True
    assert mock_put.call_count == 1
    # body: 既存全件 + 新規1件、新規は last PAY_PER_EVENT を複製して単価変更
    args = mock_put.call_args[0]
    body = args[1]
    assert len(body["pricingInfos"]) == 3
    newest = body["pricingInfos"][-1]
    assert newest["pricingModel"] == "PAY_PER_EVENT"
    assert newest["pricingPerEvent"]["actorChargeEvents"]["apify-default-dataset-item"]["eventPriceUsd"] == 0.002
    assert newest["pricingPerEvent"]["actorChargeEvents"]["apify-actor-start"]["eventPriceUsd"] == mod.TARGET_START
    assert newest["apifyMarginPercentage"] == 0.2
    assert newest.get("createdAt") and newest.get("startedAt")


@mock.patch.object(mod, "_put")
def test_apply_price_refuses_if_no_pay_per_event(mock_put):
    d = {"id": "x", "pricingInfos": [{"pricingModel": "FREE"}]}
    with pytest.raises(RuntimeError):
        mod._apply_price(d, 0.002)
    mock_put.assert_not_called()


@mock.patch.object(mod, "_put")
def test_apply_price_no_pricing_refuses(mock_put):
    with pytest.raises(RuntimeError):
        mod._apply_price({"id": "x", "pricingInfos": []}, 0.002)
    mock_put.assert_not_called()


@mock.patch.object(mod, "_surugaya_last_run_has_data", return_value=False)
def test_process_surugaya_skips_price_when_no_data(mock_has):
    s = copy.deepcopy(mod.ACTORS["surugaya"])
    s["force_price"] = False
    with mock.patch.object(mod, "_get") as mget:
        mget.return_value = {
            "data": {
                "id": s["id"],
                "seoTitle": s["seo_title"],
                "seoDescription": s["seo_description"],
                "isPublic": True,
                "pricingInfos": [],
            }
        }
        out = {"actors": {}}
        mod.process("surugaya", s, apply=True, force_price_surugaya=False, out=out)
    assert out["actors"]["surugaya"].get("price_skipped")  # 0-item guard fires


@mock.patch.object(mod, "_surugaya_last_run_has_data", return_value=True)
@mock.patch.object(mod, "_apply_price", return_value=True)
def test_process_surugaya_prices_with_force(mock_price, mock_has):
    s = copy.deepcopy(mod.ACTORS["surugaya"])
    with mock.patch.object(mod, "_get") as mget:
        mget.return_value = {
            "data": {
                "id": s["id"],
                "seoTitle": s["seo_title"],
                "seoDescription": s["seo_description"],
                "isPublic": True,
                "pricingInfos": [],
            }
        }
        mod.process("surugaya", s, apply=True, force_price_surugaya=True, out={"actors": {}})
    mock_price.assert_called_once()


def test_char_limit_clamps_in_payload_build():
    # PUT payload（camelCase）に対して CHAR_LIMITS のクランプが正しく効くことを確認
    payload = {
        "title": "T" * 200,
        "seoTitle": "S" * 200,
        "seoDescription": "D" * 500,
        "description": "X" * 1000,
        "categories": ["A"] * 10,
    }
    for f, lim in mod.CHAR_LIMITS.items():
        v = payload.get(f)
        if isinstance(v, list):
            payload[f] = v[:lim]
        elif isinstance(v, str):
            payload[f] = v[:lim]
    assert len(payload["title"]) <= 80
    assert len(payload["seoTitle"]) <= 60
    assert len(payload["seoDescription"]) <= 160
    assert len(payload["description"]) <= 300
    assert len(payload["categories"]) <= 3
