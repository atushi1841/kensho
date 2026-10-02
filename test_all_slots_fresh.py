import sys
sys.path.insert(0, 'scripts')
import importlib
import apify_store_promo as promo
importlib.reload(promo)
from datetime import date, timedelta

state = promo._load_json(promo.STATE_FILE)
actors = promo.pick_actors_for_promo(date.today(), max_actors=3)
today = date.today()

print('=== TEST ALL SLOTS ===')
for slot_idx, slot in enumerate(['a', 'b']):
    for week_offset in range(8):
        test_date = date(2026, 9, 29) + timedelta(weeks=week_offset)
        iso = test_date.isocalendar()
        idx = promo._slot_index(iso.week, slot)
        raw = promo.WEEKLY_TWEETS[idx]
        
        primary = actors[0] if actors else {}
        actor_display = primary.get('display','Apify Actor')
        category = primary.get('category','データ')
        hashtags = primary.get('hashtags','#Apify #データセット')
        actor_url = promo.APIFY_ACTOR_URLS.get(primary.get('actual_name',''), promo.APIFY_STORE_BASE)
        price_usd = primary.get('price_usd',0.005)
        
        other_names = [a['display'] for a in actors[1:3]] if len(actors) > 1 else []
        other_mention = ' 他: ' + ', '.join(other_names) if other_names else ''
        
        text_raw = raw.format(
            actor_display=actor_display, category=category, hashtags=hashtags,
            store_url=promo.APIFY_STORE_BASE, actor_url=actor_url, price_usd=f'{price_usd:.3f}',
            gumroad_url=promo.GUMROAD_PROMO_URL
        ) + other_mention
        
        text = promo.trim_to_x_limit(text_raw)
        has_gumroad = 'gumroad' in text.lower()
        x_len = promo.x_text_len(text)
        
        status = 'OK' if has_gumroad else 'NO GUMROAD'
        print(f'week={iso.year}-W{iso.week:02d} slot={slot} idx={idx} xlen={x_len} {status}')
        if not has_gumroad:
            print(f'  TEXT: {text[:120]}...')

print('ALL DONE')