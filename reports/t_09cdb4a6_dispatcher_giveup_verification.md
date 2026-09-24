# 検証証跡: t_09cdb4a6 — dispatcher give_up撤去(t_334219b7)の効果未発現を実測検証

## summary
- 依頼: t_334219b7(dispatcher: clean-exit protocol_violationをfailure計上せずgive_up撤去・常にready自動リカバリー化)が2026-09-22 15:07完了したにも関わらず、t_efc31433のrun 915-939(18:24-22:41)+941+943でgive_up継続(protocol_violations 10-11回)。変更が実行機構(dispatcher)に正しく反映されたか実測確認。
- 結論(FAIL — 但しコード欠陥ではなく「プロセス未再起動」): **修正b37d6946はディスク上に正しく存在しテストも通るが、稼働中のdispatcher(gatewayプロセス)が古いコードをメモリ実行しており、修正が反映されていない。** git grep検証自体は「コードに変更を含む」=PASSだったが、「稼働中dispatcherが修正を反映」=FAIL。
- 根因: dispatcher兼gatewayプロセスPID 477(tai, 2026-09-09開始)とPID 1122795(kensho-sweeps, 2026-09-12開始)は**修正b37d6946着弾(2026-09-22 14:54)より前に起動**され、以後一度も再起動されていない。修正後にgive_up→blockedが残ったのは新しいコードを読み込めないため。
- 決定的証拠: 修正が撤去したフィールド`protocol_violation_limit`と`protocol_violations`が、稼働中give_upイベントのpayload(2026-09-22 22:45, 2026-09-23 00:24)に**今も出現**。ディスク上の最新コードには両フィールドが存在しない → 稼働コード ≠ ディスクコード を厳密証明。

## verification_evidence

### 1. ディスク上の修正は存在する(依頼のgit grep確認 = PASS)
$ cd /home/atushi/.hermes/hermes-agent && git log --oneline -1
> b37d694649 fix(kanban): never auto-block on clean-exit protocol violation

$ cd /mnt/d/Project2/kensho && grep -rn "t_334219b7" docs/ reports/ | head
> docs/terminal-call-enforcement-redesign.md, reports/t_334219b7_verification.md に言及あり(検証証跡は既存)

### 2. ディスク上の修正が正しい(on-diskテスト = PASS)
$ cd /home/atushi/.hermes/hermes-agent && venv/bin/python -m pytest tests/hermes_cli/test_kanban_db.py -q -k "protocol or crash or give_up or recover or orphan"
> 1 passed, 31 deselected in 2.84s
(baseline: t_334219b7_verification.md 記載の 26 passed / 1 passed(protocol_violation_budget_not_consumed)も成立)

### 3. 修正が撤去したフィールドが最新コードに存在しない
$ grep -n "protocol_violation_limit\|protocol_violations" /home/atushi/.hermes/hermes-agent/hermes_cli/kanban_db.py
> (空 — 最新ディスクコードには存在しない)

### 4. 稼働中give_upイベントに撤去されたフィールドが出現 → 稼働コード = 旧コード(決定的)
$ hermes kanban --board kensho-ai-team show t_efc31433 | grep -A6 "gave_up"
> [2026-09-22 22:45] gave_up {'failures': 2, 'effective_limit': 3, 'limit_source': 'dispatcher',
>    'trigger_outcome': 'crashed', 'retry_status': 'ready',
>    'protocol_violations': 10, 'protocol_violation_limit': 3}   ← 旧コードのみが持つフィールド
> [2026-09-23 00:24] gave_up {'failures': 1, 'effective_limit': 3, 'limit_source': 'dispatcher',
>    'protocol_violations': 11, 'protocol_violation_limit': 3}   ← 同様(修正後にもgive_up継続を証明)

### 5. dispatcher(gateway)プロセスが修正より先に起動され未再起動
$ ps -o pid,lstart,etime,cmd -p 477 1122795
> 477    Wed Sep  9 13:43:00 2026  13-10:48  python -m hermes_cli.main --profile tai gateway run
> 1122795 Sat Sep 12 22:34:02 2026 10-01:57  python -m hermes_cli.main --profile kensho-sweeps gateway run
$ systemctl --user show hermes-gateway-tai --property=ExecMainStartTimestamp
> ExecMainStartTimestamp=Wed 2026-09-09 12:59:18 JST   (修正b37d6946着弾 2026-09-22 14:54 より前)

## 投げ込み(判明した運用事実)
- dispatcherはgatewayプロセス内で稼働し、Pythonコードはプロセス起動時にメモリ読み込み。2026-09-09/12開始のgatewayはディスク変更を検知しない。
- **修正を有効化するには`systemctl --user restart hermes-gateway-tai.service`(および同仕組みで起動しているkensho-sweeps gateway)が必要**。再起動後、次のclean-exit protocol_violationはgive_upとならずreadyへ自動リカバリーされる見込み。
- 再起動はgateway稼働中プロセスを落とすため、稼働中タスクへの影響を確認してから実行すべき(本QAでは実行せず記録に留める)。

## recommendation
1. (必須) dispatcher/gatewayを再起動して修正をロード(file reload)。
2. 再起動後、t_efc31433等で次のprotocol_violationがgive_upを踏まずreadyへ戻ることを実測確認 → t_334219b7の効果発現を確定。
3. t_efc31433は実装完了済み(commit 6ec0a8d + e73a7a1・pytest 3 passed)なので、再起動後にworkerがcompleteを直行させる運用手順をmaintain(既存方針どおり)。
4. この「コード変更してもgateway未再起動で効果が出ない」知見は、将来のdispatcher改修検証時のチェックリストに加える(変更検証 = gitを示すだけでなく稼働プロセス再起動まで)。
