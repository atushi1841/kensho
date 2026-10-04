#!/bin/bash
# qiita_weekly_pipeline.sh — cron wrapper for publish_qiita.py
# cron: 0 9 * * 1  (週1、月曜9時JST)
#
# 引数: /mnt/d/Project2/apify-sales-funnel/blog/qiita-YYYYWNN.md [--publish --public]
# 既定は dry-run。cron では --publish --public を渡す想定。

set -euo pipefail
cd /mnt/d/Project2/kensho

DRAFT="${1:-}"
if [[ -z "$DRAFT" ]]; then
  echo "[ERR] 対象 draft ファイルパスを第1引数に指定してください" >&2
  exit 2
fi

echo "[INFO] qiita pipeline start: $DRAFT"
python3 scripts/publish_qiita.py "$DRAFT" "$@"
RC=$?
echo "[INFO] qiita pipeline end: rc=$RC"
exit $RC
