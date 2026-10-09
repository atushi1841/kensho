"""Tests for proxy dead compensation behavior in orchestrator."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import get_pending_batches, load_state, save_state


class TestCompensationOrchestratorIntegration:
    def test_get_pending_batches_atushi16_with_compensation(self, tmp_path, monkeypatch):
        cfg = {
            "accounts": [
                {
                    "key": "atushi16",
                    "schedule": {
                        "batches": [
                            {"max": 10, "time": "08:02"},
                            {"max": 10, "time": "09:12"},
                        ]
                    },
                }
            ],
            "orchestrator": {"priority": "round_robin"},
        }
        state = {"last_processed": {"atushi16": ""}}
        result = get_pending_batches(cfg, state, account_key="atushi16")
        assert len(result) == 2
        keys = [r[0] for r in result]
        maxes = [r[2] for r in result]
        assert all(k == "atushi16" for k in keys)
        assert all(8 <= m <= 12 for m in maxes)

    def test_get_pending_batches_tankan_notes_with_compensation(self, tmp_path, monkeypatch):
        cfg = {
            "accounts": [
                {
                    "key": "TankanNotes",
                    "schedule": {
                        "batches": [
                            {"max": 18, "time": "09:29"},
                            {"max": 18, "time": "10:52"},
                        ]
                    },
                }
            ],
            "orchestrator": {"priority": "round_robin"},
        }
        state = {"last_processed": {"TankanNotes": ""}}
        result = get_pending_batches(cfg, state, account_key="TankanNotes")
        assert len(result) == 2
        keys = [r[0] for r in result]
        maxes = [r[2] for r in result]
        assert all(k == "TankanNotes" for k in keys)
        assert all(16 <= m <= 20 for m in maxes)