# 評価レポート: Show HN: Titles – Can you write a better Hacker News title?

- Task: t_1838bcfb
- 対象: https://www.orangecrumbs.com/hn-titles / HN: https://news.ycombinator.com/item?id=49599509 (score 2, コメント 1)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**HN Titles** = OrangeCrumbs が公開する「低スコア HN タイトルを書き換えて、実在した投稿・勝者タイトルと比較・採点する」ブラウザお題ゲーム。
- クライアントサイド静的 React SPA (Vite, Cloudflare ホスト)。全機能が静的バンドル JS + 1 つの静的 JSON で完結し、サーバ・API・DB は無い。
- データは `/hn-titles/title-oracle-decks.json`(5.3 MB) にある「低スコア・勝者タイトルのペア集」。著者の解析パイプラインが HN の公開 Firebase/Algolia API からタイトル変更ペアを検出し、タイミング補正で residual title signal 順に deck 化(956 pairs 等)。
- 収益モデル: **無し**。orangecrumbs.com 全体が「Hacker News tools and stories」個人趣味サイトの一部。pricing / api / subscribe / login / signup 全て **404**。課金・広告・購読ゼロ。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード: なし」。本件は純粋なインタラクティブ・データ可視化ゲームで、自動収集・自動配信・AI配信の収益商品ではない。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング/LLM資産を活かせる**排他的・独占データが無い**。
- データは公開 HN API(Firebase + Algolia)由来で、`sourceRefresh` が全量の出所を明記(stories 447 万, current_year_show_hn 32643)。**誰でも同じAPIから同価値のペアDSを再現可能 = コモディティ**。集約+アルゴリズムで再現できるものは独占性ゼロで売り物にならない。
- 差別化要素(勝者タイトルとのギャップ分析)も公開データから導出可能で、再現困難性なし。Kensho が同じものを自前ホストしても価格差・排他性が生まれない。
- ダウンロード可能 JSON は存在するが、そのデータ自体に有料化余地がない(再現可能な公開情報の派生物)。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路(データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI)はすべて「売れるデータ or 販売ツール」前提で、売るものがない。
- 原サイト自体に課金導線ゼロ。個人趣味サイトのひとつのデモとして公開されており、事業性なし。

### 3) 集客 — 不成立
- Kensho の集客アセット(属性データ / CtoA / 既存トラフィック / 既存観客)ゼロ。
- 元 HN は score 2 / コメント 1(しかも「If HN has turned into a contest for the most clicks, I guess I missed the memo」と**否定的**)。観客規模は極小。この種の「タイトル書き換えゲーム」は HN 圏の刹那的なお遊びで、有料の反復需要は成立しない。

## 結論
HN Titles は公開 HN API データの分析・可視化ゲームで、データに独占性ゼロ(誰でも再現可能)、収益・課金導線ゼロ、HN score 2 + 否定的コメントで観客もゼロ。Kensho の「スクレイピング+LLM要約 → データ商品/販売ツール」型非API収益に転換可能な構成要素が一つもない。スキル判定パターン「公開ソース由来の集約(コモディティ)、有料化余地なし → 却下」に該当。ランク高フラグは(重要度:高の自動検出によるもの)で、優先評価対象に残す価値なし。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない。

## 検出パイプラインへの推奨除外/優先ルール
- 「HN データを可視化・ゲーム化するラボ系ツール」(title-change 分析、タイトル書き換え対戦等)は、公開 Algolia/Firebase 由来データのコモディティ + 課金導線ゼロ + score 極小 として即却下してよい。
- `sourceRefresh`/`generatedAt` などがデータの公開 API 由来であることを示唆するサイトは、専有データではないのでスキップ可能。

## verification_evidence
$ curl -A "Mozilla/5.0" -o /dev/null -w "%{http_code}" https://www.orangecrumbs.com/hn-titles
200 (React SPA: #root のみ、静的 index.html 1.2KB)
$ curl -s https://www.orangecrumbs.com/hn-titles/title-oracle-decks.json | wc -c
5290002 (5.3MB 静的 JSON。sourceRefresh=HN公開API由来の全量出所を明記)
$ curl -s https://www.orangecrumbs.com/robots.txt
Allow: / , Allow: /hn/ , Sitemap: https://www.orangecrumbs.com/sitemap.xml
$ curl -s -o /dev/null -w "%{http_code}" https://www.orangecrumbs.com/pricing
404
$ curl -s -o /dev/null -w "%{http_code}" https://www.orangecrumbs.com/api
404
$ curl -s -o /dev/null -w "%{http_code}" https://www.orangecrumbs.com/subscribe
404
$ curl -s https://hn.algolia.com/api/v1/items/49599509
score 2 / コメント 1 (否定的: "If HN has turned into a contest for the most clicks, I guess I missed the memo")
$ curl -s https://hacker-news.firebaseio.com/v0/item/49599509.json
score 2 / descendants 1 (データ出所は公開HN API = 誰でも再現可能)

## 元データ
- 実測: orangecrumbs.com/hn-titles root 200(Vite/Cloudflare React SPA)、/hn-titles/title-oracle-decks.json 200(5.3MB)、robots.txt 200、sitemap.xml 200、pricing 404 / api 404 / subscribe 404 / login 404 / signup 404、hn-titles/pricing 404
- JSON sourceRefresh: stories 447萬, current_year_stories 243360, current_year_show_hn 32643, inserted 13993 → 全量が公開 HN API 由来
- HN アイテム 49599509(score 2, コメント 1, 否定的)
