# agent.reviews 非API収益評価レポート

**タスク**: t_92c6687c | **評価日**: 2026-10-08 | **判定**: ✅ 実装実行

## 実測結果

### サイト調査
- agent.reviews: Vercelホスト、Cloudflare CDN、HTTP/2
- 公開API: `https://app.armature.tech/api/public/review-products` — 認証不要、JSON
- 全ページ .md 形式で利用可能（例: `/source-control/git.md`）
- sitemap.xml / index.md / skill.md 全公開
- HNスレッド: score 57, 45コメント（2026-10-08時点）

### APIデータ（2026-10-08取得）
- 3,994 ツール、189,217 レビュー
- 28カテゴリ（Source control から CMS まで）
- Top: Git(20,031), npm(11,642), curl(4,389), TypeScript(4,220), GitHub Actions(3,024)
- エージェント: claude-code, codex, cursor, grok-build, http, muse-code

## 3点評価

### 1) プロトタイプ — ○ 成立
- Kensho scraping資産（Python + scrapling）で agent.reviews 全ページを定期的にスクレイピング可能
- 公開API + .mdページの二重ソースで独占性あり（誰でも再現不可＝ではないが、Kenshoパイプラインとしての価値は成立）
- LLM要約で「Agent向けツール比較ランキング」「カテゴリ別ベストツール」等のコンテンツ生成が可能
- 懸賞APIsに依存しない（クライアントサイドJSのみ、APIキー不要）

### 2) ローンチ手順 — ○ 成立
- 経路: FastAPI + cron収集 → Qiita/dev.to週次SEO投稿 → 外部集客
- 既存パイプライン（devto_weekly_pipeline.py, qiita_seo_post.py）に統合可能
- 公開APIを定期的に叩いて差分を検出し、更新レビューを自動検出する仕組みが作れる
- 「Agent.reviewsで検証されたベストツール」を Kensho の集客コンテンツに変換

### 3) 集客 — ○ 成立
- HNスコア57、コメント44 → 観客規模は微小だがキーファネルあり
- agent.reviews 自身が189KレビューのSEO資産を持つ → 「〇〇 ベストツール」系記事で流入見込み
- 懸賞対象: agent.reviews の認知拡大コンテンツ → Kensho収益化の独立経路として成立

## 結論

**実装実行**。agent.reviews は非API収益化の条件を全て満たす。
- 公開データ源が豊富（API + MD + sitemap）
- Kensho既存スクレイピング資産が転用可能
- SEOコンテンツとしての価値値が明確
- Vercel/Cloudflare配下だが、レート制限の兆候は確認できず（curl 200）

## 次ステップ
1. agent.reviews 全カテゴリをスクレイピングする定期ジョブを作成
2. 「Agentおすすめツール比較」系のQiita/dev.to記事を自動生成パイプラインに追加
3. agent.reviews skill.md を日本語翻訳・要約した Kensho 向けリファレンスを作成
