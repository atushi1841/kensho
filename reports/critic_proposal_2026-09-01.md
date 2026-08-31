# Kensho Critic 改善提案 — 2026-09-01（第45版・深夜更新）

> **分析対象**: 8/31日次最終レポート（687アクション）+ audit.jsonl実測検証
> **重要訂正**: anchorの「prop94 終日超過0確定」は**正しい**（実アクションhourly≤15全垢）。ただしレポートの「時間集中」はalready_*を含む集計アーティファクト（atushi16 12時=15実+1already、chugaku 08時=15実+2already）。

## エグゼクティブサマリー

| 監視項目 | 値 | 判定 |
|---------|-----|------|
| 8/31実アクション成功 | atushi16 104 / Tankan 108 / chugaku 100 / kudou 100 / zin 67 / ib 87 | ✅ |
| prop98 日次総量キャップ | 発動済（8/31 19時〜LIMITログ76件）⚠️ atushi16/Tankan=100超（prop100未発効時） | ✅ 発動確認 |
| prop100 アクション単位厳格チェック | **実装済（6087bd9）・QA49検証済 → 9/1 daily_countsで100丁度確認待ち** | 🆕 最重要監視 |
| prop94 hourly≤15 実効性 | **全垢real_hourly_max=15・超過0**（レポートの16-17件はalready_*アーティファクト） | ✅ 確定 |
| レポート精度 | already_*（既に完了済み）を成功に計上 → 成功件数+1-2/h及び達成率の過大表示 | ⚠️ 軽微 |
| toushiwatch | 0件（config除外中・要ユーザー対応） | 🔴 継続 |
| zin 1084 | 切断12回/日・dead確認（00:15） | 🔴 要ユーザー対応 |
| BOT安全監査 | シグナルなし | ✅ |

## 新規提案（1件）

### prop101【低】: daily_pipeline_report.pyの集計からalready_*除外

**根拠（実測）**: 8/31実アクション成功=104/108/100/100/67/87（全垢daily_counts一致）。レポートに表示された「時間集中（atushi16 12時=16、chugaku 08時=17）」は、audit.jsonl上でstatus=successかつreason=already_liked/already_retweetedのエントリを含めた集計による。実アクションはatushi16 12時=15（+1already）、chugaku 08時=15（+2already）で、prop94のhourly≤15は**終日完全に有効**。already_*は新規アクションを伴わないため、除外すべき。

**期待効果**: レポートの「時間集中」誤報排除、成功件数・達成率の正確性向上（daily_countsと一致）、運用判断の誤り防止。

**実装コスト**: 低（daily_pipeline_report.pyでstatus==successに加えreasonがalready_*でないもののみをカウント）

**リスク**: なし（集計ロジックの微修正のみ）

## 監視継続項目

- **🔴最重要**: prop100効果確認（9/1 daily_countsでatushi16/Tankan/chugakuが100丁度で停止しているか）— 次QAの最重要項目
- toushiwatch: config除外中。復帰条件＝ブラウザでログイン→auth_token/ct0保存→configコメント解除
- zin 1084 フラッピング: 切断12回/日継続
- inobase1-4 no_follow_button 15件: 監視継続（再発で提案化）
- zin http_0 19件: 1084フラッピング起因（改善待ち）
