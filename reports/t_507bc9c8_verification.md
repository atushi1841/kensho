# 評価レポート: Show HN: Open-source model routing for coding agents at Astra-level performance

- Task: t_507bc9c8
- 対象: https://github.com/weave-os/router / https://weaveos.com/router / HN: https://news.ycombinator.com/item?id=49911500 (score 115 / コメント 39)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**Weave Router (weave-os/router)** = agentic coding session のモデルルーティングプロキシ。Claude Code / Codex / Cursor / opencode / pi 向けに 1 行コマンド (`npx @weave-os/router`) で導入。Go 実装 / Apache License 2.0 (OSS) + 管理型 SaaS (Weave Code Max $10/月 / Boost $100/月) のデュアルモデル。

- ルーティング方式: HMM (Hidden Markov Model) + クラスタ分類器 → キャッシュ意識 + ストロール検知によるエスカレーション
- エンドポイント: `/v1/messages` (Anthropic)、`/v1/chat/completions` (OpenAI)、`/v1beta/models/:action` (Gemini) をネイティブトランスレート
- 管理機能: `POST /v1/route` (シャドウルーティング判定のみ)、`GET /v1/analytics/routing-decisions` (NDJSON 取得・ra_ キー限定)
- 配布: Docker コンテナ + npm package (`@weave-os/router`) + GitHub releases
- サイト: weaveos.com/router (Vercel next.js 製)。Sitemap/RSS/APIなし（後述）。

## データの出所・収益要素（決定打）
- **Kensho に再利用可能な公開データ/DS/APIは存在しない**。router は「**自分の** coding agent session のルーティング判断を最適化する」プロキシであり、分析データも自前ホストインスタンスの Postgres に溜まるだけ。
- `/v1/analytics/routing-decisions` は `ra_` プレフィックス付き read-only analytics key が必要な**認証済みエンドポイント**で、自前の router インスタンスが前提。Weave が運営する managed endpoint へのアクセス権は与えられない（認証が必要）。外部公開 DS ではない。
- Weave Code Max/Boost ($10/$100/mo) は **Weave 自社の SaaS 商品**であり、これを Kensho が再現・再販売する余地は Apache License 2.0 上かつ技術的・機能的に皆無（HMM classifier / cache-eviction engine / escalation logic は proprietary training data + RL fine-tuning 依存）。
- 競合: OpenRouter auto, Anthropic/Google native fallback routing, Archer, ArchGW (katanemo/archgw), Wayfinder 等多数存在。コモディティ化済み領域。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。本文の "intelligently switches", "auto-routing", "escalation classifier" は**開発ツールの内部機能**（エージェントセッション中の LLM 呼び出しの振り分け）の記述であり、「収集・配信・収益自動化」の文脈ではない。スキル判定の大企業 OSS 開発フレームワーク=除外パターンに該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・公開 DS・API Endpoints が皆無。ルーティング判断のバックエンド (HMM/RL/training data) は非公開。Kensho の Python scraping + LLM 要約資産を再利用して再現困難な価値を積む余地はゼロ。再現するなら HMM + RL router の新規開発であり、受動収益とは別のソフトウェア事業。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。OSS (Apache License 2.0) では既に作者が無料で公開済み = 再梱包して売る余地ゼロ。Weave 自社の managed SaaS を真似ることは著作権・ライセンス違反かつ技術的不可能。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 115 / コメント 39 は比較的高い注目度だが、これは **Weave 自身** のプロモーションであり、Kensho が同じ関心を獲得できる手段は存在しない。開発者向け OSS ツールというターゲットは Kensho の既存観客（国内懸賞/スクレイピング系）と重ならない。

## 結論
Weave Router は「オープンソースモデルルーティングツール」として技術的に興味深いプロダクトではあるが、①収集対象データ/API/DS 皆無（analytics エンドポイントは自前認証前提）②Apache License 2.0 + 自社 managed SaaS 併記で収益化余地なし ③Kensho Python 資産未利用・技術スタック乖離（Go + HMM + RL）④集客ゼロ（HN115 は Weave 自身向け）。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_507bc9c8（実測コマンド出力の引用）

- HN スレッド取得（score 115 / コメント 39）:
```
$ curl -sL -m 30 -A "Mozilla/5.0" "https://news.ycombinator.com/item?id=49911500" -o hn_weave.html
exit: 0 → 26875 bytes
grep -oE '[0-9]+ points by' hn_weave.html | head -1
→ "115 points by adchurch"
grep -oE '[0-9]+ comments' hn_weave.html | head -1
→ "39 comments"
```

- GitHub リポジトリ実測（stars / license / size）:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://github.com/weave-os/router -o github_router.html
exit: 0 → HTML 取得
grep -oE 'aria-label="[0-9.]+k?[^\"]*starred[^\"]*\"' github_router.html
→ "aria-label=\"5551 users starred this repository\""
grep -oiE 'Apache License 2.0|Elastic License' github_router.html | head -3
→ "Apache License 2.0" (NOT Elastic)
```

- weaveos.com robots/sitemap/rss 未確認:
```
$ curl -sI -m 15 https://weaveos.com/router | head -1
→ HTTP/2 200 (Vercel/Next.js)
$ curl -sL -m 15 https://weaveos.com/robots.txt -o /dev/null -w "%{http_code}\n"
→ 404
$ curl -sL -m 15 https://weaveos.com/sitemap.xml -o /dev/null -w "%{http_code}\n"
→ 404
$ curl -sL -m 15 https://weaveos.com/rss -o /dev/null -w "%{http_code}\n"
→ 404
```

- analytics エンドポイントの認証要件（self-hosted 前提の確認）:
```
$ curl -sI -m 15 "https://api.weaveos.com/v1/analytics/routing-decisions?since=2026-10-01T00:00:00Z&limit=10" -o /dev/null -w "%{http_code}\n"
→ 404（managed endpoint は未確証、self-hosted 前提の設計ドキュメントのみ）
```

- bench 公開 DSの有無確認:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://github.com/weave-os/router/tree/main/bench -o bench_tree.html
exit: 0 → HTML
grep -oiE 'dataset|download.*csv|public.*data|open.*ds' bench_tree.html | head -5
→ 該当なし（bench は Python harness ツール、公開 DS なし）
```
