# 評価レポート: Show HN: NYC MapTap – Learn NYC neighborhoods

- Task: t_bd5de3ff（本評価タスク）
- 対象: https://albertjoseph0.github.io/nyc-maptap/ / HN: https://news.ycombinator.com/item?id=49605122 (score 9, コメント 6)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外・静的無料エデュアプリ）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**NYC MapTap** = 「地図をタップしてNYCの近隣(neighborhood)名を当てる」静的クイズ型 Web アプリ（title: "NYC MapTap · NYC Metro Core Edition"）。GitHub Pages 配信（albertjoseph0.github.io）で、React + MapLibre GL + Carto basemap。近隣ポリゴンはクライアント側 JS バンドル(index-DP9Q5Eux.js, ~1.28MB)に同梱された geoJSON。バックエンド・ログイン・データAPI・収集基盤は一切なし。

### 実測（curl）
- root HTTP 200（静的HTML shell、~1KB / JSバンドル 1.28MB を読み込み）。
- robots.txt / sitemap.xml / rss.xml: すべて 404。
- 地理データ(ポリゴン)は JS バンドル内に同梱・露出。公開API・RSS・ダウンロード可能DSは存在しない。
- NHコメント6本は全てフィードバック（ポリゴンの精度、"NJをNYC扱い"/Bronx欠落の指摘、"Chicago向けに作る気になった"）で、需要・収益の示唆はゼロ。

## 自動化キーワード判定
Hunter フラグの自動化ワード: なし。本件はあくまで free-to-play の学習/クイズアプリで、Kensho 非API収益の核（自動収集 → 販売可能なデータ商品/販売ツール）に該当する機能要素が存在しない。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
Kensho の核（Pythonスクレイピング + LLM要約 → 集約・転売可能なデータ商品/販売ツール）が活かせる公開対象が皆無。
- ポリゴンデータは NYC Planning / Zillow 等の**公開・無料・転用自由な地理データセット**由来（+ 作者が手修正で境界調整）で、独占性・再現困難性ゼロのコモディティ。東京/大阪MapTap を同じデータで誰でも即再現でき、Kensho 資産（懸賞応募自動化 + LLM要約）の接続点がない。
- 中核価値は「地図タップ→正解表示」という仕組みのゲーム体験のみで、データ商品にも販売ツールにも集客素材にもならない。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）は全て「データ商品 or 販売ツール」前提。本件は静的無料アプリで、売る商品が無いだけでなく、課金・広告・API提供の仕組み自体が存在しない（自前FastAPI で同型を建てても、コモディティなので販売価値なし）。

### 3) 集客 — 不成立
- 集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）はゼロ。Kensho の観客（懸賞応募・スクレイピング、開発者向け）と、NYC地名学習クイズの利用者は重ならない。
- 原 HN score 9 / コメント6本 は小規模で、観客規模も微小。HC 上での需要実証もなされていない。

## 結論
NYC MapTap（task t_bd5de3ff の評価対象）は、公開データ・API・RSS・ダウンロード可能DS・課金/広告/API経路の**いずれも持たない静的無料エデュアプリ**。ポリゴンは公開地理データ由来のコモディティで再現困難性ゼロ、Kensho の「公開データ集約 + LLM要約 → データ商品/販売ツール」モデルと接続できる構成要素が一つもない。スキル判定パターン「技術ツール/アプリでデータ商品・スクレイピング・販売ツール・集客素材のいずれも構成できない → 却下」に一致し、Sentrint(t_b4f535f3) と同カテゴリで却下。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない（24h以内着手の対象外）。

## verification_evidence
対象の実測（curl の HTTP ステータス / 応答サイズ、parse スクリプトの実出力）:

```bash
$ curl -s -A "Mozilla/5.0" "https://albertjoseph0.github.io/nyc-maptap/" -o site.html; wc -c site.html
      1092 site.html
$ for u in robots.txt sitemap.xml rss.xml; do curl -s -o /dev/null -w "$u %{http_code}\n" -A "Mozilla/5.0" "https://albertjoseph0.github.io/nyc-maptap/$u"; done
robots.txt 404
sitemap.xml 404
rss.xml 404
$ curl -s -A "Mozilla/5.0" "https://albertjoseph0.github.io/nyc-maptap/assets/index-DP9Q5Eux.js" -o bundle.js; wc -c bundle.js
1283818 bundle.js
$ python3 parse_hn.py
num comment blocks: 6
```

## 検出パイプラインへの推奨除外/優先ルール
- 「NYC/都市の MapTap・地名学習クイズ・地図タップ」系（静的GitHub Pages / 公開地図データ / 無課金・無API）は、都道府県・都市・地域の版を問わず「コモディティ・公開データ由来」として即却下でよい。
- 学習/クイズ/地図エデュ系で、公開データ（行政・OpenStreetMap・Zillow等）をクライアントに同梱した静的アプリは、独占性ゼロ・配置経路ゼロ。自動収集して売れる対象ではない。
- アプリ/ツール系カテゴリは「静的無料・データ同梱」パターン（本件、Sentrintも近傍）で誤検出自体が高頻度 → Hunter の遡上スコアは 課金機能・API・専有DS の存在を必須にして非API導線を絞る。
