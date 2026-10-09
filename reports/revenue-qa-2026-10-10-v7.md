# 収益QAレポート 2026-10-10 v7（06:10 JST）

## ループ健康度
- score=49（前回39→改善）、stagnation_streak=0（前回3→解消）、priority=normal
- 前回v6で確定した「artifact_age誤検知」は盤面が動いたことで streak=0 に自然解消。
  ただし恒久修正カード t_8852e33d は ready のまま未実装 → park誤爆リスクは残存、次ワーカー待ち。
- done 889（1hで+1: t_957e7220）、ready 2（t_8852e33d / t_83f71c1e）、blocked 0。

## running 2件の生存確認（pgrep + task_events）
- t_d03a52b0（Apify ActorへGitHubリポジトリURL追加）: PID 1185560 生存、heartbeat 06:05-06:07 連続。着手02:40、まだ成果コミットなし → 検証は完了待ち。
- t_bafd539a（死プロキシ垢kudou応募停止）: PID 1221054 生存、heartbeat同上。kudou停止自体は commit 442e98d で済済み、後続作業中と判断。

## 未コミットコード監視
- config.yaml: atushi16 batches max 7→10（8バッチ）が uncommitted。runningワーカー所有と判断し非介入（notepad教訓v6準拠）。
  → 注意: ワーカー終了後も uncommitted のままなら done guard (d) で閉塞する。次QAで再確認。

## Apify外部流入（runs API userId実測）
- $APIFY_TOKEN の自垢userId = VMz6nlpHoGIjTeSXS（tokens/currentはtoken種別でuserId非返回のため、runs 100件のuserId分布で確定）
- 直近 actor-runs 100件 = 全て VMz6nlpHoGIjTeSXS → **外部流入 0 継続**（32日目）。
- actors 81本（前回監査86→81、統合/削除で減少した可能性、要次回確認）。

## 観点別分割検証（delegate未設定のため単一パス5観点・skill代替案条項）
1. コード品質 8/10: f243430 で孤立スクリプト取り込み済み＝共有repo uncommitted閉塞の恒久解消は妥当
2. BOT検出リスク 7/10: atushi16 max 7→10 は1日56→80件相当。1h20アクション上限内だが上限引き上げは検出リスク増、実応募ログで間隔確認要
3. 設計一貫性 8/10: kudou停止は batches コメントアウト方式（ユーザー確定方針準拠）
4. テスト充足 6/10: batch上限変更に対するテスト/実測記録がまだ無い
5. ライブ計測 7/10: Apify runs実測は決定論的。dev.to canonical views再実測は24-48h後（t_957e7220 done 05:11）で本実行では対象外

## 3軸評価
- technical 8: 誤検知解消・孤立スクリプト取り込み・userId決定論検証が定着
- business_kpi 4: Apify外部run 0継続（32日）。dev.to重複解消の効果測定は明日
- cost_efficiency 8: 新規コストなし、監視修正はカード起票のみ

verdict: conditional_pass（running 2件の完了検証とviews再実測が未了）

## 申し送り
- t_d03a52b0 完了時: Apify Actorの README/repositoryUrl にGitHub URLが入ったか API実測で検証すること（設定側打ち切り済みだが「信頼の証拠」系統は例外）
- config.yaml uncommitted（atushi16 7→10）: 次QAで commit 済みか確認。未コミットかつワーカー終了済みなら done guard (d) 閉塞として triage
- actors 86→81 の減少理由を次回收集監査で確認
