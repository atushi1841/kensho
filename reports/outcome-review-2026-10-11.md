# Outcome Review 定期再確認 2026-10-11

対象: 過去7日間（2026-10-04以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=178件（2026-10-04以降）/ 数値KPIあり=46件
- 実測確認: あり=40件 / 未実測=6件 / KPI非該当=132件
- 実測確認率: 87.0%（目標>50%） → 達成
- 実測済みタスク:
  - `t_ec1cbe4f` actor_count 9→85 (方向: up)
  - `t_83c84e86` dev.to 記事のApify Store外部链接未適用件数 1→0 (方向: down)
  - `t_680be7c9` Qiita apify.com links with utm_source=qiita 0→4 (方向: up)
  - `t_bc9e7140` MCP Registry atushi1841 servers 11→14 (方向: up)
  - `t_25832581` glama_registered_count 0→5 (方向: up)
  - `t_870a49c7` repos_with_mcp_json 0→10 (方向: up)
  - `t_8852e33d` artifact_age_penalty 30→0 (方向: down), loop_health_score 39→59 (方向: up), stagnation_streak 3→0 (方向: down)
  - `t_957e7220` dev.to公開一覧の重複タイトルグループ数 13→0 (方向: down)
  - `t_81919d6f` dev.to MCP紹介記事公開数 0→1 (方向: up)
  - `t_974844f8` card_templates_created_with_completion_criteria 0.005→1.0 (方向: up)
- ⚠️ after<before: 33件（悪化疑い 2件 / 方向未宣言 31件）
- 悪化疑いの詳細:
  - `t_d28cf2a8` HF Space public count 0→2 (方向: up)
  - `t_2d49610b` README apify.com link count 4→14 (方向: up)
- 方向未宣言の詳細:
  - `t_ec1cbe4f` actor_count 9→85 (方向未宣言)
  - `t_680be7c9` Qiita apify.com links with utm_source=qiita 0→4 (方向未宣言)
  - `t_bc9e7140` MCP Registry atushi1841 servers 11→14 (方向未宣言)
  - `t_25832581` glama_registered_count 0→5 (方向未宣言)
  - `t_870a49c7` repos_with_mcp_json 0→10 (方向未宣言)
  - `t_8852e33d` artifact_age_penalty 30→0 (方向未宣言)
  - `t_8852e33d` stagnation_streak 3→0 (方向未宣言)
  - `t_957e7220` dev.to公開一覧の重複タイトルグループ数 13→0 (方向未宣言)
  - `t_81919d6f` dev.to MCP紹介記事公開数 0→1 (方向未宣言)
  - `t_974844f8` card_templates_created_with_completion_criteria 0.005→1.0 (方向未宣言)
  - `t_c42a9eb6` external_runs_triggered 0→0 (方向未宣言)
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_d1df914c` 懸賞応募の有効性検証＋当選トラッキング台帳の整備（当選0の切り分け）（kensho-worker）
  - `t_7658589a` dev.to週次SEO投稿にApify PPEアクターへの外部リンクを追加し外部流入を促進（kensho-revenue-worker）
  - `t_7159cada` Error-streak cron5本を統合Health Checkへ移管（kensho-revenue-worker）
  - `t_50796569` Qiita週次SEO投稿を本番化: W41分2本をQiita APIで公開し外部流入チャネルを拡大（kensho-revenue-worker）
  - `t_6e640220` Generate SEO-friendly descriptions for repos（kensho-revenue-worker）
  - `t_74141fe5` MCP公式レジストリ経由で既存Apify actorを外部流入チャネルへ再配布（kensho-revenue-worker）

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-10-11.md`（≥5 で KPI方向性ルールの適用を確認）
