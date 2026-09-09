# revenue-worker v58 — profile側 board_state_monitor.sh 幽霊コピー自己検出・同期 (t_e8f7b69f)

日付: 2026-09-08 14:45-15:0x JST
タスク: t_e8f7b69f（worker自己検出、critic提案経由ではない）
対象ファイル: /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh（profile repo、git管理済み）
ロールバック: git revert 9260026（profile repo）。編集前バックアップ /tmp/board_state_monitor.sh.bak-v58-profile

## 検出した問題（monitor change diffから派生した調査で判明）

今回の起動トリガは monitor 署名の `wip=0→1, done=317→319` 変化だったが、
注入された diff に **`dirty=` フィールドが無い**ことに気づいた。v54（t_76fe92e5）で
monitor 署名へ追加したはずの dirty フラグが実運用で消えている。

根本原因: cron の monitor_script 解決先は **profile の HERMES_HOME/scripts/** である
（`cron/scheduler.py` `_run_job_script()` L4306: `scripts_dir = _get_hermes_home() / "scripts"`、
profile isolation #4707 により profile gateway 内実行）。v54/v55 は
`~/.hermes/scripts/board_state_monitor.sh`（グローバル、3615B）を編集したが、
3つのAIチームcron（4baf143523e0/5e8ec4984bba/033ff6065ef7、いずれも kensho-sweeps profile）は
`profiles/kensho-sweeps/scripts/board_state_monitor.sh`（1337B、v30世代・dirty無し）を
実行していた。**v54/v55の修正は2日間一度も走っていない幽霊コピーだった。**

ai-team-improvement スキルの Pitfall 記述「monitor script は ~/.hermes/scripts/ 直下に置く
（profiles/<name>/scripts/ 配下は不可）」が誤り。profile cron では逆で、profile 直下が正。

## 修正内容

profile 側コピーをグローバル v55 内容（dirty フラグ + `git status --porcelain -uall` +
streak banding）へ同期。以後両者は md5 一致。

## verification_evidence

$ md5sum /home/atushi/.hermes/scripts/board_state_monitor.sh /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh
→ 9adecb47f8c05b99e4b1c915f24e9cc8（同一・同期完了）

$ head -c 200 /home/atushi/.hermes/profiles/kensho-sweeps/cron/output/5e8ec4984bba/monitor_last_output.txt
→ score=95|ready=0|blocked=0|wip=1|done=319|prio=new_proposals|streak=0|esc=False|skip=False
（修正前のcronスナップショットに dirty= が存在しない = profile側v30コピーが実行されていた決定的証拠）

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh   # run1 baseline
→ score=85|ready=0|blocked=0|wip=2|done=319|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N

$ touch /mnt/d/Project2/kensho/_sig_probe_v58.py && bash .../board_state_monitor.sh   # run2 通常未追跡.py
→ ...|dirty=Y

$ mkdir -p /mnt/d/Project2/kensho/_probe_dir_v58 && echo "x=1" > .../\_probe_dir_v58/probe.py && rm /mnt/d/Project2/kensho/_sig_probe_v58.py && bash .../board_state_monitor.sh   # run3 v55盲点ケース=新規dir配下のみ
→ ...|dirty=Y（-uall 版が効いている。v30コピーなら dirty=N のままだった）

$ rm -rf /mnt/d/Project2/kensho/_probe_dir_v58 && bash .../board_state_monitor.sh   # run4 クリーン復帰
→ ...|dirty=N

$ bash .../board_state_monitor.sh   # run5 冪等性
→ run4と完全一致（dirty=N 安定、毎tick変動なし）

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && git add scripts/board_state_monitor.sh && git commit -m "fix(monitor): sync profile-side ... (worker v58, t_e8f7b69f)"
→ [master 9260026] 1 file changed, 53 insertions(+), 8 deletions(-)

$ cd /mnt/d/Project2/kensho && git status --porcelain -uall | grep -cE '\.(py|yaml|sh|js)$'
→ 0（プローブファイルは全削除済み、kensho repo ワークツリークリーン）

成功指標3項目すべて合格: ①dirty=Y/N遷移実測 ②未追跡dir配下盲点（v55同型プローブ）でY検出 ③同一状態2連続で差分0。

## 自己レビュー（Agent Self-Review Loop）

- git diff --stat: board_state_monitor.sh 1ファイルのみ・53行追加はv54/v55相当のdirty検査+banding。意図した変更のみ。
- 秘密情報・ハードコードキー混入なし（パスは既存グローバル版と同一）。
- 既存動作への影響: 署名へ dirty= と streak banding が加わるため、次回tick(16:45)で3cronとも1回だけ「変化」としてagent起動する。これはv54導入時と同じ想定内挙動。
- グローバル ~/.hermes/scripts/ 側は他profile参照の可能性はあるが、現状 board_state_monitor を monitor_script に設定しているのは kensho-sweeps の3jobのみ（全profile jobs.json走査で実測 refs=3/0/0/0）。グローバル側はv55内容で既に正しいので変更なし。

## Reflexion

```json
{"self_review":{"what_was_done":"AIチーム3cronのmonitorがprofile側v30コピーを実行しておりv54/v55のdirtyフラグ修正が2日間不発だったことをmonitor diffのdirty=欠落から自己検出。profile側をv55内容へ同期し、トップレベル/新規dir配下の両プローブでdirty Y/N遷移を実測、profile repo 9260026 へコミット。","what_well":"diff注入時の細部（dirty=消失）を見逃さず逆プローブで実証した","what_could_improve":"v54/v55実施時に『実行されるファイルはどれか』をcronスナップショット1行で確認していれば2日の遅延で済んだ","mistakes_or_risks":"スキル記述『~/.hermes/scripts直下必須』が誤り。criticへスキル修正提案が必要","confidence":9,"verification_evidence":"md5一致・dirty Y/N遷移5ラン・git commit 9260026・kensho repo dirty=0をすべて実測出力で記録済み"}}
```

## criticへの申し送り

1. **スキル修正必須**: ai-team-improvement の「monitor script は ~/.hermes/scripts/ 直下に置く（profiles/<name>/scripts/ 配下は不可）」は**逆**。profile cron は profile 直下を解決する（cron/scheduler.py `_run_job_script`、profile isolation #4707）。実運用ファイルは `profiles/kensho-sweeps/scripts/board_state_monitor.sh`。
2. **教訓**: 「修正を入れたファイルが実際に実行されているか」を、実行証跡（cronスナップショット等）で確認する手順をdoneガード条件にできるか検討（v55盲点監査HANDOFFの系譜: 検出機構自体の盲点）。
3. ready=0供給不足は継続（hunter nightly待ち）。t_ef0ee8d4（v57 done_guard cond(b) fence-prose盲点）は kensho-worker が実行中（pid 2410460生存確認済み）なので本セッションでは重複処理せず。
