import sys
sys.path.insert(0, 'scripts')
import apify_store_promo as promo
from datetime import date

state = promo._load_json(promo.STATE_FILE)
actors = promo.pick_actors_for_promo(date.today(), max_actors=3)
today = date.today()
text, reason, meta = promo.pick_text(today, state, actors, slot='b', force=True)
print(text)
print('---')
print('LEN:', len(text))
print('X_LEN:', promo.x_text_len(text))
print('CONTAINS GUMROAD:', 'gumroad' in text.lower())
print('GUMROAD_URL:', promo.GUMROAD_PROMO_URL)