#!/bin/bash
# devto_weekly_pipeline.sh — cron wrapper for devto_weekly_pipeline.py
# cron: 0 9 * * 2
cd /mnt/d/Project2/kensho
python3 devto_weekly_pipeline.py "$@"