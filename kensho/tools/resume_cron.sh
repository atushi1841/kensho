#!/bin/bash
# Kensho Cron 再開
# 使い方: bash tools/resume_cron.sh
#
# 手動pipeline操作完了後に実行。
# 1. data/.cron_paused を削除 → kensho_cron.pyが再開
# 2. （Hermes環境ならcron jobも再開 — オプション）

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLAG_FILE="$PROJECT_DIR/data/.cron_paused"

if [ -f "$FLAG_FILE" ]; then
    rm -f "$FLAG_FILE"
    echo "[RESUME] Cron再開 (flag削除)"
else
    echo "[RESUME] Cronは既に動作中 (flagなし)"
fi

# Hermes実行中ならcron jobも再開（任意）
if command -v hermes &>/dev/null; then
    echo "[RESUME] Hermesが利用可能 → cron jobも再開します"
    hermes cron resume kensho-orchestrator 2>/dev/null || true
fi

echo "[RESUME] 完了。cronが通常動作に戻りました。"
