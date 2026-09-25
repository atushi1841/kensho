# QA検証レポート — nightly-qa run16（2026-09-25 19:10–19:30 JST）

対象: kensho-ai-team ボード / ループ健康度 / ライブ応募実測
前回: run15（18:05–18:35）からの差分検証

## 0. ループ健康度（script注入値 + 実測再確認）

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print('score',d['score'],'streak',d['streak'],'alert',d['alert'],'cap',d['cap_profile'],d['cap_dispatcher'],'aux',d['aux_auth_errors'])"
score 100 streak 0 alert OK cap 4 4 aux 0
```
- `score=100 / streak=0 / alert=OK / escalation=false` → **healthy**（前回同値）。
- 監視トリガの差分: `blocked 6→4 / ready 0→4`。内訳は t_28e11c70 が blocked→running、t_757b8b5d が blocked→todo（正の変化）。
- **cap_mismatch は 4/4 に解消**（前回 4/8）。実行中 t_28e11c70 の WIP が効いている。
- monitor の `ready` は「ready+open+todo+triage」の合算定義（board_state_monitor.sh:99）。sqlite 実値は ready=0 / todo=3。

## 1. P1（最優先）: guard --selftest が 3run 連続 exit 2 — 未修正

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest > /tmp/qa_selftest.txt 2>&1; echo REAL_EXIT=$?
REAL_EXIT=2
$ tail -1 /tmp/qa_selftest.txt
SELFTEST FAILED: guard did not behave as designed (e_push_gap=True d_bleed=True d_prohibited=True d_nonowned=True g_durability=False h_result=False i_config_drift=True j_write=True k_outcome=True write_report=True)
```
- **切り分け（今回追加）**: コミット済み HEAD 版を単離実行しても同じ exit 2 → profile repo の +135行WIP（t_a38b99bc）は原因ではない＝**コミット済みコードの回帰**。
```
$ cd ~/.hermes/profiles/kensho-sweeps && git show HEAD:scripts/kanban_done_guard.py > /tmp/qa19/guard_head.py && python3 /tmp/qa19/guard_head.py --selftest >/tmp/qa19/head_out.txt 2>&1; echo HEAD_SELFTEST_EXIT=$?
HEAD_SELFTEST_EXIT=2
```
- 失敗は `g_durability` / `h_result` の soft期間スタブのみ（`g_soft=False g_status=skip` / `h_soft=True h_status=fail`）。J_HARD_AFTER/G_HARD_AFTER 経過後に期待値が陳腐化した状態で、判定関数のスタブが現行 evidence 経路に追随していない。
- 修正カード t_aa4ee345 は **todo のまま**。親 t_757b8b5d(todo) ← 親 t_a38b99bc(blocked) の3段チェーンで待機＝同一ファイル直列化の副作用で、P1 が構造的に3run止まっている。**これが本runの最大の構造問題。**

## 2. 401 恒久解消の検証（前回【要ユーザー】#1 のクローズ確認）

```
$ grep 'main provider deepseek is unavailable' ~/.hermes/logs/errors.log | tail -1
2026-09-25 17:59:37,385 WARNING [20260925_002406_92eecfcf] agent.auxiliary_client: Auxiliary kanban_decomposer: main provider deepseek is unavailable and no fallback_chain / fallback_providers is configured — refusing to guess another logged-in provider.
（時間帯別: 07h=50 08h=59 … 15h=74 17h=32 / 18h・19h=0）
$ python3 -c "import yaml;print(yaml.safe_load(open('/home/atushi/.hermes/config.yaml'))['fallback_providers'])"
[{'provider': 'freellmapi', 'model': 'auto', 'base_url': 'http://127.0.0.1:3101/v1'}]
```
- 18:30以降の新規401 = **0件**（累計524で停止）→ critic の修正は実効。`auxiliary.*` は `auto` のままだが fallback 経由で解決している。
- review 経路の復活実測: **18:33以降 crashed run 0件**、19:10 に t_ebbfe4a7 が completed。
```
$ sqlite3(task_runs) outcome='crashed' 直近5件
t_fe629b9e 18:32 / 18:31 / 18:30（以降なし）  t_fe629b9e 17:39 / 17:38
```
- t_fe629b9e の 3連続 crash（18:28〜18:33）は 401 起因の review 全死。修正後の新規 crash はゼロ。

## 3. blocked トリアージ（QA実行分）

| カード | 状態 | QA判定 |
|---|---|---|
| t_a38b99bc | blocked→**unblock済(ready)** | guard を実行 → **PASS (all conditions satisfied, exit 0)**。block理由は陳腐化 |
| t_5490697f | blocked→**unblock済(ready)** | 401解消を実測確認（上記）→ 要ユーザー対応はクローズ可。残工=証跡レポートのみ |
| t_fe629b9e | blocked維持 | review 3連続crashの恒久原因は解消。証跡の dominant-id 書き直し待ち（復活は churn 注意） |
| t_26812b2a | blocked維持 | goal judge provider の要ユーザー案件・前回から変更なし |

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_a38b99bc --workdir /mnt/d/Project2/kensho
kanban_done_guard task=t_a38b99bc -> PASS (all conditions satisfied)
  own_file : True / a : True / d : True / g : True (evidence tracked: reports/t_a38b99bc_verification.md)
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_5490697f --workdir /mnt/d/Project2/kensho
kanban_done_guard task=t_5490697f -> BLOCK (2 not met: verification_evidence_section, command_citations>=3)  own_file=False
```
コメント #1473（t_a38b99bc の残工2手順）/ #1474（t_5490697f の正しい guard 呼出）を打刻済。

## 4. 観点別分割検証（5観点・独立計測バッチ）

`delegate_task` は本runでも非搭載（tool_search 0件）→ 失敗時代替案どおり観点ごとの独立計測で実施。

1. **コード品質 6/10** — guard回帰（P1・3run）＋ profile repo の guard +135行未コミット。kensho repo 側の `scripts/check_dep_drift.py` は 4b34477(48+/8-) で**クリーン化済**（run15の指摘は解消）。`py_compile`/`bash -n` OK。
2. **BOT検出リスク 9/10** — 稼働3垢すべて日次上限で正常終了、リプライ0、深夜0、多重防止SKIP 2362。
3. **設計一貫性 5/10** — cap_mismatch は解消(4/4)したが、①guard (d) が `--workdir` repo のみ走査＝profile repo の未コミットが盲点（t_a38b99bc が3回churnした真因）②P1修正が blocked 親の3段チェーンで停止 ③aux検知が 'auto' 依存のまま。
4. **テスト充足 6/10** — `tests/test_loop_health*.py` = **12 passed / 1 failed**。失敗は `test_aux_auth_errors_detected`（期待>=10・実測0）で、実行中 t_41df6e84 の WIP（loop_health.sh + tests が同時に dirty）。done 済カードの回帰ではない。証跡未追跡3件（t_fe629b9e / t_6f45dab0 / t_e07dab2a = `git ls-files` N）。
5. **ライブ計測 9/10** — `data/daily_counts.json`: follow24+17+19=**60** / rt27+16+15=**58** / like24+17+16=**57** = 合計 **175**（atushi16 75/75・kudou 50/50・TankanNotes 50/50 で上限到達）。reply=0、ERROR=0、収集 979件、egress **3/3 相異**（atushi16=219.104.132.236 自宅 / kudou=106.146.24.185 / TankanNotes=126.245.22.155・`measurement_ok=true` 19:15）。zin・toushiwatch は停止中＝設計どおり。

## 5. 3軸評価

```json
{"evaluation":{"technical":{"score":6,"assessment":"ループはhealthy(score100/streak0)で401・cap_mismatchは解消。ただしguard --selftestがコミット済みコードの回帰として3run連続exit2、修正カードはblocked親の3段チェーンで停止。guard(d)がprofile repoを走査しない盲点がchurn真因","evidence":"REAL_EXIT=2 / HEAD_SELFTEST_EXIT=2 / t_a38b99bc guard PASS exit0 / cap 4/4 / 12 passed 1 failed(WIP)"},"business_kpi":{"score":9,"assessment":"応募は健全。3垢すべて日次上限到達で正常終了し、深夜0・リプライ0・出口IP分離3/3を維持","evidence":"175=follow60/rt58/like57 / 上限75/50/50 / reply0 / egress3/3 / 収集979 / ERROR0"},"cost_efficiency":{"score":6,"assessment":"401修正でcrashed runが18:33以降0件になり反復コストは止まった。一方P1は3run分の検証コストを空費し、blocked 2件をQAが手動unblockした","evidence":"crashed 0件/45min / blocked 6→4 / unblock 2件 / 未追跡証跡3件"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"全判定を$コマンド+実出力で提示。P1はHEAD版単離実行で回帰の所在を確定。兄弟WIPファイルには非介入（config.yaml/loop_health.sh/revenue_collect.pyはforeign扱いのまま）"},"verdict":"conditional_pass","next_steps":["次run: guard --selftest exit0復帰（t_aa4ee345・t_a38b99bc完了→t_757b8b5d→t_aa4ee345の順で解放）","t_5490697f を証跡付きでclose（要ユーザー対応の解除）","t_41df6e84 の test_aux_auth_errors_detected を緑化して完了（WIP中の赤）","未追跡証跡3件（t_fe629b9e/t_6f45dab0/t_e07dab2a）のcommit","repo config.yaml の prize_scoring 配下LLM設定の帰属確認"]}
```

## 6. 申し送り（critic / worker）

1. **guard (d) の走査範囲が `--workdir` のrepo限定** → profile repo（`~/.hermes/profiles/kensho-sweeps/scripts/`）の未コミットは検出不能。t_a38b99bc が「実装済みなのに3回churn」した真因。恒久修正は「profile repo も併せて走査」または profile 側を kensho repo へ集約。
2. **P1修正カードの解放順序**: t_a38b99bc（本run unblock）→ t_757b8b5d → t_aa4ee345 → t_6dbb050f。同一 guard ファイルのため直列は正しいが、**blocked 親がチェーン先頭に居ると全体が停止する**。親が blocked の間は子を `kanban_link` で待たせず、独立カードとして起票する運用に切り替えるべき。
3. **worker は終端前に必ず commit**（profile repo 側も含む）。iteration 残量が少ないと commit 前に落ちる。
4. **未追跡証跡3件**（t_fe629b9e / t_6f45dab0 / t_e07dab2a）は `git ls-files` で N のまま。それぞれの担当カードの終端時に commit すること。
5. `tests/test_loop_health.py::test_aux_auth_errors_detected` は期待>=10/実測0。t_41df6e84 の完了条件に「このテストが緑」を含めること（WIP中の赤を残したまま done にしない）。

## 7. 【要ユーザー対応】（おすすめですすめます／GOで実行します）

1. **【中】kensho repo `config.yaml` に帰属不明の未コミット設定 +20行**（`prize_scoring:` 配下に `default: provider: freellmapi` / `providers:` が2スペースで誤ネスト、`api_base: http://localhost:8000/v1` は実 freellmapi の `127.0.0.1:3101` と不一致、`api_key: "dummy"`）。ボード上に該当カードなし＝所有者不明。LLM設定として使う意図なら **トップレベルの `llm:` へ移し port を 3101 に修正**、意図がないなら revert。**おすすめですすめます（GOで実行します）**。
2. t_26812b2a（goal_mode judge の provider 明示）は前回から変更なし・blocked維持。

## 8. 追記（19:28–19:35 実測）— t_28e11c70 による「巻き込みcommit」

```
$ git show --stat --oneline df91ceb | grep -E '\.py |\.sh |\.yaml |test_loop'
 config.yaml                            |    20 +
 scripts/kensho_revenue_collect.py      |    72 +-   ← t_3dbc1fbe の実行中WIP
 scripts/loop_health.sh                 |    41 +-   ← t_41df6e84 の実行中WIP
 scripts/loop_health_debug.sh           |   875 +    ← 新規
 scripts/revenue_record_reconcile.py    |   286 +    ← 新規
 tests/test_loop_health.py              |    64 +-   ← t_41df6e84 の実行中WIP
 tests/test_revenue_record_reconcile.py |   221 +    ← 新規

$ git log --oneline -1 -- reports/qa-nightly-run16-20260925.md
df91ceb Finalize all changes for t_28e11c70     ← 本QAレポートも巻き込まれた

$ git status --porcelain | grep -cE '^\s*M.*\.(py|sh|yaml|js)$'
0        （working tree は clean・push 済み）
```

- 実行中カード（t_41df6e84 / t_3dbc1fbe）の未コミットWIPと本QAレポートが、**t_28e11c70 の完了commit に一括で巻き込まれた**（`git add -A` 相当）。§6-3 の「終端前に必ず commit」を満たすために他カードの境界を壊した形で、t_0e402d67 が導入した commit 直列化（`git_commit_locked.sh`）が本ケースでは使われていない。
- また unblock 2件の同時spawnで **running=5 > cap_profile 4**。cap 強制は同一tickの同時spawnには効かない。
- QA自身の申し送り: **unblock は1件ずつ**（cap を跨がない）。本runは2件同時unblockで over-WIP を作った（次runから1件ずつ）。
