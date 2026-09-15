# Critic観察レポート 2026-09-15

対象: 前日 2026-09-14
- KENKAKU平均取得: 10.4件（14セッション）
- ConnectTimeout: 47件/day
- [源別ConnectTimeout] KENKAKU=11 KCLUB=14 KEMA=13 CPMK=9（計47件）
  - KENKAKU: 11件
  - KCLUB: 14件
  - KEMA: 13件
  - CPMK: 9件
- apply成功率: 91.2%（成功540/エラー52）

## v150追記（21:2x 再観察）
- 【訂正】v144 t_902d09ac: 20:29 commit 7448138 で適用done（ユーザーGO 20:25頃 会話実測 @session:kensho-sweeps/20260915_194615_c4cac15a）。19:5xまでの台帳ベース「GO待ち」判定は遅延による旧情報。
- リトライ初回発火実測: `logs/collect_20260915_210001.log` に「ページ104510000: ConnectTimeout → リトライ1/2（2s待ち）」×2、ken-kaku 15件取得維持（20時=15件と同水準）。
- 9/15終日CT=46件（KENKAKU13含む・適用は20:29以降のみ有効）→ 真の効果測定は9/16 07:55 timeout_watch.tsv。
- timeout-watch自動起票: 2日連続超過成立も未クローズガード（t_902d09ac done）でスキップ=設計通り。
- apply: 222/265=83.8%（21時時点・日未完了。前日91.2%比で要再確認）。
- 報告衛生: done 16件中15件 resultカラム空（QA指摘の実体=CLI `--summary` がeventsのみに記録）。
