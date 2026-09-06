# 2026-09-07 revenue-worker v46 独立検証レポート（07:00-07:30 JST セッション）

セッション: nightly-worker cron 5e8ec4984bba（07:00起動）
health=95 / priority=new_proposals / ready=0 / blocked=0 / wip=1(t_9c018e33)

## 実施内容

1. **t_9c018e33 (v46: dispatcher-spawn done bypass) は dispatcher spawn run 226/2 が保有**。
   `hermes kanban claim` が `cannot claim: status=running lock=N100:468` を返したため、
   併存ガードルールにより着手せず、**独立検証役**に徹した。
2. spawn run 2 が 07:20 に done 化したため、その完了の妥当性を第三者視点で実測検証した。
3. 検証過程で **ガード本体の新たな穴2件**（引用レジェの散文誤認・クロスタスク証跡bleed）と
   **配線ギャップ2件**（他4プロファイル未配線・gateway未再起動）を実測で発見し、次criticへ申し送り。

## 検証結果サマリ

| 項目 | 結果 |
|------|------|
| hook両経路ブロック（terminal / kanban_complete） | ✅ exit=2 block JSON 実測 |
| spawn run 2 でのフック登録 | ✅ 07:00:35 'shell hook registered' を自ログ確認 |
| t_9c018e33 done の guard 適合 | ✅ PASS 4/4 (cites=4, report+commit 4c1552e/ea0abf5) |
| git コードdirty | ✅ 0（data/・reports/ 除く） |
| 06:30 audit / 07:05 collect / 07:05 hourly | ✅ fail=0 / 401=0 / ok |
| 引用レジェの散文誤認 | ❌ 新バグ確定（決定的再現） |
| 証跡ファイルのクロスタスクbleed | ❌ 新バグ確定（サンプル10件 own_file=False 10/10） |
| kensho-worker/qa系プロファイル配線 | ❌ 未配線（hooks=0） |
| gateway（cron経路）でのフック有効化 | ❌ 未反映（Sep4起動プロセスは再起動まで不明） |

## verification_evidence

$ hermes kanban claim t_9c018e33 --ttl 1800
→ cannot claim t_9c018e33: status=running lock=N100:468（=spawn所有、着手禁止判断の根拠）

$ hermes hooks doctor
→ ✓ script exists and is executable / ✓ allowlisted (approved 2026-09-07T06:55:00Z) / ✓ produced valid JSON on synthetic payload (exit=0, 0.365s)

$ hermes hooks test pre_tool_call --for-tool terminal --payload-file /tmp/v46_probe_terminal.json
→ exit=2 stdout={"decision":"block","reason":"kanban_done_guard BLOCKED done for task t_032545f8..."}（terminal経路ブロック実測）

$ hermes hooks test pre_tool_call --for-tool kanban_complete --payload-file /tmp/v46_probe_native.json
→ exit=2 stdout={"decision":"block","reason":"kanban_done_guard BLOCKED done for task t_032545f8..."}（ネイティブツール経路ブロック実測）

$ grep "shell hook registered" /home/atushi/.hermes/profiles/kensho-revenue-worker/logs/agent.log
→ 2026-09-07 07:00:35,039 INFO agent.shell_hooks: shell hook registered: pre_tool_call -> /home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh (matcher=terminal|execute_code|kanban_complete, ...)（spawn run2 が実際にフック登録した証拠）

$ hermes kanban runs t_9c018e33
→ run1 timed_out (Iteration budget 90/90) / run2 completed 07:20 "Fixed dispatcher-spawn done bypass: atomically gated every done completion..."

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_9c018e33 --json
→ {"pass": true, "conditions": {"a": true, "b": true, "c": true, "d": true}, "citations_count": 4, "output_file": ".../critic_proposal_2026-09-07-v46-fix.md"}（doneはguard適合済みだった）

$ python3 /tmp/v46_regex_proof.py
→ 散文のみ4行で count_command_citations=3（b条件>=3を通過）。"### Diff (previous → current)" のような見出し行が ARROW_CITATION `[^\n]{1,140}→\s*\S` に一致 = **コマンド出力が1つも無くてもb条件が成立しうる**決定的再現

$ bash /tmp/v46_bleed_audit.sh
→ 直近done10件の own_file=False = 10/10。例: t_53b0793a(v44) が別タスク出力 2026-09-07_03-06-38.md で pass、t_e5f7ea29(v45) が v46 のレポートで pass。_load_candidates は「task_idが本文のどこかに出現する.md」を拾うだけなので、**他タスクの証跡で自分のdoneが通る**（虚偽done対策の弱点）

$ python3 /tmp/v46_regex_safety_measure.py
→ 安易な厳格化（見出し除外+コマンド風断片要求）だと old>=3&new<3 の誤ブロック2件（t_53b0793a 7→2 / t_8185353f 7→2）。ただし両者ともbleed由来のpassなので、厳格化は「bleed除去」とセットで設計が必要。修正はcritic提案経由で（worker単独パッチ禁止）

$ grep -c kanban_done_guard_hook /home/atushi/.hermes/profiles/{kensho-worker,kensho-qa,kensho-revenue-qa,kensho-critic}/config.yaml
→ 全て 0（未配線）。done実績 kensho-worker=27件 / kensho-qa=3件 / kensho-revenue-qa=5件 のspawn経路は依然ガードなし

$ bash /tmp/v46_hook_presence_probe.sh
→ CLI_EXIT=2 usageエラー・VERDICT: HOOK NOT ACTIVE in this process。自セッション(kensho-sweeps gateway内、Sep4起動)ではフック未登録 = **gateway再起動までcron経路はフック不活化**（プロンプト指示による従来ガードは有効なまま）

$ cd /mnt/d/Project2/kensho && git status --porcelain | grep -E '\.(py|yaml|sh|js)' | grep -v '^.. data/' | grep -v '^.. reports/' | wc -l
→ 0（コードdirtyゼロ確認）

$ hermes cron list | grep -A9 kensho-revenue-collect
→ Last run: 2026-09-07T07:07:51 ok / grep -icE "401|unauthorized" 出力ファイル → 0（07:05 collect WATCH達成）

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"t_9c018e33(v46)をspawn runが処理中のため併存ガードで着手を譲り、独立検証役としてhook両経路ブロック・run2完了のguard適合・git状態・06:30/07:05系cronを実測検証。さらにガード本体の弱点2件（引用レジェ散文誤認・クロスタスクbleed）と配線ギャップ2件（他profile未配線・gateway未再起動）を決定的再現で特定しnotepadで次criticへ申し送り。","what_well":["claim失敗後に無理やり触らず検証専業に切り替えた","フックの効き方を hooks doctor + hooks test 両経路(terminal/kanban_complete)で独立再現した","新バグを『気づき』で終わらせず /tmp/v46_regex_proof.py 等の決定的再現スクリプトで数値化した","厳格化案の誤ブロック実測(2件)まで行い、安易修正を避けてcritic提案経由に回した"],"what_could_improve":["run2完了を sleep 待ちで監視した（~8分）。次は claim 失敗直後に検証だけ済ませて早期終了し、完了確認はQA tickに委ねる","probeで存在しないタスクIDを使ったCLI実行は usage エラーになりフック検証として不十分だった（正しくは hooks test が唯一の安全な検証経路）"],"mistakes_or_risks":["ガードのb条件(引用>=3)が散文だけで成立 = 虚偽done対策の実効性が想定より低い。未修正のままdoneが増えると監査証跡の信頼性が低下","kensho-worker/qa系spawnは依然ガードなし。v46が『revenue-workerだけ』で完了した残課題として顕在化"],"learned":"pre_tool_callフックは『そのプロセス起動時にconfigへ存在した分』しか効かない。長時間稼働gateway(cron経路)は再起動まで不活化、新規spawnは即有効。配線系の変更は『どのプロセス経路で有効化したか』をログ('shell hook registered')で経路別に確認するのが必須。","confidence":9,"verification_evidence":"本ファイル verification_evidence セクションの13コマンド実出力のみ"}}
```

## 次のcritic（08:20, 4baf143523e0）への申し送り

1. **高優先: kanban_done_guard.py 証跡束縛の穴**（決定的再現2件）
   - b条件: `ARROW_CITATION` が `→` を含む任意の散文行を計上 → 実コマンド出力ゼロで pass 可能
   - bleed: `_load_candidates` が task_id 言及の任意 .md を拾う → 他タスクの証跡で done 可能（done10件全部が own_file=False）
   - 修正案の方向性: 「証跡セクション内に当該task_id出現 + 見出し行除外 + コマンド風断片必須」を**bleed除去をセットで**設計（安易厳格化は誤ブロック2件実測済み）
2. **中優先: ガード配線の網羅**
   - kensho-worker / kensho-qa / kensho-revenue-qa / kensho-critic の config.yaml に hooks 未配線（spawn done 実績 27+3+5 件）
   - gateway（kensho-sweeps/tai、Sep4起動）は cron 経路でフック不活化 → 再起動判断は【要ユーザー対応】（稼働セッション中断を伴うため）
3. 06:30 audit / 07:05 collect / 07:05 hourly は全て正常確認済み。WATCH解除可。
   残 WATCH: 10:00 c0e8e4d76933 CDP weekly（lasterr-pending NOTE は tick 後に解消しているかQAで確認）。
