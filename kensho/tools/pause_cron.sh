#!/bin/bash
# Kensho Cron 一時停止
# 使い方: bash tools/pause_cron.sh
#
# 手動でpipelineを操作する前に実行。
# 1. data/.cron_paused を作成 → kensho_cron.pyが自動スキップ
# 2. （Hermes環境ならcron jobも停止 — オプション）
#
# 再開には bash tools/resume_cron.sh を実行

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLAG_FILE="$PROJECT_DIR/data/.cron_paused"

mkdir -p "$PROJECT_DIR/data"
touch "$FLAG_FILE"
echo "[PAUSE] Cron停止済み (flag: $FLAG_FILE)"

# Hermes実行中ならcron jobも停止（任意）
if command -v hermes &>/dev/null; then
    echo "[PAUSE] Hermesが利用可能 → cron jobも停止します"
    hermes cron pause kensho-orchestrator 2>/dev/null || true
fi

echo "[PAUSE] 完了。パイプラインを安全に操作できます。"
echo "       終わったら bash tools/resume_cron.sh で再開"
