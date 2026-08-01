#!/bin/bash
# Kensho Pipeline 状態確認スクリプト
# 使い方: bash tools/pipeline_check.sh
#
# ※ orchestrator.py は実行しない（出力最小化: LLMコンテキスト圧迫防止）
# ※ 実際にパイプラインを起動したい場合は tools/run_pipeline.sh を background で
#
# 出力は最大10行に制限（LLMコンテキストセーフ）

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

PYTHON=$(grep -oP 'python:\s+"\K[^"]+' config.yaml 2>/dev/null || echo "python3")
if [ ! -f "$PYTHON" ]; then
    PYTHON="C:\\Users\\1F\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe"
fi

# Python動作確認
"$PYTHON" -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || { echo "Python not found"; exit 1; }

# collected.json件数
"$PYTHON" -c "
import json, os
c = json.load(open('data/collected.json'))
items = c.get('collected', [])
pending = [i for i in items if not any(v for v in (i.get('applied') or {}).values())]
print(f'collected: {len(items)}件 / 未応募: {len(pending)}件')
# ロック確認（PID生存チェック付き — 誤検知防止）
import psutil
locks = os.listdir('data/locks') if os.path.isdir('data/locks') else []
stale = []
alive = []
for lf in locks:
    try:
        lpath = os.path.join('data/locks', lf)
        with open(lpath) as f:
            pid = int(f.read().strip())
        if psutil.pid_exists(pid):
            alive.append(f'{lf}(PID:{pid})')
        else:
            stale.append(f'{lf}(dead)')
    except Exception:
        stale.append(f'{lf}(?err)')
if alive:
    print(f'🔒 running: {alive}')
if stale:
    print(f'⚠️ stale: {stale}')
if not locks:
    print('locks: なし')
# 最新ログ
logs = sorted([f for f in os.listdir('logs') if f.startswith('orchestrator_') and f.endswith('.log')], reverse=True)
if logs:
    last_log = logs[0]
    size = os.path.getsize(f'logs/{last_log}')
    print(f'最新ログ: {last_log} ({size}bytes)')
" 2>/dev/null || echo "CHECK FAILED"

echo "[CHECK] 状態確認完了。パイプライン起動には bash tools/run_pipeline.sh を background で実行"
