"""競争率スコアソートロジックのテスト (t_dd7f5e39)"""

from __future__ import annotations

import sys
import datetime
from pathlib import Path
from unittest.mock import mock_open, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
_KENSHO_DIR = str(REPO_ROOT / "kensho")
if _KENSHO_DIR not in sys.path:
    sys.path.append(_KENSHO_DIR)

with patch("os.makedirs"), patch("builtins.open", mock_open(read_data="99999")), patch("sys.exit"):
    import orchestrator
    from orchestrator import get_pending_batches


class TestCompetitionSortLogic:
    """competition_scoreソートの優先度テスト"""

    def test_pending_count_priority(self) -> None:
        """pending件数が同じなら両アカウント返る"""
        cfg = {
            "accounts": [
                {"key": "acc1", "schedule": {"batches": [{"time": "10:00", "max": 20}]}},
                {"key": "acc2", "schedule": {"batches": [{"time": "10:00", "max": 20}]}},
            ],
            "orchestrator": {"priority": "competition_score"},
        }
        state = {}
        
        with patch("orchestrator.datetime") as fake_dt:
            fake_dt.now.return_value = datetime.datetime(2026, 10, 4, 10, 0)
            result = get_pending_batches(cfg, state)
        
        assert len(result) == 2
        keys = {x[0] for x in result}
        assert keys == {"acc1", "acc2"}

    def test_priority_mode_switch(self) -> None:
        """priority変更でモードが切り替わる"""
        cfg_rr = {
            "accounts": [
                {"key": "a", "schedule": {"batches": [{"time": "10:00", "max": 5}]}},
                {"key": "b", "schedule": {"batches": [{"time": "10:00", "max": 5}]}},
            ],
            "orchestrator": {"priority": "round_robin"},
        }
        cfg_comp = dict(cfg_rr)
        cfg_comp["orchestrator"]["priority"] = "competition_score"
        
        with patch("orchestrator.datetime") as fake_dt:
            fake_dt.now.return_value = datetime.datetime(2026, 10, 4, 10, 0)
            r_rr = get_pending_batches(cfg_rr, {})
            r_comp = get_pending_batches(cfg_comp, {})
        
        assert len(r_rr) == 2
        assert len(r_comp) == 2
        assert {x[0] for x in r_rr} == {"a", "b"}
        assert {x[0] for x in r_comp} == {"a", "b"}
