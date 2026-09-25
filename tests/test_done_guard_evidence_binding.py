"""Tests for scripts/done_guard_evidence_binding.py — doneガード条件(bind)（t_07945937）

背景: 条件(j) は evidence.json の必須フィールド非空と成果物パス実在しか見ないため、
「タスク名で任意ファイルをコミット + 実在パスを並べた evidence.json」だけで done ガードを
通過できた（t_47a5b3fe / t_20f49e54 の共通根 = 実装成果物が HEAD に存在しない偽done）。
本テストは (bind) が偽done経路だけを落とし、正規ケース（成果物がタスク commit に結線）を
通すこと、そして移行期間 soft / hard の切替が環境変数で明示できることを検証する。

ネットワーク不使用・共有repoの git 操作なし（すべて tmp_path 上の一時repoで完結）。
プロトタイプ（dangling ea78e29 のテスト）は cleanup に `git reset --hard` を使っており共有repoを
破壊し得たため、そのままは採用せず本ファイルで安全な形に置き換えている。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import done_guard_evidence_binding as mod  # noqa: E402

GUARD_PATH = Path.home() / ".hermes" / "profiles" / "kensho-sweeps" / "scripts" / "kanban_done_guard.py"
MODULE_PATH = Path(__file__).parent.parent / "scripts" / "done_guard_evidence_binding.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")


def _load_guard() -> Any:
    if not GUARD_PATH.is_file():
        pytest.skip(f"done guard not found: {GUARD_PATH}")
    spec = importlib.util.spec_from_file_location("_done_guard_for_bind_test", GUARD_PATH)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_evidence(repo: Path, task_id: str, paths: list[str],
                    source_commits: list[str] | None = None) -> Path:
    ev: dict[str, Any] = {
        "task_id": task_id, "status": "complete",
        "success_indicators": ["done"], "verification_commands": ["$ echo ok => ok"],
        "artifact_paths": paths, "evidence_hashes": ["sha256:0"],
    }
    if source_commits is not None:
        ev["source_commits"] = source_commits
    p = repo / "reports" / f"{task_id}_evidence.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
    return p


# --- (bind)-1: 成果物が自タスク diff に結線されているか -----------------------

def test_bind_pass_when_artifact_committed_with_task_id(tmp_path: Path) -> None:
    """具体シナリオ: 成果物をタスクID入りメッセージで commit → bind pass。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    tid = "t_facade02"
    (repo / "scripts").mkdir()
    (repo / "scripts" / "real_impl.py").write_text("# real\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{tid}: implement real artifact")
    st = mod.bind_state(repo, tid, {"artifact_paths": ["scripts/real_impl.py"]})
    assert st["status"] == "pass", st
    assert st["bound_paths"] == ["scripts/real_impl.py"]
    assert "bound to task commits/diff" in st["note"]


def test_bind_fail_when_artifact_not_in_task_diff(tmp_path: Path) -> None:
    """偽done再現: 成果物は過去commitに実在するが、タスク名の commit はコードに触れていない。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    tid = "t_facade01"
    (repo / "scripts").mkdir()
    (repo / "scripts" / "fake_impl.py").write_text("# exists but not task-bound\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial commit (no task id)")
    # 成果物を「push済みの過去」へ固定（= HEAD の差分から外す）
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"],
                   check=True, capture_output=True, text=True)
    (repo / "reports").mkdir()
    (repo / "reports" / "other.md").write_text("no code\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{tid} fake commit")
    st = mod.bind_state(repo, tid, {"artifact_paths": ["scripts/fake_impl.py"]})
    assert st["status"] == "fail", st
    assert "fake_impl.py" in st["note"]


def test_bind_skip_for_docs_only_evidence(tmp_path: Path) -> None:
    """docs/データのみの証跡は skip（markdown 経路・データ成果物カードを縛らない）。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "reports").mkdir()
    (repo / "reports" / "notes.md").write_text("docs\n", encoding="utf-8")
    st = mod.bind_state(repo, "t_facade03", {"artifact_paths": ["reports/notes.md"]})
    assert st["status"] == "skip", st


def test_bind_skip_when_no_evidence_json(tmp_path: Path) -> None:
    """evidence.json 無し（artifact_paths 空）は skip = additive。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert mod.bind_state(repo, "t_facade04", {})["status"] == "skip"
    assert mod.bind_state(repo, "t_facade04", None)["status"] == "skip"


# --- (bind)-2: source_commits の検証 -----------------------------------------

def test_bind_fail_on_ghost_source_commit(tmp_path: Path) -> None:
    """宣言された source_commits が解決不能（幽霊ハッシュ）なら fail。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "impl.py").write_text("# impl\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "t_facade05: impl")
    st = mod.bind_state(repo, "t_facade05",
                        {"artifact_paths": ["scripts/impl.py"],
                         "source_commits": ["deadbeefdeadbeefdeadbeef"]})
    assert st["status"] == "fail", st
    assert "not resolvable" in st["note"]


def test_bind_fail_when_source_commit_touches_no_code(tmp_path: Path) -> None:
    """source_commits が解決できてもコード成果物に触れていなければ fail。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "impl.py").write_text("# impl\n", encoding="utf-8")
    (repo / "reports").mkdir()
    (repo / "reports" / "doc.md").write_text("doc\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "t_facade06: impl")
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    # 2つ目の commit は docs のみ（タスクIDを含む）
    (repo / "reports" / "doc.md").write_text("doc2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "t_facade06: docs only")
    docs_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    assert sha != docs_sha
    st = mod.bind_state(repo, "t_facade06",
                        {"artifact_paths": ["scripts/impl.py"], "source_commits": [docs_sha]})
    assert st["status"] == "fail", st
    assert "touches no declared code artifact" in st["note"]


# --- モジュールCLI -----------------------------------------------------------

def test_cli_exit_codes(tmp_path: Path) -> None:
    """CLI: 結線あり=0 / 結線なし=1（soft/hard の判断は呼出側=doneガードが持つ）。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    tid = "t_facade07"
    (repo / "scripts").mkdir()
    (repo / "scripts" / "a.py").write_text("# a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{tid}: a")

    good = _write_evidence(repo, tid, ["scripts/a.py"])
    bad = _write_evidence(repo, "t_facade08", ["scripts/a.py"])
    r_ok = subprocess.run([sys.executable, str(MODULE_PATH), "--validate", str(good),
                           "--task-id", tid, "--workdir", str(repo), "--json"],
                          capture_output=True, text=True)
    r_ng = subprocess.run([sys.executable, str(MODULE_PATH), "--validate", str(bad),
                           "--task-id", "t_facade08", "--workdir", str(repo), "--json"],
                          capture_output=True, text=True)
    assert r_ok.returncode == 0, r_ok.stdout + r_ok.stderr
    assert json.loads(r_ok.stdout.strip().splitlines()[-1])["status"] == "pass"
    assert r_ng.returncode == 1, r_ng.stdout + r_ng.stderr
    assert json.loads(r_ng.stdout.strip().splitlines()[-1])["status"] == "fail"


def test_module_selftest_passes() -> None:
    """一時repoでの自己検証（pass/fail/skip + 幽霊source_commit）が緑。"""
    r = subprocess.run([sys.executable, str(MODULE_PATH), "--selftest"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ALL OK" in r.stdout


# --- doneガード本体との結線（ドリフト検出） ----------------------------------

def test_guard_invokes_bind_checker(tmp_path: Path) -> None:
    """profile側 doneガードの条件(bind) が repo 側チェッカーを実際に呼ぶ。"""
    guard = _load_guard()
    repo = tmp_path / "repo"
    _init_repo(repo)
    tid = "t_facade09"
    (repo / "scripts").mkdir()
    (repo / "scripts" / "b.py").write_text("# b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{tid}: b")
    good = _write_evidence(repo, tid, ["scripts/b.py"])
    bad = _write_evidence(repo, "t_facade10", ["scripts/b.py"])

    assert guard.evidence_binding_state(repo, tid, {"path": str(good)})["status"] == "pass"
    assert guard.evidence_binding_state(repo, "t_facade10", {"path": str(bad)})["status"] == "fail"
    # evidence.json が無ければ skip（誤ブロックしない）
    assert guard.evidence_binding_state(repo, tid, {"path": None})["status"] == "skip"


def test_guard_bind_migration_is_soft_and_env_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """移行期間は soft（既定）で、KANBAN_GUARD_BIND_HARD により hard へ明示切替できる。"""
    guard = _load_guard()
    monkeypatch.delenv("KANBAN_GUARD_BIND_HARD", raising=False)
    assert guard.BIND_HARD_AFTER == "2026-10-01"
    assert guard._bind_is_hard() is False           # 2026-09-25 時点 = 移行soft期間
    monkeypatch.setenv("KANBAN_GUARD_BIND_HARD", "1")
    assert guard._bind_is_hard() is True
    monkeypatch.setenv("KANBAN_GUARD_BIND_HARD", "0")
    assert guard._bind_is_hard() is False


def test_guard_exposes_bind_condition_key() -> None:
    """条件キーが evaluate に配線されている（削除・改名のドリフト検出）。"""
    guard = _load_guard()
    key = "bind:artifact_paths_bound_to_task_diff"
    src = GUARD_PATH.read_text(encoding="utf-8")
    assert key in src
    assert "BIND_HARD_AFTER" in src
    assert guard.BIND_SCRIPT.name == "done_guard_evidence_binding.py"
