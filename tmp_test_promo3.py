#!/usr/bin/env python3
"""Smoke test for apify_store_promo.py with mocked old timestamps."""
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')
import json
from scripts.apify_store_promo import (
    pick_actors_for_promo, week_key, WEEKLY_TWEETS,
    PRIORITY_ACTORS, pick_text,
)
from datetime import date, timedelta, datetime, UTC

# 一時的に state を古いタイムスタンプで上書き
STATE_FILE = '/mnt/d/Project2/kensho/data/apify_ppe_external_runs_state.json'
original = json.loads(open(STATE_FILE).read())

# 全エントリを 48時間前に書き換え
now = datetime.now(UTC)
old = (now - timedelta(hours=48)).isoformat()
for k in original['last_trigger']:
    original['last_trigger'][k] = old

with open(STATE_FILE, 'w') as f:
    json.dump(original, f, indent=2)

print(f"state を {old} に書き換え完了")

# テスト実行
test_date = date.today()
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

    # slot b
    text_b, reason_b, _ = pick_text(test_date, state, actors, slot="b", force=True)
    print(f"\npick_text (slot=b):")
    print(f"  text:\n{text_b}")
    print(f"  len: {len(text_b)}/280")

# 元に戻す
with open(STATE_FILE, 'w') as f:
    json.dump(json.loads(open(STATE_FILE).read()), f, indent=2)
print("\n元の state に復元済み")