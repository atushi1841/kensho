# 収益化QAレポート 2026-10-10 04:10 JST（v5）

## ループ健康度（実測）
- score=49（前回39→回復）、stagnation_streak=0、priority=normal、alert=WARN
- artifact_age_penalty=30 の原因: t_e0a0f6cc の artifact_age_hours=1.79e+308（=inf、成果物未検出）。t_1df4f8c4 は 1.13h で正常。
- escalation_target=t_e0a0f6cc（escalation_age_h=2、park_after_h=24 → park_action=none。24h超で自動park、それまで監視）
- ready=2 / running=2 / blocked=0 / done=886。cap_profile=2・cap_dispatcher=2 で一致、orphan/zombie/stale なし。

## 前回からの回復確認（t_52b46f88）
- 前回QAで regress 検出した devto-links.json は `reports/apify-seo/devto-links.json` に applied=true / rows=2（W44 MCP記事 id=4825048 ほか）で回復済。t_52b46f88 は 03:55 done。
- 注: rows が 82→2 に減少しているが、これはファイル構造が「直近適用分」持ちは異なり過去分喪失ではない（git bed3c869 系で履歴あり）。次回 worker に全件再適用の必要はなし。

## t_81919d6f（done 03:53）検証
- dev.to API 実測: `GET https://dev.to/api/articles/4825022` → 200、title="I Published 10 Free MCP Servers for Japanese Data…"、url=…/…-3dfh。記事実在確認済。
- views/positive_scores は API で None（dev.to はオーナー別経路でのみ公開）→ 流入計測は後日 external_traffic_state.json 側で確認。

## Apify external_runs 実測（重要・誤測定訂正）
- `data/apify_ppe_external_runs_state.json` の last_trigger 20件は全て 2026-10-09T16:51-52Z（=10/10 01:51 JST）。t_c42a9eb6（週次PPE外部run自動化パイプライン、01:53 done）の**自走パイプライン実行**であり、外部ユーザー流入ではない。MCP記事公開（03:53）より前。
- → 外部流入は依然 0。次の計測点: MCP記事 4825022/4825048 公開後の 24-48h 以内の last_trigger 増分（自run除外のため actor_weekly パイプライン時刻との対照が必要）。

## 未コミットコード（running ワーカーの作業中・触らない）
- `config.yaml`（72行変更）+ `scripts/actor_weekly_run.py`（50行）+ untracked: apply_readme_fix.py / add_mcp_smithery_links.py / add_smithery_links.py / kanban_done_guard.sh / test_env.py
- 所有推定: t_e0a0f6cc（mechatoku/appare、running）と t_1df4f8c4（UTM、running）。二重処理防止規律により QA は commit しない。done 時に guard 条件(d)(e)で自動的に検証される。
- 衛生申し送り: untracked の test_env.py / apply_readme_fix.py は done 後も残ったら削除 or commit 対象に整理すべき。

## 観点別分割検証（本runは実測検証中心。delegate分割は前回まで稼働済）
1. コード品質: 7/10 — 2adb683（UTM付与）は1行変更で最小スコープ。未コミット分は検証不能（作業中）。
2. BOT検出リスク: 9/10 — 本run対象に応募系変更なし。dev.to/X投稿は既存テンプレ範囲。
3. 設計一貫性: 8/10 — devto-links.json の applied フラグ運用は前回契約と整合。
4. テスト充足: 6/10 — t_e0a0f6cc の検証レポートがまだ出ていない（inf penalty の原因）。
5. ライブ計測: 7/10 — dev.to API 200 実測、Apify state は自run/外部区別が必要と判明。

## 3軸評価
```json
{"evaluation":{"technical":{"score":7,"assessment":"devto-links回復とMCP記事公開は実在確認。検証レポート未出力のrunningカードが残存","evidence":"devto API 200 id=4825022; devto-links.json applied=true rows=2"},"business_kpi":{"score":4,"assessment":"外部流入は依然0。last_trigger 20件は自走パイプラインと判明（前回教訓の裏付け）","evidence":"last_trigger全件=10/10 01:51JST、パイプラインdone 01:53より前"},"cost_efficiency":{"score":8,"assessment":"新規コストなし、既存cron/記事資産の再配布のみ","evidence":"dev.to API無料・Apify PPE自run"}},"loop_health":{"score":49,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"t_81919d6f/t_52b46f88 の検証証跡はguard経由で実在"},"verdict":"conditional_pass","next_steps":["t_e0a0f6cc の検証レポート出力を次回確認（24h超で自動park）","MCP記事公開後24-48hのlast_trigger増分を外部流入として再実測","untrackedスクリプト5件の整理（commit or 削除）"]}
```

## 申し送り
- 【監視】Apify last_trigger は自runと混在。外部流入判定には「パイプライン実行時刻以外」のフィルタ必須。
- 【停滞】t_e0a0f6cc の artifact_age=inf は成果物ファイル未生成。escalation 2h、park 24h まで監視のみで介入不要。
