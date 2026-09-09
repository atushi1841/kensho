# 評価レポート: Show HN: Forget Rigid Stock Screeners – A Universal Query API for Financial Data（t_3d163d3f）

- Task: t_3d163d3f
- 対象: HN https://news.ycombinator.com/item?id=49596033（score 9、コメント 0）
- 対象サイト: https://financialdata.net/universal-query（ドキュメントページ）/ https://financialdata.net/pricing
- カテゴリ（Hunter）: アプリ/ツール（金融データAPI）
- 実装工数推定: 適用外（実装すべき収益商品が存在しない）
- 判断: **却下（実装対象外）**

## 対象の実態（HN API・対象サイト・APIエンドポイント・pricing を実測）

financialdata.net は商用の金融データAPIプロバイダー（Finnhub/Alpha Vantage 系）で、
Show HN は自社「Universal Query API」のマーケティング投稿。収益商品ではなく競合カテゴリそのもの。

- /universal-query は API ドキュメント（GET https://financialdata.net/api/v1/universal-query?dataset=...&fields=...&key=...）。
  データセットは stock_quotes / income_statements / insider_transactions 等 60+ 種。
- API 実測: key なし・偽 key とも `{"message": "Invalid API key"}` — 公開データソースではなく認証商材。
- /robots.txt・/sitemap.xml は 404。RSS・ダウンロード可能DS なし。
- pricing 実測: Free $0（300 req/day, Personal Use）/ Standard $29/mo / Premium $69/mo /
  Professional $149/mo（Commercial Use, MCP Server）/ Enterprise $299/mo（再配布許諾）。
  Personal と Commercial が明確に分離され、データ再配布は Enterprise 帯の有料許諾。
- HN: score 9 / descendants 0（投稿者 _FDN_ = 自社アカウント、コメントゼロ）。

## 3点評価

### 1) プロトタイプ
不成立。模倣する場合、原データ（上場価格・財務諸表・SEC/議会取引等）を公開ソースから
収集して金融データAPIを構築する必要があるが、それは即ちコモディティ化の極み:
Alpha Vantage / Finnhub / FMP / Twelve Data / EODHD が無料枠付きで既に飽和供給している。
Kensho の Python scraping + LLM 資産で差別的独占性は作れない（データの出所は全て公開取引所/SEC由来）。
また対象サイト自体にスクレイピング可能な生データは無く（全部 key 認証）、転売は利用規約（Personal Use 限定、
再配布は Enterprise 帯）に直接違反。

### 2) ローンチ手順
不成立。金融データAPIは稼働SLA・データライセンス・更新インフラの継続コストを伴う長期事業で、
受動収益（月1-3万円を放置）に非適合。Kensho の配置経路（Apify/RapidAPI/自前FastAPI）に載せても、
無料枠を持つ既存大手との価格競争で勝ち目なし。競合飽和の確認済み。

### 3) 集客
不成立。HN score 9・コメント 0 はスキルの却下閾値（score<20）を下回り、観客規模が微小。
Kensho に再現可能な集客アセット（属性データ/CtoA/既存トラフィック）も対象側にない。

## 卻下理由（スキル判定例と一致）
- 「公開ソースの集約+LLM要約で誰でも再現可能ならコモディティ=価値なし」に該当 —
  金融データAPIは無料枠付き競合が飽和しており、Universal Query というクエリ設計の差別化は
  スクレイピング+FastAPI で数日以内に再現可能（＝護城河ゼロ）。
- 対象は収益商品ではなく競合他社の有料API（認証必須・再配布規約制限）= 収集データ・有料化余地なしパターン。
- 24h 以内の プロトタイプ / ローンチ / 集客 の3点で worker 実装へ切り出すべき商品ではない。

## Verification evidence

対象が認証必須の商用API（公開データソースではない）こと、規約上 Personal/Commercial が分離されていること、
HN 注目度が閾値未満であることを実コマンド出力で検証した。

```sh
$ curl -s https://hacker-news.firebaseio.com/v0/item/49596033.json
{"by":"_FDN_","descendants":0,"id":49596033,"score":9,"time":1788773057,
 "title":"Show HN: Forget Rigid Stock Screeners – A Universal Query API for Financial Data",
 "type":"story","url":"https://financialdata.net/universal-query"}
（score=9, descendants=0 → 却下閾値 score<20 未満）
```

```sh
$ curl -s "https://financialdata.net/api/v1/universal-query?dataset=company_information&fields=trading_symbol"
{
  "message": "Invalid API key"
}
$ curl -s "https://financialdata.net/api/v1/universal-query?dataset=company_information&fields=trading_symbol&key=test123"
{
  "message": "Invalid API key"
}
（key 必須の認証商材 = 公開RSS/API/DS としての収集対象ではない）
```

```sh
$ curl -s -o robots.txt -w "%{http_code}\n" https://financialdata.net/robots.txt
404
$ curl -s -o sitemap.xml -w "%{http_code}\n" https://financialdata.net/sitemap.xml
404
（robots.txt / sitemap.xml 無し — 構造化された公開データ経路なし）
```

```sh
$ python3 extract2.py  # pricing.html からスクリプト/スタイル除去後テキスト抽出
Pricing ... Free $ 0 /month 300 Requests / Day ... Personal Use ...
Standard $ 29 /month ... Premium $ 69 /month ...
Professional $ 149 /month ... MCP Server Internal Commercial Use ...
Enterprise $ 299 /month ... External Commercial Use Data Display & Redistribution ...
（Personal/Commercial 分離、データ再配布は Enterprise 帯の有料許諾 → 転売不可）
```
