"""Tests for kensho.core.self_heal — error classification, recovery, loop."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT = Path("/mnt/d/Project2/kensho")
_SYS_PATH_ALREADY = _PROJECT.as_posix() in sys.path
if not _SYS_PATH_ALREADY:
    sys.path.insert(0, _PROJECT.as_posix())

from kensho.core.self_heal import (  # noqa: E402
    ErrorKind,
    HealingEvent,
    HealingResult,
    RecoverySignal,
    SelfHealingLoop,
    capture_error_log,
    classify_error,
)


def _tmp_project(tmp_path: Path) -> Path:
    p = tmp_path / "kensho"
    p.mkdir()
    (p / "data").mkdir()
    (p / "logs").mkdir()
    cfg = {"general": {"project_dir": str(p)}, "self_healing": {}}
    (p / "config.yaml").write_text("general:\n  project_dir: " + str(p) + "\n")
    return p


def test_classify_error_network():
    info = classify_error(TimeoutError("connect timed out"))
    assert info.kind == ErrorKind.network


def test_classify_error_selector():
    info = classify_error(RuntimeError("selector not found"))
    assert info.kind == ErrorKind.selector


def test_classify_error_session():
    info = classify_error(RuntimeError("cookie expired 401"))
    assert info.kind == ErrorKind.session


def test_classify_error_rate_limit():
    info = classify_error(RuntimeError("HTTP 429"))
    assert info.kind == ErrorKind.rate_limit


def test_classify_error_runtime():
    info = classify_error(ValueError("something unexpected"))
    assert info.kind == ErrorKind.runtime


def test_capture_error_log_no_logs(tmp_path):
    p = _tmp_project(tmp_path)
    out = capture_error_log(str(p), limit=10)
    assert isinstance(out, str)


def test_capture_error_log_includes_tail(tmp_path):
    p = _tmp_project(tmp_path)
    (p / "logs" / "auto_test.log").write_text("a\nb\n" + "X" * 20 + "\n", encoding="utf-8")
    out = capture_error_log(str(p), limit=10)
    assert "X" * 20 in out


def test_sanitize_clears_api_key(tmp_path):
    from kensho.core.self_heal import _sanitize
    tainted = "Authorization: Bearer secret123\nCookie: session=abc"
    out = _sanitize(tainted)
    assert "secret123" not in out
    assert "session=abc" not in out


def test_healing_result_value_or_raise_returns_value():
    r = HealingResult(ok=True, value=(1, 0, 5))
    assert r.value_or_raise() == (1, 0, 5)


def test_healing_result_value_or_raise_raises():
    r = HealingResult(ok=False, error="boom", attempts=3)
    with pytest.raises(RuntimeError, match="boom"):
        r.value_or_raise()


def test_loop_success_first_attempt(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(cfg={"general": {"project_dir": str(p)}}, pipeline="test")

    def op():
        return (2, 0, 10)

    r = loop.run(op, validator=lambda v, **kw: None)
    assert r.ok is True
    assert r.value == (2, 0, 10)
    assert r.recovered is False


def test_loop_retries_on_exception_then_succeeds(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(cfg={"general": {"project_dir": str(p)}, "self_healing": {"max_attempts": 3}}, pipeline="test")
    calls = [0]

    def op():
        calls[0] += 1
        if calls[0] < 3:
            raise ConnectionError("connect timeout")
        return (1, 0, 3)

    r = loop.run(op)
    assert r.ok is True
    assert r.recovered is True
    assert calls[0] == 3


def test_loop_exhausts_and_fails(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={"general": {"project_dir": str(p)}, "self_healing": {"max_attempts": 2}}, pipeline="test",
    )

    def op():
        raise ConnectionError("connect timeout")

    r = loop.run(op)
    assert r.ok is False
    assert r.attempts == 2
    assert "connect timeout" in r.error


def test_validator_recovers_empty_collection(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={
            "general": {"project_dir": str(p)},
            "self_healing": {"max_attempts": 2, "retry_empty_collection": True},
        },
        pipeline="collection",
    )
    calls = [0]

    def op():
        calls[0] += 1
        if calls[0] < 2:
            return (0, 0, 0)
        return (1, 0, 3)

    from kensho.core.self_heal import RecoverySignal

    def validator(value, *, exception=None, context=None):
        if value == (0, 0, 0) and context and context.get("retry_empty_collection"):
            return RecoverySignal(kind="empty_collection", recoverable=True, severity="warn", message="empty")
        return None

    r = loop.run(op, validator=validator, context={"retry_empty_collection": True})
    assert r.ok is True
    assert calls[0] == 2


def test_validator_rejects_invalid_return(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={
            "general": {"project_dir": str(p)},
            "self_healing": {"max_attempts": 2},
        },
        pipeline="test",
    )

    def op():
        return "not-a-tuple"

    from kensho.core.self_heal import RecoverySignal

    def validator(value, *, exception=None, context=None):
        if not isinstance(value, tuple) or len(value) != 3:
            return RecoverySignal(kind="invalid_return", recoverable=True, severity="error", message="invalid")
        return None

    r = loop.run(op, validator=validator)
    assert r.ok is False
    assert "invalid" in r.error


def test_ceiling_blocks_after_consecutive_failures(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={
            "general": {"project_dir": str(p)},
            "self_healing": {
                "max_attempts": 2,
                "failure_ceiling_consecutive": 1,
                "failure_ceiling_cooldown_minutes": 60,
            },
        },
        pipeline="test",
    )

    def op():
        raise RuntimeError("boom")

    loop.run(op)
    assert loop.is_blocked("test") is True
    loop.reset("test")
    assert loop.is_blocked("test") is False


def test_ai_consult_skipped_without_api_key(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={
            "general": {"project_dir": str(p)},
            "self_healing": {"max_attempts": 3, "ai_assisted": True, "min_delay_sec": 0, "max_delay_sec": 0},
        },
        pipeline="test",
    )
    with patch("kensho.core.self_heal._ai_consult") as mock_ai:
        mock_ai.return_value = ("retry", "from mock")

        def op():
            raise ConnectionError("connect timeout")

        r = loop.run(op)
        assert r.ok is False
        assert any(e.action == "ai_consult" for e in loop.events)


def test_state_file_persists_on_failure(tmp_path):
    p = _tmp_project(tmp_path)
    loop = SelfHealingLoop(
        cfg={
            "general": {"project_dir": str(p)},
            "self_healing": {"max_attempts": 2, "failure_ceiling_consecutive": 1, "failure_ceiling_cooldown_minutes": 60},
        },
        pipeline="test",
    )

    def op():
        raise RuntimeError("boom")

    loop.run(op)
    state_path = Path(p) / "data" / "self_heal_state.json"
    data = json.loads(state_path.read_text())
    assert data["ceilings"]["test"]["count"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
# t_8946706e (2026-09-24): 恒久修正の回帰テスト
#   P0 ceiling のアカウント粒度化 / セッション失効垢への盲目的リトライ停止
#   P1 F5 毎時cronでも ceiling が発動する / F1 回復イベントの構造化ログ
#   P2 F2 ai_assisted=false で ai_consult をスキップ / F3 session系は1回で停止
#   P2 F4 max_attempts=3 のまま後段アクション（transport_fallback/scope_reduction）へ到達
#   P2 F6 config 値が呼出側ハードコードで上書きされない
# ══════════════════════════════════════════════════════════════════════════════

_T0 = {"min_delay_sec": 0, "max_delay_sec": 0, "notify_on_error": False}


def _sh_cfg(p: Path, **over: object) -> dict:
    """遅延0・通知OFF のテスト用 cfg（実時間を消費しない）。"""
    sh: dict = dict(_T0)
    sh.update(over)
    return {"general": {"project_dir": str(p)}, "self_healing": sh}


class _CaptureLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, msg: str) -> None:
        self.lines.append(str(msg))


def _fail_boom():
    raise RuntimeError("boom")


def test_ceiling_key_is_per_account(tmp_path):
    """P0: failure ceiling のキーが垢単位（apply:<acct>）で分離される。

    旧実装は apply 全体キーだったため、1垢（zin20120731）の失効失敗が
    他垢の成功で毎回リセットされ、遮断が一度も発動しなかった（実測 count=0）。
    """
    p = _tmp_project(tmp_path)
    cfg = _sh_cfg(p, max_attempts=1, failure_ceiling_consecutive=3, failure_ceiling_cooldown_minutes=60)
    a = SelfHealingLoop(cfg=cfg, pipeline="apply", context={"key": "apply:acctA"})
    b = SelfHealingLoop(cfg=cfg, pipeline="apply", context={"key": "apply:acctB"})
    for _ in range(3):
        a.run(_fail_boom)
    assert a.is_blocked("apply:acctA") is True
    assert b.is_blocked("apply:acctB") is False

    state = json.loads((Path(p) / "data" / "self_heal_state.json").read_text(encoding="utf-8"))
    assert set(state["ceilings"]) == {"apply:acctA"}

    # 別垢の成功が、遮断済み垢のカウンタ/遮断を解かない
    b.run(lambda: (1, 0), validator=lambda v, **kw: None)
    assert a.is_blocked("apply:acctA") is True


def test_fatal_session_signal_stops_without_retry(tmp_path):
    """P0/F3: セッション失効は3回リトライせず1回で停止＋当該垢のみ遮断。"""
    p = _tmp_project(tmp_path)
    cap = _CaptureLogger()
    loop = SelfHealingLoop(
        cfg=_sh_cfg(p, max_attempts=3, failure_ceiling_consecutive=3, failure_ceiling_cooldown_minutes=30),
        pipeline="apply", logger=cap, context={"key": "apply:zin20120731"},
    )
    calls: list[int] = []

    def op():
        calls.append(1)
        return (0, 1)

    def validator(value, *, exception=None, context=None):
        return RecoverySignal(kind="no_auth_session", recoverable=False, severity="error",
                              message="apply 0 success 1 errors (no_auth_session)")

    r = loop.run(op, validator=validator)
    assert r.ok is False
    assert len(calls) == 1  # 旧実装: attempts=3（ブラウザ起動＋ログイン再試行を3回）
    assert r.attempts == 1
    assert any(e.action == "stop_fatal" for e in loop.events)
    # 遮断キーは context 由来（apply:<acct>）＝ その垢だけが止まる
    assert loop.is_blocked("apply:zin20120731") is True
    assert loop.is_blocked("apply") is False


def test_ceiling_fires_on_hourly_schedule(tmp_path):
    """P1/F5: first_fail_time が古くても毎時cron（間隔60分 > cooldown30分）で遮断が発動する。

    旧実装は first_fail_time（初回固定・以後更新なし）基準だったため、
    毎時runでは cooldown 30分が常に経過済みになり構造的に発動不能だった。
    """
    p = _tmp_project(tmp_path)
    cfg = _sh_cfg(p, max_attempts=1, failure_ceiling_consecutive=3, failure_ceiling_cooldown_minutes=30)
    state_path = Path(p) / "data" / "self_heal_state.json"

    # 09:00/10:00/11:00 と1時間おきに3回失敗した状態（3回目で遮断が確定する）
    loops = []
    for _ in range(3):
        loop = SelfHealingLoop(cfg=cfg, pipeline="collection")
        loops.append(loop)
        loop.run(_fail_boom)
    assert loops[-1].is_blocked("collection") is True  # 旧実装: False（4連続失敗でも遮断されなかった）

    state = json.loads(state_path.read_text(encoding="utf-8"))
    entry = state["ceilings"]["collection"]
    assert entry["count"] >= 3
    assert entry.get("blocked_until")  # しきい値到達時点で cooldown ぶん遮断
    # first_fail_time が過去でも（＝2時間前の初回失敗でも）遮断が維持される
    old = (datetime.now() - timedelta(hours=2)).isoformat()
    state["ceilings"]["collection"]["first_fail_time"] = old
    state_path.write_text(json.dumps(state), encoding="utf-8")
    again = SelfHealingLoop(cfg=cfg, pipeline="collection")
    assert again.is_blocked("collection") is True


def test_recovery_plan_reaches_transport_and_scope(tmp_path):
    """P2/F4: max_attempts=3 のままでも transport_fallback / scope_reduction に到達する。"""
    p = _tmp_project(tmp_path)
    cfg = {
        "general": {"project_dir": str(p)},
        "collection": {"use_scrapling": True, "max_pages": 99},
        "self_healing": dict(_T0, max_attempts=3, ai_assisted=False,
                             failure_ceiling_consecutive=99, failure_ceiling_cooldown_minutes=0),
    }
    assert cfg["self_healing"]["max_attempts"] == 3  # 増やしていない
    loop = SelfHealingLoop(cfg=cfg, pipeline="collection")
    seen: set[str] = set()
    for _ in range(3):
        loop.run(lambda: (_ for _ in ()).throw(ConnectionError("connect timeout")))
        seen |= {e.action for e in loop.events}
        loop.events.clear()
    assert "transport_fallback" in seen
    assert "scope_reduction" in seen
    assert "ai_consult" not in seen          # F2: ai_assisted=false では no-op attempt を作らない
    assert loop.cfg["collection"]["use_scrapling"] is False   # アクションが実効（トグル済み）
    assert loop.cfg["collection"]["max_pages"] == 1           # アクションが実効（縮小済み）


def test_ai_assisted_false_excludes_ai_consult(tmp_path):
    """P2/F2: ai_assisted の値がプランに反映される（false なら no-op attempt を作らない）。"""
    p = _tmp_project(tmp_path)
    off = SelfHealingLoop(cfg=_sh_cfg(p, ai_assisted=False), pipeline="apply")
    on = SelfHealingLoop(cfg=_sh_cfg(p, ai_assisted=True), pipeline="apply")
    assert "ai_consult" not in off._recovery_plan()
    assert "ai_consult" in on._recovery_plan()
    # apply では collection 専用アクションを持たない（使われない設定を残さない）
    assert "transport_fallback" not in off._recovery_plan()
    assert "scope_reduction" not in off._recovery_plan()


def test_recovery_events_are_logged(tmp_path):
    """P1/F1: HealingEvent が [SELF-HEAL] の構造化1行として logger に残る。"""
    p = _tmp_project(tmp_path)
    cap = _CaptureLogger()
    loop = SelfHealingLoop(cfg=_sh_cfg(p, max_attempts=2), pipeline="apply",
                           logger=cap, context={"key": "apply:acctA"})

    def op():
        raise ConnectionError("connect timeout")

    loop.run(op)
    lines = [ln for ln in cap.lines if ln.startswith("[SELF-HEAL]")]
    assert lines, "recovery actions must be observable in the log"
    assert any("pipeline=apply" in ln and "key=apply:acctA" in ln for ln in lines)
    assert any("action=" in ln for ln in lines)


def test_state_file_is_anchored_to_project_dir(tmp_path, monkeypatch):
    """state_file（相対）は CWD ではなく project_dir 基準で解決される。

    CWD基準だとプロジェクトルート以外からの run が別ファイルに状態を書き、
    failure ceiling のカウンタが実質リセットされる（遮断不発の一因）。
    """
    p = _tmp_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = _sh_cfg(p, state_file="data/self_heal_state.json", max_attempts=1,
                  failure_ceiling_consecutive=1, failure_ceiling_cooldown_minutes=60)
    loop = SelfHealingLoop(cfg=cfg, pipeline="collection")
    loop.run(_fail_boom)
    assert (Path(p) / "data" / "self_heal_state.json").exists()
    assert not (Path(tmp_path) / "data" / "self_heal_state.json").exists()


def test_collect_context_respects_config(tmp_path, monkeypatch):
    """P2/F6: collector は config の self_healing 値を尊重する（旧: True固定のハードコード）。"""
    from kensho.scraping import collector

    p = _tmp_project(tmp_path)
    captured: dict = {}

    class _Stub:
        def __init__(self, cfg=None, pipeline="", logger=None, context=None):
            captured["context"] = dict(context or {})
            captured["pipeline"] = pipeline
            self.cfg = dict(cfg or {})

        def run(self, op, **kw):  # type: ignore[no-untyped-def]
            return HealingResult(ok=True, value=(0, 0, 0), attempts=1)

    monkeypatch.setattr("kensho.core.self_heal.SelfHealingLoop", _Stub)
    cfg = {"general": {"project_dir": str(p)}, "self_healing": {"retry_empty_collection": True}}
    collector.collect(cfg=cfg, log=None)
    assert captured["context"]["retry_empty_collection"] is True
    cfg["self_healing"]["retry_empty_collection"] = False
    collector.collect(cfg=cfg, log=None)
    assert captured["context"]["retry_empty_collection"] is False
    assert captured["pipeline"] == "collection"


def test_apply_uses_account_key_and_fatal_reason(tmp_path, monkeypatch):
    """P0/F6: apply の ceiling キーが垢単位になり、失効理由が validator でリトライ不可になる。"""
    from kensho.application import applier
    from kensho.core import self_heal as self_heal_mod

    p = _tmp_project(tmp_path)
    captured: dict = {}

    class _SpyLoop(self_heal_mod.SelfHealingLoop):
        def __init__(self, **kw):  # type: ignore[no-untyped-def]
            captured["context"] = dict(kw.get("context") or {})
            super().__init__(**kw)

    calls: list[int] = []

    def _fake_impl(account_key, max_n, cfg=None, log=None, dry_run=False,
                   shared_browser=None, shared_ipw=None, reason_out=None):
        calls.append(1)
        if reason_out is not None:
            reason_out["kind"] = "no_auth_session"
        return (0, 1)

    monkeypatch.setattr(self_heal_mod, "SelfHealingLoop", _SpyLoop)
    monkeypatch.setattr(applier, "_apply_impl", _fake_impl)
    cfg = _sh_cfg(p, max_attempts=3, retry_partial_apply=True,
                  failure_ceiling_consecutive=3, failure_ceiling_cooldown_minutes=30)
    with pytest.raises(RuntimeError):
        applier.apply_for_account("acctA", 5, cfg=cfg)
    assert captured["context"]["key"] == "apply:acctA"     # P0: 垢単位キー
    assert captured["context"]["retry_partial"] is True    # F6: config を尊重
    assert len(calls) == 1                                 # 失効は3回リトライしない


def test_check_ip_separation_blocks_unreachable(tmp_path, monkeypatch):
    """追加要件: プロキシ不通垢は警告ではなく blocked（応募を試行しない）。"""
    from kensho.application import browser
    from kensho.utils import safety

    monkeypatch.setattr(browser, "USE_PROXY", True)
    monkeypatch.setattr(browser, "PROXY_MAP", {"acctA": "socks5://127.0.0.1:1", "acctB": "socks5://127.0.0.1:2"})
    monkeypatch.setattr(safety, "_get_ip_via_socks5", lambda host, port, timeout=10: ("1.2.3.4" if port == 2 else None))
    ok, msgs, blocked = safety.check_ip_separation({"safety": {"home_internet_accounts": []}}, log=None)
    assert ok is True
    assert blocked == ["acctA"]
    assert any("不通" in m for m in msgs)


def test_safety_blocks_dead_proxy_status(tmp_path):
    """追加要件: status/<acct>.json が dead_proxy の垢は blocked 扱い（実測 zin20120731 相当）。"""
    from kensho.utils import safety

    p = _tmp_project(tmp_path)
    (p / "data" / "status").mkdir()
    (p / "data" / "status" / "zin20120731.json").write_text(
        json.dumps({"status": "dead_proxy", "port": 1084, "stop_reason": "プロキシ死骸（TCP疎通 or 出口IP確認失敗）",
                    "updated": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    cfg = {"general": {"project_dir": str(p), "project_dir_abs": str(p)},
           "accounts": [{"key": "zin20120731"}, {"key": "atushi16"}],
           "safety": {"ip_separation_check": True}}
    assert safety.dead_proxy_accounts(cfg) == ["zin20120731"]
    assert "プロキシ死骸" in safety.dead_proxy_reason(cfg, "zin20120731")
    assert safety.dead_proxy_reason(cfg, "atushi16") == ""
    assert safety.dead_proxy_accounts(dict(cfg, safety={"dead_proxy_check": False})) == []


def test_apply_impl_skips_dead_proxy_account(tmp_path, monkeypatch):
    """追加要件: 死骸プロキシ垢はブラウザを起動せず応募を試行しない（自宅IPへフォールバックしない）。"""
    from kensho.application import applier

    p = _tmp_project(tmp_path)
    (p / "data" / "status").mkdir(exist_ok=True)
    (p / "data" / "status" / "deadacct.json").write_text(
        json.dumps({"status": "dead_proxy", "stop_reason": "プロキシ死骸"}), encoding="utf-8")
    (Path(p) / "data" / "x_session_dead.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(applier, "is_active_hours", lambda cfg: True)
    monkeypatch.setattr(applier, "check_rate_limit", lambda key, cfg: False)
    monkeypatch.setattr(applier, "verify_ip_separation", lambda cfg, log=None: (True, []))

    launched: list[int] = []

    def _boom(*a, **kw):  # type: ignore[no-untyped-def]
        launched.append(1)
        raise AssertionError("ブラウザを起動してはならない")

    monkeypatch.setattr(applier, "create_browser", _boom)
    monkeypatch.setattr(applier, "create_account_context", _boom)

    cfg = {
        "general": {"project_dir": str(p)},
        "accounts": [{"key": "deadacct", "display": "@dead", "session": "data/x_session_dead.json"}],
        "safety": {"ip_separation_check": True, "dead_proxy_check": True},
        "self_healing": dict(_T0),
    }
    reason: dict[str, str] = {}
    assert applier._apply_impl("deadacct", 5, cfg=cfg, log=_CaptureLogger(), reason_out=reason) == (0, 0)
    assert launched == []                    # 試行そのものがゼロ
    assert reason.get("kind") == "dead_proxy"
