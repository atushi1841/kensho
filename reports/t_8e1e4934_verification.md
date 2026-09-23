# t_8e1e4934 QA検証証跡 — t_d5ac9f32 DeepSeek鍵ローテーション done_guard準拠の再確認

## verification_evidence

nightly-qa（033ff6065ef7）が 2026-09-24 01:5x JST に、このカードの検証条件6項目を一次証跡で独立再測定した。
前回測定（2026-09-23 22:25 のコメント）で **FAIL していた条件3のみ** が以後の兄弟タスク完了で解消し、
**6/6 PASS** に到達したことを確認した。

### 条件1/2: 証跡レポートの見出しとコマンド引用

$ grep -n 'verification_evidence' reports/t_d5ac9f32_verification.md => 3:## verification_evidence
$ grep -cE '^[[:space:]]*[$] ' reports/t_d5ac9f32_verification.md => 5
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_d5ac9f32 --workdir /mnt/d/Project2/kensho => PASS (all conditions satisfied) / worker_output_file: /mnt/d/Project2/kensho/reports/t_d5ac9f32_verification.md / own_file: True (owner_task_id=t_d5ac9f32) / a verification_evidence: True / b command cites >=3: True (count=5)

### 条件3: リポジトリに未コミットコードが無いこと（前回FAIL→今回PASS）

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_d5ac9f32 --workdir /mnt/d/Project2/kensho => d no uncommitted code: True (scope=repo)

（前回FAILの真因は t_96c94435 / t_0b949bda の実行中WIP。両タスクは 2026-09-24 01:2x〜01:4x に done 化済みで、
以後 `git status` のコードファイル差分は当QA実行中の別タスクWIPのみ。`git checkout` による巻き戻しは兄弟作業破壊のため禁止のまま。）

### 条件4: バックアップ .env が5件存在

$ ls -1 /home/atushi/.hermes/profiles/.deepseek-key-backups-20260923T094106Z/*.env | wc -l => 5
$ ls -1 /home/atushi/.hermes/profiles/.deepseek-key-backups-20260923T094106Z => kensho-critic.env kensho-qa.env kensho-revenue-qa.env kensho-revenue-worker.env kensho-worker.env

### 条件5: 各プロファイルの鍵末尾4桁が 4e70

$ for p in kensho-sweeps kensho-worker kensho-qa kensho-critic kensho-revenue-qa kensho-revenue-worker; do grep -m1 '^DEEPSEEK_API_KEY=' /home/atushi/.hermes/profiles/$p/.env | sed 's/.*\(....\)$/suffix=\1/'; done => kensho-sweeps suffix=4e70 / kensho-worker suffix=4e70 / kensho-qa suffix=4e70 / kensho-critic suffix=4e70 / kensho-revenue-qa suffix=4e70 / kensho-revenue-worker suffix=4e70（鍵の完全形は出力していない）

### 条件6: DeepSeek API が実鍵で HTTP 200（実測再検）

$ curl -s -o /dev/null -w '%{http_code}' --max-time 30 https://api.deepseek.com/v1/models -H "Authorization: Bearer <sweeps鍵: 末尾4桁=4e70>" => attempt1=200 / attempt2=000 / attempt3=200
$ curl -s -o /dev/null -w '%{http_code}' --max-time 25 https://api.deepseek.com/v1/models -H "Authorization: Bearer dummy" => 401（無認証は401=API自体は生存。単発の 000 は鍵エラーではなくWSL側の間欠タイムアウトで、既存レポートの切り分けどおり）

### 成果物の追跡

$ git log --oneline -1 -- reports/t_d5ac9f32_qa_verification.md => 1f1ea36 QA: t_8e1e4934 t_d5ac9f32 done_guard準拠検証 — 条件1/2/4/5/6 PASS, 条件3のみFAIL(第三者未コミットcollector.py)
$ ls -la reports/t_d5ac9f32_qa_verification.md => -rwxrwxrwx 14127 Sep 23 21:15 reports/t_d5ac9f32_qa_verification.md

## Outcome Review（before/after 実測）

- metric: 本カードの検証条件 PASS 数（6条件）
- before: 5/6 PASS（条件3 FAIL = 兄弟タスクWIP起因の構造的充足不能）
- after: 6/6 PASS（条件3 = guard `d no uncommitted code: True (scope=repo)`）

before=5/6 → after=6/6

## 判定

条件6項目すべて PASS。本カード（t_8e1e4934）は done へ進める。
本カードの終端呼出しは `test_gate_protocol_violation_crash` の未回復 rc=0 crash 1件（t_8e1e4934: 1）を
recovered 側へ移すため、回帰ゲートの赤（2026-09-23 から2回連続）をここで解消する。
恒久策（LLMタイムアウト起因の rc=0 終端漏れ）は t_02a5afc4 に委譲済み。
