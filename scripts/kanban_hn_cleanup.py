#!/usr/bin/env python3
"""
scripts/kanban_hn_cleanup.py

Kensho AIチーム kanban の「Show HN」重複案件を二重化排除して自動クローズする。

背景:
  kensho-non-api-revenue-hunter.py は HN showstories の上位記事を cron で毎回 kanban に投入するが、
  同記事が複数 cron 実行にまたがって残留するため、同一 Show HN 記事が 3〜4 回重複作成される
  (Run内 dedup は URL ベースで対策済みだが、Run横断の dedup が無い)。

本スクリプト:
  1) アクティブ状態(ready/todo/running/blocked/triage)の Show HN 案件を、正規化タイトルでグループ化
  2) 各グループで最古の1件を「正本」として残し、残りを done へ自動クローズ(コメント付き)
  3) 冪等: 再実行しても既にクローズされてれば何もしない

使い方:
  通常実行(クローズ対象を確定してから):  python3 scripts/kanban_hn_cleanup.py --apply
  ドライラン(何も変えない):              python3 scripts/kanban_hn_cleanup.py
  別DBを指定:                            python3 scripts/kanban_hn_cleanup.py --db <path> [--apply]
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

# 共通正規化ロジックは kanban_norm に集約。hunter 側と判定ルールを一致させるため。
from kanban_norm import ACTIVE_STATUSES, default_db_path, norm_title

CLEANER_CREATED_BY = "kanban_hn_cleanup"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db_path()), help="kanban DB path")
    ap.add_argument("--apply", action="store_true", help="実際にクローズする。未指定ならドライラン")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        sys.exit(f"DB not found: {db_path}")
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    q = ",".join("?" * len(ACTIVE_STATUSES))
    rows = cur.execute(
        f"SELECT id, title, status, created_at, assignee "
        f"FROM tasks WHERE lower(title) LIKE '%show hn%' "
        f"AND status IN ({q}) ORDER BY created_at, id",
        ACTIVE_STATUSES,
    ).fetchall()

    groups = {}
    for r in rows:
        key = norm_title(r["title"])
        if key:
            groups.setdefault(key, []).append(dict(r))

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    stats = {
        "active_showhn": len(rows),
        "distinct": len(groups),
        "dup_groups": len(dup_groups),
    }

    candidates = []  # (keeper_id, closed)
    to_close = []
    for key, members in dup_groups.items():
        members.sort(key=lambda m: (m["created_at"] or 0, m["id"]))
        keeper = members[0]
        dupes = members[1:]
        to_close.extend((dupe["id"], keeper["id"], keeper["title"]) for dupe in dupes)
        candidates.append((keeper, dupes))

    print(f"アクティブ Show HN 案件:  {stats['active_showhn']}")
    print(f"正規化タイトル数(重複除く): {stats['distinct']}")
    print(f"重複グループ数:            {stats['dup_groups']}")
    print(f"クローズ候補(重複分):      {len(to_close)} 件")
    print()

    if not args.apply:
        print("DRY-RUN: 以下の候補を done へ自動クローズします (--apply で実行)。")
        for cid, kid, ktitle in to_close:
            print(f"  close {cid}  -> keep {kid}  ({ktitle[:50]})")
        con.close()
        return

    # 適用: クローズ先に「正本が既に done/archived」等で安全確認してから行う
    now = int(time.time())
    closed, skipped = 0, 0
    with con:
        for cid, kid, ktitle in to_close:
            keeper_row = cur.execute("SELECT status FROM tasks WHERE id=?", (kid,)).fetchone()
            if keeper_row is None:
                skipped += 1
                continue
            ph = ",".join("?" * len(ACTIVE_STATUSES))
            cur.execute(
                f"UPDATE tasks SET status='done', completed_at=?, result=? WHERE id=? AND status IN ({ph})",
                (now, "duplicate-merged-by-kanban_hn_cleanup", cid) + ACTIVE_STATUSES,
            )
            if cur.rowcount != 1:
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?,?,?,?)",
                (
                    cid,
                    CLEANER_CREATED_BY,
                    f"自動クローズ: 同一 Show HN 案件の複製。正本は {kid} ({ktitle[:60]})。"
                    f"kanban_hn_cleanup (t_880da339) による重複排除。",
                    now,
                ),
            )
            closed += 1
    con.commit()
    print(f"適用完了: クローズ {closed} 件, スキップ {skipped} 件")
    con.close()


if __name__ == "__main__":
    main()
