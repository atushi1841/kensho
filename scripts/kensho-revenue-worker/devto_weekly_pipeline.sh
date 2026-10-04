#!/bin/bash
set -euo pipefail
export DEVTO_BLOG_DIR=/mnt/d/Project2/apify-sales-funnel/blog
export DEVTO_ENV_FILE=/mnt/d/Project2/kensho/.env
# Inject env vars from .env into cron env so scripts can read them via os.environ
export $(grep -v '^#' /mnt/d/Project2/kensho/.env | xargs)
exec python3 /mnt/d/Project2/kensho/devto_weekly_pipeline.py "$@"
