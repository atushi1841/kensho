# t_c6b4e3ed 検証証跡 — no_agent script二重ネスト2件修正 + apify_run_monitor repo追跡化

タスク: t_c6b4e3ed（QA起票・高・時制critical）
実行者: kensho-worker (run492〜run495) / 立会い: kensho-sweeps QA run492-494, critic v157/v158
日付: 2026-09-16 (JST)

## 受け入れ条件と結果

| # | 条件 | 結果 |
|---|------|------|
| 1 | f7e76dea2a0e script bare名化 + Script not found解消 | PASS（04:01 cron実発火 last_status=ok） |
| 2 | 352914c18733 script='dm_scan.py' bare化 + 解像解決 | PASS（symlink復旧、10:00発火確認はQA child t_qa_dm_scan_1000へ） |
| 3 | apify_run_monitor.py repo commit（untracked解消） | PASS（commit 180f0bd、QA push済 origin/main=180f0bd） |
| 4 | ratchet test_gate_noagent_script_path_ratchet value=0 + RATCHETS=0化 | PASS（c9e4af9済、run492実測） |
| 5 | cron-job-workflowスキルへ解実在検証追記 | PASS（6点チェックリスト反映済） |

## verification_evidence

$ git -C /mnt/d/Project2/kensho log --oneline -3
180f0bd fix(cron): apify_run_monitor.py - 3 real bugs + repo tracking (t_c6b4e3ed)
816088b docs(qa): run493 — t_433da8aa配線受け入れPASS(...)
c8234a7 docs(qa): run492 — apify-run-monitor立会い実測(...)

$ md5sum /mnt/d/Project2/kensho/scripts/apify_run_monitor.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/apify_run_monitor.py
4fd98a25f452a7a611258f1d192d966c  /mnt/d/Project2/kensho/scripts/apify_run_monitor.py
4fd98a25f452a7a611258f1d192d966c  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/apify_run_monitor.py

$ grep -A3 '"id": "f7e76dea2a0e"' /home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json
f7e76dea2a0e script=apify_run_monitor.py last_status=ok last_run_at=2026-09-16T04:01:21.140402+09:00 last_err=(empty)

$ ls -la /home/atushi/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py
lrwxrwxrwx 1 atushi atushi 41 Sep 16 04:16 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py -> /mnt/d/Project2/kensho/scripts/dm_scan.py

$ ls -la /mnt/d/Project2/kensho/kensho/application/transaction_pairs.json
-rwxrwxrwx 1 atushi atushi 5155 Aug  1 13:21 /mnt/d/Project2/kensho/kensho/application/transaction_pairs.json

$ md5sum /mnt/d/Project2/kensho/scripts/dm_scan.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py
350d4492b924e0627bf4082d200cfee6  /mnt/d/Project2/kensho/scripts/dm_scan.py
350d4492b924e0627bf4082d200cfee6  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py

### dm-winner-check 04:09 error の位置づけ（陳腐値確認）

jobs.json last_error 352914c18733 → FileNotFoundError: '/home/atushi/.hermes/profiles/kensho-sweeps/kensho/application/transaction_pairs.json'（04:09:46発火、実体コピー配置で ROOT=profile直下だった時点）。04:16 symlink化で ROOT=Path(__file__).resolve().parent.parent → /mnt/d/Project2/kensho に解決（transaction_pairs.json / config.yaml / data/ 全てexists、QA run494静的検証一致）。次回10:00発火での last_status=ok 立会い確認は child QAカードへ委譲。

### 回帰ゲート残件事項

- test_gate_protocol_violation_crash={'t_c6b4e3ed':1}（新規赤）は t_c6b4e3ed run492 の履歴検知型・24h窓 → 9/17 02:28 自動消灯予定。backfill・カード追加不要（QA run494見解）。
- early_complete 適用（v76）: 受け入れコミット 180f0bd 既存＋作業ツリーのコード部分クリーン確認済のため、再検証は打ち切り、10:00立会いのみQAへ委譲。
