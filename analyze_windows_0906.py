import collections
import datetime
import json

JST = datetime.timezone(datetime.timedelta(hours=9))


def jst(ts):
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
    except ValueError:
        return None


D = "2026-09-06"
ACCTS = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes"]
win = collections.defaultdict(collections.Counter)
already = collections.Counter()
byacct_reason = collections.defaultdict(collections.Counter)
with open("/mnt/d/Project2/kensho/data/audit.jsonl") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        acct = r.get("account")
        if acct not in ACCTS:
            continue
        j = jst(r.get("timestamp", ""))
        if j is None or j.strftime("%Y-%m-%d") != D:
            continue
        reason = r.get("reason", "") or ""
        if reason.startswith("already_"):
            already[acct] += 1
            byacct_reason[acct][reason] += 1
        if r.get("status") == "success":
            mins = j.hour * 60 + j.minute - 7 * 60
            if mins >= 0:
                win[acct][mins // 90] += 1
print("=== 9/6 success actions by 90-min window (excluding already_*) ===")
for acct in ACCTS:
    tot = sum(win[acct].values())
    parts = " ".join(f"{w}:{n}" for w, n in sorted(win[acct].items()) if n)
    print(f"{acct:14} total={tot:3d}  {parts}")
print()
print("=== already_* (duplicate re-application) per account, 9/6 ===")
for acct in ACCTS:
    det = ", ".join(f"{k}={v}" for k, v in byacct_reason[acct].most_common())
    print(f"{acct:14} {already[acct]:3d}  ({det})")
