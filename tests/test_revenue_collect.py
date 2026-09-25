"""
Tests for scripts/kensho_revenue_collect.py — actors_ppe=0 異常検出・自動再収集
(t_fc85c305: 9/3 00:20 異常の再発防止)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

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
            {
                "name": f"japan-actor-{i}",
                "actual_name": f"japan-actor-{i}",
                "billing": "ppe",
                "price": None,
                "is_public": True,
                "users": 0,
                "u30d": 0,
                "runs": 0,
            }
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
        with patch.object(krc, "collect_apify", return_value=normal), patch("kensho_revenue_collect.time.sleep"):
            result = krc._retry_apify_collect()
        assert result["actors_ppe"] == 5
        assert krc._is_ppe_zero_anomaly(result) is False

    def test_retry_returns_best_when_all_anomalous(self) -> None:
        """全試行で異常継続 → price付き詳細を持つ最良の結果を返す"""
        with (
            patch.object(krc, "collect_apify", return_value=_make_anomaly_apify()),
            patch("kensho_revenue_collect.time.sleep"),
        ):
            result = krc._retry_apify_collect()
        # 全部同じ異常値なので最後の試行値が返る
        assert result["actors_ppe"] == 0

    def test_retry_stops_at_max_attempts_when_anomalous(self) -> None:
        """異常継続時 → MAX_APIFY_RETRIES 回（2回）試行して終わる"""
        with (
            patch.object(krc, "collect_apify", return_value=_make_anomaly_apify()) as mock,
            patch("kensho_revenue_collect.time.sleep"),
        ):
            krc._retry_apify_collect()
        assert mock.call_count == krc.MAX_APIFY_RETRIES

    def test_retry_exits_early_when_recovered(self) -> None:
        """1回目で正常値取得 → 2回目は呼ばない"""
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with (
            patch.object(krc, "collect_apify", return_value=normal) as mock,
            patch("kensho_revenue_collect.time.sleep"),
        ):
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
        with (
            patch.object(krc, "collect_apify", return_value=normal) as mock_collect,
            patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()),
            patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()),
            patch.object(krc, "update_gumroad_state_via_cdp", return_value=False),
            patch.object(krc, "append_to_file") as mock_append,
            patch("kensho_revenue_collect.time.sleep"),
        ):
            krc.main()
        # 1回だけ呼ばれる（再収集なし）
        assert mock_collect.call_count == 1
        entry = mock_append.call_args[0][0]
        assert "anomaly_ppe_zero" not in entry["apify"]

    def test_main_retries_and_recovers(self) -> None:
        """初回異常→再収集で復旧 → anomaly フラグは付かない"""
        anomaly = _make_anomaly_apify()
        normal = _make_normal_apify(n_ppe=5, n_free=0)
        with (
            patch.object(krc, "collect_apify", side_effect=[anomaly, normal]) as mock_collect,
            patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()),
            patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()),
            patch.object(krc, "update_gumroad_state_via_cdp", return_value=False),
            patch.object(krc, "append_to_file") as mock_append,
            patch("kensho_revenue_collect.time.sleep"),
        ):
            krc.main()
        # 初回 + 再収集1回 = 2回
        assert mock_collect.call_count == 2
        entry = mock_append.call_args[0][0]
        assert "anomaly_ppe_zero" not in entry["apify"]
        assert entry["apify"]["actors_ppe"] == 5

    def test_main_flags_anomaly_when_persists(self) -> None:
        """全試行で異常継続 → anomaly_ppe_zero フラグ付き保存"""
        anomaly = _make_anomaly_apify()
        with (
            patch.object(krc, "collect_apify", return_value=anomaly) as mock_collect,
            patch.object(krc, "collect_rapidapi", return_value=_empty_rapidapi()),
            patch.object(krc, "collect_gumroad", return_value=_empty_gumroad()),
            patch.object(krc, "update_gumroad_state_via_cdp", return_value=False),
            patch.object(krc, "append_to_file") as mock_append,
            patch("kensho_revenue_collect.time.sleep"),
        ):
            krc.main()
        # 初回 + 再収集2回 = 3回
        assert mock_collect.call_count == krc.MAX_APIFY_RETRIES + 1
        entry = mock_append.call_args[0][0]
        assert entry["apify"].get("anomaly_ppe_zero") is True
        assert "anomaly_detected_at" in entry["apify"]


class TestFetchApifyPricing:
    """fetch_apify_pricing: 複数pricingInfos時の有効価格は最後のエントリ（t_c4343276 PPE値上げA/B）"""

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path: Any, monkeypatch: Any) -> None:
        """キャッシュ書込を実データDirへ漏らさない（v94）。

        加えて fetch_apify_pricing() 先頭の check_apify_health()（requests.get 2本消費）を
        neutral 化する。health が実ネットワーク/モックの side_effect 長に干渉しないよう
        status="ok" 固定で上書きする（v94 テストは requests.get を固定長の
        side_effect リストで渡すため、health が先に2本消費すると StopIteration になる）。
        """
        monkeypatch.setattr(krc, "PRICING_CACHE", str(tmp_path / "apify_pricing_cache.json"))
        monkeypatch.setattr(
            krc,
            "check_apify_health",
            lambda: {
                "status": "ok",
                "endpoint": "acts",
                "http_code": 200,
                "error": None,
                "recovered": False,
                "timestamp": "2026-09-18T00:00:00+00:00",
            },
        )

    def _fake_actor(self, pricing_infos: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "status_code": 200,
            "data": {"name": "japan-offmall-market-scraper", "isPublic": True, "pricingInfos": pricing_infos},
        }

    def _ppe_entry(self, price: float, created: str) -> dict[str, Any]:
        return {
            "pricingModel": "PAY_PER_EVENT",
            "pricingPerEvent": {
                "actorChargeEvents": {
                    "apify-actor-start": {"eventPriceUsd": 5e-05},
                    "apify-default-dataset-item": {"eventPriceUsd": price},
                }
            },
            "apifyMarginPercentage": 0.2,
            "createdAt": created,
            "startedAt": created,
        }

    def test_uses_last_entry_as_active_price(self) -> None:
        """PPE値上げで2エントリ化→最後のエントリ（$0.005/件）を有効単価として返す"""
        old = self._ppe_entry(0.002, "2026-08-10T10:23:09.925Z")
        new = self._ppe_entry(0.005, "2026-09-04T15:55:14.790Z")
        list_resp = FakeResponse({"data": {"items": [{"id": "zh4k", "name": "japan-offmall-market-scraper"}]}})
        actor_resp = FakeResponse(self._fake_actor([old, new]))
        with patch("requests.get", side_effect=[list_resp, actor_resp]):
            result = krc.fetch_apify_pricing()
        got = result.get("japan-offmall-market-scraper")
        assert got is not None
        assert got["price"] == 0.005  # 最後のエントリが有効
        assert got["pricing_model"] == "PAY_PER_EVENT"


class FakeResponse:
    def __init__(self, json_body: dict[str, Any]) -> None:
        self._json = json_body
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        pass


class TestGumroadCdpResilience:
    """CDP収集タイムアウト恒久対策（t_cfe11a7c / critic v60）。

    - CDPチェック・Chrome自動起動・起動待ちは node 側（Windows）が担う設計。
    - Python側は1回のsubprocessを GUMROAD_TOTAL_TIMEOUT(240s) で実行。
    - 成功時のみ last_success_at を永続化。
    - timeout-mark / fail-mark 文言で収集失敗をgrep検知可能。
    """

    class _FakeProc:
        def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    @pytest.fixture(autouse=True)
    def _fake_node_paths(self, tmp_path: Any, monkeypatch: Any) -> None:
        """CI（Linux）でも node.exe/js 存在ガードを通過させる（従来 /mnt/c 実在に暗黙依存）。"""
        node = tmp_path / "node.exe"
        node.write_text("")
        script = tmp_path / "gumroad_sales_collect.js"
        script.write_text("")
        monkeypatch.setattr(krc, "GUMROAD_NODE", str(node))
        monkeypatch.setattr(krc, "GUMROAD_SCRIPT", str(script))

    def test_collect_gumroad_reads_last_success_at(self, tmp_path: Any) -> None:
        import kensho_revenue_collect as _krc

        p = tmp_path / "gumroad_state.json"
        p.write_text(
            json.dumps({
                "state_exists": True,
                "collected_at": "2026-09-08T09:00:00",
                "last_success_at": "2026-09-08T09:00:00",
            }),
            encoding="utf-8",
        )
        _krc.GUMROAD_STATE = str(p)
        _krc.GUMROAD_BUNDLE = str(tmp_path / "bundle_missing.json")
        result = krc.collect_gumroad()
        assert result["last_success_at"] == "2026-09-08T09:00:00"
        assert result["collected_at"] == "2026-09-08T09:00:00"

    def test_persist_last_success_at_writes(self, tmp_path: Any) -> None:
        import kensho_revenue_collect as _krc

        p = tmp_path / "gumroad_state.json"
        p.write_text(json.dumps({"state_exists": True, "login_ok": True}), encoding="utf-8")
        _krc.GUMROAD_STATE = str(p)
        _krc._persist_last_success_at()
        with open(p, encoding="utf-8") as f:
            st = json.load(f)
        assert "last_success_at" in st

    def test_persist_last_success_at_noop_when_missing(self, tmp_path: Any) -> None:
        import kensho_revenue_collect as _krc

        _krc.GUMROAD_STATE = str(tmp_path / "nonexistent.json")
        _krc._persist_last_success_at()  # 例外を出さず素通り

    def test_persist_last_success_at_skips_on_login_fail(self, tmp_path: Any) -> None:
        """login_ok=False のとき last_success_at を更新しない（JS側の無条件書込を防御）。"""
        import kensho_revenue_collect as _krc

        p = tmp_path / "gumroad_state.json"
        p.write_text(
            json.dumps({
                "state_exists": True,
                "login_ok": False,
                "last_success_at": "2026-09-08T09:00:00",
            }),
            encoding="utf-8",
        )
        _krc.GUMROAD_STATE = str(p)
        _krc._persist_last_success_at()
        with open(p, encoding="utf-8") as f:
            st = json.load(f)
        assert st["last_success_at"] == "2026-09-08T09:00:00"  # 前回値を保持

    def test_update_runs_node_with_total_timeout(self) -> None:
        """cdp収集は1回のnode実行・タイムアウトは GUMROAD_TOTAL_TIMEOUT。成功時のみpersist。"""
        with (
            patch("kensho_revenue_collect.subprocess.run", return_value=self._FakeProc(returncode=0)) as mrun,
            patch.object(krc, "_persist_last_success_at") as mpersist,
        ):
            ok = krc.update_gumroad_state_via_cdp()
        assert ok is True
        mrun.assert_called_once()
        assert mrun.call_args.kwargs["timeout"] == krc.GUMROAD_TOTAL_TIMEOUT
        mpersist.assert_called_once()

    def test_update_skips_persist_on_nonzero(self) -> None:
        with (
            patch("kensho_revenue_collect.subprocess.run", return_value=self._FakeProc(returncode=1, stderr="boom")),
            patch.object(krc, "_persist_last_success_at") as mpersist,
        ):
            assert krc.update_gumroad_state_via_cdp() is False
        mpersist.assert_not_called()

    def test_update_fail_prints_fail_mark(self) -> None:
        with (
            patch("kensho_revenue_collect.subprocess.run", return_value=self._FakeProc(returncode=1, stderr="boom")),
            patch("builtins.print") as mprint,
        ):
            krc.update_gumroad_state_via_cdp()
        msgs = " ".join(str(a) for c in mprint.call_args_list for a in c.args)
        assert "fail-mark" in msgs

    def test_update_timeout_prints_timeout_mark(self) -> None:
        with (
            patch(
                "kensho_revenue_collect.subprocess.run",
                side_effect=subprocess.TimeoutExpired("node.exe", krc.GUMROAD_TOTAL_TIMEOUT),
            ),
            patch("builtins.print") as mprint,
        ):
            krc.update_gumroad_state_via_cdp()
        msgs = " ".join(str(a) for c in mprint.call_args_list for a in c.args)
        assert "timeout-mark" in msgs


# ── critic v94 (t_360dd497): Apify課金状態の二重障害（APIタイムアウト全放棄+フォールバック路径欠損）──


class TestRecordGumroadSales:
    """record_gumroad_sales: 提案A受入基準ファイル（data/gumroad_sales.log）追記"""

    def _write_state(self, tmp_path: Any, **overrides: Any) -> str:
        state = {
            "state_exists": True,
            "total_sales": 0,
            "total_earnings_usd": None,
            "balance_usd": None,
            "login_ok": True,
            "collected_at": "2026-09-16T10:00:00",
        }
        state.update(overrides)
        p = tmp_path / "gumroad_state.json"
        p.write_text(json.dumps(state), encoding="utf-8")
        return str(p)

    def test_no_sale_writes_nothing(self, tmp_path: Any) -> None:
        sf = self._write_state(tmp_path, total_sales=0, total_earnings_usd=None)
        lf = str(tmp_path / "gumroad_sales.log")
        assert krc.record_gumroad_sales(sf, lf) is False
        assert not os.path.exists(lf)

    def test_sale_writes_line(self, tmp_path: Any) -> None:
        sf = self._write_state(tmp_path, total_sales=2, total_earnings_usd=15.5)
        lf = str(tmp_path / "gumroad_sales.log")
        assert krc.record_gumroad_sales(sf, lf) is True
        content = Path(lf).read_text(encoding="utf-8")
        assert "total_sales=2" in content
        assert "earnings_usd=15.5" in content

    def test_earnings_alone_is_sale(self, tmp_path: Any) -> None:
        sf = self._write_state(tmp_path, total_sales=0, total_earnings_usd=1.0)
        lf = str(tmp_path / "gumroad_sales.log")
        assert krc.record_gumroad_sales(sf, lf) is True

    def test_dedupes_same_collected_at(self, tmp_path: Any) -> None:
        sf = self._write_state(tmp_path, total_sales=1, total_earnings_usd=5.0)
        lf = str(tmp_path / "gumroad_sales.log")
        assert krc.record_gumroad_sales(sf, lf) is True
        assert krc.record_gumroad_sales(sf, lf) is False  # 同一collected_at → 追記しない
        assert len(Path(lf).read_text(encoding="utf-8").splitlines()) == 1

    def test_is_invoked_in_main(self) -> None:
        """main() のGumroad収集直後に record_gumroad_sales が呼ばれる"""
        import inspect

        src = inspect.getsource(krc.main)
        gum_pos = src.index("gumroad = collect_gumroad()")
        assert src.index("record_gumroad_sales()", gum_pos) > gum_pos


class TestV94PpeFallbackPath:
    """項目1: APIFY_PPEパス欠損修正 — data/tmp実体を読めること"""

    def test_candidates_include_real_file(self) -> None:
        assert "/mnt/d/Project2/kensho/data/tmp/pay_per_event.json" in krc.APIFY_PPE_CANDIDATES

    def test_load_ppe_actors_reads_data_tmp_entity(self) -> None:
        """実ファイル（修正後の正パス）から5件のPPE単価が読める（従来は誤パスで{}）"""
        actors = krc.load_ppe_actors()
        assert len(actors) >= 5
        assert actors["japan-used-camera-market-scraper"] == 0.002

    def test_load_ppe_actors_tries_second_candidate(self, tmp_path: Any, monkeypatch: Any) -> None:
        first = tmp_path / "missing.json"
        second = tmp_path / "fallback.json"
        second.write_text(json.dumps({"actors_ppe": {"x": 0.01}}), encoding="utf-8")
        monkeypatch.setattr(krc, "APIFY_PPE_CANDIDATES", [str(first), str(second)])
        monkeypatch.setattr(krc, "APIFY_PPE", str(first))
        assert krc.load_ppe_actors() == {"x": 0.01}

    def test_load_ppe_actors_all_missing_is_empty(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr(krc, "APIFY_PPE_CANDIDATES", [str(tmp_path / "nope.json")])
        monkeypatch.setattr(krc, "APIFY_PPE", str(tmp_path / "nope.json"))
        assert krc.load_ppe_actors() == {}


class TestV94FetchPartialResilience:
    """項目2: 個別取得CONTINUE_ — 1本失敗でループ全放棄しない"""

    def _list_resp(self, n: int = 3) -> FakeResponse:
        return FakeResponse({
            "data": {
                "items": [
                    {"id": f"act{i}", "name": v}
                    for i, v in enumerate(sorted(set(krc.PORTFOLIO_TO_ACTUAL.values()))[:n])
                ]
            }
        })

    def _ppe_resp(self, price: float) -> FakeResponse:
        return FakeResponse({
            "data": {
                "name": "x",
                "isPublic": True,
                "pricingInfos": [
                    {
                        "pricingModel": "PAY_PER_EVENT",
                        "pricingPerEvent": {
                            "actorChargeEvents": {"apify-default-dataset-item": {"eventPriceUsd": price}}
                        },
                    }
                ],
            }
        })

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr(krc, "PRICING_CACHE", str(tmp_path / "cache.json"))
        # check_apify_health() を neutral 化（requests.get の side_effect 長に影響させない）
        monkeypatch.setattr(
            krc,
            "check_apify_health",
            lambda: {
                "status": "ok",
                "endpoint": "acts",
                "http_code": 200,
                "error": None,
                "recovered": False,
                "timestamp": "2026-09-18T00:00:00+00:00",
            },
        )

    def test_one_timeout_keeps_other_results(self) -> None:
        """1本目失敗（例外）→ 2本目成功 → 部分結果を返す（従来は全体{}）"""
        names = sorted(set(krc.PORTFOLIO_TO_ACTUAL.values()))
        responses = [self._list_resp(2), Exception("ConnectTimeout api.apify.com:443"), self._ppe_resp(0.002)]
        with patch("requests.get", side_effect=responses):
            result = krc.fetch_apify_pricing()
        assert names[1] in result
        assert names[0] not in result
        assert result[names[1]]["pricing_model"] == "PAY_PER_EVENT"

    def test_consecutive_failures_abort_loop(self) -> None:
        """連続3本失敗で打ち切る（requests.get呼出が無限に増えない）"""
        calls = {"n": 0}

        def _boom(*a: Any, **k: Any) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                return self._list_resp(25)
            raise Exception("ConnectTimeout")

        with patch("requests.get", side_effect=_boom):
            result = krc.fetch_apify_pricing()
        assert result == {}
        # list 1 + actor試行 4（3失敗で打ち切り、4本目は打ち切り判定で呼ばれない想定）
        assert calls["n"] <= 1 + 3 + 1

    def test_success_writes_cache(self, tmp_path: Any) -> None:
        """項目4: 取得成功時にキャッシュ書込"""
        cache = tmp_path / "cache.json"
        with patch("requests.get", side_effect=[self._list_resp(1), self._ppe_resp(0.002)]):
            result = krc.fetch_apify_pricing()
        assert result
        assert cache.exists()
        payload = json.loads(cache.read_text(encoding="utf-8"))
        assert "saved_at" in payload and payload["pricing"]

    def test_api_total_failure_uses_cache(self, tmp_path: Any) -> None:
        """項目4: list API失敗でも24h内キャッシュがあればそれを返す（{}→フォールバック空振り防止）"""
        cache = tmp_path / "cache.json"
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "pricing": {
                "japan-market-mcp": {"pricing_model": "PAY_PER_EVENT", "price": 5e-05, "is_public": True, "id": "abc"}
            },
        }
        cache.write_text(json.dumps(payload), encoding="utf-8")
        with patch("requests.get", side_effect=Exception("ConnectTimeout")):
            result = krc.fetch_apify_pricing()
        assert "japan-market-mcp" in result

    def test_stale_cache_ignored(self, tmp_path: Any) -> None:
        cache = tmp_path / "cache.json"
        stale = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
        cache.write_text(json.dumps({"saved_at": stale, "pricing": {"x": {}}}), encoding="utf-8")
        with patch("requests.get", side_effect=Exception("ConnectTimeout")):
            assert krc.fetch_apify_pricing() == {}


class TestApifyHealthGate:
    """check_apify_health() の結果が fetch_apify_pricing() を正しく分岐させる（commit 45f9349）。"""

    def _ok_actor(self) -> FakeResponse:
        return FakeResponse({
            "status_code": 200,
            "data": {
                "name": "japan-offmall-market-scraper",
                "isPublic": True,
                "pricingInfos": [
                    {
                        "pricingModel": "PAY_PER_EVENT",
                        "pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventPriceUsd": 0.005}}},
                    }
                ],
            },
        })

    def test_down_uses_cache(self, tmp_path: Any, monkeypatch: Any) -> None:
        """health=down → 24h内キャッシュへ早期フォールバック（requests.get は1本も呼ばれない）"""
        cache = tmp_path / "cache.json"
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "pricing": {
                "japan-market-mcp": {"pricing_model": "PAY_PER_EVENT", "price": 5e-05, "is_public": True, "id": "abc"}
            },
        }
        cache.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(krc, "PRICING_CACHE", str(cache))
        monkeypatch.setattr(
            krc,
            "check_apify_health",
            lambda: {
                "status": "down",
                "endpoint": "both",
                "http_code": 0,
                "error": "acts接続失敗: ConnectTimeout",
                "recovered": False,
                "timestamp": "2026-09-18T00:00:00+00:00",
            },
        )
        with patch("requests.get", side_effect=Exception("health down では requests を呼ばない")) as mget:
            result = krc.fetch_apify_pricing()
        assert "japan-market-mcp" in result
        mget.assert_not_called()

    def test_down_without_cache_returns_empty(self, tmp_path: Any, monkeypatch: Any) -> None:
        """health=down かつキャッシュ無し → {}（requests.get は呼ばれない）"""
        monkeypatch.setattr(krc, "PRICING_CACHE", str(tmp_path / "absent_cache.json"))
        monkeypatch.setattr(
            krc,
            "check_apify_health",
            lambda: {"status": "down", "endpoint": "both", "http_code": 0, "error": "不通"},
        )
        with patch("requests.get", side_effect=Exception("health down では requests を呼ばない")) as mget:
            assert krc.fetch_apify_pricing() == {}
        mget.assert_not_called()

    def test_degraded_continues_fetch(self, monkeypatch: Any) -> None:
        """health=degraded（補助エンドポイント不調）→ 本命fetchは継続し正常に価格を返す"""
        monkeypatch.setattr(
            krc,
            "check_apify_health",
            lambda: {
                "status": "degraded",
                "endpoint": "acts+users/me",
                "http_code": 403,
                "error": "users/me: HTTP 403",
                "recovered": False,
                "timestamp": "2026-09-18T00:00:00+00:00",
            },
        )
        list_resp = FakeResponse({"data": {"items": [{"id": "zh4k", "name": "japan-offmall-market-scraper"}]}})
        with patch("requests.get", side_effect=[list_resp, self._ok_actor()]):
            result = krc.fetch_apify_pricing()
        got = result.get("japan-offmall-market-scraper")
        assert got is not None
        assert got["pricing_model"] == "PAY_PER_EVENT"
        assert got["price"] == 0.005


class TestV94UnknownBilling:
    """項目3: API空+フォールバック空 → 「無料」でなく unknown、警告文変更、異常検知"""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr(krc, "APIFY_PPE_CANDIDATES", [str(tmp_path / "absent.json")])
        monkeypatch.setattr(krc, "APIFY_PPE", str(tmp_path / "absent.json"))

    def test_collect_apify_marks_unknown(self, tmp_path: Any, monkeypatch: Any) -> None:
        stats = tmp_path / "stats.json"
        stats.write_text(
            json.dumps([{"date": "2026-09-11", "japan-camera-market": {"users": 1, "u30d": 2, "runs": 3}}]),
            encoding="utf-8",
        )
        monkeypatch.setattr(krc, "APIFY_STATS", str(stats))
        with (
            patch.object(krc, "fetch_apify_pricing", return_value={}),
            patch.object(krc, "get_apify_token", return_value=""),
        ):
            result = krc.collect_apify()
        assert result["actors_unknown"] == 1
        assert result["actors_free"] == 0
        assert result["details"][0]["billing"] == "unknown"

    def test_warning_says_unknown_not_free(self) -> None:
        apify = _make_normal_apify(n_ppe=0, n_free=0)
        apify["actors_total"] = 25
        apify["actors_unknown"] = 25
        apify["details"] = []
        entry = krc.build_revenue_summary(apify, _empty_rapidapi(), _empty_gumroad())
        assert any("課金状態不明" in w for w in entry["warnings"])
        assert not any("無料設定" in w for w in entry["warnings"])

    def test_true_free_still_warns_free(self) -> None:
        """従来動作の維持: 全部free（unknown=0）なら従来通り「無料設定」警告"""
        apify = _make_normal_apify(n_ppe=0, n_free=25)
        entry = krc.build_revenue_summary(apify, _empty_rapidapi(), _empty_gumroad())
        assert any("無料設定" in w for w in entry["warnings"])

    def test_anomaly_detects_unknown_case(self) -> None:
        """検知ギャップ塞ぎ: ppe=0/free=25風→unknown化なら異常True（従来は素通り）"""
        result = _make_normal_apify(n_ppe=0, n_free=0)
        result["actors_total"] = 25
        result["actors_unknown"] = 25
        result["details"] = []
        assert krc._is_ppe_zero_anomaly(result) is True


# ── critic v140 (t_e3302129): RapidAPI read timeout→last-known-stateフォールバック ──


def _rap_nodes(n: int = 22) -> list[dict[str, Any]]:
    return [
        {
            "id": f"api_{i}",
            "name": f"api-{i}",
            "visibility": "PUBLIC" if i < n - 2 else "PRIVATE",
            "pricing": "FREEMIUM",
            "currentVersion": {"id": "v", "name": "1.0.0", "versionStatus": "active"},
        }
        for i in range(n)
    ]


class TestV140RapidapiFallback:
    """collect_rapidapi: リトライ＋last-known-stateフォールバック（0本虚偽報告防止）"""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path: Any, monkeypatch: Any) -> None:
        auth = tmp_path / "rapidapi_auth.json"
        auth.write_text(json.dumps({"csrf_token": "t", "entity_id": "e", "cookies": "a=1; b=2"}), encoding="utf-8")
        monkeypatch.setattr(krc, "RAPIDAPI_AUTH", str(auth))
        monkeypatch.setattr(krc, "RAPIDAPI_STATE", str(tmp_path / "revenue_rapidapi_state.json"))
        self.state_path = krc.RAPIDAPI_STATE

    def test_success_saves_state(self, monkeypatch: Any) -> None:
        """成功収集 → apis_total=22・stateファイルに apis_total=22 が保存される"""
        monkeypatch.setattr(krc, "_rapidapi_fetch_apis", lambda: _rap_nodes(22))
        result = krc.collect_rapidapi()
        assert "error" not in result
        assert result["apis_total"] == 22
        assert result["apis_public"] == 20 and result["apis_private"] == 2
        state = json.loads(Path(self.state_path).read_text(encoding="utf-8"))
        assert state["apis_total"] == 22 and state["saved_at"]

    def test_retry_recovers_from_timeout(self, monkeypatch: Any) -> None:
        """初回read timeout→リトライ1回で成功 → error無し・backoff 5秒待機"""
        calls = {"n": 0}

        def _flaky() -> list[dict[str, Any]]:
            calls["n"] += 1
            if calls["n"] == 1:
                raise Exception("Read timed out. (read timeout=15)")
            return _rap_nodes(22)

        monkeypatch.setattr(krc, "_rapidapi_fetch_apis", _flaky)
        with patch("kensho_revenue_collect.time.sleep") as msleep:
            result = krc.collect_rapidapi()
        assert calls["n"] == 2
        assert "error" not in result
        assert result["apis_total"] == 22
        msleep.assert_called_once_with(krc.RAPIDAPI_RETRY_BACKOFF)

    def test_total_failure_falls_back_to_state(self, monkeypatch: Any) -> None:
        """全試行失敗＋stateあり → last-known復元・error/fallback/last_known_* を記録"""
        state = {
            "saved_at": "2026-09-12T09:00:00",
            "apis_total": 22,
            "apis_public": 20,
            "apis_private": 2,
            "apis_freemium": 22,
            "details": _rap_nodes(22),
        }
        Path(self.state_path).write_text(json.dumps(state), encoding="utf-8")
        monkeypatch.setattr(krc, "_rapidapi_fetch_apis", lambda: (_ for _ in ()).throw(Exception("Read timed out")))
        with patch("kensho_revenue_collect.time.sleep"):
            result = krc.collect_rapidapi()
        assert "timed out" in result["error"]
        assert result["apis_total"] == 22  # 0本虚偽報告にならない
        assert result["fallback"] == "last_known_state"
        assert result["last_known_total"] == 22
        assert "timed out" in result["last_known_error"]

    def test_failure_without_state_stays_zero(self, monkeypatch: Any) -> None:
        """全試行失敗＋state無し → apis_total=0・fallbackフラグ無し（従来動作）"""
        monkeypatch.setattr(krc, "_rapidapi_fetch_apis", lambda: (_ for _ in ()).throw(Exception("Read timed out")))
        with patch("kensho_revenue_collect.time.sleep"):
            result = krc.collect_rapidapi()
        assert result["apis_total"] == 0
        assert "error" in result
        assert "fallback" not in result

    def test_missing_auth_early_returns(self, monkeypatch: Any) -> None:
        """authファイル無し → ネットワーク行かず即error（リトライもしない）"""
        monkeypatch.setattr(krc, "RAPIDAPI_AUTH", "/nonexistent/rapidapi_auth.json")

        def _boom() -> list[dict[str, Any]]:
            raise AssertionError("fetch must not run without auth")

        monkeypatch.setattr(krc, "_rapidapi_fetch_apis", _boom)
        result = krc.collect_rapidapi()
        assert result["error"] == "RapidAPI auth file not found"


class TestV140CollectorsTopLayer:
    """build_revenue_summary: collectors健全性＋フォールバック時の頂層last_known記録"""

    def test_collectors_ok_when_no_error(self) -> None:
        entry = krc.build_revenue_summary(_make_normal_apify(n_ppe=5), _empty_rapidapi(), _empty_gumroad())
        collectors = entry["collectors"]
        assert collectors["apify_ok"] is True
        assert collectors["rapidapi_ok"] is True
        assert collectors["gumroad_ok"] is False
        assert "last_known_total" not in entry
        # 2026-09-23: 収集ボリュームは実データ（収集ログ/collected.json）から自動計上される
        assert isinstance(collectors["collected_today"], int)
        assert isinstance(collectors["collected_total"], int)

    def test_collectors_include_volume_stats(self) -> None:
        """volume注入で決定的に検証（dashboardと共有する収集実績の値）。"""
        volume = {
            "collected_today": 478,
            "collected_total": 1191,
            "collected_today_runs": 14,
            "collected_today_source": "logs/collect_20260923_*.log",
        }
        entry = krc.build_revenue_summary(
            _make_normal_apify(n_ppe=5), _empty_rapidapi(), _empty_gumroad(), volume=volume
        )
        assert entry["collectors"]["collected_today"] == 478
        assert entry["collectors"]["collected_total"] == 1191
        assert entry["collectors"]["collected_today_runs"] == 14
        assert entry["collectors"]["collected_today_source"] == "logs/collect_20260923_*.log"

    def test_fallback_records_top_layer(self) -> None:
        rap = {
            **_empty_rapidapi(),
            "apis_total": 22,
            "apis_public": 20,
            "apis_private": 2,
            "apis_freemium": 22,
            "details": _rap_nodes(22),
            "error": "Read timed out. (read timeout=15)",
            "fallback": "last_known_state",
            "fallback_state_saved_at": "2026-09-12T09:00:00",
            "last_known_total": 22,
            "last_known_error": "Read timed out. (read timeout=15)",
        }
        entry = krc.build_revenue_summary(_make_normal_apify(n_ppe=5), rap, _empty_gumroad())
        assert entry["last_known_total"] == 22
        assert "timed out" in entry["last_known_error"]
        assert entry["collectors"]["rapidapi_ok"] is False
        assert entry["collectors"]["rapidapi_cache_fallback"] is True
        assert any("last-known-stateフォールバック" in w for w in entry["warnings"])
        # 非公開API机会検出はフォールバックdetailsでも機能する
        assert any("RapidAPI非公開API" in o for o in entry["opportunities"])


# ── t_fda64102 (2026-09-25): Apify pricing部分取得の誤free判定 / キャッシュ縮小 ──


def _ppe_entry(price: float = 0.005, aid: str = "x") -> dict[str, Any]:
    return {"pricing_model": "PAY_PER_EVENT", "price": price, "is_public": True, "id": aid}


class TestTfda64102PartialPricing:
    """API部分取得時に「無料」と断定しない / 部分保存でキャッシュを縮小させない。"""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr(krc, "APIFY_PPE_CANDIDATES", [str(tmp_path / "absent.json")])
        monkeypatch.setattr(krc, "APIFY_PPE", str(tmp_path / "absent.json"))
        monkeypatch.setattr(krc, "PRICING_CACHE", str(tmp_path / "apify_pricing_cache.json"))

    def _stats(self, tmp_path: Any, names: list[str], monkeypatch: Any) -> None:
        entry: dict[str, Any] = {"date": "2026-09-25"}
        for n in names:
            entry[n] = {"users": 1, "u30d": 2, "runs": 3}
        stats = tmp_path / "stats.json"
        stats.write_text(json.dumps([entry]), encoding="utf-8")
        monkeypatch.setattr(krc, "APIFY_STATS", str(stats))

    def test_partial_api_missing_actor_is_unknown_not_free(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """一部アクターの pricing が取れない場合、その分を free ではなく unknown にする。"""
        self._stats(tmp_path, ["japan-camera-market", "japan-watch-market"], monkeypatch)
        partial = {"japan-used-camera-market-scraper": _ppe_entry(0.005, "cam")}
        with (
            patch.object(krc, "fetch_apify_pricing", return_value=partial),
            patch.object(krc, "get_apify_token", return_value=""),
        ):
            result = krc.collect_apify()
        by_name = {d["name"]: d for d in result["details"]}
        assert by_name["japan-camera-market"]["billing"] == "ppe"
        assert by_name["japan-watch-market"]["billing"] == "unknown"
        assert result["actors_free"] == 0
        assert result["actors_unknown"] == 1

    def test_partial_api_missing_actor_uses_24h_cache(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """24h以内キャッシュに既知エントリがあれば、それを第2ソースとして ppe を維持する。"""
        self._stats(tmp_path, ["japan-camera-market", "japan-watch-market"], monkeypatch)
        Path(krc.PRICING_CACHE).write_text(
            json.dumps({
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "fetched": 1,
                "merged_from_cache": 0,
                "pricing": {"japan-watch-market-scraper": _ppe_entry(0.005, "wch")},
            }),
            encoding="utf-8",
        )
        partial = {"japan-used-camera-market-scraper": _ppe_entry(0.005, "cam")}
        with (
            patch.object(krc, "fetch_apify_pricing", return_value=partial),
            patch.object(krc, "get_apify_token", return_value=""),
        ):
            result = krc.collect_apify()
        by_name = {d["name"]: d for d in result["details"]}
        assert by_name["japan-watch-market"]["billing"] == "ppe"
        assert result["actors_free"] == 0
        assert result["actors_unknown"] == 0

    def test_save_pricing_cache_merges_within_ttl(self, tmp_path: Any, monkeypatch: Any) -> None:
        """部分保存（1件）でも24h以内の既存エントリを保持し、取得件数を記録する。"""
        cache = Path(krc.PRICING_CACHE)
        cache.write_text(
            json.dumps({
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "pricing": {"a": _ppe_entry(0.001, "a"), "b": _ppe_entry(0.002, "b")},
            }),
            encoding="utf-8",
        )
        krc._save_pricing_cache({"c": _ppe_entry(0.003, "c")})
        payload = json.loads(cache.read_text(encoding="utf-8"))
        assert sorted(payload["pricing"]) == ["a", "b", "c"]
        assert payload["fetched"] == 1
        assert payload["merged_from_cache"] == 2

    def test_save_pricing_cache_does_not_merge_stale(self, tmp_path: Any, monkeypatch: Any) -> None:
        """24h超のキャッシュは鮮度上限を守ってマージしない。"""
        cache = Path(krc.PRICING_CACHE)
        stale = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
        cache.write_text(
            json.dumps({"saved_at": stale, "pricing": {"a": _ppe_entry(0.001, "a")}}),
            encoding="utf-8",
        )
        krc._save_pricing_cache({"b": _ppe_entry(0.002, "b")})
        payload = json.loads(cache.read_text(encoding="utf-8"))
        assert sorted(payload["pricing"]) == ["b"]
        assert payload["merged_from_cache"] == 0
