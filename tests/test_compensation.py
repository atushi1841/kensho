import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCompensation:
    @pytest.fixture
    def cfg(self):
        return {
            "accounts": [
                {"key": "atushi16", "schedule": {"batches": [{"max": 7}, {"max": 7}]}},
                {"key": "TankanNotes", "schedule": {"batches": [{"max": 15}, {"max": 15}]}},
                {"key": "kudou", "schedule": {"batches": []}},
                {"key": "zin20120731", "schedule": {"batches": []}},
            ]
        }

    def test_load_config_reads_yaml(self, cfg, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("test: 1", encoding="utf-8")
        import yaml
        monkeypatch.setattr("yaml.safe_load", lambda p: cfg)
        from kensho.utils.compensation import load_config
        assert load_config() == cfg

    def test_is_dead_false_when_file_missing(self, tmp_path, monkeypatch):
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        monkeypatch.setattr("kensho.utils.compensation.STATUS_DIR", status_dir)
        from kensho.utils.compensation import is_dead
        assert is_dead("test") is False

    def test_is_dead_true(self, tmp_path, monkeypatch):
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / "acct.json").write_text(json.dumps({"status": "dead_proxy"}), encoding="utf-8")
        monkeypatch.setattr("kensho.utils.compensation.STATUS_DIR", status_dir)
        from kensho.utils.compensation import is_dead
        assert is_dead("acct") is True

    def test_apply_compensation_changes_max(self, cfg, monkeypatch):
        from kensho.utils.compensation import apply_compensation
        changed = apply_compensation(cfg)
        assert changed is True
        at = [a for a in cfg["accounts"] if a["key"] == "atushi16"][0]
        assert at["schedule"]["batches"][0]["max"] == 10
        tn = [a for a in cfg["accounts"] if a["key"] == "TankanNotes"][0]
        assert tn["schedule"]["batches"][0]["max"] == 18

    def test_apply_compensation_already_compenated_no_change(self, cfg, monkeypatch):
        from kensho.utils.compensation import apply_compensation
        apply_compensation(cfg)
        assert apply_compensation(cfg) is False

    def test_revert_compensation_restores_original(self, cfg):
        from kensho.utils.compensation import apply_compensation, revert_compensation
        apply_compensation(cfg)
        assert [b["max"] for b in cfg["accounts"][0]["schedule"]["batches"]] == [10, 10]
        changed = revert_compensation(cfg)
        assert changed is True
        assert [b["max"] for b in cfg["accounts"][0]["schedule"]["batches"]] == [7, 7]
