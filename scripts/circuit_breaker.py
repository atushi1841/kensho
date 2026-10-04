#!/usr/bin/env python3
"""Circuit Breaker for stagnation detection (Pattern #8).

Tracks progress signals across loop iterations and trips when no progress
is made for `stagnation_threshold` consecutive cycles.

Usage:
    # Monitor a cycle
    circuit_breaker.py record --state data/circuit_state.json --signal "changed file: foo.py"

    # Check if breaker should trip
    circuit_breaker.py check --state data/circuit_state.json

    # Reset breaker
    circuit_breaker.py reset --state data/circuit_state.json

    # Test mode - simulate 3 stagnation cycles then trip
    circuit_breaker.py test --state data/circuit_state.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "circuit_state.json"
DEFAULT_THRESHOLD = 3


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "status": "closed",
            "reason": None,
            "trip_count": 0,
            "last_trip_at": None,
            "last_reset_at": None,
            "stagnation_threshold": DEFAULT_THRESHOLD,
            "history": [],
            "history_max": 50,
            "review_required": True,
        }
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, encoding="utf-8", mode="w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def signal_hash(signal: str) -> str:
    return hashlib.sha256(signal.encode()).hexdigest()[:16]


def record(state: dict[str, Any], path: Path, signal: str, *, is_progress: bool = True) -> dict[str, Any]:
    """Record a progress signal and check for stagnation.

    Args:
        state: Current circuit state
        path: Path to state file
        signal: Progress signal description
        is_progress: If False, mark as stagnation even if signal differs
    """
    ts = datetime.now(timezone.utc).isoformat()
    sig_hash = signal_hash(signal)

    # Check if this is a new signal or duplicate
    last = state.get("history", [])[-1] if state.get("history") else None
    is_duplicate = last and last.get("signal_hash") == sig_hash and last.get("status") in ("duplicate", "stagnant")

    # If is_progress=False, force stagnation status
    if not is_progress:
        entry_status = "duplicate"
    elif is_duplicate:
        entry_status = "duplicate"
    else:
        entry_status = "progress"

    entry = {
        "timestamp": ts,
        "signal": signal,
        "signal_hash": sig_hash,
        "status": entry_status,
    }

    history = state.get("history", [])
    history.append(entry)

    # Trim history
    max_len = state.get("history_max", 50)
    if len(history) > max_len:
        history = history[-max_len:]

    state["history"] = history

    # Count consecutive stagnations
    stagnant_count = 0
    for h in reversed(history):
        if h.get("status") == "duplicate":
            stagnant_count += 1
        else:
            break

    state["consecutive_stagnant"] = stagnant_count

    # Check if breaker should trip
    threshold = state.get("stagnation_threshold", DEFAULT_THRESHOLD)
    if stagnant_count >= threshold and state.get("status") != "open":
        state["status"] = "open"
        state["reason"] = f"Stagnation threshold reached: {stagnant_count} consecutive no-progress cycles"
        state["trip_count"] = state.get("trip_count", 0) + 1
        state["last_trip_at"] = ts
        log.warning(f"[circuit-breaker] TRIPPED: {state['reason']}")
    elif stagnant_count < threshold and state.get("status") == "open":
        # Auto-close if progress resumes (but keep review_required)
        state["status"] = "closed"
        state["reason"] = None
        state["last_reset_at"] = ts

    save_state(path, state)
    return state


def check(state: dict[str, Any]) -> bool:
    """Check if circuit breaker is open."""
    return state.get("status") == "open"


def reset(state: dict[str, Any], path: Path) -> dict[str, Any]:
    """Reset the circuit breaker."""
    ts = datetime.now(timezone.utc).isoformat()
    state["status"] = "closed"
    state["reason"] = None
    state["consecutive_stagnant"] = 0
    state["last_reset_at"] = ts
    save_state(path, state)
    return state


def send_alert(message: str) -> bool:
    """Send Telegram alert if configured."""
    try:
        from kensho.utils.notify import send_telegram
        return send_telegram(f"⚠️ Circuit Breaker Tripped\n\n{message}")
    except ImportError:
        log.warning("[circuit-breaker] notify module not available")
        return False
    except Exception as e:
        log.warning(f"[circuit-breaker] Telegram send failed: {e}")
        return False


def run_test(state: dict[str, Any], path: Path) -> dict[str, Any]:
    """Test mode: simulate 3 stagnation cycles."""
    print("[test] Simulating 3 stagnation cycles...")
    for i in range(3):
        print(f"[test] Cycle {i+1}: recording no-progress signal...")
        # Use same signal to trigger duplicate detection
        state = record(state, path, signal="no progress", is_progress=False)

    print(f"\n[test] Final state: {json.dumps(state, indent=2)}")
    print(f"[test] Status: {state.get('status')}")
    print(f"[test] Should trip: {check(state)}")

    if check(state):
        print("\n[test] Circuit breaker TRIPPED successfully!")
        # Try to send alert
        msg = f"Test trip at {state.get('last_trip_at')}\nReason: {state.get('reason')}\nTrips: {state.get('trip_count')}"
        sent = send_alert(msg)
        print(f"[test] Alert sent: {sent}")
    else:
        print("\n[test] ERROR: Circuit breaker did not trip!")

    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Circuit Breaker for stagnation detection")
    parser.add_argument("--state", type=Path, default=STATE_FILE, help="Path to circuit state JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    # record
    rec = sub.add_parser("record", help="Record a progress signal")
    rec.add_argument("--signal", "-s", required=True, help="Progress signal description")
    rec.add_argument("--no-progress", "-n", action="store_true", help="Mark as no-progress signal")

    # check
    sub.add_parser("check", help="Check if breaker is open")

    # reset
    rst = sub.add_parser("reset", help="Reset the breaker")

    # test
    sub.add_parser("test", help="Test mode: simulate stagnation")

    args = parser.parse_args()
    state = load_state(args.state)

    if args.command == "record":
        state = record(state, args.state, args.signal, is_progress=not args.no_progress)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        if check(state):
            send_alert(f"Status: open\nReason: {state.get('reason')}")
            return 1
        return 0

    elif args.command == "check":
        print(json.dumps({"status": state.get("status"), "trip_count": state.get("trip_count")}, indent=2))
        return 1 if check(state) else 0

    elif args.command == "reset":
        state = reset(state, args.state)
        print("Circuit breaker reset.")
        return 0

    elif args.command == "test":
        run_test(state, args.state)
        return 1 if check(state) else 0

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
