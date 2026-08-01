#!/bin/bash
# Kensho Pipeline 直接起動スクリプト
# 使い方: bash tools/run_pipeline.sh
# （cronjob run の代わりに terminal() からこれを叩く）
# 最終行の20行（最大5KB）のみ出力 → LLMコンテキスト過多防止

# ── config.yamlからPythonパスを取得 ──
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=$(grep -oP 'python:\s+"\K[^"]+' "$PROJECT_DIR/config.yaml" 2>/dev/null || echo "python3")

if [ ! -f "$PYTHON" ]; then
    # config.yamlのパスが無効なら直書きフォールバック
    PYTHON="C:\\Users\\1F\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe"
fi

cd "$PROJECT_DIR" || exit 1
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/orchestrator_$(date +%Y%m%d_%H%M%S).log"

echo "[PIPELINE] Orchestrator 起動中... (Python: $PYTHON, ログ: $LOG_FILE)"

# orchestrator を実行（stdout/stderrを両方ログに）
"$PYTHON" orchestrator.py >> "$LOG_FILE" 2>&1
RC=$?

# ログ末尾を最大5KB・最大20行まで出力
if [ -f "$LOG_FILE" ]; then
    SIZE=$(wc -c < "$LOG_FILE")
    if [ "$SIZE" -gt 5120 ]; then
        echo "[PIPELINE] ログ $SIZE bytes → 末尾20行（最大5KB）のみ表示"
    fi
    tail -20 "$LOG_FILE" 2>/dev/null | head -c 5120
fi

echo ""
echo "[PIPELINE] 終了コード: $RC"
exit $RC
