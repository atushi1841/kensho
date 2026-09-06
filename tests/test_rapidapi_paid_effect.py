"""
Tests for scripts/rapidapi_paid_effect.py — RapidAPI 有料プラン2週間効果測定
(t_868caac2). ネットワーク非依存：hygiene検出・無料tier分類・collect側attachロジック。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import rapidapi_paid_effect as rpe


def _limit(amount: int, overage: float, limit_type: str | None = "hard", period: str = "MONTHLY") -> dict[str, Any]:
    return {
        "amount": amount,
        "limitType": limit_type,
        "overageprice": overage,
        "period": period,
        "unlimited": False,
        "item_name": "Requests",
    }


def _paid_version(price: float, subs: int = 0, period: str = "PERUSE", current: bool = True) -> dict[str, Any]:
    return {
        "plan_id": "p",
        "plan_name": "PRO",
        "version_id": "vp",
        "version_name": "1",
        "price_field": 0,
        "period": period,
        "status": "ACTIVE",
        "current": current,
        "limits": [_limit(0, price, None)],
        "subscribers": subs,
    }


def _free_version(subs: int = 0, current: bool = True, plan: str = "BASIC") -> dict[str, Any]:
    return {
        "plan_id": "p",
        "plan_name": plan,
        "version_id": "v",
        "version_name": "1",
        "price_field": 0,
        "period": "MONTHLY",
        "status": "ACTIVE",
        "current": current,
        "limits": [_limit(500000, 0.0, "hard")],
        "subscribers": subs,
    }


class TestFreeMonthly:
    def test_free_500k_hard_is_free(self) -> None:
        v = {"limits": [_limit(500000, 0.0, "hard")]}
        assert rpe.is_free_monthly(v) is True

    def test_paid_zero_amount_overage_gt0_not_free(self) -> None:
        v = {"limits": [_limit(0, 0.001, None)]}
        assert rpe.is_free_monthly(v) is False

    def test_small_amount_monthy_not_free(self) -> None:
        v = {"limits": [_limit(1000, 0.0, "hard")]}
        assert rpe.is_free_monthly(v) is False


class TestPerCallPrice:
    def test_returns_overageprice(self) -> None:
        assert rpe.per_call_price({"limits": [_limit(0, 0.005, None)]}) == 0.005

    def test_zero_overage_returns_none(self) -> None:
        assert rpe.per_call_price({"limits": [_limit(500000, 0.0, "hard")]}) is None


class TestMeasureApiWarnings:
    """measure_api の hygiene 警告：消費者向け複数(current) / 無料オーファン購読者."""

    def test_conflicting_current_versions_flagged(self) -> None:
        info = {"name": "A", "visibility": "PUBLIC"}
        versions = [
            {**_paid_version(0.005), "plan_name": "PRO"},
            {**_paid_version(0.02), "plan_name": "PRO"},
        ]
        with patch.object(rpe, "rps") as mock:
            mock.fetch_api_info.return_value = info
            mock.TARGET_APIS = {}
            # fetch_versions_with_subs を直接置換（ネットワーク回避）
            with patch.object(rpe, "fetch_versions_with_subs", return_value=versions):
                r = rpe.measure_api({"e": "x"}, "k", {"api_id": "a"})
        assert any("共存" in w for w in r["warnings"])
        assert r["subscribers"]["paid"] == 0

    def test_current_free_only_warns_no_paid(self) -> None:
        info = {"name": "A", "visibility": "PUBLIC"}
        versions = [_free_version(subs=0, current=True)]
        with patch.object(rpe, "rps") as mock:
            mock.fetch_api_info.return_value = info
            with patch.object(rpe, "fetch_versions_with_subs", return_value=versions):
                r = rpe.measure_api({"e": "x"}, "k", {"api_id": "a"})
        assert any("収益 $0" in w for w in r["warnings"])
        assert r["subscribers"] == {"total": 0, "paid": 0, "free": 0}

    def test_free_orphan_with_subscriber_warns(self) -> None:
        info = {"name": "A", "visibility": "PUBLIC"}
        versions = [
            {**_paid_version(0.001), "plan_name": "BASIC"},
            _free_version(subs=1, current=False),
        ]
        with patch.object(rpe, "rps") as mock:
            mock.fetch_api_info.return_value = info
            with patch.object(rpe, "fetch_versions_with_subs", return_value=versions):
                r = rpe.measure_api({"e": "x"}, "k", {"api_id": "a"})
        assert any("無料オーファン版に既存購読者 1人" in w for w in r["warnings"])
        assert r["subscribers"] == {"total": 0, "paid": 0, "free": 0}


class TestAttachRapidapiPaidEffect:
    """kensho_revenue_collect.attach_rapidapi_paid_effect_keys: state からの日次添付."""

    def _state(self, date: str) -> dict[str, Any]:
        return {
            "points": {
                date: {
                    "point": "measured",
                    "point_date": date,
                    "measured_at": "2026-09-05T00:00:00+09:00",
                    "per_api": {
                        "japan-camera": {
                            "visibility": "PUBLIC",
                            "subscribers": {"total": 1, "paid": 0, "free": 1},
                            "warnings": ["BASIC: ACTIVE 2版が共存"],
                            "paid_plan_active": True,
                            "tier_effective_prices": {"BASIC": 0.001, "PRO": 0.005, "ULTRA": 0.01},
                        }
                    },
                }
            }
        }

    def _call(self, tmp_path: Any, date: str) -> dict[str, Any]:
        import kensho_revenue_collect as _krc

        _krc.RAPIDAPI_PAID_EFFECT_STATE = str(tmp_path / "rpe_state.json")
        (tmp_path / "rpe_state.json").write_text(json.dumps(self._state(date)), encoding="utf-8")
        return _krc.attach_rapidapi_paid_effect_keys({})

    def test_attaches_today_point(self, tmp_path: Any) -> None:
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        entry = self._call(tmp_path, today)
        eff = entry.get("rapidapi_paid_effect")
        assert eff is not None
        assert eff["point_date"] == today
        cam = eff["apis"]["japan-camera"]
        assert cam["subscribers"] == {"total": 1, "paid": 0, "free": 1}
        assert cam["paid_plan_active"] is True

    def test_falls_back_to_latest_point(self, tmp_path: Any) -> None:
        entry = self._call(tmp_path, "2026-09-01")
        eff = entry.get("rapidapi_paid_effect")
        assert eff is not None
        assert "当日point未取得" in eff.get("note", "")
        assert eff["apis"]["japan-camera"]["paid_plan_active"] is True

    def test_missing_state_returns_unchanged(self, tmp_path: Any) -> None:
        import kensho_revenue_collect as _krc

        _krc.RAPIDAPI_PAID_EFFECT_STATE = str(tmp_path / "nonexistent.json")
        entry: dict[str, Any] = {"x": 1}
        assert _krc.attach_rapidapi_paid_effect_keys(entry) == {"x": 1}
