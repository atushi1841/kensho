#!/bin/sh
# sh<->python polyglot header: `bash scripts/git_stale_lock_guard.py ...`,
# `python3 scripts/git_stale_lock_guard.py ...`, `./scripts/git_stale_lock_guard.py ...`
# のいずれでも動作する（scripts/kanban_done_guard.py と同一パターン）。
''':'
exec python3 "$0" "$@"
'''
"""
scripts/git_stale_lock_guard.py — stale .git/index.lock 自動検知・復旧ガード (t_f01a3a9e)

背景 (2026-09-30):
  共有リポジトリ /mnt/d/Project2/kensho/.git/index.lock が同日2回 stale 発生
  （16:02起・約15分残留 / 16:53起・約55分残留）。いずれも git プロセス無し・0バイトで、
  `git add -n ...` が `fatal: Unable to create '.../.git/index.lock': File exists.`
  で即死し、commit/push 系の全作業を阻害していた（復旧は手動 rm）。

  既存の回収処理 kensho_github_sync.py::reclaim_stale_index_lock は github_sync の
  commit リトライ内部からしか呼ばれないため、「素の git 操作の入口」では無防備だった。
  本ガードは **単一ファイル** で、任意の commit/push 入口から呼べる形に実装している
  （既存共有スクリプトは編集せず、ロールバック = 本ファイルの削除のみ）。

検知条件（3条件すべて満たすときだけ stale とみなして自動削除する）:
  1. `<gitdir>/<lock>` が存在する
  2. 作成後 age_threshold 秒以上（既定 600秒 = 10分）
  3. 保持者がいない — 以下をいずれも検出しない
     a. /proc/*/fd で lock を開いているプロセス（index.lock は open 継続中）
     b. repo 内で動いている git プロセス（argv0=git かつ cwd/argv が repo を指す）
  加えて削除直前に stat を再取得し (dev, inode, mtime_ns) が一致することを確認する
  （確認中に別の git が作り直した lock を誤って消さないための TOCTOU 対策）。
  年齢不足・保持者ありは「削除しない」だけで、git 操作を止めているのは本ガードではなく
  lock 自体である（exit 2 = まだ commit/push してはいけない）。

使い方:
  # 1) そのまま（検知・ログ・自動削除のみ）
  python3 scripts/git_stale_lock_guard.py

  # 2) commit/push の入口としてガード経由で実行（lock が残っていれば実行しない）
  python3 scripts/git_stale_lock_guard.py --run "git add -A && git commit -m 'msg'"
  python3 scripts/git_stale_lock_guard.py --run "git push origin main"

  # 3) 参考: 何も消さずに検知だけ確認（stale なら status=stale_dry_run / exit 2）
  python3 scripts/git_stale_lock_guard.py --dry-run --json

  # 4) 自己検証（一時ディレクトリに lock を模擬して検知→削除を実測）
  python3 scripts/git_stale_lock_guard.py --selftest

ログ:
  既定 `<repo>/logs/git_stale_lock_guard.log` へ1行追記（logs/ は .gitignore 済み）。
  同時に stdout へも同じ1行を出力する（--json 時は JSON を出力）。

exit code:
  0 = lock 無し / stale を削除済み → commit/push へ進んで良い
  1 = エラー（対象が git repo でない、引数不正、ログ不能など）
  2 = lock が残っている（新しすぎる / 保持者あり / dry-run で未削除）→ git 操作を止めろ
  --run 指定時は、ガードが 0 を返した場合のみコマンドを実行し、その rc をそのまま返す。

ロールバック: 本ファイルの削除のみ（既存ファイルへの変更は一切無い）。
"""

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 作成後10分以上・親 git プロセス無し のときだけ stale とみなす（タスク受入基準）
DEFAULT_AGE_SEC = 600
DEFAULT_LOG_REL = "logs/git_stale_lock_guard.log"
RETRY_INTERVAL_SEC = 2.0

EXIT_OK = 0  # lock 無し or stale 削除済み → git 操作へ進んで良い
EXIT_ERROR = 1  # エラー
EXIT_HELD = 2  # lock 残存（新しすぎる / 保持者あり / dry-run で未削除）→ git 操作NG

STATUS_NO_LOCK = "no_lock"
STATUS_REMOVED = "removed"
STATUS_YOUNG = "young"
STATUS_HELD = "held"
STATUS_CHANGED = "changed"
STATUS_DRY_RUN = "stale_dry_run"
STATUS_ERROR = "error"

SELF_PID = os.getpid()


# ---------------------------------------------------------------------------
# リポジトリ / lock パス
# ---------------------------------------------------------------------------
def resolve_git_dir(repo: Path) -> Path | None:
    """.git が dir ならそのまま、gitfile(worktree)なら内側の gitdir を返す。無ければ None."""
    git = repo / ".git"
    if git.is_dir():
        return git
    if git.is_file():
        try:
            text = git.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None
        if text.startswith("gitdir:"):
            raw = text.split(":", 1)[1].strip()
            p = Path(raw)
            return (p if p.is_absolute() else (repo / p)).resolve()
    return None


def find_repo(explicit: str | None) -> Path:
    """--repo 無し時は「本ファイルの祖 repo」→ cwd 上方向の順で .git を探す。"""
    if explicit:
        return Path(explicit).expanduser().resolve()
    for start in (Path(__file__).resolve().parent, Path.cwd()):
        cur = start.resolve()
        for cand in (cur, *cur.parents):
            if (cand / ".git").exists():
                return cand
    return Path.cwd()


# ---------------------------------------------------------------------------
# 保持者検出（親 git プロセス無し条件）
# ---------------------------------------------------------------------------
def lock_holders(lock: Path) -> list[int]:
    """/proc/*/fd を走査して lock を開いているプロセスの pid を返す（無いなら空）."""
    target = os.path.realpath(str(lock))
    pids: list[int] = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return pids
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            fds = list((entry / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                if os.path.realpath(os.readlink(fd)) == target:
                    pids.append(int(entry.name))
                    break
            except OSError:
                continue
    return sorted(pids)


def git_processes(repo: Path, git_dir: Path) -> list[str]:
    """repo 内で動いている git プロセス（pid=cmdline）を返す。

    任意プロセスは対象外（worker 本体が repo を cwd にしていても誤検知しないよう、
    argv0 が git / git.exe のものに限定し、さらに cwd または argv が repo を指すものだけ採用）。
    """
    repo_s = str(repo.resolve())
    gitdir_s = str(git_dir)
    found: list[str] = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == SELF_PID or pid == os.getppid():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        args = [a for a in raw.decode("utf-8", "replace").split("\0") if a]
        if not args:
            continue
        if os.path.basename(args[0]) not in ("git", "git.exe"):
            continue
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        in_repo = (
            cwd == repo_s
            or cwd.startswith(repo_s + os.sep)
            or any((repo_s in a) or (gitdir_s in a) for a in args[1:])
        )
        if in_repo:
            found.append(f"{pid}={' '.join(args)[:120]}")
    return found


# ---------------------------------------------------------------------------
# 検知本体
# ---------------------------------------------------------------------------
def classify(repo: Path, lock_name: str, age_threshold: float, dry_run: bool) -> dict:
    """lock を評価して 1件の記録（dict）を返す。削除は dry_run=False のときだけ行う。"""
    rec: dict = {
        "status": STATUS_ERROR,
        "repo": str(repo),
        "git_dir": "",
        "lock": "",
        "age_sec": None,
        "size": None,
        "holders": [],
        "git_procs": [],
        "threshold_sec": age_threshold,
        "dry_run": dry_run,
        "removed": False,
        "message": "",
    }
    git_dir = resolve_git_dir(repo)
    if git_dir is None:
        rec["message"] = f"git リポジトリではない（.git 不在）: {repo}"
        return rec
    rec["git_dir"] = str(git_dir)

    lock = git_dir / lock_name
    rec["lock"] = str(lock)
    if lock.is_symlink():
        rec["message"] = f"lock がシンボリックリンクなので触らない: {lock}"
        return rec
    if not lock.exists():
        rec["status"] = STATUS_NO_LOCK
        rec["message"] = f"{lock_name} なし → commit/push へ進んで良い"
        return rec

    try:
        st = lock.stat()
    except OSError as exc:
        rec["message"] = f"lock の stat に失敗: {exc}"
        return rec
    age = time.time() - st.st_mtime
    rec["age_sec"] = round(age, 1)
    rec["size"] = st.st_size

    # 条件2: 年齢ゲート（ここを通過したものだけ削除候補）
    if age < age_threshold:
        rec["status"] = STATUS_YOUNG
        rec["holders"] = lock_holders(lock)
        rec["git_procs"] = git_processes(repo, git_dir)
        rec["message"] = (
            f"{lock_name} は新しい（age={int(age)}s < {int(age_threshold)}s）→ 削除しない"
            f"（保持者={rec['holders'] or '-'} git={len(rec['git_procs'])}件）"
        )
        return rec

    # 条件3: 親 git プロセス無し
    holders = lock_holders(lock)
    procs = git_processes(repo, git_dir)
    rec["holders"] = holders
    rec["git_procs"] = procs
    if holders or procs:
        rec["status"] = STATUS_HELD
        rec["message"] = (
            f"{lock_name} は保持中のまま age={int(age)}s → 削除しない"
            f"（holders={holders or '-'} git={procs or '-'}）"
        )
        return rec

    if dry_run:
        rec["status"] = STATUS_DRY_RUN
        rec["message"] = (
            f"stale {lock_name} を検知（age={int(age)}s >= {int(age_threshold)}s・保持者なし）"
            f" — dry-run のため未削除"
        )
        return rec

    # TOCTOU: 削除直前に同一の lock であることを再確認（作り直されたら手を引く）
    try:
        st2 = lock.stat()
    except OSError:
        rec["status"] = STATUS_NO_LOCK
        rec["message"] = f"{lock.name} は確認中に消えた（他処理が回収済み）→ OK"
        return rec
    if (st2.st_dev, st2.st_ino, st2.st_mtime_ns) != (st.st_dev, st.st_ino, st.st_mtime_ns):
        rec["status"] = STATUS_CHANGED
        rec["message"] = f"{lock.name} が検知中に更新された → 削除を中止（念のため残す）"
        return rec
    if lock_holders(lock):
        rec["status"] = STATUS_HELD
        rec["message"] = f"{lock.name} に保持者が出現した → 削除を中止"
        return rec

    try:
        lock.unlink()
    except OSError as exc:
        rec["message"] = f"stale {lock_name} の削除に失敗: {exc}"
        return rec
    rec["status"] = STATUS_REMOVED
    rec["removed"] = True
    rec["message"] = (
        f"stale {lock_name} を自動削除（age={int(age)}s >= {int(age_threshold)}s・"
        f"保持プロセスなし・{st.st_size}バイト）→ git 操作を再開して良い"
    )
    return rec


def exit_code_for(status: str) -> int:
    if status in (STATUS_NO_LOCK, STATUS_REMOVED):
        return EXIT_OK
    if status == STATUS_ERROR:
        return EXIT_ERROR
    # young / held / changed / stale_dry_run = lock が残っている
    return EXIT_HELD


def format_line(rec: dict) -> str:
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    holders = ",".join(str(p) for p in rec.get("holders") or []) or "-"
    gprocs = str(len(rec.get("git_procs") or []))
    age = rec.get("age_sec")
    return (
        f"{stamp} [{rec['status']}] repo={rec['repo']} lock={rec['lock']} "
        f"age={'-' if age is None else str(age) + 's'} size={rec.get('size')} "
        f"threshold={int(rec['threshold_sec'])}s holders={holders} git_procs={gprocs} "
        f"pid={SELF_PID} | {rec['message']}"
    )


def emit(rec: dict, as_json: bool, log_file: Path | None) -> None:
    line = format_line(rec)
    if as_json:
        print(json.dumps(rec, ensure_ascii=False))
    else:
        print(line)
    if log_file is None:
        return
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"[warn] ログ書き込みに失敗（続行する）: {log_file}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 自己検証（一時 repo に lock を模擬 → 検知/不削除を実測）
# ---------------------------------------------------------------------------
def _selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="stale_lock_guard_"))
    repo = tmp / "repo"
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)
    try:
        subprocess.run(
            ["git", "init", "-q", str(repo)], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        pass

    log_file = repo / DEFAULT_LOG_REL
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # 1) lock 無し → no_lock / exit 0
    rec = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=False)
    add("no lock", rec["status"] == STATUS_NO_LOCK and exit_code_for(rec["status"]) == EXIT_OK,
        f"status={rec['status']} exit={exit_code_for(rec['status'])}")

    # 2) 720秒古くて保持者なし → 削除される / exit 0
    lock = git_dir / "index.lock"
    lock.write_bytes(b"")
    old = time.time() - 720
    os.utime(lock, (old, old))
    rec = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=False)
    add("stale lock removed",
        rec["status"] == STATUS_REMOVED and not lock.exists()
        and exit_code_for(rec["status"]) == EXIT_OK,
        f"status={rec['status']} lock_exists={lock.exists()} "
        f"age={rec['age_sec']}s exit={exit_code_for(rec['status'])}")

    # 3) 作りたて（age=0s）→ 削除しない / exit 2
    lock.write_bytes(b"")
    rec = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=False)
    add("fresh lock kept",
        rec["status"] == STATUS_YOUNG and lock.exists()
        and exit_code_for(rec["status"]) == EXIT_HELD,
        f"status={rec['status']} lock_exists={lock.exists()} "
        f"age={rec['age_sec']}s exit={exit_code_for(rec['status'])}")

    # 4) 古いが fd を保持プロセスあり → 削除しない / exit 2
    old = time.time() - 720
    os.utime(lock, (old, old))
    holder_pid = os.fork()
    if holder_pid == 0:  # 子プロセス: lock を開いたまま待つ
        fd = os.open(str(lock), os.O_RDONLY)
        time.sleep(30)
        os.close(fd)
        os._exit(0)
    try:
        time.sleep(0.3)
        rec = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=False)
        add("held lock kept",
            rec["status"] == STATUS_HELD and lock.exists()
            and exit_code_for(rec["status"]) == EXIT_HELD,
            f"status={rec['status']} lock_exists={lock.exists()} holders={rec['holders']} "
            f"exit={exit_code_for(rec['status'])}")
    finally:
        os.kill(holder_pid, signal.SIGKILL)
        os.waitpid(holder_pid, 0)

    # 5) dry-run: 検知するが消さない / exit 2
    lock.write_bytes(b"")
    old = time.time() - 720
    os.utime(lock, (old, old))
    rec = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=True)
    add("dry-run detects but keeps",
        rec["status"] == STATUS_DRY_RUN and lock.exists()
        and exit_code_for(rec["status"]) == EXIT_HELD,
        f"status={rec['status']} lock_exists={lock.exists()} "
        f"age={rec['age_sec']}s exit={exit_code_for(rec['status'])}")

    # 6) ログが実際に追記されていること
    rec2 = classify(repo, "index.lock", DEFAULT_AGE_SEC, dry_run=False)
    emit(rec2, as_json=False, log_file=log_file)
    logged = log_file.is_file() and log_file.read_text(encoding="utf-8").count("\n") >= 1
    add("log written", logged, f"log_file={log_file} exists={log_file.is_file()}")

    lock.unlink(missing_ok=True)
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"selftest: {passed}/{len(checks)} PASS")
    return 0 if passed == len(checks) else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="stale .git/index.lock を（作成後10分以上・親gitプロセス無しのときだけ）"
                    "検知してログ出力＋自動削除する commit/push 入口ガード",
    )
    p.add_argument("--repo", help="対象リポジトリ（既定: 本ファイルの祖 repo → cwd 上方向）")
    p.add_argument("--lock", default="index.lock", help="lock ファイル名（既定: index.lock）")
    p.add_argument("--age", type=float, default=DEFAULT_AGE_SEC, dest="age",
                   help=f"stale とみなす秒数（既定: {DEFAULT_AGE_SEC} = 10分）")
    p.add_argument("--wait", type=float, default=0.0,
                   help="held/young のとき再試行する最大秒数（既定: 0 = 1回判定）")
    p.add_argument("--dry-run", action="store_true",
                   help="検知・ログのみ（削除しない）。stale でも exit 2")
    p.add_argument("--json", action="store_true", help="結果を JSON 1行で標準出力")
    p.add_argument("--log-file", default=None,
                   help=f"ログ先（既定: <repo>/{DEFAULT_LOG_REL} / '-' でログ無効）")
    p.add_argument("--run", default=None, dest="run", metavar="CMD",
                   help="ガードが exit 0 のときだけ shell で実行するコマンド"
                        "（commit/push の入口として使う）")
    p.add_argument("--selftest", action="store_true",
                   help="一時 repo で lock を模擬し、検知→削除を自己検証する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.age <= 0:
        print("error: --age は正の秒数を指定", file=sys.stderr)
        return EXIT_ERROR

    repo = find_repo(args.repo)
    if args.log_file == "-":
        log_file: Path | None = None
    elif args.log_file:
        log_file = Path(args.log_file).expanduser()
    else:
        log_file = repo / DEFAULT_LOG_REL

    deadline = time.monotonic() + max(0.0, args.wait)
    rec: dict = {}
    rc = EXIT_ERROR
    while True:
        rec = classify(repo, args.lock, args.age, dry_run=args.dry_run)
        emit(rec, as_json=args.json, log_file=log_file)
        rc = exit_code_for(rec["status"])
        if rc == EXIT_OK or rec["status"] == STATUS_ERROR or time.monotonic() >= deadline:
            break
        time.sleep(min(RETRY_INTERVAL_SEC, max(0.0, deadline - time.monotonic())))

    if rc != EXIT_OK:
        if args.run and not args.json:
            print(f"[guard] lock 残存のためコマンドを実行しない (rc={rc}): {args.run}")
        return rc

    if args.run:
        print(f"[guard] run: {args.run}")
        proc = subprocess.run(args.run, shell=True)
        print(f"[guard] command exited rc={proc.returncode}")
        return proc.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
