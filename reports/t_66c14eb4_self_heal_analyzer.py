#!/usr/bin/env python3
"""t_66c14eb4 — self_heal 本番稼働の実測アナライザ v3（読み取り専用）.

v3 の目的:
  self_heal の「retry が本当にログに残っているか」を、失敗メッセージの
  `attempts=N` と、リトライで再実行された操作の痕跡（[Kensho] アカウント: @行）を
  突き合わせて検証する。

重要な前提（コード実測）:
  - self_heal.SelfHealingLoop.__init__ は logger を受け取るが self.logger を一切使わない
    (grep -n logger kensho/core/self_heal.py => 312,318 の代入のみ)。
    → HealingEvent はログに一切出力されない。観測できるのは value_or_raise() の最終失敗のみ。
  - applier.apply_for_account は SelfHealingLoop.run(_run, validator=_validate_apply) で
    _apply_impl を包む。_apply_impl の先頭付近 (applier.py:919) が
    "[Kensho] アカウント: <display> (<key>)" を出力する。
    → retry されれば同アカウントの同種行が再度出るはず（仮説）。
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta

ROOT = "/mnt/d/Project2/kensho"
LOGS = os.path.join(ROOT, "logs")

# self_heal が production の applier に配線された瞬間（TypeError で検知）
WIRING_FIRST = datetime(2026, 9, 22, 12, 52, 20)
# self_heal.py が applier と整合した commit f906e3a の時刻
COMMIT_TS = datetime(2026, 9, 22, 13, 22, 42)
# 収集系 guarded_source 修正 commit 290c480 の時刻（collector 側の根治）
COLLECT_FIX_TS = datetime(2026, 9, 23, 21, 27, 4)

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ \|")
SH_FAIL_RE = re.compile(r"self_heal failed: (.*?) \(attempts=(\d+)\)")
ACCOUNT_RE = re.compile(r"\[Kensho\] アカウント: @(\S+) \((\S+)\)")


def iter_lines():
    for path in sorted(glob.glob(os.path.join(LOGS, "auto_*.log"))):
        day = os.path.basename(path)
        for raw in open(path, encoding="utf-8", errors="ignore"):
            m = TS_RE.match(raw)
            if not m:
                continue
            yield datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), day, raw.rstrip("\n")


def analyze() -> dict:
    account_starts: list[tuple[datetime, str, str]] = []   # (ts, account_key, day)
    sh_fails: list[tuple[datetime, str, int]] = []          # (ts, message, attempts)
    ctor_errors: list[datetime] = []
    applied_ok: list[datetime] = []
    login_fails: list[datetime] = []

    for ts, day, line in iter_lines():
        if "self_heal failed:" in line and "[NG]" in line:
            m = SH_FAIL_RE.search(line)
            if m:
                sh_fails.append((ts, m.group(1), int(m.group(2))))
        elif "SelfHealingLoop.__init__() got an unexpected keyword argument" in line and "[NG]" in line:
            ctor_errors.append(ts)
        elif ACCOUNT_RE.search(line):
            m2 = ACCOUNT_RE.search(line)
            if m2:
                account_starts.append((ts, m2.group(2), day))
        elif "[RESULT] ✅ ツイート正常（応募成立）" in line:
            applied_ok.append(ts)
        elif "[NG] ログイン失敗 - auth_tokenが必要" in line:
            login_fails.append(ts)

    sh_fails.sort()
    account_starts.sort()

    # ── 各 self_heal 失敗について、直近のアカウント行からの「試行トレース」を突き合わせ ──
    fail_rows = []
    for ts, msg, attempts in sh_fails:
        # 直前 30 分以内のアカウント開始行のうち、最も近いもののアカウントを採用
        near = [a for a in account_starts if 0 <= (ts - a[0]).total_seconds() <= 1800]
        # 同一アカウントの連続行を「1 heal-run の試行」とみなす
        acct = near[-1][1] if near else None
        same = [a for a in near if acct and a[1] == acct]
        fail_rows.append({
            "ts": ts.isoformat(sep=" "),
            "msg": msg,
            "attempts_reported": attempts,
            "account_guess": acct,
            "account_lines_within_30min": [a[0].isoformat(sep=" ") for a in same],
            "account_lines_same_acct_count": len(same),
        })

    trace_match = sum(1 for r in fail_rows if r["account_lines_same_acct_count"] == r["attempts_reported"])

    # ── before/after KPI ──
    def window(lo: datetime, hi: datetime) -> dict:
        f = [x for x in sh_fails if lo <= x[0] < hi]
        a = [x for x in account_starts if lo <= x[0] < hi]
        ok = [x for x in applied_ok if lo <= x < hi]
        return {
            "from": lo.isoformat(sep=" "),
            "to": hi.isoformat(sep=" "),
            "self_heal_final_failures": len(f),
            "apply_operation_starts": len(a),
            "applied_ok": len(ok),
            "failure_rate_per_operation_start": round(len(f) / len(a), 4) if a else None,
        }

    now = datetime.now().replace(microsecond=0)
    last_fail = sh_fails[-1][0] if sh_fails else None

    return {
        "generated_at": now.isoformat(sep=" "),
        "self_heal_introduced": WIRING_FIRST.isoformat(sep=" "),
        "self_heal_commit": COMMIT_TS.isoformat(sep=" "),
        "collector_fix_commit_290c480": COLLECT_FIX_TS.isoformat(sep=" "),
        "sh_fail_total": len(sh_fails),
        "sh_fail_first": sh_fails[0][0].isoformat(sep=" ") if sh_fails else None,
        "sh_fail_last": last_fail.isoformat(sep=" ") if last_fail else None,
        "sh_fail_attempts_values": dict(Counter(a for _, _, a in sh_fails)),
        "sh_fail_by_day": dict(sorted(Counter(t.strftime("%Y-%m-%d") for t, _, _ in sh_fails).items())),
        "sh_fail_distinct_messages": dict(Counter(m for _, m, _ in sh_fails)),
        "ctor_typeerror_events": len(ctor_errors),
        "ctor_typeerror_ts": [t.isoformat(sep=" ") for t in ctor_errors],
        "hours_since_last_failure": round((now - last_fail).total_seconds() / 3600, 2) if last_fail else None,
        "hours_of_observation_since_intro": round((now - WIRING_FIRST).total_seconds() / 3600, 2),
        "hours_of_observation_since_last_failure": round((now - last_fail).total_seconds() / 3600, 2) if last_fail else None,
        "apply_operation_starts_since_last_failure": sum(1 for a in account_starts if last_fail and a[0] > last_fail),
        "applied_ok_since_last_failure": sum(1 for x in applied_ok if last_fail and x > last_fail),
        "apply_operation_starts_total": len(account_starts),
        "applied_ok_total": len(applied_ok),
        "login_fail_total": len(login_fails),
        "retry_trace_cross_check": {
            "failures": len(fail_rows),
            "attempts_reported_matches_retry_trace": trace_match,
            "examples": fail_rows[:6],
        },
        "kpi_window_A_intro_to_collect_fix": window(WIRING_FIRST, COLLECT_FIX_TS),
        "kpi_window_B_collect_fix_to_now": window(COLLECT_FIX_TS, now + timedelta(seconds=1)),
        "kpi_window_C_last_failure_to_now": window(last_fail, now + timedelta(seconds=1)) if last_fail else None,
        "kpi_histogram_account_lines_per_failure": dict(sorted(Counter(
            r["account_lines_same_acct_count"] for r in fail_rows).items())),
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
