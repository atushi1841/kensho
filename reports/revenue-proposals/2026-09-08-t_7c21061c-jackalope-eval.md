# 検証記録: Jackalope.dev 非API収益評価（t_7c21061c）

- 対象: https://jackalope.dev/ / HN: https://news.ycombinator.com/item?id=49605236
- 判断: 却下（実装対象外）— 既存 CLI エージェント（Codex/Claude Code/Grok/OpenCode）を並列実行するネイティブデスクトップアプリ（クローズドβ waitlist）。公開データ面・API・RSS(データ源)・ダウンロード可能DS が全て無く、収益モデルはアプリ販売のみ。既存 Kensho scraping/LLM 資産での再現・ローンチ・集客が成立しない（ネイティブデスクトップアプリ却下パターン）。
- カテゴリ「アプリ/ツール」は誤ラベルに近い: 「Running tasks in parallel」はアプリ機能説明で、自動化・データ商品・スクレイピング対象のいずれでもない。
- 詳細は添付 evaluation_report.md。

## 3点評価

### 1) プロトタイプ — 不可
- ランディングは「desktop workspace for coding agents」「Join waitlist / Coming soon」のクローズドβのみ。
- 抽出可能な公開データ・DS・API ゼロ。robots.txt は Cloudflare content-signals、sitemap は社内ブログの9URLのみ。アプリ本体はクローズドソースで Kensho 資産とゼロ重複。

### 2) ローンチ手順 — 不可
- Kensho の配置経路（データAPI / 自動化 / FastAPI / Apify/RapidAPI）のいずれにも載らない。ネイティブデスクトップアプリは却下確定パターン。

### 3) 集客 — 不可
- HN score 3 / コメント1（ai.dosa.dev ツール一覧への掲載通知のみ）。観客規模ゼロ。

## verification_evidence

```
$ python /tmp/fetch_jk.py
  URL: https://jackalope.dev/            | 200 | text/html
  URL: https://jackalope.dev/robots.txt  | 200 | Cloudflare content-signals, CCBot/GPTBot/ClaudeBot Disallow
  URL: https://jackalope.dev/sitemap.xml | 200 | 9 urls (blog/changelog/privacy/terms 系のみ)
  URL: https://jackalope.dev/rss         | 404
  URL: https://jackalope.dev/feed.xml    | 200 | "Jackalope field notes" マーケティングRSS
  URL: https://jackalope.dev/api         | 404
  URL: https://jackalope.dev/api/feed    | 404
  URL: https://jackalope.dev/pricing     | 404
$ python /tmp/jk_hn.py
  TITLE: Show HN: Jackalope.dev | Hacker News
  POINTS: 3
  NUM COMMENTS: 1
$ python /tmp/jk_main.py
  "Jackalope — A desktop workspace for coding agents ... Get early access ... Coming soon"
```

冒頭から証跡セクション末尾まで言及 task_id は t_7c21061c（本タスク）のみ。
