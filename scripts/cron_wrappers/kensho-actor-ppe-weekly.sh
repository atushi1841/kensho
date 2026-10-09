#!/usr/bin/env bash
# kensho-actor-ppe-weekly — Apify PPE アクターの週次外部run自動起動
# 2026-10-10 t_c42a9eb6 で登録。apify_ppe_external_runner.py は X投稿機能を持たないため、
# 本 wrapper では X投稿機能を呼ばない（actor_weekly_run.py の --skip-x-post とは別実装）。
set -euo pipefail
cd /mnt/d/Project2/kensho
exec python3 scripts/apify_ppe_external_runner.py --top 5