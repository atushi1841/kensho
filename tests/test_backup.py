"""
Tests for utils/backup.py — JSON保存・復旧・整合性チェック
"""
from __future__ import annotations

import json
from pathlib import Path

# ── テスト用の恒久的なプロジェクトルート設定 ──
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.backup import safe_save_json, verify_collected_integrity


class TestSafeSaveJson:
    """safe_save_json: アトミック保存 + 自動バックアップ"""

    def test_save_new_file(self, tmp_path: Path) -> None:
        """新規ファイルに保存できる"""
        filepath = tmp_path / "test.json"
        data = {"key": "value"}
        safe_save_json(filepath, data, "test")
        assert filepath.exists()
        loaded = json.loads(filepath.read_text(encoding="utf-8"))
        assert loaded == data

    def test_backup_created(self, tmp_path: Path) -> None:
        """既存ファイルがあればバックアップが作られる"""
        filepath = tmp_path / "test_backup.json"
        filepath.write_text('{"version": 1}', encoding="utf-8")
        data = {"version": 2}
        safe_save_json(filepath, data, "test_backup")
        # バックアップディレクトリに.bakファイルが存在
        backup_dir = tmp_path / "backups"
        baks = list(backup_dir.glob("test_backup.json.*.bak"))
        assert len(baks) == 1
        # 中身はオリジナル版
        bak_data = json.loads(baks[0].read_text(encoding="utf-8"))
        assert bak_data == {"version": 1}
        # 現行ファイルは新データ
        current = json.loads(filepath.read_text(encoding="utf-8"))
        assert current == {"version": 2}

    def test_tmp_file_cleaned(self, tmp_path: Path) -> None:
        """一時ファイル（.tmp）が残らない"""
        filepath = tmp_path / "clean_tmp.json"
        safe_save_json(filepath, {"data": 1}, "clean_test")
        assert not filepath.with_suffix(".tmp").exists()

    def test_collected_list_save(self, tmp_path: Path) -> None:
        """collected形式のデータ（リスト内包dict）を保存できる"""
        filepath = tmp_path / "collected.json"
        data = {
            "collected": [
                {"detail_url": "/abc", "applied": {"atushi16": None}},
                {"detail_url": "/def", "applied": {"atushi16": "2026-06-24T10:00:00"}},
            ]
        }
        safe_save_json(filepath, data, "collected.json")
        loaded = json.loads(filepath.read_text(encoding="utf-8"))
        assert len(loaded["collected"]) == 2
        assert loaded["collected"][0]["detail_url"] == "/abc"


class TestVerifyCollectedIntegrity:
    """verify_collected_integrity: processed.jsonとの整合性チェック"""

    def test_healthy(self, tmp_path: Path) -> None:
        """正常状態: collected > 0, processed > 0"""
        col_f = tmp_path / "collected.json"
        proc_f = tmp_path / "processed.json"
        col_f.write_text(
            json.dumps({"collected": [{"detail_url": "/a"}, {"detail_url": "/b"}]},
                       ensure_ascii=False),
            encoding="utf-8"
        )
        proc_f.write_text(
            json.dumps({"ids": ["/a", "/b", "/c"]}, ensure_ascii=False),
            encoding="utf-8"
        )
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is True
        assert result["collected_count"] == 2
        assert result["processed_count"] == 3

    def test_empty_collected(self, tmp_path: Path) -> None:
        """collected.jsonが存在しない"""
        col_f = tmp_path / "collected_missing.json"
        proc_f = tmp_path / "processed.json"
        proc_f.write_text(
            json.dumps({"ids": ["/a", "/b"]}, ensure_ascii=False),
            encoding="utf-8"
        )
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is False
        assert "空" in result.get("message", "")

    def test_no_processed(self, tmp_path: Path) -> None:
        """processed.jsonが存在しない（初期状態）"""
        col_f = tmp_path / "collected.json"
        proc_f = tmp_path / "processed_missing.json"
        col_f.write_text(
            json.dumps({"collected": []}, ensure_ascii=False),
            encoding="utf-8"
        )
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is True
        assert "初期状態" in result.get("message", "")
