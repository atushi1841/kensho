"""Tests for circuit_breaker.py (Pattern #8)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.circuit_breaker import (
    check,
    load_state,
    record,
    reset,
    run_test,
    signal_hash,
)


@pytest.fixture
def tmp_state(tmp_path: Path) -> Path:
    """Create a temporary circuit state file."""
    state_file = tmp_path / "circuit_state.json"
    state = {
        "schema_version": 1,
        "status": "closed",
        "reason": None,
        "trip_count": 0,
        "last_trip_at": None,
        "last_reset_at": None,
        "stagnation_threshold": 3,
        "history": [],
        "history_max": 50,
        "review_required": True,
    }
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


def test_load_state_default(tmp_path: Path) -> None:
    """Test loading state from non-existent file creates defaults."""
    state_file = tmp_path / "missing.json"
    state = load_state(state_file)
    assert state["status"] == "closed"
    assert state["stagnation_threshold"] == 3
    assert state["history"] == []


def test_load_state_existing(tmp_state: Path) -> None:
    """Test loading state from existing file."""
    state = load_state(tmp_state)
    assert state["status"] == "closed"
    assert isinstance(state["history"], list)


def test_signal_hash_deterministic() -> None:
    """Test that signal_hash produces consistent output."""
    signal = "changed file: foo.py"
    h1 = signal_hash(signal)
    h2 = signal_hash(signal)
    assert h1 == h2
    assert len(h1) == 16


def test_signal_hash_different() -> None:
    """Test that different signals produce different hashes."""
    h1 = signal_hash("signal one")
    h2 = signal_hash("signal two")
    assert h1 != h2


def test_record_progress(tmp_state: Path) -> None:
    """Test recording a progress signal."""
    state = load_state(tmp_state)
    state = record(state, tmp_state, "changed file: foo.py")

    assert state["status"] == "closed"
    assert len(state["history"]) == 1
    assert state["history"][0]["status"] == "progress"
    assert state.get("consecutive_stagnant") == 0


def test_record_duplicate(tmp_state: Path) -> None:
    """Test recording a duplicate signal after stagnation."""
    state = load_state(tmp_state)

    # Record first signal as stagnation
    state = record(state, tmp_state, "no progress", is_progress=False)
    assert state["history"][-1]["status"] == "duplicate"

    # Record same signal again
    state = record(state, tmp_state, "no progress", is_progress=False)
    assert state["history"][-1]["status"] == "duplicate"
    assert state.get("consecutive_stagnant") == 2


def test_record_multiple_stagnation(tmp_state: Path) -> None:
    """Test recording multiple stagnation signals."""
    state = load_state(tmp_state)

    for i in range(3):
        state = record(state, tmp_state, "no progress", is_progress=False)

    assert state["status"] == "open"
    assert state["reason"] is not None
    assert state["trip_count"] == 1
    assert state.get("consecutive_stagnant") == 3


def test_record_resets_after_progress(tmp_state: Path) -> None:
    """Test that progress after stagnation resets the counter."""
    state = load_state(tmp_state)

    # 3 stagnation signals
    for i in range(3):
        state = record(state, tmp_state, "no progress", is_progress=False)
    assert state["status"] == "open"

    # Progress signal
    state = record(state, tmp_state, "changed file: bar.py")
    assert state["status"] == "closed"
    assert state.get("consecutive_stagnant") == 0


def test_check_open(tmp_state: Path) -> None:
    """Test check() returns True when breaker is open."""
    state = load_state(tmp_state)
    for i in range(3):
        state = record(state, tmp_state, "no progress", is_progress=False)

    assert check(state) is True


def test_check_closed(tmp_state: Path) -> None:
    """Test check() returns False when breaker is closed."""
    state = load_state(tmp_state)
    state = record(state, tmp_state, "some progress")
    assert check(state) is False


def test_reset(tmp_state: Path) -> None:
    """Test resetting the breaker."""
    state = load_state(tmp_state)

    # Trip the breaker
    for i in range(3):
        state = record(state, tmp_state, "no progress", is_progress=False)
    assert state["status"] == "open"

    # Reset
    state = reset(state, tmp_state)
    assert state["status"] == "closed"
    assert state["reason"] is None
    assert state.get("consecutive_stagnant") == 0


def test_history_trim(tmp_state: Path) -> None:
    """Test that history is trimmed to max length."""
    state = load_state(tmp_state)
    state["history_max"] = 5

    for i in range(10):
        state = record(state, tmp_state, "signal", is_progress=False)

    assert len(state["history"]) <= 5


def test_test_mode_trips(tmp_state: Path) -> None:
    """Test run_test() trips the breaker after 3 cycles."""
    state = load_state(tmp_state)

    with patch("scripts.circuit_breaker.send_alert") as mock_alert:
        state = run_test(state, tmp_state)

    assert state["status"] == "open"
    assert mock_alert.called


def test_custom_threshold(tmp_state: Path) -> None:
    """Test that custom threshold is respected."""
    state = load_state(tmp_state)
    state["stagnation_threshold"] = 5
    from scripts.circuit_breaker import save_state
    save_state(tmp_state, state)

    # Reload with new threshold
    state = load_state(tmp_state)

    # Only 3 cycles, should not trip with threshold=5
    for i in range(3):
        state = record(state, tmp_state, "no progress", is_progress=False)

    assert state["status"] == "closed"  # Not enough cycles to trip
    assert state.get("consecutive_stagnant") == 3