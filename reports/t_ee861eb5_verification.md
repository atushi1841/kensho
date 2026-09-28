# t_ee861eb5 verification report — Apify Store promo 投稿検証

## verification_evidence

本検証は worker (kensho-revenue-worker) が自ら実行したコマンドの出力に基づく。

### 1. tweet_id 取得（real tweet_id、excluding placeholder/unknown_*）

```
$ cd /mnt/d/Project2/kensho && KENSHO_PROMO_BROWSER=firefox USE_PROXY=0 python3 scripts/apify_store_promo.py --slot b --force
[2026-09-29 04:29:18] 対象週: 2026-W40 / slot=b / atushi16 / Apify Store PPEプロモ
[2026-09-29 04:29:18] Playwright起動: account=atushi16
[2026-09-29 04:29:21] WARN: SOCKS5プロキシ(172.26.80.1:1081) に接続不可 → USE_PROXY=0 で実行
[2026-09-29 04:31:41] 投稿後URL: https://x.com/compose/post
[2026-09-29 04:31:51] [OK] 投稿成功 tweet_id=2104655287496114428
[2026-09-29 04:32:14] 状態記録: /mnt/d/Project2/kensho/data/apify_store_promo_state.json (tweet_id=2104655287496114428, slot=b)
```

tweet_id=2104655287496114428 は 18 桁の数字のみ（placeholder_2026W40a / unknown_* ではない）。

### 2. 翌週 dedup スキップ確認（同週同スロット再実行の冪等性）

```
$ cd /mnt/d/Project2/kensho && python3 scripts/apify_store_promo.py --dry-run --slot b
[2026-09-29 04:32:27] スキップ: 今週bスロットは投稿済み (week=2026-W40, tweet_id=2104655287496114428)
```

### 3. external_views 計測（成功指標2の事前確認 — 10/9 本検証予定）

```
$ cd /mnt/d/Project2/kensho && python3 scripts/apify_ppe_external_views.py --point now
  ポイント: 168h  日付: 2026-09-11  baseline: 2026-09-04
  japan-camera-market    ext_views=  0  runs= 122  u30d=1  bm=0  SEO✓
  japan-watch-market     ext_views=  0  runs= 113  u30d=1  bm=0  SEO✓
  japan-luxury-market    ext_views=  0  runs= 112  u30d=1  bm=0  SEO✓
  japan-instrument-market ext_views=  0  runs= 113  u30d=1  bm=0  SEO✓
  japan-offmall-market   ext_views=  0  runs= 289  u30d=1  bm=0  SEO✓
  合計 external_views(proxy) = 0
```

mandarake-auction-scraper は KEYS に含まれていないため上記対象外。外部viewが Apify API に反映されるまで数日〜1週間かかるため、10/9 の計測で再検証する。

### 4. セッション検証（keyring から auth_token/ct0 確認）

```
$ cd /mnt/d/Project2/kensho && python3 /home/atushi/.hermes/profiles/kensho-revenue-worker/cache/scratch/probe_cookies.py
  keys: ['cookies', 'origins']
  n_cookies: 12
  auth_token: len=40 head='be0a30b356ae'
  ct0: len=160 head='9cbeb66d3597'
  twid: len=12 head='u%3D54196675'
```

### 5. X 投稿セレクタ検証（実測セレクタ）

```
$ cd /mnt/d/Project2/kensho && USE_PROXY=0 timeout 180 .venv/bin/python /home/atushi/.hermes/profiles/kensho-revenue-worker/cache/scratch/probe_compose2.py
  [data-testid="tweetTextarea_0"]  count=1 visible=True
  [data-testid="tweetButton"]       count=1 visible=True
  button:has-text("ポスト")          count=3 visible=True
  CONTENTEDITABLE HTML: <div data-contents="true">...
  typed into contenteditable; page url now: https://x.com/compose/post
```