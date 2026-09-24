"""Tests for safe_write.py — CAS, claims, and atomic writes."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import safe_write as sw


class TestSafeWriter:
    def setup_method(self, method):
        self.tmp = tempfile.mkdtemp()
        self.writer = sw.SafeWriter(data_dir=self.tmp)
        self.test_file = Path(self.tmp) / "test.txt"
        self.test_file.write_text("hello world")

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_existing_file(self):
        result = self.writer.read(str(self.test_file))
        assert result["sha256"] is not None
        assert result["lines"] == 1

    def test_read_missing_file(self):
        missing = Path(self.tmp) / "missing.txt"
        result = self.writer.read(str(missing))
        assert result["sha256"] is None
        assert result["lines"] == 0

    def test_write_success(self):
        content = b"updated content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        
        current_hash = self.writer._get_file_hash(str(self.test_file))
        # Should succeed
        self.writer.write(str(self.test_file), current_hash, from_file=str(tmp_content))
        assert self.test_file.read_bytes() == content

    def test_write_hash_mismatch(self):
        content = b"new content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        
        with pytest.raises(SystemExit) as exc_info:
            self.writer.write(str(self.test_file), "wronghash", from_file=str(tmp_content))
        assert exc_info.value.code == 3

    def test_write_missing_file(self):
        missing = Path(self.tmp) / "missing.txt"
        content = b"new content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        
        with pytest.raises(SystemExit) as exc_info:
            self.writer.write(str(missing), "nonexistent", from_file=str(tmp_content))
        assert exc_info.value.code == 3

    def test_write_creates_parent_dirs(self):
        nested = Path(self.tmp) / "subdir" / "deep" / "file.txt"
        content = b"nested content"
        tmp_content = Path(self.tmp) / "nested_content.bin"
        tmp_content.write_bytes(content)
        
        self.writer.write(str(nested), "nonexistent", from_file=str(tmp_content))
        assert nested.exists()
        assert nested.read_bytes() == content

    def test_claim_and_release(self):
        self.writer.claim(str(self.test_file), "task-1")
        # Verify claim was saved
        claims = self.writer._load_claims()
        assert len(claims) == 1
        assert claims[0]["path"] == str(self.test_file)
        assert claims[0]["task_id"] == "task-1"

        # Release the claim
        self.writer.release(str(self.test_file), "task-1")
        claims = self.writer._load_claims()
        assert len(claims) == 0

    def test_claim_conflict(self):
        self.writer.claim(str(self.test_file), "task-1")
        with pytest.raises(SystemExit) as exc_info:
            self.writer.claim(str(self.test_file), "task-2")
        assert exc_info.value.code == 4

    def test_release_nonexistent(self):
        with pytest.raises(SystemExit) as exc_info:
            self.writer.release(str(self.test_file), "nonexistent")
        assert exc_info.value.code == 7

    def test_claims_list(self):
        self.writer.claim(str(self.test_file), "task-1")
        # Should list claims
        self.writer.claims()

    def test_claims_json(self):
        self.writer.claim(str(self.test_file), "task-1")
        # Should output JSON
        self.writer.claims(json_output=True)

    def test_prune_stale_claims(self):
        # Add a claim with old timestamp
        claims = [{
            "path": str(self.test_file),
            "task_id": "old-task",
            "pid": "999999",
            "timestamp": time.time() - 10000  # 10000 seconds ago, way past TTL
        }]
        self.writer._save_claims(claims)
        
        pruned = self.writer._prune_stale_claims()
        assert pruned == 1
        assert len(self.writer._load_claims()) == 0

    def test_write_atomic(self):
        """Verify atomic write: file should never be in a partial state."""
        content = b"atomic test content"
        tmp_content = Path(self.tmp) / "atomic_content.bin"
        tmp_content.write_bytes(content)
        
        current_hash = self.writer._get_file_hash(str(self.test_file))
        self.writer.write(str(self.test_file), current_hash, from_file=str(tmp_content))
        
        # Verify no temp files left behind
        temp_files = list(Path(self.tmp).glob("*.tmp"))
        assert len(temp_files) == 0
        
        # Verify content is complete
        assert self.test_file.read_bytes() == content

    def test_write_with_stdin(self):
        """Test writing from stdin"""
        import io
        old_stdin = sys.stdin
        try:
            sys.stdin = io.BytesIO(b"stdin content")
            current_hash = self.writer._get_file_hash(str(self.test_file))
            self.writer.write(str(self.test_file), current_hash, stdin=True)
            assert self.test_file.read_bytes() == b"stdin content"
        finally:
            sys.stdin = old_stdin

    def test_write_no_source(self):
        """Test error when no source specified"""
        current_hash = self.writer._get_file_hash(str(self.test_file))
        with pytest.raises(SystemExit) as exc_info:
            self.writer.write(str(self.test_file), current_hash)
        assert exc_info.value.code == 1