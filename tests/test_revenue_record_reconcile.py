"""Tests for scripts/revenue_record_reconcile.py — 収益記録とライブstateの乖離 検出/修復

背景（2026-09-25 実測 / t_3dbc1fbe）:
  日次収集は7:05の1回だけ。Cookie失効で login_ok=false の当日entryが書かれた後、
  同日中に Cookie が復旧して収集が成功しても当日entryは失効のまま残る。
  実測: entry login_ok=false(07:11) / ライブ data/gumroad_state.json login_ok=true(13:19)。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import kensho_revenue_collect as krc
import revenue_record_reconcile as rrr

DATE = "2026-09-25"


def _state(login_ok: bool, collected_at: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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
        "collected_at": collected_at,
        "last_success_at": collected_at,
        "dashboard_url": "https://gumroad.com/dashboard",
        "login_ok": login_ok,
        "sales_page_ok": login_ok,
    }
    base.update(extra)
    return base


def _entry(
    gumroad: dict[str, Any],
    collectors: dict[str, Any],
    warnings: list[str] | None = None,
    date: str = DATE,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "date": date,
        "collected_at": f"{date}T07:11:01.524558",
        "apify": {"actors_total": 25},
        "gumroad": gumroad,
        "collectors": collectors,
        "warnings": warnings if warnings is not None else [],
    }
    return entry


def _write(tmp_path: Path, entry: dict[str, Any], state: dict[str, Any]) -> tuple[Path, Path]:
    daily = tmp_path / "revenue-daily.json"
    state_path = tmp_path / "gumroad_state.json"
    daily.write_text(json.dumps([{"date": "2026-09-24", "gumroad": {"login_ok": False}}] + [entry]), encoding="utf-8")
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return daily, state_path


def _expired_entry() -> dict[str, Any]:
    """本番 2026-09-25 07:11 entry の実shape（失効 + collectors自己矛盾）。"""
    gum = _state(False, f"{DATE}T07:07:35.390")
    return _entry(
        gum,
        {"apify_ok": True, "rapidapi_ok": True, "gumroad_ok": True, "gumroad_login_ok": False},
        warnings=["Gumroadログインセッション失効（Cookie再エクスポートが必要）"],
    )


def test_divergence_detected_and_applied(tmp_path: Path) -> None:
    """失効記録 ↔ 復旧したライブstate の乖離を検出し、再導出で修復する。"""
    daily, state_path = _write(tmp_path, _expired_entry(), _state(True, f"{DATE}T13:19:41"))
    det = rrr.detect(str(daily), str(state_path))
    assert det["applicable"] is True
    assert det["diverged"] is True
    assert det["collectors_mismatch"] is True
    assert {d["key"] for d in det["differences"]} >= {"login_ok", "last_success_at", "sales_page_ok"}

    res = rrr.apply(str(daily), str(state_path))
    assert res["applied"] is True

    saved = json.loads(daily.read_text(encoding="utf-8"))
    today = saved[-1]
    assert today["gumroad"]["login_ok"] is True
    assert today["gumroad"]["last_success_at"] == f"{DATE}T13:19:41"
    assert today["collectors"]["gumroad_ok"] is True
    assert today["collectors"]["gumroad_login_ok"] is True
    assert today["warnings"] == []  # 失効warningは復旧時に除去
    rec = today["gumroad_reconciled"]
    assert rec["login_ok_before"] is False and rec["login_ok_after"] is True
    assert "login_ok" in rec["changed_keys"]
    assert rec["removed_stale_warnings"] == ["Gumroadログインセッション失効（Cookie再エクスポートが必要）"]
    # 過去日entryは不変
    assert saved[0] == {"date": "2026-09-24", "gumroad": {"login_ok": False}}
    # 再検出はクリーン
    assert rrr.detect(str(daily), str(state_path))["diverged"] is False


def test_no_divergence_when_record_matches_state(tmp_path: Path) -> None:
    """記録とライブstateが一致していれば何もしない（冪等）。"""
    state = _state(True, f"{DATE}T13:19:41")
    daily, state_path = _write(tmp_path, _entry(state, {"gumroad_ok": True, "gumroad_login_ok": True}), state)
    before = daily.read_bytes()
    det = rrr.detect(str(daily), str(state_path))
    assert det["diverged"] is False
    res = rrr.apply(str(daily), str(state_path))
    assert res["applied"] is False
    assert daily.read_bytes() == before


def test_collectors_mismatch_alone_is_divergence(tmp_path: Path) -> None:
    """フィールドは一致していても collectors.gumroad_ok が規則と食い違えば乖離。"""
    state = _state(True, f"{DATE}T13:19:41")
    daily, state_path = _write(tmp_path, _entry(dict(state), {"gumroad_ok": False, "gumroad_login_ok": True}), state)
    det = rrr.detect(str(daily), str(state_path))
    assert det["differences"] == []
    assert det["collectors_mismatch"] is True
    assert det["diverged"] is True
    assert rrr.apply(str(daily), str(state_path))["applied"] is True
    assert json.loads(daily.read_text(encoding="utf-8"))[-1]["collectors"]["gumroad_ok"] is True


def test_past_entry_not_touched(tmp_path: Path) -> None:
    """entry日付とstate日付が違う（過去日）なら対象外＝不変。"""
    daily = tmp_path / "revenue-daily.json"
    state_path = tmp_path / "gumroad_state.json"
    daily.write_text(
        json.dumps([_entry(_state(False, "2026-09-24T07:07:35"), {"gumroad_ok": False}, date="2026-09-24")]),
        encoding="utf-8",
    )
    state_path.write_text(json.dumps(_state(True, f"{DATE}T13:19:41")), encoding="utf-8")
    before = daily.read_bytes()
    det = rrr.detect(str(daily), str(state_path))
    assert det["applicable"] is False
    assert det["diverged"] is False
    assert "日付不一致" in det["reason"]
    assert rrr.apply(str(daily), str(state_path))["applied"] is False
    assert daily.read_bytes() == before


def test_state_older_than_entry_skips(tmp_path: Path) -> None:
    """ライブstateがentryより古ければ再導出しない（新しい方を正とする）。"""
    daily, state_path = _write(tmp_path, _expired_entry(), _state(True, f"{DATE}T06:00:00"))
    before = daily.read_bytes()
    det = rrr.detect(str(daily), str(state_path))
    assert det["applicable"] is False
    assert "ライブstateの方が古い" in det["reason"]
    assert daily.read_bytes() == before


def test_login_fail_both_keeps_warning(tmp_path: Path) -> None:
    """双方が失効なら乖離なし＝warningを消さない（失効の握り潰し防止）。"""
    state = _state(False, f"{DATE}T07:07:35.390")
    entry = _entry(
        dict(state),
        {"gumroad_ok": False, "gumroad_login_ok": False},
        warnings=["Gumroadログインセッション失効（Cookie再エクスポートが必要）"],
    )
    daily, state_path = _write(tmp_path, entry, state)
    det = rrr.detect(str(daily), str(state_path))
    assert det["diverged"] is False
    assert rrr.apply(str(daily), str(state_path))["applied"] is False
    saved = json.loads(daily.read_text(encoding="utf-8"))
    assert saved[-1]["warnings"] == ["Gumroadログインセッション失効（Cookie再エクスポートが必要）"]


def test_mirror_keys_shared_with_collector(tmp_path: Path, monkeypatch: Any) -> None:
    """ミラー定義が単一ソースであること: 本番 collect_gumroad が mirror keys をそのまま写す。"""
    state = _state(True, f"{DATE}T13:19:41")
    sp = tmp_path / "gumroad_state.json"
    sp.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(krc, "GUMROAD_STATE", str(sp))
    monkeypatch.setattr(krc, "GUMROAD_BUNDLE", str(tmp_path / "missing_bundle.json"))
    got = krc.collect_gumroad()
    expected = {k: state[k] for k in krc.GUMROAD_STATE_MIRROR_KEYS if k in state}
    assert expected
    for k, v in expected.items():
        assert got[k] == v
    # 定義外のstateキーは写さない（currency/dashboard_url等）
    assert "currency" not in got and "dashboard_url" not in got
    assert got["state_exists"] is True


def test_cli_exit_codes(tmp_path: Path) -> None:
    """CLI: 乖離あり=exit1 / --apply後=exit0、マーカーがgrep可能。"""
    daily, state_path = _write(tmp_path, _expired_entry(), _state(True, f"{DATE}T13:19:41"))
    script = Path(__file__).parent.parent / "scripts" / "revenue_record_reconcile.py"
    chk = subprocess.run(
        [sys.executable, str(script), "--daily", str(daily), "--state", str(state_path)],
        capture_output=True, text=True,
    )
    assert chk.returncode == 1, chk.stdout + chk.stderr
    assert rrr.MARK_DIVERGED in chk.stdout
    assert "login_ok" in chk.stdout

    app = subprocess.run(
        [sys.executable, str(script), "--daily", str(daily), "--state", str(state_path), "--apply"],
        capture_output=True, text=True,
    )
    assert app.returncode == 0, app.stdout + app.stderr
    assert rrr.MARK_APPLIED in app.stdout

    again = subprocess.run(
        [sys.executable, str(script), "--daily", str(daily), "--state", str(state_path), "--json"],
        capture_output=True, text=True,
    )
    assert again.returncode == 0
    payload = json.loads(again.stdout)
    assert payload["diverged"] is False and payload["applicable"] is True
