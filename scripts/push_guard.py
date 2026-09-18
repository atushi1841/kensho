#!/usr/bin/env python3
"""scripts/push_guard.py — コミット・プッシュ忘れ防止 git フック本体 (t_c2104009)

背景: worker が commit 後 push せずに done を完了 → guard(e) ``unpushed code commits``
で FAIL（QA 最大ボトルネック / t_c1ec5f8b v77）。コミットのタイミングで未pushコードを
検出して自動 push し、push 不可能な場合はコミットをブロック（= 重ね積みを防ぐ）ことで、
guard(e) が FAIL する状態を作らせない。

guard(e) と同一のコード判定規則を踏襲:
  コード = *.py / *.yaml / *.sh / *.js   （.html・data/・reports/ はデータchurn扱いで除外）
  origin/main が解決できない（ローカル専用repo / 未settings）場合は skip（止めない）。

使い方:
  python3 scripts/push_guard.py --stage pre-commit   # 未pushコードがあれば自動push。
                                                      # push 失敗時は exit 1（commit を止めて手動pushを促す）
  python3 scripts/push_guard.py --stage post-commit  # commit 後に自動push。失敗しても警告のみ（exit 0）
  python3 scripts/push_guard.py --selftest           # 隔離repoで動作検証
  python3 scripts/push_guard.py --workdir <path>     # 対象repoを明示（既定 /mnt/d/Project2/kensho）

exit code:
  0 = OK / skip / post-commit警告
  1 = ブロック（pre-commit で未pushコードの push に失敗）
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_WORKDIR = Path("/mnt/d/Project2/kensho")
CODE_SUFFIXES = (".py", ".yaml", ".sh", ".js")
CODE_EXCLUDE_TOPDIRS = ("data", "reports")


def is_code_file(relpath: str) -> bool:
    low = relpath.replace("\\", "/").lower()
    if low.endswith(".html"):
        return False
    if low.split("/", 1)[0] in CODE_EXCLUDE_TOPDIRS:
        return False
    return low.endswith(CODE_SUFFIXES)


def _git(workdir: Path, *args: str) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(workdir), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (OSError, subprocess.SubprocessError):
        return 127, "", "git unavailable"


def unpushed_code_state(workdir: Path) -> dict:
    """guard 条件(e) と同一: origin/main..HEAD がコードファイルに触れる未pushコミットを持つか。

    返り値 {"status": "skip"|"pass"|"fail", "n": int, "note": str}
      - skip: origin/main が解決できない / git 不能（判定不能はブロックしない）
      - pass: 未pushゼロ、または未pushが docs/data のみ
      - fail: 未pushコミットがコードに触れている
    """
    rc, _, _ = _git(workdir, "rev-parse", "--verify", "-q", "origin/main")
    if rc != 0:
        return {"status": "skip", "n": 0, "note": "no origin/main ref — push check skipped"}
    rc, out, _ = _git(workdir, "rev-list", "--count", "origin/main..HEAD")
    if rc != 0 or not out.isdigit():
        return {"status": "skip", "n": 0, "note": f"rev-list origin/main..HEAD failed (rc={rc}) — skipped"}
    n_unpushed = int(out)
    if n_unpushed == 0:
        return {"status": "pass", "n": 0, "note": "0 unpushed commits"}
    rc, names, _ = _git(workdir, "diff", "--name-only", "origin/main..HEAD")
    if rc != 0:
        return {"status": "fail", "n": n_unpushed, "note": "file list unavailable"}
    code_files = sorted({f for f in names.splitlines() if f and is_code_file(f)})
    if not code_files:
        return {"status": "pass", "n": 0, "note": "unpushed commits touch docs/data only — allowed"}
    return {
        "status": "fail",
        "n": n_unpushed,
        "note": f"unpushed code commits: {n_unpushed} ({', '.join(code_files[:5])}...)",
    }


def current_upstream(workdir: Path) -> str | None:
    """現在ブランチの上流（例: 'main'）を返す。無ければ None。"""
    rc, ref, _ = _git(workdir, "rev-parse", "--abbrev-ref", "@{upstream}")
    if rc != 0 or not ref or ref in ("HEAD", "@{upstream}"):
        return None
    # 'origin/main' のブランチ名部分
    return ref.split("/", 1)[1] if "/" in ref else ref


def auto_push(workdir: Path, branch: str) -> tuple[bool, str]:
    """未pushコードを origin へ自動 push。成功/失敗とメッセージを返す。"""
    rc, out, err = _git(workdir, "push", "origin", f"HEAD:{branch}")
    if rc == 0:
        tail = (out or err or "ok").strip().splitlines()
        return True, tail[-1][:160] if tail else "pushed"
    return False, (err or out or "push failed").strip()[:600]


def handle_precommit(workdir: Path) -> int:
    st = unpushed_code_state(workdir)
    branch = current_upstream(workdir)
    if st["status"] == "skip":
        print(f"[push-guard pre-commit] skip: {st['note']}")
        return 0
    if st["status"] == "pass":
        return 0
    # 未pushコードあり → 自動pushを試みる
    print(f"[push-guard pre-commit] {st['note']}")
    if branch is None:
        print(
            "[push-guard pre-commit] BLOCK: no upstream branch configured — "
            "push manually then retry commit (git push -u origin HEAD)"
        )
        return 1
    ok, msg = auto_push(workdir, branch)
    if ok:
        print(f"[push-guard pre-commit] auto-pushed to origin/{branch}: {msg}")
        return 0
    print(f"[push-guard pre-commit] BLOCK: auto-push origin/{branch} failed — {msg}")
    print(
        "[push-guard pre-commit] 手動リカバリ: git push origin HEAD:"
        f"{branch} を実行してから commit を再実行してください。"
    )
    return 1


def handle_postcommit(workdir: Path) -> int:
    st = unpushed_code_state(workdir)
    branch = current_upstream(workdir)
    if st["status"] != "fail" or branch is None:
        return 0  # 未pushコードが無い / push対象不明 → 何もしない
    ok, msg = auto_push(workdir, branch)
    if ok:
        print(f"[push-guard post-commit] auto-pushed origin/{branch}: {msg}")
    else:
        print(f"[push-guard post-commit] WARN: auto-push failed — {msg}")
        print(
            "[push-guard post-commit] guard(e) で FAIL しないよう、",
            "あとで git push origin HEAD:",
            branch,
            " してください。",
        )
    return 0  # commit 完了後はブロックしない（exit 1 では commit は元に戻らない）


def selftest() -> int:
    """隔離 temp repo で (1) 未pushコード検出 (2) 自動push (3) ブロック/logic を検証する。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remote = root / "remote.git"
        repo = root / "repo"
        # 共有 bare remote を作る
        rc, _, err = _git(root, "init", "--bare", "-q", str(remote))
        if rc != 0:
            print("SELFTEST FAIL: cannot init bare remote:", err)
            return 1
        rc, _, err = _git(root, "init", "-q", str(repo))
        if rc != 0:
            print("SELFTEST FAIL: cannot init repo:", err)
            return 1
        for cmd in [
            ["config", "user.email", "test@example.com"],
            ["config", "user.name", "guard-test"],
            ["remote", "add", "origin", str(remote)],
        ]:
            rc, _, err = _git(repo, *cmd)
            if rc != 0:
                print("SELFTEST FAIL:", cmd, err)
                return 1
        # 初期 main を push して origin/main を作る
        (repo / "readme.md").write_text("base\n", encoding="utf-8")
        rc, _, err = _git(repo, "add", ".")
        if rc != 0:
            print("SELFTEST FAIL: add:", err)
            return 1
        rc, _, err = _git(repo, "commit", "-m", "base")
        if rc != 0:
            print("SELFTEST FAIL: base commit:", err)
            return 1
        rc, _, err = _git(repo, "branch", "-M", "main")
        if rc != 0:
            print("SELFTEST FAIL: branch -M:", err)
            return 1
        rc, _, err = _git(repo, "push", "-u", "origin", "main")
        if rc != 0:
            print("SELFTEST FAIL: initial push:", err)
            return 1

        def check(fn, label: str, want: int) -> bool:
            got = fn(repo)
            ok = got == want
            print(f"  [{label}] want={want} got={got} -> {'OK' if ok else 'FAIL'}")
            return ok

        # (1) コード未pushが存在する状態で pre-commit を実行 → 自動push成功し exit 0
        (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        rc, _, _ = _git(repo, "add", ".")
        rc, _, _ = _git(repo, "commit", "-m", "code 1")
        if rc != 0:
            print("SELFTEST FAIL: 'code 1' commit rc!=0 rc=", rc)
            return 1
        st = unpushed_code_state(repo)
        if st["status"] != "fail":
            print("SELFTEST FAIL: expected unpushed fail after code commit, got", st)
            return 1
        (repo / "app.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n", encoding="utf-8")
        rc, _, _ = _git(repo, "add", ".")
        if not check(handle_precommit, "pre-commit(auto-push prior)", 0):
            return 1
        rc, _, _ = _git(repo, "commit", "-m", "code 2")
        if rc != 0:
            print("SELFTEST FAIL: commit 'code 2' rc != 0, rc=", rc)
            return 1
        # commit 産生後: 新コミット(code 2)が未push → post-commit が自動push
        if not check(handle_postcommit, "post-commit(push new)", 0):
            return 1
        st_after = unpushed_code_state(repo)
        if st_after["status"] != "pass":
            print("SELFTEST FAIL: after post-commit auto-push expected pass, got", st_after)
            return 1

        # (2) docs/data のみ未push → pass（ブロックしない）
        data = repo / "data"
        data.mkdir()
        (data / "churn.json").write_text("{}", encoding="utf-8")
        (repo / "notes.md").write_text("note", encoding="utf-8")
        rc, _, _ = _git(repo, "add", ".")
        rc, _, _ = _git(repo, "commit", "-m", "docs only")
        st_docs = unpushed_code_state(repo)
        if st_docs["status"] != "pass":
            print("SELFTEST FAIL: docs/data-only should pass, got", st_docs)
            return 1
        print("  [docs-only] status=pass -> OK")

        print("SELFTEST OK: unpushed detection + auto-push + docs-exclusion behave as guard(e).")
        return 0
    return 1  # unreachable


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="commit/push 忘れ防止 git hook")
    ap.add_argument("--stage", choices=["pre-commit", "post-commit"], default="pre-commit")
    ap.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    workdir = args.workdir
    if not workdir.is_dir():
        print(f"[push-guard] workdir not found: {workdir} — skip (exit 0)")
        return 0

    if args.stage == "pre-commit":
        return handle_precommit(workdir)
    return handle_postcommit(workdir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
