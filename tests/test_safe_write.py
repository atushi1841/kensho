"""Tests for safe_write.py — CAS, claims, and atomic writes."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Path to the module
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
SAFE_WRITE_PATH = str(Path(SCRIPTS_DIR) / "safe_write.py")


class TestSafeWriter:
    def setup_method(self, method):
        self.tmp = tempfile.mkdtemp()
        self.writer = None
        self.test_file = Path(self.tmp) / "test.txt"
        self.test_file.write_text("hello world")
        self.data_dir = Path(self.tmp) / "data"
        self.data_dir.mkdir()

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_safe_write(self, args):
        cmd = [sys.executable, SAFE_WRITE_PATH] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def _read_file(self, path):
        code, stdout, stderr = self._run_safe_write(['--read', '--path', path])
        return json.loads(stdout) if stdout else None

    def test_read_existing_file(self):
        result = self._read_file(str(self.test_file))
        assert result is not None
        assert result['sha256'] is not None
        assert result['lines'] == 1

    def test_read_missing_file(self):
        missing = Path(self.tmp) / "missing.txt"
        result = self._read_file(str(missing))
        assert result is not None
        assert result['sha256'] is None
        assert result['lines'] == 0

    def test_write_success(self):
        content = b"updated content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        result = self._read_file(str(self.test_file))
        current_hash = result['sha256']
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(self.test_file),
            '--expect-sha256', current_hash,
            '--from-file', str(tmp_content)
        ])
        assert code == 0, f"Write failed: {stderr}"
        assert self.test_file.read_bytes() == content

    def test_write_hash_mismatch(self):
        content = b"new content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(self.test_file),
            '--expect-sha256', 'wronghash',
            '--from-file', str(tmp_content)
        ])
        assert code == 3, f"Expected exit 3, got {code}: {stderr}"

    def test_write_missing_file(self):
        missing = Path(self.tmp) / "missing.txt"
        content = b"new content"
        tmp_content = Path(self.tmp) / "new_content.bin"
        tmp_content.write_bytes(content)
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(missing),
            '--expect-sha256', 'nonexistent',
            '--from-file', str(tmp_content)
        ])
        assert code == 3, f"Expected exit 3, got {code}: {stderr}"

    def test_write_creates_parent_dirs(self):
        nested = Path(self.tmp) / "subdir" / "deep" / "file.txt"
        content = b"nested content"
        tmp_content = Path(self.tmp) / "nested_content.bin"
        tmp_content.write_bytes(content)
        result = self._read_file(str(self.test_file))
        current_hash = result['sha256']
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_bytes(b"hello world")
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(nested),
            '--expect-sha256', current_hash,
            '--from-file', str(tmp_content)
        ])
        assert code == 0, f"Write failed: {stderr}"
        assert nested.read_bytes() == content

    def test_claim_and_release(self):
        code, stdout, stderr = self._run_safe_write([
            '--claim', '--path', str(self.test_file), '--task', 'task-1'
        ])
        assert code == 0, f"Claim failed: {stderr}"
        claims_file = Path(self.tmp) / "data" / "edit_claims.json"
        assert claims_file.exists()
        with open(claims_file) as f:
            claims = json.load(f)
        assert len(claims) == 1
        assert claims[0]['path'] == str(self.test_file)
        assert claims[0]['task_id'] == 'task-1'
        code, stdout, stderr = self._run_safe_write([
            '--release', '--path', str(self.test_file), '--task', 'task-1'
        ])
        assert code == 0, f"Release failed: {stderr}"
        with open(claims_file) as f:
            claims = json.load(f)
        assert len(claims) == 0

    def test_claim_conflict(self):
        self._run_safe_write(['--claim', '--path', str(self.test_file), '--task', 'task-1'])
        code, stdout, stderr = self._run_safe_write([
            '--claim', '--path', str(self.test_file), '--task', 'task-2'
        ])
        assert code == 4, f"Expected exit 4, got {code}: {stderr}"

    def test_release_nonexistent(self):
        code, stdout, stderr = self._run_safe_write([
            '--release', '--path', str(self.test_file), '--task', 'nonexistent'
        ])
        assert code == 7, f"Expected exit 7, got {code}: {stderr}"

    def test_claims_list(self):
        self._run_safe_write(['--claim', '--path', str(self.test_file), '--task', 'task-1'])
        code, stdout, stderr = self._run_safe_write(['--claims'])
        assert code == 0, f"Claims failed: {stderr}"
        assert 'task-1' in stdout or 'Claims' in stdout

    def test_claims_json(self):
        self._run_safe_write(['--claim', '--path', str(self.test_file), '--task', 'task-1'])
        code, stdout, stderr = self._run_safe_write(['--claims', '--json'])
        assert code == 0, f"Claims JSON failed: {stderr}"
        claims = json.loads(stdout)
        assert len(claims) >= 1

    def test_prune_stale_claims(self):
        claims_file = Path(self.tmp) / "data" / "edit_claims.json"
        claims_file.parent.mkdir(parents=True, exist_ok=True)
        with open(claims_file, 'w') as f:
            json.dump([{
                'path': str(self.test_file),
                'task_id': 'old-task',
                'pid': '999999',
                'timestamp': time.time() - 10000
            }], f)
        code, stdout, stderr = self._run_safe_write(['--claims'])
        assert code == 0, f"Claims failed: {stderr}"
        with open(claims_file) as f:
            claims = json.load(f)
        assert len(claims) == 0

    def test_write_atomic(self):
        content = b"atomic test content"
        tmp_content = Path(self.tmp) / "atomic_content.bin"
        tmp_content.write_bytes(content)
        result = self._read_file(str(self.test_file))
        current_hash = result['sha256']
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(self.test_file),
            '--expect-sha256', current_hash,
            '--from-file', str(tmp_content)
        ])
        assert code == 0, f"Write failed: {stderr}"
        temp_files = list(Path(self.tmp).glob("*.tmp"))
        assert len(temp_files) == 0
        assert self.test_file.read_bytes() == content

    def test_write_with_stdin(self):
        content = b"stdin content"
        result = self._read_file(str(self.test_file))
        current_hash = result['sha256']
        proc = subprocess.run(
            [sys.executable, SAFE_WRITE_PATH, '--write', '--path', str(self.test_file),
             '--expect-sha256', current_hash, '--stdin'],
            input=content, capture_output=True
        )
        assert proc.returncode == 0, f"Stdin write failed: {proc.stderr.decode()}"
        assert self.test_file.read_bytes() == content

    def test_write_no_source(self):
        result = self._read_file(str(self.test_file))
        current_hash = result['sha256']
        code, stdout, stderr = self._run_safe_write([
            '--write', '--path', str(self.test_file),
            '--expect-sha256', current_hash
        ])
        assert code == 1, f"Expected exit 1, got {code}: {stderr}"
