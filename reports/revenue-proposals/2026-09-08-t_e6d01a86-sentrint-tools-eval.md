# 検証記録: "Show HN: Security and JSON tools that run in the browser"（t_e6d01a86）非API収益評価

- 対象: https://sentrint.com/tools（元 HN: https://news.ycombinator.com/item?id=49600459）
- 判断: 却下（実装対象外）— Sentrint 自体が有料セキュリティスキャン SaaS（Pro $190/年等）で、free /tools ページは顧客獲得用リードマグネット。ブラウザ内 JWT復号・.env秘密鍵スキャン・CSP評価・SRI生成は入力がユーザー貼付の commodity ユーティリティで、スクレイピング対象の公開DS/API/RSSが皆無。Kensho の scraping+LLM 資産で再現できる非API収益商品を構成できない。観客も HNscore 4・コメント0 で微小。
- 検出カテゴリ「アプリ/ツール」は誤ラベルではないが「自動化キーワードなし」の通り、自動化機能は site 本体の掃引サービスで本 /tools ページとは無関係。商品として成立するのは手作業の受託的サブスク SaaS（競合飽和分野）で受動収益に非適合。

## 3点評価

### 1) プロトタイプ — 不可
- /tools は「JWT decode, .env secret scan, CSP grade, SRI/hash generate」で、全てユーザーがペーストした自分のデータをブラウザ内処理するだけ。公開スクレイピング源・DL可能DS・RSS/API エンドポイントは実測で不在（/rss・/feed・/blog/feed 全404）。robots.txt も /dashboard・/scan 等のアプリ内部のみ disallow。
- ブログ本体「自動セキュリティチェック for Bolt/Cursor/v0 アプリ」は競合の有料 LLM コード監査サービスで、Kensho のスクレイプ済み懸賞データ資産と一切重複せず、再現にはセキュリティ専門知・信頼・監査基盤が必要。JWT復号等の個別ツールは OSS に溢れるコモディティで再現困難性ゼロ=価値なし。

### 2) ローンチ手順 — 不可
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも載らない。これは零から観客と信用を作る手動サブスク SaaS で、受動収益に非適合。AI生成コード向け脆弱性スキャンは既に多数競合が存在し飽和。

### 3) 集客 — 不可
- HN Score 4 / コメント0（Algolia 実測）で、原 launch 自体の観客が極小。Sentrint の売上は site の掃引サブスク依存で、freeツールは導線のみ。Kensho 側に転用できる既存観客・属性データ・CtoA 資産なし。

## verification_evidence

```
$ curl -sS -w "%{http_code} %{content_type} %{size_download}B\n" -o /dev/null -A "Mozilla/5.0" -L https://sentrint.com/tools
  200 text/html 97825B   # <title>Free security tools | Sentrint</title>
$ curl -sS -w "HTTP %{http_code}\n" -o /dev/null -L -A "Mozilla/5.0" https://sentrint.com/rss
  404   # {"detail":"Not Found"}
$ for p in /feed /feed.xml /blog/rss /blog/feed /atom.xml /rss.xml; do printf "$p -> "; curl -sS -o /dev/null -w "%{http_code}\n" -L -A "Mozilla/5.0" https://sentrint.com$p; done
  /feed -> 404  /feed.xml -> 404  /blog/rss -> 404  /blog/feed -> 404  /atom.xml -> 404  /rss.xml -> 404
$ curl -sS "https://hn.algolia.com/api/v1/items/49600459"   # points:4, children:0, author xEcho, url https://sentrint.com/tools
$ grep -oE '₹[0-9.,]+|\$[0-9.,]+' /tmp/pricing.html   # Pro: ₹14,990/$190 年, ₹1,499/$19 月, Free ₹0 等 — 有料サブスク
```

冒頭から証跡セクション末尾まで言及 task_id は t_e6d01a86（本タスク）のみ。
