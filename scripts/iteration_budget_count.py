#!/usr/bin/env python3
"""evolution v103 成功指標: 'Iteration budget' 枯渇によるblocked件数カウンタ.

使い方（絶対パス実行。WSL cwd の scripts/ 相対は誤パス）:
  python3 /mnt/d/Project2/kensho/scripts/iteration_budget_count.py  # ボード全件
  # ゲート日以降限定: 同スクリプトに --since 2026-09-12 を付ける

ボード kensho-ai-team から hermes CLI でJSONを取り込み、'Iteration budget' を
含むタスクを数える。--since は created_at (epoch int) を閾値比較（文字列比較禁止・v102教訓）。
終了コードは常に0（監視用・件数をstdoutに出力するだけ）。
"""

import argparse
import datetime
import json
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", help="YYYY-MM-DD: この日付(JST 0時)以降に作成されたタスクのみ数える")
    ap.add_argument("--board", default="kensho-ai-team")
    args = ap.parse_args()

    try:
        out = subprocess.run(
            ["hermes", "kanban", "--board", args.board, "list", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        data = json.loads(out)
    except Exception as exc:  # noqa: BLE001 - 監視スクリプトは失敗時も数字を出す
        print(f"ERROR: board list failed: {exc}", file=sys.stderr)
        return 0

    tasks = data if isinstance(data, list) else data.get("tasks", [])
    gate = 0.0
    if args.since:
        gate = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()

    hits = []
    blocked_hits = []
    for t in tasks:
        if gate and (t.get("created_at") or 0) < gate:
            continue
        if "Iteration budget" in json.dumps(t, ensure_ascii=False):
            hits.append(t.get("id", "?"))
            if t.get("status") == "blocked":
                blocked_hits.append(t.get("id", "?"))

    label = f"since {args.since}" if args.since else "all-time"
    print(f"Iteration budget exhausted tasks ({label}): {len(hits)} | blocked NOW: {len(blocked_hits)}")
    for h in hits:
        print(f"  - {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
