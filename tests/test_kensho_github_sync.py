"""tests/test_kensho_github_sync.py — github_sync push 復旧の回帰テスト (t_5dff275b).

対象: kensho_github_sync.py（非対話 push / index.lock 競合 / 失敗の持ち越し）

観点:
  1. credential 源の解決順（env ファイル → GCM helper → なし）
  2. git 失敗出力の理由分類（auth / network / index.lock / rejected）
  3. index.lock 競合: 退避リトライ・stale 回収・保持中は触らない
  4. リポジトリ排他ロック（flock）による直列化
  5. push 再試行（network のみ再試行・auth は即失敗）と exit code/理由の記録
  6. 実行状態の持ち越し（pending_commits / consecutive_push_failures）
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import kensho_github_sync as sync  # noqa: E402

REL = Path("docs/daily_reports/2026-09-24.md")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=True).stdout


def _completed(rc: int, stderr: str = "", stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["git"], returncode=rc, stdout=stdout, stderr=stderr)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """最小の git リポジトリを作り、モジュール定数をそこへ向ける."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    (root / "docs" / "daily_reports").mkdir(parents=True)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", "--", "README.md")
    _git(root, "commit", "-q", "-m", "base")
    monkeypatch.setattr(sync, "BASE", root)
    monkeypatch.setattr(sync, "_REPO_LOCK_PATH", root / ".git" / "kensho-github-sync.lock")
    monkeypatch.setattr(sync, "_INDEX_LOCK_PATH", root / ".git" / "index.lock")
    monkeypatch.setattr(sync, "STATE_PATH", root / "logs" / "github_sync_state.json")
    monkeypatch.setattr(sync, "CRON_LOG_PATH", root / "logs" / "github_sync_cron.log")
    return root


def _set_remote_ref(repo: Path) -> None:
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


def _write_target(repo: Path, text: str = "hello\n") -> Path:
    target = repo / REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# 1. env ファイル読み込み / credential 源の解決
# ---------------------------------------------------------------------------

def test_load_env_file_parses_values(tmp_path: Path) -> None:
    path = tmp_path / "x.env"
    path.write_text("# comment\n\nexport GITHUB_TOKEN=abc123\nGITHUB_USER=\"user1\"\nBAD_LINE\n", encoding="utf-8")
    assert sync.load_env_file(path) == {"GITHUB_TOKEN": "abc123", "GITHUB_USER": "user1"}


def test_load_env_file_missing_is_empty(tmp_path: Path) -> None:
    assert sync.load_env_file(tmp_path / "nope.env") == {}


def test_credential_config_prefers_env_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "github-sync.env"
    env_file.write_text("GITHUB_TOKEN=tok123\nGITHUB_USER=u1\n", encoding="utf-8")
    helper = tmp_path / "cred.sh"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(sync, "_REPO_CRED_HELPER", helper)
    monkeypatch.setattr(sync, "credential_env_candidates", lambda: [env_file])
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    cfg = sync.credential_config()
    assert cfg is not None
    args, label = cfg
    # 既存 helper（GCM 等）を打ち消してから自前の helper を積む
    assert args[0:2] == ["-c", "credential.helper="]
    assert args[2:] == ["-c", f"credential.helper={helper}"]
    assert label.startswith("token(")
    assert os.environ["GITHUB_TOKEN"] == "tok123"


def test_credential_config_falls_back_to_gcm_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gcm = tmp_path / "gcm.sh"
    gcm.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(sync, "_WSL_GCM_HELPER", gcm)
    monkeypatch.setattr(sync, "_REPO_CRED_HELPER", tmp_path / "missing.sh")
    monkeypatch.setattr(sync, "credential_env_candidates", lambda: [tmp_path / "none.env"])
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    assert sync.credential_config() == (
        ["-c", "credential.helper=", "-c", f"credential.helper={gcm}"], "gcm-helper(wsl)")


def test_credential_config_none_without_any_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "_WSL_GCM_HELPER", tmp_path / "no-gcm.sh")
    monkeypatch.setattr(sync, "_REPO_CRED_HELPER", tmp_path / "missing.sh")
    monkeypatch.setattr(sync, "credential_env_candidates", lambda: [tmp_path / "none.env"])
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    assert sync.credential_config() is None


# ---------------------------------------------------------------------------
# 2. 失敗理由の分類（実ログの文言で検証）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("output", "exit_code", "expected"), [
    ("fatal: could not read Username for 'https://github.com': No such device or address", 128, "auth"),
    ("fatal: could not read Username for 'https://github.com': terminal prompts disabled", 128, "auth"),
    ("remote: Invalid username or password.\nfatal: Authentication failed", 128, "auth"),
    ("remote: Invalid username or token. Password authentication is not supported for Git operations.\n"
     "fatal: Authentication failed for 'https://github.com/atushi1841/kensho.git/'", 128, "auth"),
    ("fatal: unable to access 'https://github.com/atushi1841/kensho.git/': Failed to connect to github.com"
     " port 443 after 134543 ms: Couldn't connect to server", 128, "network"),
    ("fatal: unable to access 'https://github.com/x/': Could not resolve host: github.com", 128, "network"),
    ("fatal: Unable to create '/mnt/d/Project2/kensho/.git/index.lock': File exists.", 128, "index_lock_busy"),
    ("! [rejected]        main -> main (non-fast-forward)", 1, "rejected"),
    ("error: pathspec 'nope' did not match any file(s) known to git", 1, "git_1"),
])
def test_classify_git_failure(output: str, exit_code: int, expected: str) -> None:
    assert sync.classify_git_failure(exit_code, output) == expected


def test_first_line_trims_and_limits() -> None:
    assert sync.first_line("\n\n  fatal: xyz  \nmore") == "fatal: xyz"
    assert sync.first_line("") == ""
    assert len(sync.first_line("a" * 500, 10)) == 10


# ---------------------------------------------------------------------------
# 3. index.lock 競合
# ---------------------------------------------------------------------------

def test_reclaim_stale_index_lock_removes_old_lock(repo: Path) -> None:
    lock = sync._INDEX_LOCK_PATH
    lock.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))

    note = sync.reclaim_stale_index_lock(600)
    assert "回収" in note
    assert not lock.exists()


def test_reclaim_leaves_fresh_index_lock(repo: Path) -> None:
    lock = sync._INDEX_LOCK_PATH
    lock.write_text("", encoding="utf-8")

    assert sync.reclaim_stale_index_lock(600) == ""
    assert lock.exists()


def test_reclaim_skips_lock_held_by_process(repo: Path) -> None:
    lock = sync._INDEX_LOCK_PATH
    with open(lock, "w", encoding="utf-8"):
        old = time.time() - 3600
        os.utime(lock, (old, old))
        note = sync.reclaim_stale_index_lock(600)
        assert "保持中" in note
        assert lock.exists()


def test_commit_owned_path_commits_only_target(repo: Path) -> None:
    _write_target(repo)
    (repo / "other.txt").write_text("other\n", encoding="utf-8")

    result = sync.commit_owned_path(REL, "docs: test")
    assert result.ok and result.reason == "ok"
    assert _git(repo, "log", "-1", "--format=%s").strip() == "docs: test"
    # 対象外ファイルは巻き込まない
    assert "other.txt" not in _git(repo, "show", "--stat", "--format=", "HEAD")


def test_commit_owned_path_nothing_to_commit(repo: Path) -> None:
    _write_target(repo)
    assert sync.commit_owned_path(REL, "m").ok

    again = sync.commit_owned_path(REL, "m")
    assert again.ok and again.reason == "nothing_to_commit"


def test_commit_owned_path_fails_on_fresh_index_lock(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KENSHO_SYNC_LOCK_RETRIES", "2")
    monkeypatch.setenv("KENSHO_SYNC_LOCK_BACKOFF_SEC", "0")
    _write_target(repo)
    lock = sync._INDEX_LOCK_PATH
    lock.write_text("", encoding="utf-8")   # 若い lock（保持者不在でも年齢条件で回収しない）

    result = sync.commit_owned_path(REL, "m")
    assert not result.ok
    assert result.reason == "index_lock_busy"
    assert result.exit_code != 0
    assert result.attempts == 2
    assert lock.exists()   # 触っていない
    assert _git(repo, "log", "-1", "--format=%s").strip() == "base"


def test_commit_owned_path_reclaims_stale_lock(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KENSHO_SYNC_LOCK_RETRIES", "1")
    monkeypatch.setenv("KENSHO_SYNC_LOCK_BACKOFF_SEC", "0")
    _write_target(repo)
    lock = sync._INDEX_LOCK_PATH
    lock.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))

    result = sync.commit_owned_path(REL, "m")
    assert result.ok and result.attempts == 2
    assert not lock.exists()
    assert _git(repo, "log", "-1", "--format=%s").strip() == "m"


# ---------------------------------------------------------------------------
# 4. リポジトリ排他ロック
# ---------------------------------------------------------------------------

def test_repo_lock_is_exclusive(repo: Path) -> None:
    first = sync.acquire_repo_lock(timeout=1.0)
    assert first is not None
    try:
        assert sync.acquire_repo_lock(timeout=0.3) is None   # 直列化される
    finally:
        sync.release_repo_lock(first)

    third = sync.acquire_repo_lock(timeout=1.0)
    assert third is not None
    sync.release_repo_lock(third)


# ---------------------------------------------------------------------------
# 5. push（非対話・再試行・exit code/理由）
# ---------------------------------------------------------------------------

def _stub_push_head(monkeypatch: pytest.MonkeyPatch, result: sync.PushResult) -> None:
    monkeypatch.setattr(sync, "push_head", lambda *a, **k: result)


def test_push_head_uses_low_speed_and_resets_helper(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "credential_config",
                        lambda: (["-c", "credential.helper="], "token(test)"))
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _completed(0, "Everything up-to-date")

    monkeypatch.setattr(sync, "run_git", fake_run_git)
    result = sync.push_head(attempts=3, backoff=0)

    assert result.ok and result.exit_code == 0 and result.attempts == 1
    assert result.source == "token(test)"
    assert calls[0][:2] == ["-c", "credential.helper="]
    assert "http.lowSpeedLimit=1000" in calls[0] and "http.lowSpeedTime=30" in calls[0]
    assert calls[0][-3:] == ["push", "origin", "HEAD"]


def test_push_head_retries_network_then_succeeds(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "credential_config", lambda: (["-c", "credential.helper="], "token(test)"))
    net = ("fatal: unable to access 'https://github.com/atushi1841/kensho.git/': Failed to connect to"
           " github.com port 443 after 30000 ms: Couldn't connect to server")
    results = [_completed(128, net), _completed(128, net), _completed(0, "")]
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return results[min(len(calls) - 1, len(results) - 1)]

    monkeypatch.setattr(sync, "run_git", fake_run_git)
    result = sync.push_head(attempts=3, backoff=0)

    assert result.ok and result.attempts == 3 and len(calls) == 3


def test_push_head_does_not_retry_auth_failure(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "credential_config", lambda: (["-c", "credential.helper="], "token(test)"))
    auth = "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _completed(128, auth)

    monkeypatch.setattr(sync, "run_git", fake_run_git)
    result = sync.push_head(attempts=3, backoff=0)

    assert not result.ok
    assert result.reason == "auth" and result.exit_code == 128 and result.attempts == 1
    assert len(calls) == 1


def test_push_head_timeout_reason_and_attempts(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "credential_config", lambda: (["-c", "credential.helper="], "token(test)"))

    def fake_run_git(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=timeout)

    monkeypatch.setattr(sync, "run_git", fake_run_git)
    result = sync.push_head(attempts=2, backoff=0)

    assert not result.ok and result.reason == "timeout" and result.exit_code == 124 and result.attempts == 2


def test_push_head_without_credential_source_fails_closed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "credential_config", lambda: None)
    monkeypatch.setattr(sync, "run_git", lambda *a, **k: pytest.fail("git を実行してはいけない"))

    result = sync.push_head()
    assert not result.ok and result.reason == "auth" and result.exit_code == 128 and result.attempts == 0


# ---------------------------------------------------------------------------
# 6. 状態の永続化・持ち越し
# ---------------------------------------------------------------------------

def test_state_roundtrip_and_log_append(repo: Path) -> None:
    assert sync.read_state() == {}
    sync.write_state({"pending_commits": 2, "consecutive_push_failures": 1})
    assert sync.read_state()["pending_commits"] == 2

    sync.log_run("result=ok exit=0 reason=in_sync pending=0")
    text = sync.CRON_LOG_PATH.read_text(encoding="utf-8")
    assert "[sync]" in text and "result=ok exit=0 reason=in_sync pending=0" in text


def test_main_dry_run_generates_report(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["kensho_github_sync.py", "--date", "2026-09-24", "--dry-run"])
    monkeypatch.setattr(sync, "run_git", lambda *a, **k: pytest.fail("dry-run では git を実行しない"))

    assert sync.main() == 0
    assert (repo / REL).exists()


def test_main_commits_and_records_success(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_remote_ref(repo)
    monkeypatch.setattr(sys, "argv", ["kensho_github_sync.py", "--date", "2026-09-24"])
    _stub_push_head(monkeypatch, sync.PushResult(True, 0, "ok", "up-to-date", 1, "token(test)"))

    assert sync.main() == 0
    assert _git(repo, "log", "-1", "--format=%s").strip() == "docs: 稼働サマリー 2026-09-24 (auto)"
    state = sync.read_state()
    assert state["last_result"] == "ok"
    assert state["pending_commits"] == 0 and state["consecutive_push_failures"] == 0
    log = sync.CRON_LOG_PATH.read_text(encoding="utf-8")
    assert "result=ok exit=0 reason=ok" in log


def test_main_carries_over_failed_push(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_remote_ref(repo)
    monkeypatch.setattr(sys, "argv", ["kensho_github_sync.py", "--date", "2026-09-24"])
    failure = sync.PushResult(False, 128, "network", "Failed to connect to github.com port 443", 3, "token(test)")
    _stub_push_head(monkeypatch, failure)

    assert sync.main() == 2
    state = sync.read_state()
    assert state["last_result"] == "push_failed"
    assert state["last_reason"] == "network" and state["last_exit_code"] == 128
    assert state["pending_commits"] >= 1 and state["consecutive_push_failures"] == 1
    log = sync.CRON_LOG_PATH.read_text(encoding="utf-8")
    assert "result=push_failed exit=2 reason=network" in log
    assert "pending=" in log

    # 次回実行: 同じ内容でも未push分を再送し、持ち越しが解消する
    _stub_push_head(monkeypatch, sync.PushResult(True, 0, "ok", "ok", 1, "token(test)"))
    assert sync.main() == 0
    state2 = sync.read_state()
    assert state2["last_result"] == "ok" and state2["consecutive_push_failures"] == 0
    assert "result=ok exit=0 reason=ok" in sync.CRON_LOG_PATH.read_text(encoding="utf-8")


def test_main_records_commit_failure(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_remote_ref(repo)
    monkeypatch.setattr(sys, "argv", ["kensho_github_sync.py", "--date", "2026-09-24"])
    monkeypatch.setenv("KENSHO_SYNC_LOCK_RETRIES", "1")
    monkeypatch.setenv("KENSHO_SYNC_LOCK_BACKOFF_SEC", "0")
    _stub_push_head(monkeypatch, sync.PushResult(True, 0, "ok", "ok", 1, "token(test)"))
    lock = sync._INDEX_LOCK_PATH
    lock.write_text("", encoding="utf-8")   # 若い lock で commit を失敗させる

    assert sync.main() == 2
    state = sync.read_state()
    assert state["last_result"] == "commit_failed"
    assert state["last_reason"] == "index_lock_busy"
    assert "result=commit_failed exit=2 reason=index_lock_busy" in sync.CRON_LOG_PATH.read_text(encoding="utf-8")
    assert (repo / REL).exists()   # 生成は必ず行われる（push 失敗でも当日レポートは残る）
