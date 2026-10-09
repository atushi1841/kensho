#!/usr/bin/env bash
# smithery_useCount_fetch.sh — Smithery CLI で namespace=atushi1841 の全 MCP useCount を取得
# 成功時: JSON配列を stdout へ出力、exit 0
# 失敗時: エラーメッセージを stderr へ、exit 1
set -euo pipefail

NAMESPACE="${1:-atushi1841}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${SMITHERY_OUTPUT_DIR:-${SCRIPT_DIR}/../data}"
OUTPUT_FILE="${OUTPUT_DIR}/smithery_usecount_$(date +%Y%m%d_%H%M%S).json"
mkdir -p "$OUTPUT_DIR"

# Smithery CLI search --namespace で useCount を取得
# JSON Lines 出力を1行ずつパースして useCount を抽出
TMP_RAW="$(mktemp)"
trap 'rm -f "$TMP_RAW"' EXIT

if ! npx -y @smithery/cli search --namespace "$NAMESPACE" > "$TMP_RAW" 2>/dev/null; then
    echo "ERROR: smithery CLI search failed" >&2
    exit 1
fi

# JSON Lines → 配列化 + useCount フィールド抽出
python3 -c "
import json, sys
servers = []
with open('$TMP_RAW') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        servers.append({
            'name': obj.get('name', ''),
            'qualifiedName': obj.get('qualifiedName', ''),
            'useCount': obj.get('useCount', 0),
            'connectionUrl': obj.get('connectionUrl', ''),
        })
servers.sort(key=lambda s: s['useCount'], reverse=True)
with open('$OUTPUT_FILE', 'w') as out:
    json.dump({'namespace': '$NAMESPACE', 'fetched_at': '$(date -Iseconds)', 'count': len(servers), 'servers': servers}, out, indent=2, ensure_ascii=False)
total = sum(s['useCount'] for s in servers)
zero = sum(1 for s in servers if s['useCount'] == 0)
print(json.dumps({'total_useCount': total, 'zero_count': zero, 'server_count': len(servers), 'output_file': '$OUTPUT_FILE'}, ensure_ascii=False))
"

echo "Output: $OUTPUT_FILE"
exit 0