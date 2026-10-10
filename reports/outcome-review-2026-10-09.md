# Outcome Review 定期再確認 2026-10-09

対象: 過去7日間（2026-10-02以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=161件（2026-10-02以降）/ 数値KPIあり=40件
- 実測確認: あり=33件 / 未実測=7件 / KPI非該当=121件
- 実測確認率: 82.5%（目標>50%） → 達成
- 実測済みタスク:
  - `t_f02878ee` apify_store_badges_added 0→8 (方向: up)
  - `t_08a7ba62` pseudo_done_fixed 1→0 (方向: down)
  - `t_b71a800a` actor_count 16→6 (方向: down)
  - `t_b9cb9a48` external_runs 0→0 (方向: equal)
  - `t_723b9d84` Qiita public apify-linked articles 0→2 (方向: up)
  - `t_3b063251` Smithery MCP公開数 0→1 (方向: up)
  - `t_a898df9c` Hatena/Bookmark 関連 Apify Actor 数（更新対象） 0→0 (方向: equal)
  - `t_68d83095` 検証セクションに before→after 記載
  - `t_5e56e00f` dev.to公開記事数 43→44 (方向: up)
  - `t_e3e0d19c` 検証セクションに before→after 記載
- ⚠️ after<before: 26件（悪化疑い 2件 / 方向未宣言 24件）
- 悪化疑いの詳細:
  - `t_d28cf2a8` HF Space public count 0→2 (方向: up)
  - `t_2d49610b` README apify.com link count 4→14 (方向: up)
- 方向未宣言の詳細:
  - `t_f02878ee` apify_store_badges_added 0→8 (方向未宣言)
  - `t_08a7ba62` pseudo_done_fixed 1→0 (方向未宣言)
  - `t_b71a800a` actor_count 16→6 (方向未宣言)
  - `t_b9cb9a48` external_runs 0→0 (方向未宣言)
  - `t_723b9d84` Qiita public apify-linked articles 0→2 (方向未宣言)
  - `t_3b063251` Smithery MCP公開数 0→1 (方向未宣言)
  - `t_a898df9c` Hatena/Bookmark 関連 Apify Actor 数（更新対象） 0→0 (方向未宣言)
  - `t_5e56e00f` dev.to公開記事数 43→44 (方向未宣言)
  - `t_5ab9300b` README_apify_links_verified 0→3 (方向未宣言)
  - `t_f5f6f8a9` dev.to article published 0→1 (方向未宣言)
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_d1df914c` 懸賞応募の有効性検証＋当選トラッキング台帳の整備（当選0の切り分け）（kensho-worker）
  - `t_7658589a` dev.to週次SEO投稿にApify PPEアクターへの外部リンクを追加し外部流入を促進（kensho-revenue-worker）
  - `t_7159cada` Error-streak cron5本を統合Health Checkへ移管（kensho-revenue-worker）
  - `t_50796569` Qiita週次SEO投稿を本番化: W41分2本をQiita APIで公開し外部流入チャネルを拡大（kensho-revenue-worker）
  - `t_6e640220` Generate SEO-friendly descriptions for repos（kensho-revenue-worker）
  - `t_74141fe5` MCP公式レジストリ経由で既存Apify actorを外部流入チャネルへ再配布（kensho-revenue-worker）
  - `t_5c77082d` 収益モニタリング一本化（4つのerror cronを統合Health Checkへ）（kensho-revenue-worker）

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-10-09.md`（≥5 で KPI方向性ルールの適用を確認）
