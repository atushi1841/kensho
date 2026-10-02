import sys
sys.path.insert(0, 'scripts')
import apify_store_promo as promo
from datetime import date

state = promo._load_json(promo.STATE_FILE)
actors = promo.pick_actors_for_promo(date.today(), max_actors=3)
today = date.today()

# Get raw text before trimming
raw = promo.WEEKLY_TWEETS[0]
other = ' 他: ' + ', '.join([a['display'] for a in actors[1:3]]) if len(actors)>1 else ''
primary = actors[0] if actors else {}
actor_display = primary.get('display','Apify Actor')
category = primary.get('category','データ')
hashtags = primary.get('hashtags','#Apify #データセット')
actor_url = promo.APIFY_ACTOR_URLS.get(primary.get('actual_name',''), promo.APIFY_STORE_BASE)
price_usd = primary.get('price_usd',0.005)
text_raw = raw.format(
    actor_display=actor_display, category=category, hashtags=hashtags,
    store_url=promo.APIFY_STORE_BASE, actor_url=actor_url, price_usd=f'{price_usd:.3f}',
    gumroad_url=promo.GUMROAD_PROMO_URL
) + other

print('RAW TEXT (before trim):')
print(text_raw)
print('---')
print('RAW LEN:', len(text_raw))
print('RAW X_LEN:', promo.x_text_len(text_raw))
print('CONTAINS GUMROAD:', 'gumroad' in text_raw.lower())
print('GUMROAD_URL:', promo.GUMROAD_PROMO_URL)
print('ENDING:', text_raw[-80:])