import sys
sys.path.insert(0, 'scripts')
import apify_store_promo as promo

for i, t in enumerate(promo.WEEKLY_TWEETS):
    has_g = '{gumroad_url}' in t
    print(f'{i}: gumroad={has_g} len={len(t)}')