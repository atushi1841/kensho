#!/usr/bin/env python3
"""BOT安全監査 — 前日のaudit.jsonlに対して以下のBOTシグナルを検査する。

1. 深夜(00:00-07:59)のアクション     → 深夜ガード(no_action_window 00-07)の機能確認
2. 5秒未満のアクション間隔           → ACCOUNT_SAFETY_RULESの連続アクション規制確認
3. 同一ツイート(tweet_id)への複数種アクション → 同一ツイート多重アクション禁止の確認
4. 同一主催者(screen_name)へのフォロー過多 → 単一hostへの集中フォロー監視
5. 同一垢の1時間あたりアクション数   → hourly上限(max_actions_per_hour)確認

使い方:
    python3 scripts/audit_bot_safety.py [date]
    date省略時は「昨日」を検査。dateはYYYY-MM-DD形式。

出力: 問題がなければ何も出さない(終了コード0)。問題があれば該当行を出力(終了コード1)。
      cronのmonitor判定: 出力が空=安全 / 出力あり=要確認。
"""

from __future__ import annotations

import collections
import datetime
import json
import sys
from pathlib import Path

ACCOUNTS = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes", "inobase1-4"]
AUDIT_PATH = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"

# 判定しきい値
NIGHT_HOURS = range(0, 8)  # 00:00-07:59 を深夜とみなす
MIN_ACTION_GAP = 5.0  # 秒。これ未満の2アクション間隔は規制違反
MAX_FOLLOWS_PER_OWNER = 4  # 同一主催者への1日当たりフォロー上限(人間らしさ)
MAX_ACTIONS_PER_HOUR = 15  # 時間あたり上限(config rate_limits.max_actions_per_hour)


def _load_target_date() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def main() -> int:
    date_s = _load_target_date()
    if not AUDIT_PATH.exists():
        print(f"[audit_bot_safety] audit.jsonl なし: {AUDIT_PATH}")
        return 1

    problems: list[str] = []
    # 時系列データ: (timestamp, account, action_type, target, status)
    rows = []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("account") not in ACCOUNTS:
                continue
            ts = r.get("timestamp", "")
            if ts[:10] != date_s:
                continue
            rows.append((
                ts,
                r.get("account", ""),
                r.get("action_type", ""),
                r.get("target", ""),
                r.get("status", ""),
            ))

    if not rows:
        print(f"[audit_bot_safety] {date_s}: 成功アクションなし")
        return 0  # データがないのは安全側

    rows.sort(key=lambda x: x[0])

    # 1) 深夜アクション
    night = collections.Counter()
    for ts, acct, at, tgt, status in rows:
        hh = int(ts[11:13])
        if hh in NIGHT_HOURS:
            night[(acct, at)] += 1
    if night:
        for (acct, at), c in sorted(night.items()):
            problems.append(f"[深夜] {date_s} {acct} {at} {c}回 (深夜ガード未効? no_action_window 00-07 確認)")

    # 2) 5秒未満の間隔
    per_acct = collections.defaultdict(list)
    for ts, acct, at, tgt, status in rows:
        if status == "success":
            per_acct[acct].append(ts)
    for acct, tss in per_acct.items():
        prev: datetime.datetime | None = None
        for ts in tss:
            try:
                dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if prev is not None:
                gap = (dt - prev).total_seconds()
                if gap < MIN_ACTION_GAP:
                    problems.append(f"[連続] {date_s} {acct} アクション間隔 {gap:.1f}s (<{MIN_ACTION_GAP}s)")
            prev = dt

    # 3) 同一ツイート(tweet_id)への複数種アクション
    tweet_actions: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for ts, acct, at, tgt, status in rows:
        if status == "success" and str(tgt).isdigit():
            tweet_actions[(acct, tgt)].add(at)
    for (acct, tgt), kinds in tweet_actions.items():
        if len(kinds) >= 2:
            problems.append(f"[多重] {date_s} {acct} 同一ツイート{tgt}に複数アクション {sorted(kinds)}")

    # 4) 同一主催者へのフォロー過多
    owner_follows = collections.Counter()
    for ts, acct, at, tgt, status in rows:
        if at == "follow" and status == "success" and not str(tgt).isdigit():
            owner_follows[(acct, tgt)] += 1
    for (acct, owner), c in owner_follows.items():
        if c > MAX_FOLLOWS_PER_OWNER:
            problems.append(f"[過フォロー] {date_s} {acct} → {owner} フォロー{c}回 (上限{MAX_FOLLOWS_PER_OWNER})")

    # 5) 1時間あたりアクション数
    hourly = collections.Counter()
    for ts, acct, at, tgt, status in rows:
        if status == "success":
            hourly[(acct, ts[11:13])] += 1
    for (acct, hh), c in hourly.items():
        if c > MAX_ACTIONS_PER_HOUR:
            problems.append(f"[過集中] {date_s} {acct} {hh}時台に{c}アクション (上限{MAX_ACTIONS_PER_HOUR}/時)")

    if problems:
        print(f"[audit_bot_safety] {date_s}: {len(problems)}件のBOTシグナル検出")
        for p in problems:
            print("  " + p)
        return 1

    print(f"[audit_bot_safety] {date_s}: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
