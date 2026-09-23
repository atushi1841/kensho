#!/usr/bin/env python3
"""Kensho 稼働サマリー GitHub自動同期.

毎日23:55に実行される想定で、当日の稼働ログ・収集・応募・AIチームKanban完了タスク・
収益データを集計した日次レポート (Markdown) を生成し、
GitHub リポジトリ atushi1841/kensho の docs/daily_reports/YYYY-MM-DD.md に commit & push する。

データソース（すべて存在しなくても部分的に動作する）:
  - logs/auto_YYYYMMDD.log            → 応募完了「N成功/Mエラー」集計
  - logs/YYYY-MM-DD/ の orchestrator ログ → 実行回数
  - data/collected_today.json         → 当日収集件数
  - data/daily_counts.json            → アカウント別応募アクション数
  - /home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db → 当日完了タスク
  - data/revenue-daily.json           → 収益サマリー

出力先ディレクトリ: docs/daily_reports/（リポジトリルート相対）

使い方:
    python3 kensho_github_sync.py            # 当日分 生成＋push
    python3 kensho_github_sync.py --dry-run  # 生成のみ、push/commit しない
    python3 kensho_github_sync.py --date 2026-09-22   # 指定日の分
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Any

BASE = Path(__file__).resolve().parent
KANBAN_DB = Path("/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db")
OUTPUT_DIR_REL = Path("docs") / "daily_reports"  # リポジトリルート相対 → 絶対は BASE/...

REMOTE = "origin"
REMOTE_URL = "https://github.com/atushi1841/kensho.git"


# ---------------------------------------------------------------------------
# データ収集ヘルパー
# ---------------------------------------------------------------------------

def parse_auto_apply(log: Path) -> dict:
    """auto_YYYYMMDD.log から応募完了行の 成功/エラー/警告 を集計する."""
    stats = {"session_lines": 0, "ok": 0, "err": 0, "warn": 0, "patterns": {}}
    if not log.exists():
        return stats
    text = log.read_text(encoding="utf-8", errors="ignore")
    stats["session_lines"] = len(text.splitlines())
    for m in re.finditer(r"完了[：:]\s*([0-9]+)成功[／/]([0-9]+)エラー", text):
        stats["ok"] += int(m.group(1))
        stats["err"] += int(m.group(2))
    stats["warn"] = len(re.findall(r"警告", text))
    for pat in ("BOT", "FALLBACK", "ConnectTimeout", "ログイン失敗"):
        stats["patterns"][pat] = len(re.findall(pat, text))
    return stats


def count_orchestrator_runs(day_dir: Path) -> int:
    """logs/YYYY-MM-DD/ にある orchestrator_*.log の数を数える."""
    if not day_dir.exists():
        return 0
    return len(list(day_dir.glob("orchestrator_*.log")))


def load_json(path: Path) -> list | dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_collected(collected: list | None) -> int:
    if isinstance(collected, list):
        return len(collected)
    return 0


def sum_actions(counts: dict | None) -> dict:
    """daily_counts.json のアカウント別アクション数を合計する."""
    out: dict = {"accounts": 0, "follow": 0, "rt": 0, "like": 0, "reply": 0}
    if not isinstance(counts, dict):
        return out
    accts = counts.get("counts", {})
    out["accounts"] = len(accts)
    for a, v in accts.items() if isinstance(accts, dict) else []:
        out["follow"] += int(v.get("follow", 0))
        out["rt"] += int(v.get("rt", 0))
        out["like"] += int(v.get("like", 0))
        out["reply"] += int(v.get("reply", 0))
    return out


def completed_kanban_tasks(day_start_epoch: int, day_end_epoch: int) -> list[dict]:
    """当日に完了(done)した Kanban タスクを取得する."""
    if not KANBAN_DB.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{KANBAN_DB}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT id,title,status,priority,created_by,completed_at,result "
            "FROM tasks WHERE status='done' AND completed_at>=? AND completed_at<? "
            "ORDER BY completed_at",
            (int(day_start_epoch), int(day_end_epoch)),
        ).fetchall()
        con.close()
    except Exception:
        return []
    tasks = []
    for r in rows:
        tasks.append({
            "id": r[0],
            "title": r[1] or "",
            "priority": int(r[3] or 0),
            "created_by": r[4],
            "completed_at": datetime.fromtimestamp(r[5]).strftime("%H:%M") if r[5] else "",
        })
    return tasks


def revenue_line(rev: dict | list | None) -> str:
    """revenue-daily.json から簡潔な収益サマリーを作る."""
    if isinstance(rev, list):
        rev = rev[-1] if rev else None
    if not isinstance(rev, dict):
        return "収益データなし"
    parts = []
    apify = rev.get("apify", {})
    if isinstance(apify, dict):
        u = apify.get("total_users_30d", 0)
        runs = apify.get("total_runs", 0)
        parts.append(f"Apify: アクター{apify.get('actors_total','?')}個 / 30日利用者{u}")
        parts.append(f"run {runs}回")
        if isinstance(apify.get("details"), list):
            sum_billing = sum(int(d.get("billing_usd", 0) or 0) for d in apify["details"] if isinstance(d, dict))
            if sum_billing:
                parts.append(f"課金見込み ${sum_billing}")
    gum = rev.get("gumroad")
    if isinstance(gum, dict) and gum.get("revenue"):
        parts.append(f"Gumroad: ${gum.get('revenue')}")
    total = rev.get("total", 0)
    if total:
        parts.append(f"合計 ${total}")
    return " / ".join(parts) if parts else "収益データなし"


# ---------------------------------------------------------------------------
# レポート生成
# ---------------------------------------------------------------------------

def build_report(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    ymd = d.strftime("%Y%m%d")

    auto_log = BASE / "logs" / f"auto_{ymd}.log"
    day_dir = BASE / "logs" / date_str
    collected = load_json(BASE / "data" / "collected_today.json")
    counts = load_json(BASE / "data" / "daily_counts.json")
    rev = load_json(BASE / "data" / "revenue-daily.json")

    day_start = d.timestamp()
    day_end = day_start + 86400

    apply = parse_auto_apply(auto_log)
    orch_runs = count_orchestrator_runs(day_dir)
    actions = sum_actions(counts)
    kanban = completed_kanban_tasks(int(day_start), int(day_end))

    L: list[str] = []
    L.append(f"# 📊 Kensho 稼働サマリー {date_str}")
    L.append("")
    L.append(f"- **生成時刻:** {datetime.now().strftime('%Y-%m-%d %H:%M')} JST")
    L.append(f"- **ソース:** [atushi1841/kensho]({REMOTE_URL}) (自動生成)")
    L.append("")

    # --- 実行サマリー ---
    L.append("## 🚀 実行サマリー")
    L.append("")
    L.append("| 項目 | 値 |")
    L.append("|------|-----|")
    L.append(f"| orchestrator 実行回数 | {orch_runs} |")
    L.append(f"| autoログ行数 | {apply['session_lines']} |")
    L.append(f"| 応募成功 | {apply['ok']} |")
    L.append(f"| 応募エラー | {apply['err']} |")
    L.append(f"| 警告 | {apply['warn']} |")
    L.append(f"| 当日収集件数 | {count_collected(collected)} |")
    if actions["accounts"]:
        L.append(f"| 応募アクション (アカウント{actions['accounts']}) | "
                 f"フォロー{actions['follow']} / RT{actions['rt']} / いいね{actions['like']} / リプライ{actions['reply']} |")
    L.append("")

    # --- AIチーム ---
    L.append("## 🤖 AIチーム完了タスク")
    L.append("")
    if kanban:
        L.append("| 時刻 | タスク |")
        L.append("|------|-------|")
        for t in kanban:
            L.append(f"| {t['completed_at']} | {t['title'][:70]} (`{t['id']}`) |")
    else:
        L.append("完了タスクなし（AIチーム稼働なし）")
    L.append("")

    # --- 収益 ---
    L.append("## 💰 収益サマリー")
    L.append("")
    L.append(revenue_line(rev))
    L.append("")

    # --- 異常パターン ---
    L.append("## ⚠️ 異常パターン")
    L.append("")
    pats = [k for k, v in apply["patterns"].items() if v > 0]
    if pats:
        L.append("| パターン | 件数 |")
        L.append("|----------|-----|")
        for k, v in apply["patterns"].items():
            if v:
                L.append(f"| `{k}` | {v} |")
    else:
        L.append("異常なし ✅")
    L.append("")

    L.append("---")
    L.append("*自動生成: kensho_github_sync.py*")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# credential（非対話 push）
# ---------------------------------------------------------------------------

_REPO_CRED_HELPER = BASE / "scripts" / "git-credential-kensho-env.sh"
_WSL_GCM_HELPER = Path("/home/atushi/.git-credential-helper-wsl.sh")


def load_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE 形式の env ファイルを読む（コメント/空行/export 前置きを許容）."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            out[key] = value.strip().strip('"').strip("'")
    return out


def credential_env_candidates() -> list[Path]:
    """token を探す env ファイル候補（順序維持・重複除去）."""
    candidates: list[Path] = []
    explicit = os.environ.get("KENSHO_GITHUB_SYNC_ENV", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path.home() / ".config" / "kensho" / "github-sync.env")
    candidates.append(Path("/home/atushi/.config/kensho/github-sync.env"))
    seen: set[str] = set()
    uniq: list[Path] = []
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            uniq.append(path)
    return uniq


def load_credentials() -> str:
    """env ファイルの token を os.environ へ反映する（既存の環境変数を優先）. 使用元ラベルを返す."""
    for path in credential_env_candidates():
        values = load_env_file(path)
        token = values.get("GITHUB_TOKEN") or values.get("GH_TOKEN")
        if not token:
            continue
        os.environ.setdefault("GITHUB_TOKEN", token)
        if values.get("GITHUB_USER"):
            os.environ.setdefault("GITHUB_USER", values["GITHUB_USER"])
        return f"env-file:{path}"
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return "env-var"
    return ""


def credential_config() -> tuple[list[str], str] | None:
    """git に渡す credential 設定(-c ...) と使用元ラベル。無ければ None（＝非対話 push 不可）."""
    label = load_credentials()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    # 既存の credential.helper（GCM 等）を打ち消してから自前の源だけを積む
    args = ["-c", "credential.helper="]
    if token and _REPO_CRED_HELPER.exists():
        args += ["-c", f"credential.helper={_REPO_CRED_HELPER}"]
        return args, f"token({label or 'env'})"
    if _WSL_GCM_HELPER.exists():
        args += ["-c", f"credential.helper={_WSL_GCM_HELPER}"]
        return args, "gcm-helper(wsl)"
    return None


# ---------------------------------------------------------------------------
# git 実行（非対話を強制）
# ---------------------------------------------------------------------------

def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"   # 対話プロンプトを禁止（cron でハングしない）
    env["GCM_INTERACTIVE"] = "never"
    return env


def run_git(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(BASE), *args], capture_output=True, text=True,
                          check=False, env=_git_env(), timeout=timeout)


def first_line(text: str, limit: int = 200) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:limit]
    return ""


def classify_git_failure(exit_code: int, output: str) -> str:
    """git 失敗出力を理由クラスへ分類する（ログと再試行判断に使う）."""
    low = (output or "").lower()
    if "index.lock" in low:
        return "index_lock_busy"
    if ("could not read username" in low or "terminal prompts disabled" in low
            or "authentication failed" in low or "permission to" in low
            or "invalid username or password" in low or "invalid username or token" in low
            or "password authentication is not supported" in low
            or "403 forbidden" in low or "requires authentication" in low):
        return "auth"
    if ("failed to connect" in low or "could not resolve host" in low or "unable to access" in low
            or "connection timed out" in low or "operation timed out" in low
            or "connection reset" in low or "network is unreachable" in low or "tls" in low):
        return "network"
    if ("non-fast-forward" in low or "fetch first" in low or "protected branch" in low
            or "rejected" in low or "remote rejected" in low):
        return "rejected"
    return f"git_{exit_code}"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# リポジトリ排他ロック / index.lock 競合対策
# ---------------------------------------------------------------------------

_REPO_LOCK_PATH = BASE / ".git" / "kensho-github-sync.lock"
_INDEX_LOCK_PATH = BASE / ".git" / "index.lock"


def acquire_repo_lock(timeout: float | None = None) -> IO[str] | None:
    """flock で同一リポジトリへの同期処理を直列化する。取得できなければ None."""
    if timeout is None:
        timeout = float(_int_env("KENSHO_SYNC_LOCK_TIMEOUT_SEC", 120))
    try:
        _REPO_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        handle = open(_REPO_LOCK_PATH, "a+")
    except OSError as exc:
        print(f"[warn] lock ファイルを開けません: {exc}", file=sys.stderr)
        return None
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.5)


def release_repo_lock(handle: IO[str] | None) -> None:
    if handle is None:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


def index_lock_holders() -> list[int]:
    """/proc から .git/index.lock を開いているプロセスを探す（同一 WSL 内の一覧）."""
    target = str(_INDEX_LOCK_PATH)
    pids: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fds = list((entry / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                if os.readlink(fd) == target:
                    pids.append(int(entry.name))
                    break
            except OSError:
                continue
    return pids


def reclaim_stale_index_lock(stale_sec: int | None = None) -> str:
    """古い index.lock を、保持プロセスが居ない場合に限り回収する。実施内容を返す（無実施は空文字）."""
    if stale_sec is None:
        stale_sec = _int_env("KENSHO_SYNC_INDEX_LOCK_STALE_SEC", 600)
    try:
        age = time.time() - _INDEX_LOCK_PATH.stat().st_mtime
    except OSError:
        return ""
    if age < stale_sec:
        return ""
    holders = index_lock_holders()
    if holders:
        return f"index.lock は pid={holders} が保持中（回収しない, age={int(age)}s）"
    try:
        _INDEX_LOCK_PATH.unlink()
    except OSError as exc:
        return f"stale index.lock の削除に失敗: {exc}"
    return f"stale index.lock を回収（age={int(age)}s）"


# ---------------------------------------------------------------------------
# commit / push
# ---------------------------------------------------------------------------

@dataclass
class GitOpResult:
    ok: bool
    exit_code: int
    reason: str
    detail: str = ""
    attempts: int = 1


@dataclass
class PushResult:
    ok: bool
    exit_code: int
    reason: str
    detail: str = ""
    attempts: int = 0
    source: str = ""


def commit_owned_path(rel_path: Path, message: str) -> GitOpResult:
    """対象パスだけを stage して commit する（index.lock 競合は退避リトライ＋stale 回収）."""
    retries = max(1, _int_env("KENSHO_SYNC_LOCK_RETRIES", 5))
    backoff = float(_int_env("KENSHO_SYNC_LOCK_BACKOFF_SEC", 3))
    pathspec = str(rel_path)
    last = GitOpResult(False, 1, "git_1", "commit 未実施")
    for attempt in range(1, retries + 1):
        add = run_git(["add", "--", pathspec])
        if add.returncode != 0:
            reason = classify_git_failure(add.returncode, add.stderr)
            last = GitOpResult(False, add.returncode, reason, first_line(add.stderr), attempt)
            if reason == "index_lock_busy" and attempt < retries:
                time.sleep(backoff * attempt)
                continue
            break
        staged = run_git(["diff", "--cached", "--quiet", "--", pathspec])
        if staged.returncode == 0:
            return GitOpResult(True, 0, "nothing_to_commit", "対象パスに差分なし", attempt)
        commit = run_git(["commit", "-m", message, "--", pathspec])
        if commit.returncode == 0:
            return GitOpResult(True, 0, "ok", first_line(commit.stdout), attempt)
        output = (commit.stderr or "") + (commit.stdout or "")
        reason = classify_git_failure(commit.returncode, output)
        last = GitOpResult(False, commit.returncode, reason, first_line(output), attempt)
        if reason != "index_lock_busy" or attempt >= retries:
            break
        time.sleep(backoff * attempt)
    # リトライ尽きた index.lock は、古くて保持者不在なら回収して 1 回だけ再挑戦
    if last.reason == "index_lock_busy":
        note = reclaim_stale_index_lock()
        if note:
            print(f"[warn] {note}", file=sys.stderr)
        if "回収" in note:
            add = run_git(["add", "--", pathspec])
            staged = run_git(["diff", "--cached", "--quiet", "--", pathspec])
            if add.returncode == 0 and staged.returncode != 0:
                commit = run_git(["commit", "-m", message, "--", pathspec])
                if commit.returncode == 0:
                    return GitOpResult(True, 0, "ok", first_line(commit.stdout), retries + 1)
                output = (commit.stderr or "") + (commit.stdout or "")
                return GitOpResult(False, commit.returncode, classify_git_failure(commit.returncode, output),
                                   first_line(output), retries + 1)
    return last


def commits_ahead() -> int:
    """origin/main..HEAD のコミット数（参照解決不能なら -1）."""
    proc = run_git(["rev-list", "--count", f"{REMOTE}/main..HEAD"])
    if proc.returncode != 0:
        return -1
    try:
        return int(proc.stdout.strip() or "0")
    except ValueError:
        return -1


def push_head(attempts: int | None = None, backoff: float | None = None) -> PushResult:
    """非対話 push。network/timeout のみ再試行し、失敗理由を exit code 付きで返す."""
    if attempts is None:
        attempts = max(1, _int_env("KENSHO_SYNC_PUSH_ATTEMPTS", 3))
    if backoff is None:
        backoff = float(_int_env("KENSHO_SYNC_PUSH_BACKOFF_SEC", 15))
    timeout = _int_env("KENSHO_SYNC_PUSH_TIMEOUT_SEC", 240)
    cred = credential_config()
    if cred is None:
        return PushResult(False, 128, "auth",
                          "credential 源なし（env ファイルも GCM helper も無い）", 0, "none")
    cred_args, source = cred
    # lowSpeedLimit/lowSpeedTime: 無制限ハング（実測 134543ms）を防ぐ
    base = [*cred_args, "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30"]
    last = PushResult(False, 1, "git_1", "", 0, source)
    for attempt in range(1, attempts + 1):
        try:
            proc = run_git([*base, "push", REMOTE, "HEAD"], timeout=timeout)
        except subprocess.TimeoutExpired:
            last = PushResult(False, 124, "timeout", f"push が {timeout}s で timeout", attempt, source)
            if attempt >= attempts:
                return last
            time.sleep(backoff * attempt)
            continue
        output = (proc.stderr or "") + (proc.stdout or "")
        if proc.returncode == 0:
            return PushResult(True, 0, "ok", first_line(output), attempt, source)
        reason = classify_git_failure(proc.returncode, output)
        last = PushResult(False, proc.returncode, reason, first_line(output), attempt, source)
        # auth/rejected は再試行しても回復しない
        if reason not in ("network", "timeout") or attempt >= attempts:
            return last
        time.sleep(backoff * attempt)
    return last


# ---------------------------------------------------------------------------
# 実行状態（次回への持ち越し）
# ---------------------------------------------------------------------------

STATE_PATH = BASE / "logs" / "github_sync_state.json"
CRON_LOG_PATH = BASE / "logs" / "github_sync_cron.log"


def read_state() -> dict[str, Any]:
    data = load_json(STATE_PATH)
    return data if isinstance(data, dict) else {}


def write_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[warn] state 書き込み失敗: {exc}", file=sys.stderr)


def log_run(line: str) -> None:
    """実行結果を logs/github_sync_cron.log へ必ず追記する（wrapper の redirect に依存しない）."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")
    try:
        CRON_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CRON_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(f"[sync] {stamp} {line}\n")
    except OSError as exc:
        print(f"[warn] ログ追記失敗: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Kensho 稼働サマリーを GitHub に自動同期")
    today = datetime.now().strftime("%Y-%m-%d")
    parser.add_argument("--date", default=today, help="対象日 YYYY-MM-DD（既定=今日）")
    parser.add_argument("--dry-run", action="store_true", help="生成のみ・push しない")
    args = parser.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"[err] 日付形式が不正: {args.date}（YYYY-MM-DD を指定）", file=sys.stderr)
        return 1

    report = build_report(args.date)

    rel = OUTPUT_DIR_REL / f"{args.date}.md"
    abs_path = BASE / rel

    # 生成（レポート作成）は push の成否にかかわらず必ず行う
    unchanged = False
    try:
        unchanged = abs_path.exists() and abs_path.read_text(encoding="utf-8") == report
    except Exception:
        unchanged = False
    if unchanged:
        print(f"[info] 既に同一レポートが {args.date} 分として存在 — 本文は更新なし")
        print(str(abs_path))
    else:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(report, encoding="utf-8")
        print(f"[gen] {abs_path} ({len(report)} 文字)")

    if args.dry_run:
        return 0

    state = read_state()
    prev_failures = int(state.get("consecutive_push_failures", 0) or 0)
    carry = bool(state.get("pending_commits")) or prev_failures > 0

    lock = acquire_repo_lock()
    if lock is None:
        print("[warn] リポジトリロックを取得できません（他プロセスが同期中）", file=sys.stderr)
        log_run("result=lock_timeout exit=2 reason=lock_timeout pending=unknown")
        return 2

    try:
        # --- commit（対象パスのみ・index.lock 競合は退避リトライ）---
        commit = commit_owned_path(rel, f"docs: 稼働サマリー {args.date} (auto)")
        if commit.reason == "nothing_to_commit":
            print("[info] 差分なし・commit なし（既に同期済み）")
        elif commit.ok:
            print(f"[ok] commit (attempt={commit.attempts})")
        else:
            print(f"[warn] git 操作失敗 (exit={commit.exit_code}) reason={commit.reason}: {commit.detail}",
                  file=sys.stderr)
        commit_failed = not commit.ok

        ahead = commits_ahead()
        if ahead < 0:
            print(f"[warn] {REMOTE}/main の参照を解決できません（未 fetch 等）", file=sys.stderr)
            ahead = 0

        # --- push 不要（完全同期）---
        if ahead == 0:
            if commit_failed:
                log_run(f"result=commit_failed exit=2 reason={commit.reason} "
                        f"exit_code={commit.exit_code} pending=0 detail={commit.detail}")
                _record(state, "commit_failed", commit.reason, commit.exit_code,
                        commit.detail, 0, prev_failures + 1)
                return 2
            print("[info] origin/main と同期済み（push 不要）")
            log_run("result=ok exit=0 reason=in_sync pending=0")
            _record(state, "ok", "in_sync", 0, "", 0, 0)
            return 0

        # --- push（前回失敗分の持ち越しもここで再送する）---
        if carry:
            print(f"[carry] 前回の未push分を検出: 未push {ahead} 件を再送する")
        push = push_head()
        if push.ok:
            print(f"[ok] pushed: {rel} (attempt={push.attempts}, credential={push.source}, pending_before={ahead})")
            if commit_failed:
                log_run(f"result=commit_failed exit=2 reason={commit.reason} exit_code={commit.exit_code} "
                        f"pending=0 detail={commit.detail}")
                _record(state, "commit_failed", commit.reason, commit.exit_code,
                        commit.detail, 0, prev_failures + 1)
                return 2
            log_run(f"result=ok exit=0 reason=ok pending_before={ahead} attempts={push.attempts} "
                    f"credential={push.source}")
            _record(state, "ok", "ok", 0, push.detail, 0, 0)
            return 0

        print(f"[warn] push 失敗 (exit={push.exit_code}) reason={push.reason}: {push.detail}\n"
              f"コミットはローカルに残留 — 次回実行時に {ahead} 件を再送する", file=sys.stderr)
        log_run(f"result=push_failed exit=2 reason={push.reason} exit_code={push.exit_code} "
                f"attempts={push.attempts}/{_int_env('KENSHO_SYNC_PUSH_ATTEMPTS', 3)} "
                f"credential={push.source} pending={ahead} detail={push.detail}")
        _record(state, "push_failed", push.reason, push.exit_code, push.detail, ahead, prev_failures + 1)
        return 2
    finally:
        release_repo_lock(lock)


def _record(state: dict[str, Any], result: str, reason: str, exit_code: int,
            detail: str, pending: int, failures: int) -> None:
    """実行結果を state へ永続化する（次回実行の持ち越し判定に使う）."""
    now = datetime.now().isoformat(timespec="seconds")
    state.update({
        "last_run": now,
        "last_result": result,
        "last_reason": reason,
        "last_exit_code": exit_code,
        "last_detail": detail,
        "pending_commits": pending,
        "consecutive_push_failures": failures,
    })
    if result == "ok":
        state["last_success"] = now
    write_state(state)


if __name__ == "__main__":
    sys.exit(main())
