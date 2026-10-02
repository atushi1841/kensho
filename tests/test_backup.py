"""
Tests for utils/backup.py — JSON保存・復旧・整合性チェック
"""

from __future__ import annotations

import json

# ── テスト用の恒久的なプロジェクトルート設定 ──
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.utils.backup import safe_save_json, verify_collected_integrity


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

    def test_overwrite_existing(self, tmp_path: Path) -> None:
        """既存ファイルを上書きして保存できる"""
        filepath = tmp_path / "overwrite.json"
        filepath.write_text('{"version": 1}', encoding="utf-8")
        safe_save_json(filepath, {"version": 2}, "overwrite_test")
        loaded = json.loads(filepath.read_text(encoding="utf-8"))
        assert loaded == {"version": 2}

    def test_no_backup_on_first_save(self, tmp_path: Path) -> None:
        """新規保存時はバックアップが作られない"""
        filepath = tmp_path / "first.json"
        safe_save_json(filepath, {"n": 1}, "first_test")
        backup_dir = tmp_path / "backups"
        assert not backup_dir.exists() or list(backup_dir.glob("first.json.*.bak")) == []

    def test_tmp_file_cleaned(self, tmp_path: Path) -> None:
        """一時ファイル（.tmp）が残らない"""
        filepath = tmp_path / "clean_tmp.json"
        safe_save_json(filepath, {"data": 1}, "clean_test")
        assert not filepath.with_suffix(".tmp").exists()

    def test_overwrite_leaves_no_tmp(self, tmp_path: Path) -> None:
        """上書き保存後も一時ファイル（.tmp）が残らない"""
        filepath = tmp_path / "overwrite_tmp.json"
        filepath.write_text('{"old": true}', encoding="utf-8")
        safe_save_json(filepath, {"new": True}, "overwrite_tmp_test")
        assert filepath.exists()
        assert not filepath.with_suffix(".tmp").exists()

    def test_empty_existing_file_not_backed_up(self, tmp_path: Path) -> None:
        """既存ファイルが空（0バイト）ならバックアップを作らない"""
        filepath = tmp_path / "empty.json"
        filepath.write_text("", encoding="utf-8")
        safe_save_json(filepath, {"data": 1}, "empty_test")
        backup_dir = tmp_path / "backups"
        assert list(backup_dir.glob("empty.json.*.bak")) == []

    def test_old_backups_cleaned_up(self, tmp_path: Path) -> None:
        """バックアップがMAX_BACKUPS(20)件を超えたら古いものが削除される"""
        from kensho.utils.backup import BACKUP_DIR_NAME, MAX_BACKUPS

        filepath = tmp_path / "rot.json"
        backup_dir = tmp_path / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)
        # MAX_BACKUPS + 2件のダミーバックアップを事前作成
        for i in range(MAX_BACKUPS + 2):
            (backup_dir / f"rot.json.2026010{i % 10}_00000{i}.bak").write_text('{"v": 1}', encoding="utf-8")
        safe_save_json(filepath, {"v": 2}, "rot_test")
        remaining = list(backup_dir.glob("rot.json.*.bak"))
        assert len(remaining) <= MAX_BACKUPS

    def test_roundtrip_preserves_unicode(self, tmp_path: Path) -> None:
        """日本語データがensure_ascii=Falseで可読なまま保存される"""
        filepath = tmp_path / "jp.json"
        safe_save_json(filepath, {"賞品": "Amazonギフト券"}, "jp_test")
        raw = filepath.read_text(encoding="utf-8")
        assert "Amazonギフト券" in raw  # \uXXXXエスケードされていない
        assert json.loads(raw) == {"賞品": "Amazonギフト券"}

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
            json.dumps({"collected": [{"detail_url": "/a"}, {"detail_url": "/b"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        proc_f.write_text(json.dumps({"ids": ["/a", "/b", "/c"]}, ensure_ascii=False), encoding="utf-8")
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is True
        assert result["collected_count"] == 2
        assert result["processed_count"] == 3

    def test_empty_collected(self, tmp_path: Path) -> None:
        """collected.jsonが存在しない"""
        col_f = tmp_path / "collected_missing.json"
        proc_f = tmp_path / "processed.json"
        proc_f.write_text(json.dumps({"ids": ["/a", "/b"]}, ensure_ascii=False), encoding="utf-8")
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is False
        assert "空" in result.get("message", "")

    def test_no_processed(self, tmp_path: Path) -> None:
        """processed.jsonが存在しない（初期状態）"""
        col_f = tmp_path / "collected.json"
        proc_f = tmp_path / "processed_missing.json"
        col_f.write_text(json.dumps({"collected": []}, ensure_ascii=False), encoding="utf-8")
        result = verify_collected_integrity(col_f, proc_f)
        assert result["ok"] is True
        assert "初期状態" in result.get("message", "")
