# Show HN: n8n workflow — 3-market JP price research, no API keys, ~30s

Hi HN — author of the workflow here. Built a free n8n template that runs **one search keyword across three Japanese markets in parallel** (Kakaku new, Suruga-ya used, eBay US auction) and posts a cheapest-first Markdown summary to Slack. 14 nodes, ~12KB JSON, runs in ~30s on a free n8n cloud instance. Drop-in `price-research-workflow.json` on the repo.

**Why this exists.** I searched n8n's official library (12,116 templates) for "three-market parallel" workflows and found exactly zero — every scraper template I've seen targets a single source. Cross-market price comparison for used/auction retail goods is mostly manual work. This template normalizes three very different response formats (HTML for kakaku/suruga-ya, JSON for eBay) into one `{keyword, source, title, price, url, fetched_at}` shape and sorts cheapest-first within each source.

**Implementation choices worth noting.** 1) Parallelism is structural — three HTTP Request nodes share one Schedule/Manual Trigger and join at two Merge nodes, so wall-clock time is `max(t_kakaku, t_suruga, t_ebay)` rather than their sum. 2) Suruga-ya returns relative URLs from the CSS selector; the Expand Code node prepends the origin in 5 lines so downstream nodes see absolute URLs — a tiny detail that catches everyone once. 3) The Format Slack Code node does the cheapest-first sort per source rather than relying on upstream order, which means each source's top-5 is stable regardless of which market returned fastest.

**No API keys required for the Japanese sources.** Kakaku and Suruga-ya's public search endpoints respond without auth; only eBay needs a free Finding API app ID via `{{$env.EBAY_APP_ID}}`. If you skip it, the eBay branch errors and the other two still post — graceful degradation by design. Robots.txt for both JP sources permits the search endpoints; default schedule is daily to stay well under any polite rate limit. **Use this for market research and price-watch alerting, not for automated purchasing or cross-border arbitrage bots** — that's out of scope and against most marketplaces' ToS anyway.

**What's there.** The repo ships three templates: this multi-market workflow, a GooBike used-motorcycle monitor (30 listings/day), and an UpGarage auto-parts JSON monitor (800K+ items). All MIT. Open to PRs for additional sources (Yahoo Auctions, Mercari if someone solves the DPoP header, Rakuma). Repo is `atushi1841/n8n-japan-price-monitor` — happy to answer questions.

---

## 日本語訳

### タイトル
Show HN: n8nワークフロー — 3市場横断の日本価格リサーチ、APIキー不要、約30秒

### 本文
HNの皆様、作者です。**1つの検索キーワードを日本の3市場（価格.comの新品、駿河屋の中古、eBay USのオークション）で並列に実行**し、市場ごとに最安値順に整列したMarkdownサマリーをSlackに投稿する、フリーのn8nテンプレートを作りました。14ノード、約12KBのJSON、n8nクラウドの無料枠で30秒ほど。`price-research-workflow.json`をリポジトリに置いてあります。

**なぜ作ったか。** n8n公式ライブラリ（12,116本）を「3市場並列」で検索したところ、ぴったり0件でした。既存のスクレイパーテンプレートは単一ソース向けがほとんどで、中古/オークション品の市場横断比較は手作業に頼っています。本テンプレートは3つの異なるレスポンス形式（kakaku/suruga-yaはHTML、eBayはJSON）を `{keyword, source, title, price, url, fetched_at}` という1つの形に正規化し、市場ごとに最安値順で並べます。

**実装上のポイント。** 1) 並列性は構造によるもの — 3つのHTTP RequestノードがSchedule/Manual Triggerを共有し、2つのMergeノードで合流するため、実行時間は合計ではなく `max(t_kakaku, t_suruga, t_ebay)`。 2) 駿河屋はCSSセレクタが相対URLを返すため、5行のCodeノードでオリジンを付けています。地味ですが皆一度はハマる箇所。 3) Format Slack のCodeノードで市場単位の最安ソートを自前で行うため、どの市場が先に返ってきても各市場トップ5が安定します。

**日本のソースはAPIキー不要。** kakakuとsuruga-yaの公開検索エンドポイントは認証なしで応答します。eBayのみ無料 のFinding APIキーを `{{$env.EBAY_APP_ID}}` で。未設定でもeBay枝だけがエラーになり、残り2市場は投稿を続けます — 設計上のグレースフルデグラデーションです。両JPソースのrobots.txtは検索エンドポイントを許可しており、デフォルト日次実行でも礼儀正しいレート制限内に収まります。**本テンプレートの用途は市場調査と価格ウォッチ通知です。自動購入や越境裁定（arbitrage bot）には使わないでください** — どの市場のToSにも反しますし、本テンプレートの対象外です。

**同梱物。** この多市場ワークフローのほか、GooBike中古バイクモニター（30件/日）、UpGarage中古パーツJSONモニター（80万件以上）をMITで公開しています。Yahoo オークション、DPoPヘッダ問題を解決できた場合のMercari、Rakuma等の追加ソースはPR歓迎です。リポジトリは `atushi1841/n8n-japan-price-monitor` です。質問お気軽にどうぞ。
