#!/usr/bin/env bash
# kensho-env-audit-cron.sh — 週次環境監査（問題時のみ通知）
# 全て正常なら [SILENT]（配信抑制）、問題があれば詳細を出力
cd /mnt/d/Project2/kensho || exit 1

OUT=$(python3 scripts/kensho-env-audit.py 2>/dev/null)
RC=$?

if [ $RC -eq 0 ]; then
  echo "[SILENT]"
  exit 0
fi

# 問題あり → 構造化レポートをTelegram向けに整形
echo "$OUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('監査スクリプトエラー')
    sys.exit(0)

print('🏥 環境監査: ' + d['summary'])
print()
for i in d['issues']:
    print('🔴 ' + i)
print()
print('正常項目:')
for c in d['checks']:
    ok = c.get('alive', c.get('active', False))
    if ok:
        print('  ✅ ' + c['name'])
"
