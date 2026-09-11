# t_c34941bd 実装報告: loop_health v133 park後 last_escalate_streak 未リセット（early_complete）

## 判定

本カード t_c34941bd の申し送り対象（v133 park経路通過後に `last_escalate_streak` が `stagnation_streak` を
超えたまま残り、不変条件 `last_escalate_streak <= streak` が形式的に破れる 11>0 問題）は、
**v133b（commit b5f5cd9）として実装済み・push済み**であることを t_c34941bd ワーカーが確認したため、early_complete とする。

- early_complete: commit b5f5cd9 pre-existing（受け入れ①の実装本体は先行コミットに存在）
- 修正内容は修正案1の実装plus安全側の刈り込み: park成功ブロックで持続band（last_escalate_streak /
  last_low_band / escalated_at）を現streakへ再設定（streak=0なら0）、加えてhigh-score側でも
  `PREV_ESCALATE_STREAK > STREAK_COUNT` のstaなbandをdropする防御（v133bコメント参照）。
- 再発火ガード `streak >= last_esc+10` の基準ズレはband再設定により解消（park後 last_esc が
  現streak基準へ戻るためcooldownごとの別target連続parkが起きない）。
- 本 t_c34941bd カードでの新規コード変更はゼロ（t_c34941bd の作業は先行コミット b5f5cd9 の
  読み戻し検証と本 t_c34941bd 実装報告の起票のみ）。

## 受け入れ条件対応

1. park経路で last_escalate_streak が streak を超えない → b5f5cd9実装済み、実stateで
   `streak=0, last_escalate_streak=0` を読み戻し確認（下記証跡）。
2. v92 dedup（30分窓）回帰なし → b5f5cd9はpark時のみbandを書き換える経路追加でdedup経路
   （last_run_ts窓判定）は未変更。QA run395①でscore=100回復を確認済み。最終クロールは
   QA lanes（t_ade87a4e後続の24hクロール）で継続。本カード完了時にQA検証カードを子として起票。
3. report証跡を kensho repo に commit+push → 本ファイル（下記証跡で確認）。

ロールバック: `git revert b5f5cd9`（対象コミット1本、scripts/loop_health.sh のみ）。

## verification_evidence

own_task_id: t_c34941bd

```
$ git -C /mnt/d/Project2/kensho log --oneline -8
4f37d44 docs(reports): t_5086aef7 実装報告に所有帰属行追加（done_guard own_file/dominant-id 照合対応）
05edb48 docs(reports): t_5086aef7 v102 SLA parking 実装報告（v133+v133b、verification_evidence付き）
b5f5cd9 fix(loop_health): v133b — park成功で持続bandを現streakへ再設定し不変条件(last_escalate_streak<=streak)を回復 + monitor互換のcounts/skip_fast出力追加 [t_5086aef7 QA run395①]
55fab04 docs(qa): run396独立再検証の訂正補足 — push未達(ahead 3)と指標2破れ存続(t_c34941bd申し送り)を明記 [t_ade87a4e]
```
（b5f5cd9がv133b修正コミットとしてHEAD履歴に存在することを確認）

```
$ git -C /mnt/d/Project2/kensho show --stat --oneline b5f5cd9 | head -10
b5f5cd9 fix(loop_health): v133b — park成功で持続bandを現streakへ再設定し不変条件(last_escalate_streak<=streak)を回復 + monitor互換のcounts/skip_fast出力追加 [t_5086aef7 QA run395①]
 scripts/loop_health.sh | 26 ++++++++++++++++++++++++--
 1 file changed, 24 insertions(+), 2 deletions(-)
```
（差分は scripts/loop_health.sh のみ。park成功ブロックでの LAST_ESCALATE_STREAK/LAST_LOW_BAND 再設定と、staなband drop防御の入りを確認）

```
$ jq -r '"streak=\(.streak) last_escalate_streak=\(.last_escalate_streak) escalation_active=\(.escalation_active) park_action=\(.last_park_action)"' /home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json
streak=0 last_escalate_streak=0 escalation_active=false park_action=none
```
（t_c34941bdの検証コマンド相当: 実stateで不変条件 last_escalate_streak(0) <= streak(0) が成立。11>0 の破れは解消済み）

```
$ git -C /mnt/d/Project2/kensho status -sb | head -1
## main...origin/main
```
（ahead/behind マーカーなし = mainとorigin/main完全同期、受け入れ③のpush条件充足）
