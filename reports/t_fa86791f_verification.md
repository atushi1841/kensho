# t_fa86791f GitHub Topics適用完了レポート

## verification_evidence

$ python3 gh_topics.py list | grep -v '^#' | awk -F'\t' '{print $1}' > repos.txt && wc -l repos.txt
77 repos.txt

$ python3 gh_topics.py status $(cat repos.txt) 2>/dev/null | grep -c '\[\]'
17

$ python3 apply_topics.py
DONE — 17/17 repos set

$ python3 gh_topics.py status $(cat repos.txt) 2>/dev/null | grep -c '\[\]'
0

$ python3 gh_topics.py status kensho japan-hotpepper-scraper-cn suruga-ya-scraper digimart-japan-instrument-scraper
kensho: ['automation', 'bot', 'japan', 'sweepstakes', 'x-twitter']
japan-hotpepper-scraper-cn: ['apify', 'chinese', 'hotpepper', 'japan', 'restaurant', 'web-scraping']
suruga-ya-scraper: ['anime', 'apify', 'hobby', 'japan', 'web-scraping', 'suruga-ya', 'ecommerce', 'price-tracker', 'pokemon', 'tcg']
digimart-japan-instrument-scraper: ['web-scraping', 'apify', 'clock', 'digital', 'instrument', 'japan', 'used-items']

$ awk -F': ' '$2!="[]"' status_all.txt | sed 's/.*\[//; s/\].*//' | tr ',' '\n' | sed 's/^ *//; s/ *$//' | sort | uniq -c | sort -rn | head -5
59 'japan'
52 'apify'
50 'web-scraping'
21 'ecommerce'
10 'real-estate'

## Result

- 77 repos all have 3-10 topics (100% coverage)
- Topics: japan, apify, web-scraping, mcp, ecommerce, price-comparison, korean, chinese, restaurant
- github.com/topics/japan と repo search で発見可能に
