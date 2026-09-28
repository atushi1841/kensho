#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG="${REPO_ROOT}/logs/apify_ppe_external_views_cron.log"
mkdir -p "$(dirname "$LOG")"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START" >> "$LOG"
cd "$REPO_ROOT"
python3 scripts/apify_ppe_external_views.py --point now >> "$LOG" 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) END" >> "$LOG"
