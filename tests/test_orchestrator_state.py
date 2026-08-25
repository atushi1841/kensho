"""orchestrator state保存の競合対策テスト — マージ保存の動作保証。"""

from __future__ import annotations

import json
from pathlib import Path

import kensho.orchestrator as orch


def _set_state_file(tmp_path: Path) -> str:
    state_file = str(tmp_path / "state.json")
    orch.STATE_FILE = state_file
    orch.STATE_DIR = str(tmp_path)
    return state_file


def test_save_state_basic(tmp_path: Path) -> None:
    """基本的な保存ができる。"""
    _set_state_file(tmp_path)
    orch.save_state({"last_processed": {"acct1": "2026-08-25:10:00"}})
    data = json.loads(Path(orch.STATE_FILE).read_text(encoding="utf-8"))
    assert data["last_processed"]["acct1"] == "2026-08-25:10:00"


def test_save_state_merges_new_keys(tmp_path: Path) -> None:
    """別垢の保存が既存stateとマージされる（lost update防止の核心）。"""
    _set_state_file(tmp_path)
    orch.save_state({"last_processed": {"acct1": "2026-08-25:10:00"}})
    orch.save_state({"last_processed": {"acct2": "2026-08-25:10:15"}})
    data = json.loads(Path(orch.STATE_FILE).read_text(encoding="utf-8"))
    lp = data["last_processed"]
    assert lp["acct1"] == "2026-08-25:10:00"  # 既存が残る
    assert lp["acct2"] == "2026-08-25:10:15"  # 新規が追加


def test_save_state_preserves_existing(tmp_path: Path) -> None:
    """既存の他垢エントリを上書きしない。"""
    _set_state_file(tmp_path)
    orch.save_state({"last_processed": {"acct0": "2026-08-25:08:00"}})
    orch.save_state({"last_processed": {"acct1": "2026-08-25:09:00"}})
    data = json.loads(Path(orch.STATE_FILE).read_text(encoding="utf-8"))
    lp = data["last_processed"]
    assert lp["acct0"] == "2026-08-25:08:00"  # 既存保持
    assert lp["acct1"] == "2026-08-25:09:00"


def test_save_state_last_collect(tmp_path: Path) -> None:
    """last_collectもマージ保存される。"""
    _set_state_file(tmp_path)
    orch.save_state({"last_processed": {"acct1": "2026-08-25:10:00"}})
    orch.save_state({"last_collect": "2026-08-25 11:00"})
    data = json.loads(Path(orch.STATE_FILE).read_text(encoding="utf-8"))
    assert data["last_collect"] == "2026-08-25 11:00"
    assert data["last_processed"]["acct1"] == "2026-08-25:10:00"