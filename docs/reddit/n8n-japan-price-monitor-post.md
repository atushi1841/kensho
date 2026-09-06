# Reddit r/n8n Announcement Post — n8n Template #2 (Japan Price Monitor)

File: `docs/reddit/n8n-japan-price-monitor-post.md`
Audience: overseas n8n users
Constraint: do NOT endorse automated reselling / arbitrage execution. Frame as **research / market-intelligence** only.

---

## 🇺🇸 English version (for r/n8n)

### Title (≤ 100 chars)

**Free n8n template: parallel multi-market research on Mercari, Suruga-ya & Kakaku (no API keys)**

(Length: 99 characters — fits the 100-char limit.)

---

### Post body

Hey r/n8n — sharing a small workflow I built for **multi-market price research** on Japanese second-hand / hobby marketplaces.

**Repo:** https://github.com/atushi1841/n8n-japan-price-monitor
**File:** `price-research-workflow.json` (≈12 KB, 14 nodes, zero API keys, runs end-to-end in ~30s)

**Why I built it**

I collect used Japanese-market prices for personal market research (collectibles, hobby parts, secondhand goods) and I needed one workflow that could pull from multiple Japanese sources **at the same time**, normalize everything to a single JSON schema, and ping me on Slack with a summary. Every example I found on the official template library (12k+ workflows) handled one site at a time, so I wired up a 3-way parallel fan-out and added a normalization step.

> ⚠️ **What this is / isn't.** This is a **research & price-discovery** workflow for analyzing market data — it does not place bids, buy items, scrape user accounts, or anything that would automate a transaction. The workflow stops at "here are the listings I found, here are the prices, here's a Slack digest." What you do with that data (read it, archive it, compare it, alert on it) is your call. If you're building automated *purchase* tooling, please respect each marketplace's TOS and rate limits — that's a separate problem this template intentionally does not solve.

**Node map (14 nodes)**

```
Manual Trigger ──┐
                 ├─► HTTP Request (Mercari JP search) ──► HTML Extract ──► Code (Expand) ──┐
                 ├─► HTTP Request (Suruga-ya search)    ──► HTML Extract ──► Code (Expand) ──┼─► Merge ─► Format ─► Slack
Schedule Trigger ┘                                                                       ┘
                                                                                         Merge ─► Format ─► Slack
                 └─► HTTP Request (Kakaku.com search)   ──► HTML Extract ──► Code (Expand) ──┘
```

- **Triggers (2):** Manual Trigger for one-off runs + Schedule Trigger (cron-style) for recurring research — one of them routes to the fan-out, both feed the same downstream path.
- **HTTP Request ×3 (parallel):** Plain `GET` requests against each marketplace's public search URL. No headers trickery, no auth tokens — these are normal search pages.
- **HTML Extract ×3:** CSS-selector extraction pulling `title`, `price`, `url`, `seller`, `condition` out of each site's listing markup.
- **Code ×3 (Expand):** Small JS that normalizes each site into one canonical record shape so the downstream Merge node can join them cleanly:
  ```js
  // canonical record shape produced by every Code node
  { source: "mercari" | "surugaya" | "kakaku",
    title, priceJpy: number, url, seller, condition, fetchedAt: ISO8601 }
  ```
- **Merge ×2 + Set / Format:** Joins the three streams and reshapes into a Slack-friendly digest table.
- **Slack (final):** Posts a markdown summary — top-N lowest-priced items per source, plus a count of items seen per marketplace.

**What I like about it**

- **No API keys, no proxy, no headless browser.** Just HTTP Request + selectors. If a site changes markup, only one HTML Extract needs updating.
- **True parallel fetch.** All three marketplaces fire at once via n8n's fan-out, so wall-clock time ≈ slowest site, not sum of all three.
- **Single canonical schema.** Once the three Code nodes emit the same shape, the rest of the workflow (Merge → Format → Slack) doesn't care which site a record came from. Adding a 4th marketplace is "drop in another HTTP+Extract+Code branch."
- **Idempotent & cheap.** A 30-second scheduled run every few hours is enough for research cadence — you're not hammering any site.

**What it is not**

- ❌ Not a "buy-it-now" bot. It does not interact with carts, place bids, or perform any purchase action.
- ❌ Not a stealth scraper. It's polite HTML parsing of public search pages; you should still respect each site's robots.txt / TOS.
- ❌ Not an arbitrage signal. The Slack output is data, not a recommendation.

**Try it / fork it**

1. Import `price-research-workflow.json` into your n8n instance.
2. Wire your Slack credential in the final Slack node.
3. (Optional) tweak the search keyword in each HTTP Request node.
4. Hit Execute Workflow.

If you fork it for a different region (e.g., adding eBay US, Vinted, etc.), the normalization Code node is the only piece that needs adapting per-source. Happy to answer questions in the comments.

---

## 🇯🇵 日本語版（記録・社内共有用）

### タイトル（80字以内）

**【無料n8nテンプレ】メルカリ駿河屋価格コム 3市場並列リサーチ（APIキー不要・14ノード）**

（80字）

---

### 本文

r/n8n に投稿した告知記事の日本語版です。**転売自動化を肯定する内容は含めず、「市場リサーチ／価格調査」用途としてのみ紹介しています**。

**リポジトリ:** https://github.com/atushi1841/n8n-japan-price-monitor
**ファイル:** `price-research-workflow.json`（約12KB・14ノード・APIキー不要・約30秒で完走）

**作った理由**

中古・ホビー系の日本市场价格をリサーチする目的で、複数サイトを**同時に**叩いて同一スキーマで正規化、Slack にダイジェストを投げるワークフローを組みました。n8n 公式の 12,000本超のテンプレートを探しても「3市場を並列で」扱う例がなかったので、HTTP Request を 3本並列にファンアウトして Code ノードで正規化する構成にしています。

> ⚠️ **このテンプレの守備範囲**
> - ✅ やっていること: 公開検索ページを取得し、商品タイトル・価格・URL・出品者・状態を抽出し、1つの正規化スキーマにまとめて Slack に通知する
> - ❌ やっていないこと: 入札・購入・カート操作・アカウント操作・ステルスクレイピング・自動取引のトリガ
> - 用途は「市場データの調査・定点観測・比較」。購入自動化は各サイトの TOS に従い別途設計してください

**14ノード構成**

```
Manual Trigger ──┐
                 ├─► HTTP Request (メルカリ) ─► HTML Extract ─► Code (Expand) ─┐
                 ├─► HTTP Request (駿河屋)    ─► HTML Extract ─► Code (Expand) ─┼─► Merge ─► Format ─► Slack
Schedule Trigger ┘                                                                      ┘
                                                                                    Merge ─► Format ─► Slack
                 └─► HTTP Request (価格.com) ─► HTML Extract ─► Code (Expand) ─┘
```

- トリガー: Manual（単発実行）+ Schedule（定期リサーチ）。両方が同じ下流経路へ合流
- 並列 HTTP×3: 各市場の公開検索 URL を GET。ヘッダ細工・認証なし
- HTML Extract×3: CSS セレクタで `title` / `price` / `url` / `seller` / `condition` を抽出
- Code×3 (Expand): サイトを横断して以下の正規化スキーマに揃える

  ```js
  { source: "mercari" | "surugaya" | "kakaku",
    title, priceJpy: number, url, seller, condition, fetchedAt: ISO8601 }
  ```

- Merge×2 + Format + Slack: 3ストリームを結合→Slack 向けマークダウンに整形→投稿（市場ごとの件数・最安トップN）

**気に入っている点**

- APIキー・プロキシ・ヘッドレスブラウザ不要。サイト構造が変わっても HTML Extract 1ノードだけ直せばいい
- 真の並列取得なので wall-clock は「最も遅いサイト≒合計時間」にならない
- 正規化スキーマが1つなので、4市場目を増やすのも HTTP+Extract+Code の枝を追加するだけ
- 30秒で完走、数時間おきのスケジュールでも各サイトに負荷をかけない

**これは何ではないか**

- ❌ 「今すぐ買う」ボットではない。入札・購入・カート操作は一切しない
- ❌ ステルススクレイパーではない。公開ページの丁寧なパース。各サイトの robots.txt / TOS は尊重すること
- ❌ 裁定アービトラージのシグナルではない。Slack に出るはデータであって推奨ではない

**使い方**

1. `price-research-workflow.json` を n8n にインポート
2. 最後の Slack ノードに自分の credential を設定
3. （任意）各 HTTP Request ノードの検索キーワードを変える
4. Execute Workflow

海外 eBay / Vinted などへ拡張する場合も、Code ノードの正規化マッピングを1箇所ずつ追加するだけで済む構造です。
