## verification_evidence

$ git -C /mnt/d/Project2/kensho log --oneline -1
f917567 t_974844f8: add repo-local wrapper for kanban_done_guard.py (condition l deliverable token)

$ python3 /mnt/d/Project2/kensho/scripts/devto_internal_links.py --list | grep -E "W41|W42|W43"
既存 id=4817742 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4809368 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803750 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803469 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_52b46f88/check_links2.py
4817742: 8 unique links: ['japan-offmall-market-scraper)', 'japan-prize-giveaway-scraper)', 'japan-used-camera-market-scraper)', 'kitamura-japan-used-camera-scraper)', 'mandarake-auction-scraper)', 'mercari-japan-search-scraper)', 'tackleberry-japan-fishing-tackle-scraper)', 'yahoo-auctions-japan-scraper)']
  Markdown links: 8
    https://apify.com/fruitful_quintessence/mandarake-auction-scraper
    https://apify.com/fruitful_quintessence/japan-offmall-market-scraper
    https://apify.com/fruitful_quintessence/tackleberry-japan-fishing-tackle-scraper
4809368: 3 unique links: ['fruitful_quintessence)', 'japan-prize-giveaway-scraper)', 'kensho-sweep-mcp)']
  Markdown links: 3
    https://apify.com/fruitful_quintessence
    https://apify.com/fruitful_quintessence/kensho-sweep-mcp
    https://apify.com/fruitful_quintessence/japan-prize-giveaway-scraper
4803750: 1 unique links: ['japan-prize-giveaway-scraper)']
  Markdown links: 1
    https://apify.com/fruitful_quintessence/japan-prize-giveaway-scraper
4803469: 1 unique links: ['japan-prize-giveaway-scraper)']
  Markdown links: 1
    https://apify.com/fruitful_quintessence/japan-prize-giveaway-scraper