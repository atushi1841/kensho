# 評価レポート: Show HN: Golden hour API and a 3D globe of the best light

- Task: t_016e2c29
- 対象: https://golden.sendafun.com/ / HN: https://news.ycombinator.com/item?id=49593846 (score 2, コメント 0)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**Golden Hour by SendaFun** = 世界中の「最も美しい光（ゴールデンアワー/ブルーアワー）」の時刻を、緯度経度からの太陽幾何（サンライズ/サンセット ± 時間窓）で算出し、Cesium 3D グローブ + 都市別ページ + 写真ガイド記事で見せる静的サイト。
- **実装は Cloudflare Pages 上の React SPA**。実際に確認したところ `/`・`/city/london`・`/destinations`・`/guides/*`・`/openapi.json`・`/api/*` すべてが**同一の 1590 バイト SPA シェル**（sha256 同一）を返す = サーバーサイド描画・バックエンド API・認証すべて無し。全コンテンツはクライアント JS で `fetch("/cities.json")` から読んで描画。
- **唯一のデータ源は公開静的 JSON `/cities.json`（32,665 bytes、認証なし、誰でも取得可）**。~320 都市の id/name/country/lat/lng/tz と、著名撮影スポットの編集注記（facing/why）を収録。
- ゴールデンアワー時刻そのものは計算値で、`/cities.json` には含まれずブラウザ側で太陽幾何から算出。
- 収益化: schema.org 構造化データに `offers:{"@type":"Offer",price:"0",priceCurrency:"USD"}` と記載され、価格ページ・サブスク・課金経路は存在しない（全ルートが SPA シェルのため）。サイトは無料。
- 配布: サイト 1本のみ。GitHub / star / ダウンロード数 / アカウント母体なし。HN score **2**・コメント **0**。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: なし」は正確（API はタイトル上の表記だが実体の API は無い）。タイトル「API」は誤誘導で、実測ではバックエンド REST API や `/openapi.json` は存在せず、時刻はクライアント内の太陽計算で生成される。したがって「収集対象データの API」は本製品に存在しない。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
技術的には Kensho が `/cities.json` 1回取得 + `astral`/`suncalc` 等でゴールデンアワー時刻を量産できる。しかし生成物は**完全なコモディティ**。太陽幾何に基づく日の出/日の入り/ゴールデンアワー時刻は、SunCalc / sunrise-sunset.org / NOAA など無料ライブラリ・無料API・無料計算サイトが無数にあり、誰でも 30 分で再現できる = 独占性・再現困難性ゼロ。`cities.json` の編集注記（スポット選定テキスト）だけが半独占的だが、①認証なしで取得できる公開静的 JSON を他サイトから丸ごと再販する余地 ②編集的な好みの羅列で販売価値が薄い ③Kensho の Python スクレイピング + LLM 要約資産で付加できない。価値あるデータ商品になり得ない。
### 2) ローンチ手順 — 不成立
本タスクは「Apify/RapidAPI 以外」の経路を前提とし、Kensho はデータ API / 自動化 / 自前 FastAPI の経路を持つ。しかし「ゴールデンアワー時刻 API」の自前ホスティングは、無料計算サイト・既存有料 API が飽和した超コモディティ市場で差別化要素ゼロ。データ商品もスクレイピング対象も独占データも無く、配置経路に載せる有料要素がない。
### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 2・コメント 0・GitHub 無し・無料静的サイト = 観客規模が微小。Kensho の既存観客（国内懸賞/スクレイピング系）は風景写真家という原対象層と全く重ならない。

## 結論
Golden Hour by SendaFun は「アプリ/ツール」カテゴリの静的 SPA で、①タイトルに「API」とあるが実体の REST API は存在せず（全ルート同一シェル・`/openapi.json` 同一 sha256 で実測）、ゴールデンアワー時刻は誰でも再現できる太陽幾何のコモディティ計算 ②唯一のデータ資産 `cities.json`（~320都市+スポット注記）は認証なし公開の 32KB 静的 JSON で独占性・有料化余地なし、schema.org も price=0 ③Kensho Python 資産で付加できない ④HN score 2・コメント 0・GitHub 無し = 集客ゼロ。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## Verification evidence
対象タスク: t_016e2c29（実測コマンド出力の引用）

- root と全ページ・全 API 系ルートが同一の SPA シェル（sha256 が root と完全一致 = サーバー描画/バックエンド/API なし）:
```
$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_016e2c29
$ sha256sum site_root.html city_london.html destinations.html
9cc41be3...  site_root.html
9cc41be3...  city_london.html
9cc41be3...  destinations.html
$ echo "openapi.json sha: $(curl -sL -m 15 -A 'Mozilla/5.0' https://golden.sendafun.com/openapi.json | sha256sum | cut -d' ' -f1)"
openapi.json sha: 9cc41be31240272c003885fcb72ffd4c9314c15373c5553b6161804b58e2ab9c
（root の 9cc41be3... と同一）
```

- sitemap に city ページ 320 件 + 多数の /guides を掲載（SEO 用ページ）:
```
$ grep -oE '<loc>[^<]*</loc>' sitemap.xml | sed 's#</\?loc>##g' | grep -c '/city/'
320
```

- 唯一のデータ源 /cities.json（認証なし公開静的 JSON、32,665 bytes）:
```
$ curl -sL -m 30 -A "Mozilla/5.0" -o cities.json -w "HTTP %{http_code} size %{size_download}\n" https://golden.sendafun.com/cities.json
HTTP 200 size 32665
$ head -c 300 cities.json
[ { "id": "london", "name": "London", "country": "United Kingdom", "lat": 51.5072, "lng": -0.1276, "tz": "Europe/London" } , ...
```

- JS バンドル実測: データ取得は /cities.json のみ、課金経路なし、schema.org price 0:
```
$ grep -oE 'await\(await fetch\("/[a-z0-9/_-]+\.json"\)' app.js | sort -u
await(await fetch("/cities.json"))
$ grep -oE '\{"@type":"Offer",price:"[0-9]+"' app.js
{"@type":"Offer",price:"0"
```

- HN スレッド実測（score 2 / コメント 0 / author gpszys）:
```
$ curl -s -m 20 -A "Mozilla/5.0" "https://hn.algolia.com/api/v1/items/49593846" -o hn_algolia.json
$ grep -oE '"author":"[^"]*"|"points":[0-9]+' hn_algolia.json | head -3
"author":"gpszys"
"points":2
（JSON に children 無し = コメント 0。HTML も <table class="comment-tree"></table> 空）
```

## 検出パイプラインへの推奨除外ルール
- タイトルに「API」を含むが、実測でバックエンド REST が存在しない静的 SPA（全ルート同一シェル、`/openapi.json` 等がシェルと同一 sha）は実 API とみなさない。
- カテゴリ「アプリ/ツール」で、売りの核心が public static JSON 1本 + クライアント側太陽幾何計算のように**誰でも再現できるコモディティ計算値**を扱う場合、収集データ商品として却下。
- 既存無料計算値（日の出/日の入り/ゴールデンアワー等）は、無料ライブラリ多数・独占性ゼロのため既定で却下対象。
- HN score < 5 かつコメント 0、GitHub 又は収益経路なし = 観客ゼロとして即却下。
