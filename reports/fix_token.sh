#!/bin/bash
# t_1b2ecfa1: トークン行の確実な修復 + 検証
cd /mnt/d/Project2/kensho || exit 1
python3 - <<'PY'
p = "reports/weekly_market_report.py"
s = open(p, encoding="utf-8").read()
old = 'f"Authorization: Bearer ***"'
new = 'f"Authorization: Bearer {GUMROAD_TOKEN}"'
n = s.count(old)
print("occurrences before:", n)
if n >= 1:
    s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)
    print("replaced")
else:
    print("token line pattern not found; current Authorization lines:")
    for i, l in enumerate(s.splitlines(), 1):
        if "Authorization" in l:
            print(i, l)
PY
echo "===verification grep==="
grep -n "Authorization" reports/weekly_market_report.py
stat -c '%s %y' reports/weekly_market_report.py
