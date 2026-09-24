"""test_precommit_test_gate: scripts/precommit_test_gate.sh の検証 (t_1570eca6)

成功指標:
  ① 赤テストを含むダミーコミット試行で exit != 0（拒否）
  ② 緑のダミーコミットで exit = 0
  ③ 本テスト自体が 8 passed 以上（①②を含む）
  ④ 実装後の loop_health.sh 変更コミットで (d)(e) ともに True（未push・未コミット残0）

背景: 赤テストのまま commit が進行し HEAD が破損 → loop_health.sh 全断
（QA notepad 9/25 実測: NameError: repeats → score=0/ERROR、3 monitor 同時盲目化）。
既存 push-guard (t_c2104009) は push 忘れ防止のみでテスト未実行だったため、
「commit 前に対応テストを実行し、赤なら exit != 0」のゲートを追加する。
"""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "precommit_test_gate.sh"


def _init_repo(tmp_path: Path) -> Path:
    """隔離 temp git repo を作る（main repo に一切触れない）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "gate-test"],
    ):
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, f"{cmd} failed: {r.stderr}"
    return repo


def _stage(repo: Path) -> None:
    r = subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, f"git add failed: {r.stderr}"


def _run_gate(repo: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """ゲートを temp repo に対して pre-commit 相当で実行する。"""
    return subprocess.run(
        ["bash", str(SCRIPT), "--workdir", str(repo), "--stage", "pre-commit"],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


def test_green_commit_passes(tmp_path: Path) -> None:
    """成功指標②: コード＋緑テストをステージ → exit 0（commit 許可）。"""
    repo = _init_repo(tmp_path)
    (repo / "good.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_good.py").write_text("def test_add():\n    assert 1 + 1 == 2\n")
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode == 0, (
        f"green staged tree must pass: rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    )
    assert "PASS" in proc.stdout
    # 対象テストが実際に実行されたこと（走らずに exit 0 になる防波堤）
    assert "testing tests/test_good.py" in proc.stdout


def test_red_commit_fails(tmp_path: Path) -> None:
    """成功指標①: 赤テストを含むステージ → exit != 0（commit 拒否）。"""
    repo = _init_repo(tmp_path)
    (repo / "bad.py").write_text("def sub(a: int, b: int) -> int:\n    return a - b\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_bad.py").write_text("def test_sub():\n    assert 5 - 3 == 1\n")  # 赤
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode != 0, (
        f"red staged tree must be rejected: rc=0\n{proc.stdout}\n{proc.stderr}"
    )
    assert "test_bad.py" in (proc.stdout + proc.stderr)


def test_no_matching_test_warns_but_allows(tmp_path: Path) -> None:
    """実装内容②: 対応テストが特定できない場合は警告のみ（ブロックしない）。"""
    repo = _init_repo(tmp_path)
    (repo / "lonely_module.py").write_text("VALUE = 1\n")  # tests/test_lonely_module.py なし
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode == 0, (
        f"warning-only case must allow commit:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "warning" in proc.stdout.lower()


def test_tests_directory_change_is_skipped(tmp_path: Path) -> None:
    """tests/ 配下の変更はゲート対象外（ゲート自身の無限ループ防止）。"""
    repo = _init_repo(tmp_path)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_red.py").write_text("def test_x():\n    assert False\n")
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode == 0, (
        f"tests/ change must be skipped:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "testing" not in proc.stdout


def test_mixed_green_and_red_rejected(tmp_path: Path) -> None:
    """緑・赤が混在 → 赤側で拒否されるべき（緑も実行される）。"""
    repo = _init_repo(tmp_path)
    (repo / "good.py").write_text("def mul(a: int, b: int) -> int:\n    return a * b\n")
    (repo / "bad.py").write_text("def div(a: int, b: int) -> int:\n    return a // b\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_good.py").write_text("def test_mul():\n    assert 2 * 3 == 6\n")
    (repo / "tests" / "test_bad.py").write_text("def test_div():\n    assert 10 // 3 == 4\n")  # 赤
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode != 0, (
        f"mixed tree with a red test must fail:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "test_good.py" in proc.stdout  # 緑側も実行された
    assert "test_bad.py" in (proc.stdout + proc.stderr)


def test_non_code_files_ignored(tmp_path: Path) -> None:
    """.html / data/ / reports/ はコード対象外 → 警告もせず exit 0。"""
    repo = _init_repo(tmp_path)
    (repo / "index.html").write_text("<html></html>\n")
    (repo / "data").mkdir()
    (repo / "data" / "x.yaml").write_text("k: v\n")
    (repo / "reports").mkdir()
    (repo / "reports" / "r.sh").write_text("#!/bin/bash\ntrue\n")
    _stage(repo)

    proc = _run_gate(repo)
    assert proc.returncode == 0, (
        f"non-code files must pass silently:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "testing" not in proc.stdout
    assert "warning" not in proc.stdout.lower()


def test_empty_staging_area_skips(tmp_path: Path) -> None:
    """ステージ無し → skip（exit 0）。"""
    repo = _init_repo(tmp_path)
    (repo / "orphan.py").write_text("X = 1\n")  # git add しない

    proc = _run_gate(repo)
    assert proc.returncode == 0, f"empty staging must skip:\n{proc.stdout}\n{proc.stderr}"
    assert "skip" in proc.stdout.lower()


def test_absolute_python_resolution_no_bare_python3(tmp_path: Path) -> None:
    """cron 最小PATH (/usr/bin:/bin) でも bare python3 に依存せず動くこと。

    実装内容③: bare `python3` / bare `hermes` 禁止、絶対パス解決。
    PATH を /usr/bin:/bin に絞り、HERMES_VENV_BIN を未設定のまま実行して
    既定の絶対パス (/home/atushi/.hermes/hermes-agent/venv/bin/python3) で
    動くこと（無音縮退の再発防止）。
    """
    repo = _init_repo(tmp_path)
    (repo / "pathmod.py").write_text("def f() -> int:\n    return 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_pathmod.py").write_text("def test_f():\n    assert 1 == 1\n")
    _stage(repo)

    env = {k: v for k, v in os.environ.items() if k != "HERMES_VENV_BIN"}
    env["PATH"] = "/usr/bin:/bin"
    proc = _run_gate(repo, env=env)
    assert proc.returncode == 0, (
        f"must work under minimal PATH: rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    )
    assert "PASS" in proc.stdout
