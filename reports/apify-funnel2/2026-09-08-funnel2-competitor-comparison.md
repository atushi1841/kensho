# Apify収益ファネル第2段: 競合fatihtahta比較と自社actor改善 (t_9540d147)

日付: 2026-09-08 / 優先度1 / 実測データ: Apify Store API + storeページHTML (2026-09-08 JST取得)

## 1. 比較表 (競合上位 vs 自社top5、30日統計)

| actor | users累計 | users30d | runs30d | 成功率30d | review | bookmark | 価格 | 入力field数 |
|---|---|---|---|---|---|---|---|---|
| COMP fatihtahta/mercari-japan-scraper | 207 | 25 | 25,527 | 99.6% | 3 | 3 | PPE FREE$0.00399→Diamond$0.00199/件 | 6 |
| COMP piotrv1001/mercari-listings-scraper | 107 | 12 | 3,973 | 99.9% | 0 | 1 | PPE $0.004/件 | 4 |
| COMP abotapi/mercari-jp-scraper | 23 | 5 | 634 | 85.2% | 0 | 0 | PPE | 4 |
| COMP jpmarketdata/mercari-japan-price-checker | 10 | 6 | 100 | 100% | 0 | 0 | PPE $0.02/keyword | 1 |
| COMP crawlerbros/yahoo-auctions-japan-scraper | 39 | 7 | 74 | — | 0 | 1 | PPE | 2 |
| OWN mandarake-auction-scraper | 2 | 1 | 33 | 100% | 0 | 0 | PPE $0.001/検索 | 3 |
| OWN japan-offmall-market-scraper | 2 | 1 | 7 | 100% | 0 | 0 | PPE $0.005/件 | 2 |
| OWN tackleberry-japan-fishing-tackle-scraper | 2 | 1 | 29 | **0%** | 0 | 0 | PPE $0.005/件 | 4 |
| OWN mercari-japan-search-scraper | 2 | 1 | 29 | **79.3%** | 0 | 0 | PPE $0.005/件 | 7 |
| OWN japan-used-camera-market-scraper | 2 | 1 | 29 | 100% | 0 | 0 | PPE $0.005/件 | 2 |

数値サマリ: 競合平均users30d=6.8 vs 自社=1.0(users1=自社自分自身の可能性大)。README平均長は競合1,554 vs 自社1,442と同等、説明長も同等 → **コンテンツ量ではなく (a)成功率 (b)価格 (c)タイトルSEO (d)社会的証明 の4差**。

## 2. 30日publicラン0のactor特定 (14本)

publicActorRunStats30Days.TOTAL=0 の自社actor (run累計/最終run日):

- japan-market-mcp (runs=591, last=09-08) ← 直近runはあるが全部private=外部から0に見える
- komehyo-japan-brand-scraper (43, 09-07) / iosys-japan-used-smartphone-scraper (39, 09-07) / kitamura-japan-used-camera-scraper (32, 09-07) / jackroad-used-watch-scraper (32, 09-07) — 同様にprivate runのみ
- japan-jma-weather (9) / rakuten-japan-mcp (7, 07-29) / tackleberry-scraper旧 (2) / japan-crowdfunding-trend-feed (2) / mandarake-surugaya-mcp (1, 07-27) / amazon-paapi-jp-actor (0)
- 非公開3本: rakuten-debug-fetch / tabelog-debug-fetch / mini-actor-test-0903 (テスト残骸)

→ 自社71本中、外部から見ると「動いている証拠」が5本にしか付いていない。テスト残骸3本は削除対象。

## 3. 改善提案 (5件、すべて即適用可能な差分案)

### 提案1: tackleberryの成功率0%を最優先修正 (信頼性=転換の前提)
30dで29 run全部失敗 (succ30=0/29)。競合は99.6〜100%。ストアページに「失敗率」は出ないが、レビュー1つで死ぬ数値。
- 差分案: スクレイプ対象B-netのAPI/HTML変更を差分デバッグ (competitor abotapiも85%なので Mercari系より難所)。修正完了までREADME冒頭に「⚠ maintenance」を出さず、まず`maxItems`デフォルトを10に下げテストrun→`GET /v2/actor-runs?actorId=…&status=FAILED`のlastErrorMessageで原因確定。
- 検証コマンド: `curl -s "https://api.apify.com/v2/actor-runs?actorId=<ID>&limit=20&token=$APIFY_TOKEN" | jq '.data.items[].status' | sort | uniq -c`

### 提案2: タイトルを「head keyword = 平台名+Scraper」語順に統一 (fatihtahta型)
fatihtahtaのタイトル `Mercari Japan Scraper | Fast & Reliable` はストア検索クエリ "mercari scraper" の完全一致語順。自社 `Japan Mercari Prices — Listings & Market Data` は "Japan" が先頭で head keyword 後置、`Japan cameras Prices` は文法崩れ。before→after:
- `Japan Mercari Prices — Listings & Market Data` → `Mercari Japan Scraper — Listings, Sold Prices & Market Data API`
- `Japan cameras Prices — Listings & Market Data` → `Used Camera Japan Scraper — Map, Kitamura, Komehyo Price Comparison API`
- `Japan Hard Off OffMall Prices — Listings & Market Data` → `Hard Off OffMall Japan Scraper — Used Goods Prices & Listings API`
- `Mandarake Auction Japan Scraper - Used Collectibles Prices API` → 据え置き (既に語順正しい、唯一の合格ライン)
- `Tackleberry Japan Scraper - Used Fishing Tackle Prices API` → 据え置き
適用: `PUT /v2/acts/<id>` の title/seoTitle/shortDescription 同時更新 (SEO見出しは別フィールドなので片方だけ変えると不整合)。

### 提案3: FREEティア価格をfatihtahta以下に ($0.005→$0.00399/record + ティアリング)
fatihtahtaはFREE $0.00399、Bronze $0.00299、Silver以上 $0.00199 のティア設定。自社$0.005はFREEユーザーに25%高く、しかも単一価格。新規ユーザーの初回runはFREEクレジット($5)で回る回数がそのまま体感価値になる。
- 差分案: pricingPerEvent.actorChargeEvents の tieredEventPriceUsd を `{FREE:0.00399, BRONZE:0.00299, SILVER:0.00199, GOLD:0.00199, PLATINUM:0.00199, DIAMOND:0.00199}` に (fatihtahta踏襲)。粗利は当てるべき相手は上位ティア利用者で、獲得面はFREEで絞る。
- 検証: `GET /v2/acts/<id>?fields=pricingInfos` で tieredEventPriceUsd 確認。

### 提案4: 入力schemaを「keyword 1つで即実行」に簡素化 + 実行例の実データ化
自社mercari-japan-search-scraperは入力7fieldと競合最多 (fatihtahta 6、piotrv1001 4、jpmarketdata **1**)。field数とusers30dは逆相関 (jpmarketdataはusers10でもruns/users=16.7と最深度)。必須を`keyword`(または`searchKeyword`)1つに減らし、残りは全部default付きoptionに降格。
- 差分案: exampleRunInput を現行 `{"searchKeyword":"CBR250RR","maxItems":100,"maxPages":5,"proxyConfiguration":{"useApifyProxy":false}}` → `{"searchKeyword":"ポケモン カード","maxItems":50}` の2行のみに (fatihtahtaは例が `{"helloWorld":123}` プレースホルダでも207ユーザー獲得しており、例は「動く最小入力」が本命、プレースホルダより下にはならない)。
- 注意: schema field名(`keyword`系)とexampleのキー(`searchKeyword`)が不一致だとワンクリック実行が失敗する — 提案2適用時にschema/README/exampleの3者一致を機械検証。

### 提案5: 社会的証明の0→1 (レビュー獲得とprivate runの可視化)
自社review=0/bookmark=0 vs 競合2〜4レビュー。累計users=2のうち1は自分。加えて提案2章の通り、累計591 runsの japan-market-mcp まで「30d public run=0」= 自社テストrunがprivate扱いで外部証拠にならない。
- 差分案a: 動作実績のある5本 (komehyo/iosys/kitamura/jackroad/mcp) の定期cron runを public に切替 (storeページの「runs this month」に積める)。
- 差分案b: README末尾 CTA 追加: `## Feedback — If this actor saved you time, a ⭐ review on the Store page helps a small independent developer enormously.` (fatihtahtaの3レビューはレビューCTA+安さの組み合わせ)。
- 差分案c: テスト残骸3本 (rakuten-debug-fetch, tabelog-debug-fetch, mini-actor-test-0903) を削除/アーカイブし、ストア表示71本を整理。

## 4. 期待効果の数値見通し
- 提案1+3 (信頼性+価格) で mercari系2本の転換率が競合水準に近づく: 現状 users30d=1 → 競合中位=5〜6 が現実的な2週目標。
- 提案2 (タイトル) はストア検索 "mercari japan scraper" のインデックス一致で露出増、fatihtahtaの25 users30dは同一キーワードの需要証明。
- 提案5a は即効 (設定変更のみ、71本中5本の「動いている証拠」が30日以内に可視化)。

## verification_evidence

dominant task_id: t_9540d147

競合・自社統計の取得 (APIFY_TOKENは環境変数のみ、ファイルに非掲載):

```
$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_9540d147 && python3 collect_store.py
# → store検索mercari/jp系 競合15本+自社71本 → store_jp.json / competitor_detail.json
$ python3 collect_detail.py && python3 collect_own_detail.py
# → 各actorのstats(totalUsers, publicActorRunStats30Days), pricingInfos, README → own_detail.json
$ python3 extract_fields.py
# → storeページHTMLから入力schema field名抽出 (APIのversions端点はinputSchema非返却のため代替スクレイピング) → schema_fields.json
$ python3 build_comparison.py
# → 比較表+30dゼロrun 14本特定 → comparison_rows.json / own_zero30.json
comp avg u30 6.8 own u30 avg 1.0 / comp with reviews 2/15 own 0/5 / 30d-zero: 14
$ python3 succ_probe.py
fruitful_quintessence/tackleberry-japan-fishing-ta runs30=29 succ30=0 rate=0.0
fruitful_quintessence/mercari-japan-search-scraper runs30=29 succ30=23 rate=79.3
fatihtahta/mercari-japan-scraper runs30=25527 succ30=25432 rate=99.6
```

生データ (再検証用): reports/apify-funnel2/2026-09-08-comparison_rows.json, 2026-09-08-own_zero30.json
