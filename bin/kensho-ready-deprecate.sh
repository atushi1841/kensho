#!/bin/bash
# kensho-ready-deprecate.sh — ready滞留のHN撒き系タスク恒久隔離 (v23-A, t_4bd48e99)
#
# 目的: Kanban kensho-ai-team ボードの ready タスクのうち、
#       タイトルが '[非API自動収益]' prefix かつ 'Show HN'/'Ask HN' を含む
#       Hunter系HN撒きタスクを自動で archive する（収益化方針と不一致のため隔離）。
#
# 使い方:
#   kensho-ready-deprecate.sh            # dry-run（対象表示のみ・デフォルト）
#   kensho-ready-deprecate.sh --apply    # 実際に archive 実行
#
# 設計メモ:
#   - v23-A本文では 'hermes kanban delete' を想定していたが、2026-09-05実測で
#     deleteサブコマンドは存在しないことが判明（archive --rm のみ permanent）。
#     そのため恒久隔離は archive 方式に変更（復元可能・低リスク）。
#   - ready のみ対象。in_progress/blocked 等は絶対に触らない。
#   - 対象0件なら exit 0（冪等・cronで毎日実行して安全）。

set -u

MODE="dry-run"
[ "${1:-}" = "--apply" ] && MODE="apply"

BOARD="kensho-ai-team"

# ready タスクからHN撒き系を抽出（title prefix '[非API自動収益]' AND Show HN/Ask HN）
TARGETS=$(hermes kanban --board "$BOARD" list --status ready --json 2>/dev/null | python3 -c "
import json, sys
try:
    tasks = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ids = []
for t in tasks:
    title = (t.get('title') or '')
    if title.startswith('[非API自動収益]') and ('Show HN' in title or 'Ask HN' in title):
        ids.append(t.get('id'))
print(' '.join(ids))
")

if [ -z "${TARGETS// }" ]; then
    echo "[ready-deprecate] 対象0件（ready滞留なし or HN撒きなし）mode=$MODE"
    exit 0
fi

echo "[ready-deprecate] 対象 $(echo $TARGETS | wc -w) 件 mode=$MODE"
echo "$TARGETS" | tr ' ' '\n' | sed 's/^/  - /'

if [ "$MODE" = "apply" ]; then
    # shellcheck disable=SC2086
    hermes kanban --board "$BOARD" archive $TARGETS
    RC=$?
    echo "[ready-deprecate] archive 終了コード=$RC"
    exit $RC
fi

echo "[ready-deprecate] dry-run のため archive は未実行（--apply で実行）"
exit 0
