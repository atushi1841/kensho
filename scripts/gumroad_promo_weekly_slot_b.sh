#!/bin/bash
# gumroad_promo_weekly_slot_b.sh — cron wrapper for gumroad_promo_weekly.py (slot b: Friday)
# cron: 40 8 * * 5
cd /mnt/d/Project2/kensho
python3 scripts/gumroad_promo_weekly.py --slot b "$@"