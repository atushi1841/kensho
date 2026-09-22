#!/bin/bash
# t_3aa5365c: TCG価格データセット 蓄積cron (1日1回・低頻度=TOS遵守)
# runs tcg_price_collect.py --commit --pages 1 to append a daily price-history snapshot.
cd /mnt/d/Project2/kensho && /usr/bin/env python3 scripts/tcg_price_collect.py --commit --pages 1 >> /mnt/d/Project2/kensho/logs/tcg_price_collect.log 2>&1
