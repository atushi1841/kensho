#!/usr/bin/env bash
# scripts/overseas_saas_monitor.sh — 海外SaaS需要モニタ & 提案DMテンプレ生成 日次ラッパー
#
# gumroad_x_post.sh / kensho-apify-seo-effect-sched.sh と同じ「profile 配下 .sh + native crontab」型。
# 内部で scripts/overseas_saas_prospect_monitor.py を実行し、
#   1) data/overseas_prospects/_leads_YYYYMMDD.json   生ヒット
#   2) data/overseas_prospects/_drafts_YYYYMMDD.json  提案DM下書き
#   3) data/overseas_prospects/_templates.json        商品別再利用テンプレ
#   4) reports/revenue-proposals/2026-09-05-overseas-saas-monitor.md レポート
# を書き出し。直近7日以内の需要投稿のみ扱う(HN Algolia 公式API・レート制限遵守)。
# 自動送信はしない — 下書きまで。冪等。
set -uo pipefail

PROJECT_ROOT="${HERMES_KENSHO_ROOT:-/mnt/d/Project2/kensho}"
PY="${PROJECT_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

for _i in $(seq 1 30); do
  [ -d /mnt/d/Project2 ] && break
  sleep 10
done
[ -d /mnt/d/Project2 ] || { echo "D:ドライブ未マウント"; exit 1; }

cd "$PROJECT_ROOT"
"$PY" "$PROJECT_ROOT/scripts/overseas_saas_prospect_monitor.py" --limit 40 2>&1
