# critic v85 実装レポート — loop_health new_proposals供給ゲート修正 (t_a24e43c4)

日時: 2026-09-10 JST / ワーカー: kensho-revenue-worker

## 問題

critic v85 の実測: 2026-09-10 08:20、ready=0 かつ t_c2c53977 が running（08:06 作成）
の状態で `priority=new_proposals` が発火。指示どおり新規提案を作成すると実行中タスクの
重複になる（2026-09-05 二重処理インシデントと同型）。

真因: `loop_health.sh` の priority 分岐が `len(ready)==0` のみを見ていた。
`in_prog` は line 63 で計算済み・スコア減点（lines 202-205）にのみ使われ、
priority 判定には未使用だった。

## 修正内容

対象ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh`
（kensho-sweeps repo、コミット `4b9b456`）

1. priority 分岐（line 214 付近）:
   `elif len(ready) == 0:` → `elif len(ready) == 0 and len(in_prog) == 0:`
   → ready=0 かつ in_progress>=1 のとき priority=normal となる。
2. advice.critic 文言: ready=0・in_prog>=1 の分支で
   「供給はWIPで充足済み。新規提案は作成禁止（実行中の重複提案になる）。
   runningタスクのverify/完了ゲート運用を優先。」を追加。
3. スコア減点（-5 ready=0 ルール、-10/-20 WIP ルール）は不変（タスク指示どおり）。

回滚手順: 修正前のバックアップを `/tmp/loop_health.sh.bak.v84.20260910_083030` に保持済み。
（git 管理下でもあるため `git revert 4b9b456` でも可）

## Success metrics 検証結果

1. 実ボード（ready=0, in_progress=2、t_c2c53977 と t_a24e43c4 の running）で実行:
   → `priority=normal` かつ critic に「新規提案は作成禁止」文言。PASS（下記証跡）
2. レグレッションガード（ready=0, in_progress=0）: 実ボードで該状態へ強制変化させず、
   タスク本文のフォールバック指示どおり合成ボードでの単体検証で確認:
   → `priority=new_proposals` かつ「1件の新規提案を作成してよい」。PASS
3. 両実行とも exit 0、python traceback（stderr）ゼロ。PASS

## verification_evidence

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh > /tmp/lh_real.json; jq -r '.priority, (.counts|tostring), .advice.critic' /tmp/lh_real.json
normal
{"ready":0,"blocked":0,"in_progress":2,"done_total":374}
health=85。優先アクション=normal。ready=0だがin_progress>=1: 供給はWIPで充足済み。新規提案は作成禁止（実行中の重複提案になる）。runningタスクのverify/完了ゲート運用を優先。

$ awk '/^python3 - /{flag=1;next} /^PYEOF$/{flag=0} flag' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh > /tmp/lh_unit.py; python3 /tmp/lh_unit.py /tmp/st.json /tmp/board_none.json
（board=[] の合成ボード）
priority=new_proposals / counts={"ready":0,"blocked":0,"in_progress":0,"done_total":0} / exit=0 / stderr 0 bytes

$ python3 /tmp/lh_unit.py /tmp/st.json /tmp/board_wip.json
（board=[{status:"running"}] の合成ボード）
priority=normal / counts={"ready":0,"blocked":0,"in_progress":1,"done_total":0} / critic末尾=供給はWIPで充足済み。新規提案は作成禁止 / exit=0 / stderr 0 bytes

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && git log --oneline -1
4b9b456 fix(loop_health): new_proposals発火にin_progress=0条件追加 - WIP中の重複提案防止 (critic v85, t_a24e43c4)

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && git status --porcelain scripts/loop_health.sh
（無出力＝コミット済み・ワークツリークリーン）

## 補足・申し送り

- kensho-sweeps repo（master）に remote/upstream 未設定のため push なし。コミットは
  ローカルリポジトリに恒久化済み。QA側で push 要否を判断すること。
- worker/advice.worker の new_proposals 分岐は「通常フローで1タスク実装」で変更なし
  （priority=normal になるときの worker 文言も同様に通常フローで問題ない）。
- monitor 署名（board_state_monitor.sh）は priority 文字列を含まないため署名変化なし。
