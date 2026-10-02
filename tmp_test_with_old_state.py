#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
import json
from scripts.apify_store_promo import pick_actors_for_promo, pick_text
from datetime import date, timedelta, datetime, UTC

# state を古いタイムスタンプで一時的に上書き
STATE_FILE = 'data/apify_ppe_external_runs_state.json'
with open(STATE_FILE) as f:
    original = json.load(f)

now = datetime.now(UTC)
old = (now - timedelta(hours=48)).isoformat()
for k in original['last_trigger']:
    original['last_trigger'][k] = old

with open(STATE_FILE, 'w') as f:
    json.dump(original, f, indent=2)

try:
    # テスト実行
    test_date = date.today()
    actors = pick_actors_for_promo(test_date, max_actors=3)
    print(f'選出対象: {len(actors)}件')
    for a in actors:
        print(f'  - {a["display"]} price={a["price_usd"]:.4f}')
    
    state = {}
    text, reason, meta = pick_text(test_date, state, actors, slot='a', force=True)
    print(f'\nslot a text ({len(text)}/280):')
    print(text)
    
    text_b, reason_b, _ = pick_text(test_date, state, actors, slot='b', force=True)
    print(f'\nslot b text ({len(text_b)}/280):')
    print(text_b)
finally:
    # 元に戻す
    with open(STATE_FILE, 'w') as f:
        json.dump(original, f, indent=2)