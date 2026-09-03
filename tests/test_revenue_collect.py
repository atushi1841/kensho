"""
Tests for scripts/kensho_revenue_collect.py — actors_ppe=0 異常検出・自動再収集
(t_fc85c305: 9/3 00:20 異常の再発防止)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import kensho_revenue_collect as krc


def _make_normal_apify(n_ppe: int = 5, n_free: int = 0) -> dict[str, Any]:
    """正常なApify収集結果を生成するヘルパー。"""
    details: list[dict[str, Any]] = []
    for i in range(n_ppe):
        details.append({
            "name": f"japan-actor-{i}",
            "actual_name": f"japan-actor-{i}",
            "billing": "ppe",
            "price": 0.002,
            "is_public": True,
            "users": 0,
            "u30d": 0,
            "runs": 0,
        })
    for i in range(n_free):
        details.append({
            "name": f"japan-free-{i}",
            "actual_name": f"japan-free-{i}",
            "billing": "free",
            "price": None,
            "is_public": True,
            "users": 0,
            "u30d": 0,
            "runs": 0,
        })
    return {
        "source": "apify",
        "actors_total": n_ppe + n_free,
        "actors_public": n_ppe + n_free,
        "actors_ppe": n_ppe,
        "actors_free": n_free,
        "total_users_30d": 0,
        "total_runs": 0,
        "details": details,
    }


def _make_anomaly_apify() -> dict[str, Any]:
    """9/3 00:20 異常を再現するApify収集結果（actors_ppe=0, price付き詳細0件）。"""
    return {
        "source": "apify",
        "actors_total": 25,
        "actors_public": 25,
        "actors_ppe": 0,
        "actors_free": 0,
        "total_users_30d": 0,
        "total_runs": 0,
        "details": [
            {"name": f"japan-actor-{i}", "actual_name": f"japan-actor-{i}",
             "billing": "ppe", "price": None, "is_public": True,
             "users": 0, "u30d": 0, "runs": 0}
            for i in range(25)
        ],
    }


class TestIsPpeZeroAnomaly:
    """_is_ppe_zero_anomaly: 9/3 00:20 actors_ppe=0 異常の検出"""

    def test_normal_ppe5_is_not_anomaly(self) -> None:
        """正常値（PPE 5件 / price付き）→ 異常ではない"""
        assert krc._is_ppe_zero_anomaly(_make_normal_apify(n_ppe=5, n_free=0)) is False

    def test_normal_ppe0_free5_is_not_anomaly(self) -> None:
        """PPE 0でも free 5件で price=None は妥当（無料設定）→ 異常ではない"""
        result = _make_normal_apify(n_ppe=0, n_free=5)
        assert krc._is_ppe_zero_anomaly(result) is False

    def test_actors_total_zero_is_not_anomaly(self) -> None:
        """アクターが0件 → そもそも集計対象外"""
        empty = _make_normal_apify(n_ppe=0, n_free=0)
        empty["actors_total"] = 0
        empty["details"] = []
        assert krc._is_ppe_zero_anomaly(empty) is False

    def test_anomaly_ppe_zero_no_priced_detail(self) -> None:
        """9/3 00:20 の異常ケース: Total=25 / PPE=0 / price付き詳細0件 → 異常検出"""
        assert krc._is_ppe_zero_anomaly(_make_anomaly_apify()) is True

    def test_error_result_is_not_anomaly(self) -> None:
        """errorキーあり → 異常検出スキップ（既存のerror処理に任せる）"""
        result = _make_anomaly_apify()
        result["error"] = "Apify stats file not found"
        assert krc._is_ppe_zero_anomaly(result) is False


class TestRetryApifyCollect:
    """_retry_apify_collect: 自動再収集で異常復旧"""

    def test_retry_recovers_to_normal(self) -> None:
        """初回異常→再収集で正常値取得 → 正常結果を返す"""
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with patch.object(krc, "collect_apify", return_value=normal), \
             patch("kensho_revenue_collect.time.sleep"):
            result = krc._retry_apify_collect()
        assert result["actors_ppe"] == 5
        assert krc._is_ppe_zero_anomaly(result) is False

    def test_retry_returns_best_when_all_anomalous(self) -> None:
        """全試行で異常継続 → price付き詳細を持つ最良の結果を返す"""
        with patch.object(krc, "collect_apify", return_value=_make_anomaly_apify()), \
             patch("kensho_revenue_collect.time.sleep"):
            result = krc._retry_apify_collect()
        # 全部同じ異常値なので最後の試行値が返る
        assert result["actors_ppe"] == 0

    def test_retry_stops_at_max_attempts_when_anomalous(self) -> None:
        """異常継続時 → MAX_APIFY_RETRIES 回（2回）試行して終わる"""
        with patch.object(krc, "collect_apify", return_value=_make_anomaly_apify()) as mock, \
             patch("kensho_revenue_collect.time.sleep"):
            krc._retry_apify_collect()
        assert mock.call_count == krc.MAX_APIFY_RETRIES

    def test_retry_exits_early_when_recovered(self) -> None:
        """1回目で正常値取得 → 2回目は呼ばない"""
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with patch.object(krc, "collect_apify", return_value=normal) as mock, \
             patch("kensho_revenue_collect.time.sleep"):
            krc._retry_apify_collect()
        assert mock.call_count == 1


def _empty_rapidapi() -> dict[str, Any]:
    return {
        "source": "rapidapi",
        "apis_total": 0,
        "apis_public": 0,
        "apis_private": 0,
        "apis_freemium": 0,
        "details": [],
    }


def _empty_gumroad() -> dict[str, Any]:
    return {
        "source": "gumroad",
        "products": 0,
        "details": [],
        "state_exists": False,
    }


class TestToWindowsPath:
    """_to_windows_path: WSLパス→Windowsパス変換（node.exe実行用）"""

    def test_mnt_path(self) -> None:
        assert krc._to_windows_path("/mnt/d/Project2/kensho/scripts/x.js") == "D:\\Project2\\kensho\\scripts\\x.js"

    def test_windows_path_passthrough(self) -> None:
        assert krc._to_windows_path("D:\\already\\win.js") == "D:\\already\\win.js"

    def test_root_path(self) -> None:
        assert krc._to_windows_path("/tmp/x.js") == "/tmp/x.js"


class TestCollectGumroadState:
    """collect_gumroad: gumroad_state.json の新フィールド（CDP収集）読み取り"""

    def _write_state(self, tmp_path: Any, **overrides: Any) -> None:
        state = {
            "state_exists": True,
            "sales": 0,
            "revenue": 0,
            "total_sales": 0,
            "total_revenue": 0,
            "balance_usd": 0,
            "last_7_days_usd": 0,
            "last_28_days_usd": 0,
            "total_earnings_usd": 0,
            "currency": "USD",
            "login_ok": True,
            "collected_at": "2026-09-02T23:36:57.990Z",
        }
        state.update(overrides)
        p = tmp_path / "gumroad_state.json"
        p.write_text(json.dumps(state), encoding="utf-8")
        import kensho_revenue_collect as _krc
        _krc.GUMROAD_STATE = str(p)
        _krc.GUMROAD_BUNDLE = str(tmp_path / "bundle_info_missing.json")

    def test_reads_cdp_fields(self, tmp_path: Any) -> None:
        self._write_state(tmp_path, total_earnings_usd=12.34, login_ok=True)
        result = krc.collect_gumroad()
        assert result["state_exists"] is True
        assert result["total_earnings_usd"] == 12.34
        assert result["login_ok"] is True
        assert result["balance_usd"] == 0
        assert result["collected_at"].startswith("2026-09-02")

    def test_reads_zero_earnings(self, tmp_path: Any) -> None:
        self._write_state(tmp_path, total_earnings_usd=0, login_ok=True)
        result = krc.collect_gumroad()
        assert result["state_exists"] is True
        assert result["total_earnings_usd"] == 0

    def test_missing_state_is_false(self, tmp_path: Any) -> None:
        import kensho_revenue_collect as _krc
        _krc.GUMROAD_STATE = str(tmp_path / "nonexistent.json")
        _krc.GUMROAD_BUNDLE = str(tmp_path / "bundle_info_missing.json")
        result = krc.collect_gumroad()
        assert result["state_exists"] is False


class TestBuildRevenueSummaryGumroad:
    """build_revenue_summary: Gumroad売上の反映（t_83d9144f）"""

    def _summary(self, gumroad: dict[str, Any]) -> dict[str, Any]:
        apify = _make_normal_apify(n_ppe=5, n_free=0)
        return krc.build_revenue_summary(apify, _empty_rapidapi(), gumroad)

    def test_state_false_warns_unfetched(self) -> None:
        entry = self._summary(_empty_gumroad())
        assert any("Gumroad売上データ未取得" in w for w in entry["warnings"])
        assert entry["revenue_estimate"]["gumroad_monthly"] == 0

    def test_zero_earnings_warns_zero(self) -> None:
        gum = {**_empty_gumroad(), "state_exists": True, "total_earnings_usd": 0, "login_ok": True}
        entry = self._summary(gum)
        assert any("Gumroad売上ゼロ継続" in w for w in entry["warnings"])
        assert entry["revenue_estimate"]["gumroad_monthly"] == 0

    def test_login_fail_warns_cookie(self) -> None:
        gum = {**_empty_gumroad(), "state_exists": True, "total_earnings_usd": 0, "login_ok": False}
        entry = self._summary(gum)
        assert any("Cookie再エクスポート" in w for w in entry["warnings"])

    def test_positive_earnings_opportunity(self) -> None:
        gum = {**_empty_gumroad(), "state_exists": True, "total_earnings_usd": 25.5, "login_ok": True}
        entry = self._summary(gum)
        assert any("Gumroad売上" in o for o in entry["opportunities"])
        assert entry["revenue_estimate"]["gumroad_monthly"] == 25.5
        assert entry["revenue_estimate"]["total_monthly"] == 25.5



class TestMainIntegration:
    """main(): 異常検出→再収集→復旧の全体フロー"""

    def test_main_no_retry_when_normal(self) -> None:
        """正常値 → 再収集ループは走らない"""
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with patch.object(krc, "collect_apify", return_value=normal) as mock_collect, \
             patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()), \
             patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()), \
             patch.object(krc, "append_to_file") as mock_append, \
             patch("kensho_revenue_collect.time.sleep"):
            krc.main()
        # 1回だけ呼ばれる（再収集なし）
        assert mock_collect.call_count == 1
        entry = mock_append.call_args[0][0]
        assert "anomaly_ppe_zero" not in entry["apify"]

    def test_main_retries_and_recovers(self) -> None:
        """初回異常→再収集で復旧 → anomaly フラグは付かない"""
        anomaly = _make_anomaly_apify()
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with patch.object(krc, "collect_apify", side_effect=[anomaly, normal]) as mock_collect, \
             patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()), \
             patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()), \
             patch.object(krc, "append_to_file") as mock_append, \
             patch("kensho_revenue_collect.time.sleep"):
            krc.main()
        # 初回 + 再収集1回 = 2回
        assert mock_collect.call_count == 2
        entry = mock_append.call_args[0][0]
        assert "anomaly_ppe_zero" not in entry["apify"]
        assert entry["apify"]["actors_ppe"] == 5

    def test_main_flags_anomaly_when_persists(self) -> None:
        """全試行で異常継続 → anomaly_ppe_zero フラグ付き保存"""
        anomaly = _make_anomaly_apify()
        with patch.object(krc, "collect_apify", return_value=anomaly) as mock_collect, \
             patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()), \
             patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()), \
             patch.object(krc, "append_to_file") as mock_append, \
             patch("kensho_revenue_collect.time.sleep"):
            krc.main()
        # 初回 + 再収集2回 = 3回
        assert mock_collect.call_count == krc.MAX_APIFY_RETRIES + 1
        entry = mock_append.call_args[0][0]
        assert entry["apify"].get("anomaly_ppe_zero") is True
        assert "anomaly_detected_at" in entry["apify"]
