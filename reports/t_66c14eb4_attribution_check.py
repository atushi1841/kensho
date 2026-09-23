#!/usr/bin/env python3
"""t_66c14eb4 — 失敗32件のアカウント帰属と retry トレース厳密照合（読み取り専用）."""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from datetime import datetime

ROOT = "/mnt/d/Project2/kensho"
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ \|")
SH_FAIL_RE = re.compile(r"self_heal failed: (.*?) \(attempts=(\d+)\)")
ACCOUNT_RE = re.compile(r"\[Kensho\] アカウント: @(\S+) \((\S+)\)")
RETRY_GAP_SEC = 900.0   # リトライ間隔の上限（同一 heal-run 内とみなす）

account_starts: list[tuple[datetime, str]] = []
sh_fails: list[tuple[datetime, int]] = []

for path in sorted(glob.glob(os.path.join(ROOT, "logs", "auto_*.log"))):
    for raw in open(path, encoding="utf-8", errors="ignore"):
        m = TS_RE.match(raw)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if "self_heal failed:" in raw and "[NG]" in raw:
            f = SH_FAIL_RE.search(raw)
            if f:
                sh_fails.append((ts, int(f.group(2))))
        else:
            a = ACCOUNT_RE.search(raw)
            if a:
                account_starts.append((ts, a.group(2)))

account_starts.sort()
sh_fails.sort()


def walk_back(ts: datetime) -> tuple[str | None, list[datetime]]:
    """失敗時刻から遡り、同一アカウントの連続する操作開始行を heal-run の試行列とみなす。"""
    prior = [a for a in account_starts if a[0] < ts]
    if not prior:
        return None, []
    acct = prior[-1][1]
    chain: list[datetime] = []
    cursor = ts
    for a_ts, a_acct in reversed(prior):
        if a_acct != acct:
            continue
        if (cursor - a_ts).total_seconds() > RETRY_GAP_SEC:
            break
        chain.append(a_ts)
        cursor = a_ts
    chain.reverse()
    return acct, chain


rows = []
for ts, attempts in sh_fails:
    acct, chain = walk_back(ts)
    rows.append({
        "ts": ts.isoformat(sep=" "),
        "attempts_reported": attempts,
        "account": acct,
        "trace_count": len(chain),
        "trace_ts": [c.isoformat(sep=" ") for c in chain],
        "match": len(chain) == attempts,
    })

print(json.dumps({
    "failures": len(rows),
    "chain_match_attempts": sum(1 for r in rows if r["match"]),
    "account_distribution": dict(Counter(r["account"] for r in rows)),
    "attempts_distribution": dict(Counter(r["attempts_reported"] for r in rows)),
    "trace_count_distribution": dict(sorted(Counter(r["trace_count"] for r in rows).items())),
    "rows": rows,
}, ensure_ascii=False, indent=2))
