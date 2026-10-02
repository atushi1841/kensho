#!/usr/bin/env python3
"""Smoke test for apify_store_promo.py with past date."""
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')
from scripts.apify_store_promo import (
    pick_actors_for_promo, week_key, WEEKLY_TWEETS,
    PRIORITY_ACTORS, pick_text,
)
from datetime import date, timedelta

# 昨日より前の日付でテスト（24時間経過を強制）
test_date = date.today() - timedelta(days=2)
print(f"テスト日付: {test_date}, 週: {week_key(test_date)}")

actors = pick_actors_for_promo(test_date, max_actors=3)
print(f"選出対象: {len(actors)}件")
for a in actors:
    print(f"  - {a['display']} ({a['category']}) price={a['price_usd']:.4f} hours_since={a['hours_since_last_trigger']:.1f}")

if actors:
    state = {}
    text, reason, meta = pick_text(test_date, state, actors, slot="a", force=True)
    print(f"\npick_text (force=True):")
    print(f"  text:\n{text}")
    print(f"  len: {len(text)}/280")
    print(f"  reason: {reason}")
    print(f"  meta: {meta}")

    # 同週同スロット再実行（force=False）
    text2, reason2, _ = pick_text(test_date, state, actors, slot="a", force=False)
    print(f"\npick_text (force=False):")
    print(f"  text: {text2}")
    print(f"  reason: {reason2}")

    # slot b
    text_b, reason_b, _ = pick_text(test_date, state, actors, slot="b", force=True)
    print(f"\npick_text (slot=b):")
    print(f"  text:\n{text_b}")
    print(f"  len: {len(text_b)}/280")