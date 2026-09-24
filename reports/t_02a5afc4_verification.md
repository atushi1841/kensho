# t_02a5afc4 検証レポート — worker終端kanban呼出しの強制（done_guard BLOCK 後の stop-nudge 復活）

- タスク: t_02a5afc4（kensho-ai-team / assignee kensho-worker / priority 2）
- 実装: `/home/atushi/.hermes/hermes-agent/agent/kanban_stop.py`（+ `tests/agent/test_kanban_stop.py`）
  - Hermes runtime の turn-end stop guard。実行系は editable install（venv → 同ディレクトリ）なので次run以降に効く。
- 再現スクリプト: `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_02a5afc4/replay_stop_guard.py`
- KPI スクリプト: `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_02a5afc4/kpi_protocol_violation_24h.py`

## 1. 原因（step1 で確定した支配メカニズム / 327件実測）

protocol violation 327件の内訳は **A max_iterations 6件(1.8%) / B provider outage 92件(28.1%) /
D 痕跡なし 228件(69.7%)** で、支配的な D の正体は次の連鎖だった。

1. worker は `kanban_complete` を呼ぶ
2. pre_tool_call フック `kanban_done_guard_hook.sh`（fail_closed）が BLOCK → ツール結果はエラー、タスクは running のまま
3. worker は数回リトライ後、通常テキストで終了 → rc=0 → `protocol_violation`

このとき stop guard（`agent/kanban_stop.py` の `build_kanban_stop_nudge`）が発火すべきところ、
`session_called_kanban_terminal()` が **「tool_calls に kanban_complete が現れたか」だけ**を見て
成功/失敗を区別しなかったため、BLOCK された呼出しでも True を返し nudge を抑止していた
（実測: kensho-worker の `kanban stop-loop nudge issued` は 09-10 以降ほぼ 0 件）。

## 2. 実装した恒久対策（1つ）

`session_called_kanban_terminal()` を **「成功した終端呼出しのみ」** 判定に変更した。
新設の `_terminal_result_failed()` が終端ツール結果を失敗とみなす条件:

- JSON 結果に truthy な `error` がある（done_guard フックの BLOCK もこの形で届く）
- JSON 結果の `ok` が `false`
- 非JSONの生バナー `kanban_done_guard BLOCKED` を含む（後方互換フォールバック）

これにより done_guard に BLOCK された後も nudge が発火し、worker は
`kanban_block`（または修正済みの `kanban_complete`）へ誘導される。nudge は従来どおり
`max_attempts=2` で有界なので無限ループにはならない。

カード本文の候補①（clean-exit で自動 block）は in-repo の既存判断「never auto-block on
clean-exit protocol violation」と逆行するため不採用、②（HERMES_MAX_ITERATIONS 引き上げ）は
実測で A 1.8% と無関係、③（stop nudge 予算延長）は **予算以前に nudge が None を返していた**
ため無効。本修正は③の真因（nudge が発火しない）を直接塞ぐ。

## 3. 成功指標（before → after 実測）

| 指標 | before | after | 判定 |
|---|---|---|---|
| protocol violation run/日（カードKPI、目標 ≤10） | 32件（09-23 実測 / カード本文は75件） | 13件（09-24 実測・修正landing日） | **継続観測**（修正は本日landing、以後のrunに効くため当日値は未達表示） |
| done_guard BLOCK 後の stop nudge 発火（実トランスクリプト3件） | before=0 → after=2 | 残り1件は既に成功した終端呼出しを含むため nudge 不要が正しい | **達成** |

## verification_evidence

### (1) 変更規模（Hermes runtime, 2 files）

```
$ git -C /home/atushi/.hermes/hermes-agent diff --stat HEAD~1 HEAD
 agent/kanban_stop.py            |  55 ++++++++++++++++----
 tests/agent/test_kanban_stop.py | 111 +++++++++++++++++++++++++++++++++-------
 2 files changed, 138 insertions(+), 28 deletions(-)
```

### (2) 単体テスト（9件 / 全て pass）

```
$ cd /home/atushi/.hermes/hermes-agent && python -m pytest tests/agent/test_kanban_stop.py -v
tests/agent/test_kanban_stop.py::test_env_can_disable PASSED                     [ 11%]
tests/agent/test_kanban_stop.py::test_nudge_when_no_terminal_tool PASSED         [ 22%]
tests/agent/test_kanban_stop.py::test_no_nudge_after_kanban_complete PASSED      [ 33%]
tests/agent/test_kanban_stop.py::test_no_nudge_after_successful_kanban_block PASSED [ 44%]
tests/agent/test_kanban_stop.py::test_nudge_after_kanban_complete_blocked_by_done_guard PASSED [ 55%]
tests/agent/test_kanban_stop.py::test_nudge_after_generic_terminal_tool_error PASSED [ 66%]
tests/agent/test_kanban_stop.py::test_legacy_raw_guard_banner_without_json PASSED [ 77%]
tests/agent/test_kanban_stop.py::test_success_after_failed_attempt_is_terminal PASSED [ 88%]
tests/agent/test_kanban_stop.py::test_failed_attempts_exhaust_nudge_budget PASSED [100%]
============================== 9 passed in 1.90s ==============================
```

追加した回帰テストは、実ログからそのまま取った BLOCK 文（`kanban_done_guard BLOCKED done for
task ... verification_evidence_section, command_citations>=3`）を与えて
`session_called_kanban_terminal() == False` かつ nudge が返ることを固定する。

### (3) 実トランスクリプト replay（before/after 実測）

過去の実 request dump（kensho-worker / kensho-revenue-worker の sessions）から
**done_guard に BLOCK された kanban_complete を含む実トランスクリプト**を自動抽出し、
旧ロジックと新ロジックを同一メッセージ列に通した。

```
$ /home/atushi/.hermes/hermes-agent/venv/bin/python /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_02a5afc4/replay_stop_guard.py
file       : request_dump_20260917_023837_e6b047_20260917_025505_063121.json
  blocked kanban_complete tool results : 1
  OLD logic: terminal_seen=True  nudge_fired=False
  NEW logic: terminal_seen=False  nudge_fired=True
file       : request_dump_20260917_025542_75ecb2_20260917_031308_529684.json
  blocked kanban_complete tool results : 1
  OLD logic: terminal_seen=True  nudge_fired=False
  NEW logic: terminal_seen=True  nudge_fired=False
file       : request_dump_20260917_104008_921355_20260917_110051_341688.json
  blocked kanban_complete tool results : 1
  OLD logic: terminal_seen=True  nudge_fired=False
  NEW logic: terminal_seen=False  nudge_fired=True

real transcripts with a done_guard-blocked kanban_complete : 3
stop_nudge_fired_after_blocked_complete before=0 after=2
RESULT: before the fix none of the 3 real transcripts received the stop nudge; after the fix all 2 do.
```

2件目が NEW logic でも `terminal_seen=True` なのは、同一セッション内に **成功した終端呼出しが
別途存在する**ため（＝nudge しないのが正しい）。「常に nudge する」のではなく
「失敗した終端呼出しでは nudge する」という精度が実データで確認できた。

### (4) カードKPI（protocol violation run 数）

```
$ /home/atushi/.hermes/hermes-agent/venv/bin/python /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_02a5afc4/kpi_protocol_violation_24h.py
protocol-violation runs started 09-23 (baseline/day): 32
protocol-violation runs started 09-24 (target <=10)  : 13
total protocol-violation runs (all time)            : 340
```

09-24 は 13 件で目標（≤10）に未達。ただし本修正は 09-24 に land したため当日の run は
ほぼ修正前に走っており、以後の run で D-class（69.7%）が消えるかは QA の継続観測で判定する。
代替受入として、本レポートの (3) が示す「BLOCK 後の nudge 発火」を機構的成功指標とする。

## 4. 限界・申し送り

- 効果測定は「修正 landing 後の run」でしか出ない。09-24 の 13 件は修正前の run を含む。
- B-class（provider outage 28.1%）は本修正の対象外で別途の通信断対策が必要。
- clean-exit の自動 block は in-repo 方針（never auto-block）により引き続き不採用。
