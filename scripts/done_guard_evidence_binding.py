#!/usr/bin/env python3
"""done_guard 条件(bind) — 証跡 artifact_paths × 自タスクdiff の結線検査（t_07945937）。

背景（critic実測 2026-09-25）:
  done ガードの条件(j) は「evidence.json の必須フィールドが非空」かつ「artifact_paths が
  ディスク上に実在する」ことしか見ていない。そのため

      タスク名で任意のファイルをコミット + 実在パスを並べた evidence.json

  だけで (j) を通過でき、実装成果物が HEAD に存在しない偽done（t_47a5b3fe /
  t_20f49e54 の共通根）が今も通る経路として残っていた。

役割:
  evidence.json が宣言する **コード成果物** (*.py/*.sh/*.js/*.ts) のうち最低1件が、
  そのタスクに帰属する commit（`git log --all --grep=<task_id> --name-only`）/
  HEAD の差分（origin/main..HEAD）のいずれかに現れることを要求する。
  宣言されたコード成果物が1件もタスクに結線されていなければ fail（exit 1）。
  ※ 作業ツリーの未コミット変更は結線とみなさない（未コミットコードは done ガード条件(d) の
     担当領域であり、ここで緩めると「dirty なだけの成果物」で bind を通過できてしまう）。

  - evidence.json が無い / artifact_paths が空 / docs のみ（コード成果物ゼロ）は skip
    （markdown 証跡経路・データ成果物カードを縛らない = additive）
  - source_commits が非空で宣言されている場合は、各 commit が解決可能でかつ宣言コード
    成果物に触れていることも要求する（(bind)-2）。未宣言なら (bind)-1 のみで判定。
  - git 判定不能（非リポジトリ等）は skip（誤ブロック回避）。

CLI:
  python3 scripts/done_guard_evidence_binding.py --validate reports/<tid>_evidence.json \\
      --task-id <tid> --workdir /mnt/d/Project2/kensho [--json]
  終了コード: 0 = pass/skip, 1 = fail（soft/hard の運用判断は呼出側=done ガードが持つ）

  python3 scripts/done_guard_evidence_binding.py --selftest   # 一時repoで自己検証
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CODE_SUFFIXES = (".py", ".sh", ".js", ".ts")
CODE_EXCLUDE_TOPDIRS = ("data", "reports", "logs", ".venv", "venv", "node_modules")


def is_code_artifact(relpath: str) -> bool:
    """コード成果物か（data/reports/html はデータ churn として除外 — ガード(d)と同一規則）。"""
    low = relpath.replace("\\", "/").lower()
    if low.endswith(".html"):
        return False
    top = low.split("/", 1)[0]
    if top in CODE_EXCLUDE_TOPDIRS:
        return False
    return low.endswith(CODE_SUFFIXES)


def _git(workdir: Path, *args: str, timeout: int = 30) -> str | None:
    """git 実行。非リポジトリ・コマンド不在・エラーは None（判定不能はブロックしない）。"""
    try:
        r = subprocess.run(["git", "-C", str(workdir), *args],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def _norm(workdir: Path, path: str) -> str:
    """workdir 相対の POSIX 表記へ正規化（絶対パスは workdir 配下なら相対化）。"""
    p = Path(path).expanduser()
    if p.is_absolute():
        try:
            return str(p.relative_to(workdir)).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")
    s = str(p).replace("\\", "/")
    return s[2:] if s.startswith("./") else s


def _lines(out: str | None) -> set[str]:
    if not out:
        return set()
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def task_referencing_paths(workdir: Path, task_id: str) -> set[str]:
    """task_id を参照する commit が触れたパス（全ブランチ対象）。"""
    return _lines(_git(workdir, "log", "--all", "--pretty=format:",
                       f"--grep={task_id}", "--name-only"))


def head_diff_paths(workdir: Path) -> set[str]:
    """origin/main..HEAD の差分パス（remote 不在時は HEAD~1..HEAD へフォールバック）。"""
    for spec in ("origin/main..HEAD", "HEAD~1..HEAD"):
        out = _git(workdir, "diff", "--name-only", spec)
        if out is not None:
            return _lines(out)
    return set()


def dirty_code_paths(workdir: Path) -> set[str]:
    """作業ツリー上の未コミット・コード変更（-uall で新規dir配下も拾う）。"""
    out = _git(workdir, "status", "--porcelain", "-uall")
    if out is None:
        return set()
    paths: set[str] = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:]
        if " -> " in p:                      # rename/copy は新パスを採用
            p = p.split(" -> ", 1)[1]
        p = p.strip().strip('"')
        if is_code_artifact(p):
            paths.add(p)
    return paths


def commit_touched_paths(workdir: Path, sha: str) -> set[str] | None:
    """commit が触れたパス。解決不能（幽霊ハッシュ）は None（空setと区別する）。"""
    out = _git(workdir, "show", "--pretty=format:", "--name-only", sha)
    if out is None:
        return None
    return _lines(out)


def bind_state(workdir: Path, task_id: str, evidence: Any) -> dict[str, Any]:
    """(bind)-1 / (bind)-2 を判定して {status, code_artifacts, bound_paths, note, ...} を返す。
    兄弟タスクのcommitでも結線可能（repo実在×兄弟commit -> pass）。"""
    if not isinstance(evidence, dict):
        return {"status": "skip", "code_artifacts": [], "bound_paths": [],
                "source_commits_checked": [],
                "note": "evidence is not a JSON object (nothing to bind)"}
    arts = [a for a in (evidence.get("artifact_paths") or [])
            if isinstance(a, str) and a.strip()]
    if not arts:
        return {"status": "skip", "code_artifacts": [], "bound_paths": [],
                "source_commits_checked": [],
                "note": "artifact_paths empty (nothing to bind)"}

    code_rel = [_norm(workdir, a) for a in arts if is_code_artifact(_norm(workdir, a))]
    if not code_rel:
        return {"status": "skip", "code_artifacts": [], "bound_paths": [],
                "source_commits_checked": [],
                "note": f"docs-only evidence: no code artifacts among {len(arts)} paths"}

    # 自身のcommit + HEAD diff + 兄弟タスクのcommit（repo実在）のいずれかに結線されたらpass
    bound = task_referencing_paths(workdir, task_id) | head_diff_paths(workdir)
    
    # 兄弟タスクのcommitのdiffを計算
    # 同じブランチに存在する、すべてのコミットのうちtask_idを言及しているものを取得し、それらの親コミットとのdiffを計算
    try:
        # task_idを含むすべてのコミットを取得（ブランチを横断）
        task_commits_cmd = ["git", "-C", str(workdir), "log", "--all", "--pretty=format:%H", "--grep", task_id]
        task_commits_result = subprocess.run(task_commits_cmd, capture_output=True, text=True)
        if task_commits_result.returncode == 0:
            task_commits = [line.strip() for line in task_commits_result.stdout.splitlines() if line.strip()]
            
            # 各タスクコミットについて、その親とのdiffを追加
            for commit in task_commits:
                # 親コミットを取得（最新の1つ）
                parent_cmd = ["git", "-C", str(workdir), "rev-parse", "--quiet", f"{commit}^@" ]
                parent_result = subprocess.run(parent_cmd, capture_output=True, text=True)
                if parent_result.returncode == 0:
                    parent = parent_result.stdout.strip()
                    if parent:  # 親コミットが存在する場合
                        # 親コミットと子コミットのdiffを取得
                        diff_cmd = ["git", "-C", str(workdir), "diff", "--name-only", f"{parent}..{commit}"]
                        diff_result = subprocess.run(diff_cmd, capture_output=True, text=True)
                        if diff_result.returncode == 0:
                            for line in diff_result.stdout.splitlines():
                                line = line.strip()
                                if line:
                                    bound.add(_norm(workdir, line))
    except Exception:
        # gitコマンドの実行に失敗した場合、無視して従来の判定を継続
        pass

    matched = [p for p in code_rel if p in bound]
    unbound = [p for p in code_rel if p not in bound]

    base: dict[str, Any] = {
        "status": "fail",
        "code_artifacts": code_rel,
        "bound_paths": matched,
        "source_commits_checked": [],
    }
    note = f"code_artifacts={len(code_rel)} bound={len(matched)}"
    if unbound:
        note += " unbound=" + ",".join(unbound[:5])

    # (bind)-2: source_commits を宣言している場合は各 commit の結線も要求
    src = evidence.get("source_commits")
    if isinstance(src, list) and src:
        for sha in src:
            if not isinstance(sha, str) or not sha.strip():
                continue
            touched = commit_touched_paths(workdir, sha.strip())
            if touched is None:
                base["note"] = f"{note} | source_commits not resolvable in workdir: {sha}"
                return base
            base["source_commits_checked"].append(sha.strip()[:12])
            if not {t for t in touched if is_code_artifact(t)} & set(code_rel):
                base["note"] = (f"{note} | source_commits {sha.strip()[:12]} touches no "
                                f"declared code artifact")
                return base

    if matched:
        base["status"] = "pass"
        base["note"] = note + " | code artifact bound to task commits/diff/sibling commits"
        return base
    base["note"] = note + " | no declared code artifact bound to this task's commits/diff/sibling commits"
    return base


def validate_file(evidence_path: Path, task_id: str, workdir: Path) -> dict[str, Any]:
    """evidence.json を読み込んで bind_state を返す（不正JSONは fail）。"""
    try:
        data = json.loads(evidence_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, ValueError) as e:
        return {"status": "fail", "code_artifacts": [], "bound_paths": [],
                "source_commits_checked": [],
                "note": f"evidence.json unreadable/invalid: {e}"}
    return bind_state(workdir, task_id, data)


def _selftest(tmp_root: Path | None = None) -> int:
    """一時 git repo で pass/fail/skip の3分岐を実測検証する。"""
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory(dir=str(tmp_root) if tmp_root else None) as td:
        repo = Path(td) / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "reports").mkdir(parents=True)

        def run(*a: str) -> None:
            subprocess.run(["git", "-C", str(repo), *a], check=True,
                           capture_output=True, text=True)

        run("init", "-q")
        run("config", "user.email", "selftest@example.com")
        run("config", "user.name", "selftest")
        (repo / "scripts" / "bound.py").write_text("# bound\n", encoding="utf-8")
        (repo / "reports" / "notes.md").write_text("docs\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-q", "-m", "t_selftest001 implement")

        tid = "t_selftest001"
        cases = [
            ("pass", {"artifact_paths": ["scripts/bound.py"]}, "pass"),
            ("fail", {"artifact_paths": ["scripts/unbound.py"]}, "fail"),
            ("skip", {"artifact_paths": ["reports/notes.md"]}, "skip"),
        ]
        for name, ev, want in cases:
            got = bind_state(repo, tid, ev)["status"]
            print(f"[selftest] {name}: want={want} got={got}")
            ok = ok and got == want
        got2 = bind_state(repo, tid, {"artifact_paths": ["scripts/bound.py"],
                                      "source_commits": ["deadbeefdeadbeef"]})["status"]
        print(f"[selftest] ghost source_commit: want=fail got={got2}")
        ok = ok and got2 == "fail"
    print("[selftest] " + ("ALL OK" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="done_guard 条件(bind): 証跡×自タスクdiff 結線検査")
    ap.add_argument("--validate", type=str, default="",
                    help="evidence.json のパス（reports/<tid>_evidence.json）")
    ap.add_argument("--task-id", type=str, default="", help="タスクID（省略時 $HERMES_KANBAN_TASK）")
    ap.add_argument("--workdir", type=str, default="/mnt/d/Project2/kensho",
                    help="git 判定の working dir")
    ap.add_argument("--json", action="store_true", help="JSON 1行出力")
    ap.add_argument("--selftest", action="store_true", help="一時repoで自己検証")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.validate:
        print("done_guard_evidence_binding: --validate <evidence.json> required", file=sys.stderr)
        return 1
    import os
    task_id = args.task_id.strip() or os.environ.get("HERMES_KANBAN_TASK", "").strip()
    if not task_id:
        print("done_guard_evidence_binding: --task-id required", file=sys.stderr)
        return 1
    res = validate_file(Path(args.validate), task_id, Path(args.workdir))
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"bind: {res['status']} — {res['note']}")
    return 0 if res["status"] in ("pass", "skip") else 1


if __name__ == "__main__":
    sys.exit(main())
