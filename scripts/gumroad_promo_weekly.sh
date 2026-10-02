#!/bin/bash
# gumroad_promo_weekly.sh — cron wrapper for gumroad_promo_weekly.py (slot a: Monday)
# cron: 40 8 * * 1
cd /mnt/d/Project2/kensho
python3 scripts/gumroad_promo_weekly.py --slot a "$@"