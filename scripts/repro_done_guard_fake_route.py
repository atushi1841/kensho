#!/usr/bin/env python3
"""偽done経路の再現ハーネス（t_07945937 / scripts/repro_done_guard_fake_route.py）（t_07945937 検証用・共有repoには一切触らない）。

シナリオ: 「タスク名で任意ファイルをコミット + 実在パスを並べた evidence.json」だけで
done ガードを通過できてしまう経路を、一時repo上で再現する。
  1. commit A  : scripts/fake_impl.py（成果物・タスク名を含まないメッセージ）
  2. origin/main を A に固定（= 成果物は「push済みの過去」にある）
  3. commit B  : reports/other.md + reports/t_fake001_evidence.json（メッセージにタスクID）
                 → タスク名のコミットはコード成果物に一切触れていない
  4. worker出力 dir に a/b を満たす「所有証跡」を置く（虚偽レポート）
結果: 旧ガード（.bak）は j=pass で通る / 新ガードは bind=fail。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

GUARD = Path.home() / ".hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py"
GUARD_BAK = Path(str(GUARD) + ".bak-20260925")
TID = "t_facade01"


def git(repo: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def build(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    out = root / "worker_out"
    (repo / "scripts").mkdir(parents=True)
    (repo / "reports").mkdir(parents=True)
    out.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fake@example.com")
    git(repo, "config", "user.name", "fake")
    (repo / "scripts" / "fake_impl.py").write_text("# 成果物（過去commitに存在）\n", encoding="utf-8")
    (repo / "reports" / "fake.md").write_text("initial\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial commit (no task id)")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")   # 成果物は origin 側
    ev = {
        "task_id": TID, "status": "complete",
        "success_indicators": ["done"],
        "verification_commands": ["$ echo ok => ok"],
        "artifact_paths": ["scripts/fake_impl.py"],   # 実在するがタスクに無関係
        "evidence_hashes": ["deadbeef"],
    }
    (repo / "reports" / f"{TID}_evidence.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
    (repo / "reports" / "other.md").write_text("task-named commit, no code artifact\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"{TID} fake commit")
    # 虚偽の worker 出力（a/b を満たす）
    (out / f"{TID}_verification.md").write_text(
        f"# {TID} 検証\n\n## verification_evidence\n"
        "$ ls scripts/fake_impl.py\nscripts/fake_impl.py\n"
        "$ python3 -c \"print('ok')\"\nok\n"
        "$ date '+%F'\n2026-09-25\n", encoding="utf-8")
    return repo, out


def run_guard(guard: Path, repo: Path, out: Path, hard: bool | None) -> tuple[int, dict]:
    env = dict(os.environ)
    env.pop("KANBAN_GUARD_BIND_HARD", None)
    if hard is True:
        env["KANBAN_GUARD_BIND_HARD"] = "1"
    elif hard is False:
        env["KANBAN_GUARD_BIND_HARD"] = "0"
    r = subprocess.run([sys.executable, str(guard), TID, "--workdir", str(repo),
                        "--output-dirs", str(out), "--json"],
                       capture_output=True, text=True, env=env, timeout=600)
    try:
        data = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        data = {"raw": (r.stdout or "")[-400:] + (r.stderr or "")[-400:]}
    return r.returncode, data


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/fake_done_repro")
    # 破壊的操作は自分の作業ルート配下に限定（rm -rf は使わない）
    root = root.resolve()
    if root.exists():
        assert str(root).startswith("/home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch"), \
            f"refusing to clean non-scratch path: {root}"
        shutil.rmtree(root)
    root.mkdir(parents=True)
    repo, out = build(root)
    report = {}
    for label, guard, hard in (("before_soft", GUARD_BAK, None),
                               ("after_soft", GUARD, None),
                               ("after_hard", GUARD, True)):
        rc, d = run_guard(guard, repo, out, hard)
        conds = d.get("conditions", {})
        failing = [k for k, v in conds.items() if not v]
        rec = {"exit": rc, "pass": d.get("pass"), "failing": failing,
               "bind": conds.get("bind:artifact_paths_bound_to_task_diff", "ABSENT"),
               "bind_status": (d.get("detail") or {}).get("bind_status"),
               "bind_note": (d.get("detail") or {}).get("bind_note"),
               "j": conds.get("j:evidence_json_valid"), "n_conditions": len(conds)}
        report[label] = rec
        print(f"--- {label}: exit={rc} pass={rec['pass']} bind={rec['bind']} "
              f"j={rec['j']} failing={failing}")
        if rec["bind_note"]:
            print(f"    bind_note: {rec['bind_note']}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
