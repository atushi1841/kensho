# Revenue #2 — README English 800-1500 word enhancement + deploy (t_d0893584)

Date: 2026-09-06
Scope: mercari / surugaya / mandarake / yahoo-auctions / tackleberry — README only
Baseline words: mercari 448 / surugaya 329 / mandarake 615 / yahoo 329 / tackleberry 465

## verification_evidence

$ python3 scripts/apify_readme_deploy.py --audit
> ok  mercari-japan-search-scraper  GIT_REPO     readme=6515  gh:atushi1841/mercari-japan-search-scraper
> ok  surugaya-japan-hobby-prices   SOURCE_FILES readme=5553  sf:0.3
> ok  mandarake-auction-scraper     GIT_REPO     readme=5877  gh:atushi1841/mandarake-auction-scraper
> ok  yahoo-auctions-japan-scraper  SOURCE_FILES readme=5882  sf:0.0
> ok  tackleberry-japan-fishing-tackle-scraper GIT_REPO readme=5821 gh:atushi1841/tackleberry-scraper
> --- gaps (<800 chars) needed deploy: 0 / 63

$ python3 /tmp/wc.py   (new README word counts)
> mandarake-auction-scraper.md     chars=5877  words=902
> mercari-japan-search-scraper.md  chars=6515  words=986
> surugaya-japan-hobby-prices.md   chars=5553  words=843
> tackleberry-japan-fishing-tackle-scraper.md chars=5821 words=864
> yahoo-auctions-japan-scraper.md  chars=5882  words=897

$ python3 /tmp/deploy_readmes.py   (push + build + read-back)
> mercari-japan-search-scraper  push True gh-push 200  build H8ILV0w3vKTKNezs2 SUCCEEDED in 32s  readback present words=986
> surugaya-japan-hobby-prices   push True sf-put 200  build f45jlFCGxEHTZN0cJ SUCCEEDED in 47s  readback present words=843
> mandarake-auction-scraper     push True gh-push 200  build 0v4ebrgVSJPQWJP8b SUCCEEDED in 18s  readback present words=902
> yahoo-auctions-japan-scraper push True sf-put 200  build jmtlTAUhK3iteSY5a SUCCEEDED in 80s  readback present words=897
> tackleberry-japan-fishing-tackle-scraper push True gh-push 200 build SKcw4Dv07gyStgi33 SUCCEEDED in 48s readback present words=864

## Result
All 5 targets: README present in source, >=800 English words, build SUCCEEDED.
Word counts (843-986) within the 800-1500 target. Pricing reflected as PPE $0.005/item per parent task W1.
Structure per spec: What this actor does / Input schema / Output sample JSON / Use cases / Why Japan data / Pricing / FAQ / (Integrations, Limitations).
Each README written from the actual deployed output fields:
  - mercari: id/name/price/status/condition/brand/categoryId/sellerId/thumbnail/itemUrl/created/updated
  - surugaya: title/priceJpy/originalPriceJpy/discountPercent/condition/category/images/url/scrapedAt
  - mandarake: name/current_price_jpy/bid_count/watcher_count/shop_name/item_url/image_url/end_time (modes category/rss/detail/search)
  - yahoo: itemId/title/currentPrice/buyNowPrice/bidCount/timeLeft/postage/imageUrl/detailUrl/source
  - tackleberry: productId/title/name/price/regularPrice/discountRate/imageUrl/productUrl/isUsed/categoryId/inStock

Notes: inputSchema and run code NOT changed (README only). Source dispatch: 3 GIT_REPO via GitHub contents API, 2 SOURCE_FILES via version sourceFiles PUT (surugaya v0.3 = latest[-1] per audit; yahoo v0.0). README API endpoint absent is a known spec; read-back = source README present + build SUCCEEDED.
