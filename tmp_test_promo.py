#!/usr/bin/env python3
"""Smoke test for apify_store_promo.py."""
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')
from scripts.apify_store_promo import (
    pick_actors_for_promo, week_key, WEEKLY_TWEETS,
    PRIORITY_ACTORS, get_actor_display_info, pick_text,
)
from datetime import date

today = date.today()
print(f"今日: {today}, 週: {week_key(today)}")
print(f"WEEKLY_TWEETS: {len(WEEKLY_TWEETS)}種")
print(f"PRIORITY_ACTORS: {len(PRIORITY_ACTORS)}件")

actors = pick_actors_for_promo(today, max_actors=3)
print(f"選出対象: {len(actors)}件")
for a in actors:
    print(f"  - {a['display']} ({a['category']}) price={a['price_usd']:.4f} hours_since={a['hours_since_last_trigger']:.1f}")

# pick_text テスト（actors が空でない場合のみ）
if actors:
    state = {}
    text, reason, meta = pick_text(today, state, actors, slot="a", force=True)
    print(f"\npick_text (force=True):")
    print(f"  text: {text[:100]}...")
    print(f"  reason: {reason}")
    print(f"  meta keys: {list(meta.keys())}")

    # 同週同スロット再実行（force=False）
    text2, reason2, _ = pick_text(today, state, actors, slot="a", force=False)
    print(f"\npick_text (force=False):")
    print(f"  text: {text2}")
    print(f"  reason: {reason2}")
else:
    print("対象アクターなし — pick_text テストをスキップ")

# dry-run モード
print(f"\n--dry-run 実行:")
import subprocess
r = subprocess.run(
    [sys.executable, 'scripts/apify_store_promo.py', '--dry-run', '--force'],
    capture_output=True, text=True, cwd='/mnt/d/Project2/kensho'
)
print(f"exit={r.returncode}")
print(r.stdout[-500:] if r.stdout else "(no stdout)")
print(r.stderr[-500:] if r.stderr else "(no stderr)")