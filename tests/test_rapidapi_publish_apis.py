"""
Tests for scripts/rapidapi_publish_apis.py — PRIVATE→PUBLIC 公開計画ロジック
(t_0e8d78ab). ネットワーク非依存：公開対象選択・updateApi mutation JSON の検証。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import rapidapi_publish_apis as rpa


def _state() -> dict:
    return {
        "japan-offmall-cn": {"api_id": "a1", "visibility": "PRIVATE", "name": "A"},
        "japan-used-car": {"api_id": "a2", "visibility": None, "name": "B"},
        "japan-camera": {"api_id": "a3", "visibility": "PUBLIC", "name": "C"},
    }


class TestBuildPlan:
    def test_selects_non_public_only(self) -> None:
        plan = rpa.build_plan(_state())
        keys = [t["api_key"] for t in plan["to_publish"]]
        assert keys == ["japan-offmall-cn", "japan-used-car"]
        assert all(t["visibility_before"] != "PUBLIC" for t in plan["to_publish"])

    def test_state_before_preserved(self) -> None:
        plan = rpa.build_plan(_state())
        assert plan["state_before"]["japan-camera"]["visibility"] == "PUBLIC"

    def test_all_public_yields_empty(self) -> None:
        st = {k: {**v, "visibility": "PUBLIC"} for k, v in _state().items()}
        assert rpa.build_plan(st)["to_publish"] == []


class TestPublishOne:
    def test_sends_updateApi_visibility_public(self) -> None:
        with patch.object(
            rpa.rps, "_gql", return_value={"data": {"updateApi": {"id": "a1", "visibility": "PUBLIC"}}}
        ) as m:
            res = rpa.publish_one({"e": "x"}, "a1")
        assert res == {"id": "a1", "visibility": "PUBLIC"}
        _, query, variables = m.call_args.args
        assert "updateApi" in query
        assert variables == {"api": {"id": "a1", "visibility": "PUBLIC"}}
