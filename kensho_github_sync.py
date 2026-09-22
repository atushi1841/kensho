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
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

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
# Git push
# ---------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", "-C", str(BASE), *args],
                          capture_output=True, text=True, check=check).stdout


def push_report(rel_path: Path, date_str: str, dry_run: bool) -> bool:
    """repo ルート相対パスに commit & push する."""
    abs_path = BASE / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    # リポジトリが壊れていないか検査
    if not (BASE / ".git").exists():
        print(f"[err] .git が見つかりません: {BASE}", file=sys.stderr)
        return False

    if dry_run:
        print(f"[dry-run] 生成のみ（push しない）: {abs_path}")
        return True

    try:
        # 対象ファイルのみステージ（他作業ツリーの変更を巻き込まない）
        git("add", "--", str(rel_path))
        # 差分が無い場合 commit は exit code 1 + "nothing to commit" を返す
        git("commit", "-m", f"docs: 稼働サマリー {date_str} (auto)")
    except subprocess.CalledProcessError as exc:
        if "nothing to commit" in exc.stderr:
            print("[info] 差分なし・commit なし（既に同期済み）")
            return True
        print(f"[warn] git 操作失敗 ({exc.returncode}): {exc.stderr}", file=sys.stderr)
        return False
    try:
        git("push", REMOTE, "HEAD")
    except subprocess.CalledProcessError as exc:
        print(f"[warn] push 失敗 ({exc.returncode}): {exc.stderr}\nコミットはローカルに残留", file=sys.stderr)
        return False
    print(f"[ok] pushed: {rel_path}")
    return True


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
        d = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"[err] 日付形式が不正: {args.date}（YYYY-MM-DD を指定）", file=sys.stderr)
        return 1

    report = build_report(args.date)

    rel = OUTPUT_DIR_REL / f"{args.date}.md"
    abs_path = BASE / rel

    # 同一内容が既に存在するなら再生成・push をスキップ（無意味な追記コミットを防ぐ）
    try:
        if abs_path.exists() and abs_path.read_text(encoding="utf-8") == report:
            print(f"[info] 既に同一レポートが {args.date} 分として存在 — 更新不要")
            print(str(abs_path))
            return 0
    except Exception:
        pass

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(report, encoding="utf-8")

    print(f"[gen] {abs_path} ({len(report)} 文字)")
    if args.dry_run:
        return 0

    ok = push_report(rel, args.date, dry_run=False)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
