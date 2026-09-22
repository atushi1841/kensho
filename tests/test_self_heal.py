"""Tests for kensho.core.self_heal — error classification, recovery, loop."""
from __future__ import annotations

import json
import os
import sys
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
