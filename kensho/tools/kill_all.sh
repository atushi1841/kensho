#!/bin/bash
# Kensho 全プロセス緊急停止
# 使い方: bash tools/kill_all.sh
#
# 応募スクリプトがハングした時、Firefoxゾンビが溜まった時に実行。
# 以下のプロセスを強制終了:
#   - kensho_apply_single.py
#   - kensho_collect.py
#   - orchestrator.py
#   - kensho_cron.py 関連
#   - Firefox (invisible-playwright)
#   - ForceBindIP64.exe
#
# 注意: Hermes Agent 自体は停止しない

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Kensho 全プロセス緊急停止 ==="
echo ""

# 1. ロックファイルのクリア
echo "[1/4] ロックファイルをクリア..."
if [ -d "$PROJECT_DIR/data/locks" ]; then
    rm -f "$PROJECT_DIR/data/locks/"*.pid
    echo "  -> ロック削除完了"
fi

# 2. Python応募/収集プロセスを強制終了
echo "[2/4] Python応募/収集プロセスを強制終了..."
for pattern in "kensho_apply_single.py" "kensho_collect.py" "orchestrator.py" "kensho_cron"; do
    pids=$(ps -W 2>/dev/null | grep "$pattern" | awk '{print $5}' | grep -E '^[0-9]+$')
    if [ -n "$pids" ]; then
        for pid in $pids; do
            echo "  Killing $pattern (PID $pid)..."
            kill -f "$pid" 2>/dev/null || taskkill //F //PID "$pid" 2>/dev/null || true
        done
    fi
done

# 3. Firefox (invisible-playwright) プロセスを強制終了
echo "[3/4] Firefox (invisible-playwright) を強制終了..."
firefox_count=$(ps -W 2>/dev/null | grep -c "firefox.exe" || echo "0")
if [ "$firefox_count" -gt 0 ]; then
    # taskkillでfirefoxを全強制終了
    taskkill //F //IM "firefox.exe" 2>/dev/null || true
    echo "  -> $firefox_count 個のfirefoxプロセスを終了"
else
    echo "  -> Firefoxプロセスなし"
fi

# 4. ForceBindIP64.exe プロセスを強制終了
echo "[4/4] ForceBindIP64.exe を強制終了..."
bindip_count=$(ps -W 2>/dev/null | grep -c "ForceBindIP64" || echo "0")
if [ "$bindip_count" -gt 0 ]; then
    taskkill //F //IM "ForceBindIP64.exe" 2>/dev/null || true
    echo "  -> $bindip_count 個のForceBindIPを終了"
else
    echo "  -> ForceBindIPなし"
fi

echo ""
echo "=== 完了 ==="
echo "残Pythonプロセス: $(ps -W 2>/dev/null | grep -c python || echo 0)"
echo "残Firefoxプロセス: $(ps -W 2>/dev/null | grep -c firefox || echo 0)"
echo ""
echo "注意: atushi16の応募が進行中なら中断されます。"
echo "cronを再開: bash tools/resume_cron.sh"
