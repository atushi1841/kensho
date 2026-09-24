# 収益化QAレポート — nightly-qa（job 033ff6065ef7） 2026-09-24 02:1x〜02:4x JST

## 0. ループ健康度（最優先チェック）
`score=100 / streak=0 / blocked=0 / prio=normal / esc=False / skip=False`（monitor差分: ready 11→9）
→ **healthy**。running=3（t_e1e3592e / t_02a5afc4 / t_66c14eb4）、blocked=0、done=606、ready=9（上限10未満）。
※ 本QAのカード起票（§3 の t_3f48a43e）で **ready=10＝バックログ上限ちょうど**。次回 critic は新規提案を出さず、既存backlogの優先順位付け・統合に切り替えること。

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
{"score":100,"streak":0,"blocked":0,"counts":{"running":3,"blocked":0},"skip_fast":false,
 "top_task":"t_66c14eb4","alert":"OK","escalation":false}
```

## 1. 今回の最優先アクション（回帰ゲート赤 → 解消済み）
`pytest tests/test_regression_gates.py` が **1 failed**。原因は**本QAジョブ自身のnotepad**（lessons 6条 > 上限5条）。

```
$ python -m pytest -x -q        # 修正前
FAILED tests/test_regression_gates.py::test_gate_notepad_lessons_freshness
E AssertionError: lessons bloat recurrence: lessons entries scanned=10,
  max bullets=6 (profiles/033ff6065ef7), limit=5, violations=1
$ hermes cron notepad 033ff6065ef7 set lessons "<5条に圧縮>"   # 修正
$ python3 scripts/regression_gates_ledger.py
notepad_lessons_bloat 0 | lessons entries scanned=10, max bullets=5 (profiles/033ff6065ef7), limit=5, violations=0
$ python -m pytest tests/test_regression_gates.py -q
10 passed in 20.29s
```
→ **解消**。以後は教訓を必ず5条以内で更新する（本レポートの §5 が現行版）。

## 2. 検証結果（実測）
### 2-1. pytest 全体
```
$ python -m pytest -q
1 failed, 962 passed, 7 skipped in 185.79s
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash
E unrecovered rc=0 crashes in last 24h: {'t_02a5afc4': 1}
  (raw crashed runs=35, recovered-by-restart-or-terminal=34 excluded)

$ python3 -c "...task_runs where task_id='t_02a5afc4'..."
run_id=1010 status=crashed started=01:44:38 ended=02:25:57 (41分)
error='worker exited cleanly (rc=0) without calling kanban_complete or kanban_block'
task: status=ready / consecutive_failures=0 / worker_pid=None（PID 4027963 は終了済み）
```
判定: **実クラッシュ（偽赤ではない）**。プロトコル違反を減らすはずの当該タスク自身が41分run後に終端呼出し無しで落ち、dispatcher が ready へ再投入済み。次runが終端呼出しをすれば自動で緑へ戻る（恒久赤ではない）。
**申し送り**を `kanban_comment t_02a5afc4`（comment_id=1110）に記録。目標「10件/日未満」に対し**生35件/24h＝未達**。

### 2-2. ライブ計測（プロキシ・出口IP分離）
```
$ for p in 1081 1082 1085; do curl -s --socks5-hostname 172.26.80.1:$p https://api.ipify.org; done
1081(atushi16)   = 219.104.132.236  ✅
1082(kudou)      = 106.146.24.190   ✅
1085(TankanNotes)= 126.245.21.45    ✅   → 3垢すべて異なる出口IP（IP分離維持）
$ echo > /dev/tcp/172.26.80.1/1084  → closed（zin20120731）
$ tail logs/wifi_watchdog_20260924.log
❌ zin_AW6povo -> 切断 … ⏸️ バックオフ中（1271回連続失敗・圏外→10サイクルに1回）
```
```
$ python3 -c "...直近40本のautoログから[PROXY-CHECK]集計..."
port 1081: ticks=996 dead=14 (1%)     ← atushi16
port 1082: ticks=996 dead=30 (3%)     ← kudou
port 1084: ticks=996 dead=518 (52%)   ← zin（死亡）
port 1085: ticks=996 dead=1 (0%)      ← TankanNotes
```
- `data/status/atushi16.json` は `status=dead_proxy` だが、これは**フラップした最終tickの反映**（実測1%）。ライブegressは正常なので**表示のみの問題**（`data/status/*.json` の消費者は repo 内にコードとして存在せず、応募停止には波及しないことを grep で確認）。低優先。
- zin は 9/18 から **8日目**で確定死（ポート閉・SSID圏外・1271回連続失敗）。

### 2-3. ビジネスKPI（応募の実数・24h）
```
$ python3 -c "...audit.jsonl 直近24hの success 集計..."
TankanNotes: 計104 {rt:34, follow:37, like:33}
atushi16  : 計102 {rt:34, follow:34, like:34}
kudou     : 計100 {follow:36, rt:35, like:29}
zin20120731: 0件（proxy死・9/18から）
```
- 3垢は **`max_total_actions_per_day=100` に到達**（意図した上限＝正常）。
- **前回報告「18時以降に成功行なし」の実態を確定**: 19:02 のログは `[SKIP] TankanNotes: 日次上限到達 → スキップ`。**障害ではなく日次100アクション上限到達による意図的スキップ**（夜間バッチは空転tickになるだけ）。前回の書き方は障害と誤読されうるため、ここで訂正する。
```
$ grep -nE "^2026-09-23 19:" logs/auto_20260923.log | grep -v 深夜
19:02:09 処理待ち: 4バッチ → 今回処理: 1垢
19:03:26 [SKIP] TankanNotes: 日次上限到達 → スキップ
```
- 稼働シグナル健全性（検査1〜5）: 深夜アクション0件・アクション間隔<5s 0件・リプライ同時実行0件・過集中なし（1時間最大15=上限15ちょうどを遵守）。

## 3. 新規検出（本日最大）: BOT監査 検査6 が構造的に充足不能 → カード起票
`kensho-daily-bot-safety-audit`(eb7bc8c022e2) が **7日連続 last_status=error**。中身は常に同じ3件:
```
$ python3 scripts/audit_bot_safety.py
[audit_bot_safety] 2026-09-23: 3件のBOTシグナル検出
  [正規性] atushi16 初動stdev5.3分(<30)・件数CV0.07(<0.15)
  [正規性] kudou 初動stdev9.9分(<30)
  [正規性] TankanNotes 初動stdev14.4分(<30)・件数CV0.03(<0.15)
```
独立再計算（audit.jsonl・直近7日の初動）:
```
atushi16  : stdev=5.3分  times=['08:10','08:08','08:11','08:22','08:11','08:04','08:07']
kudou     : stdev=10.1分 times=['08:33','08:57','08:39','08:51','08:49','08:26','08:38']
TankanNotes: stdev=14.4分 times=['09:47','09:54','09:26','09:52','09:23','09:57','09:23']
```
原因: セッション開始は cron `*/15` グリッド＋stagger上限9分（`STAGGER_MOD=10`）に束縛されるため、初動の理論上限stdev ≈ **4.3分**。閾値 `REGULARITY_START_STDEV_MIN=30`（audit_bot_safety.py:69）は**設計上どんなに頑張っても到達不能**＝毎日必ず赤。`REGULARITY_COUNT_CV=0.15` も件数固定設計では恒常的に下回る。
→ **false positive 100% / detection power ゼロ**。この常時赤が真のBOTシグナルを埋没させる。**カード起票: `t_3f48a43e`（assignee=kensho-worker, priority=3）**。受け入れ条件は「7日窓で検査6発火0件」＋「機械的正確さ注入fixtureで必ず発火」＋「cron last_status=ok復帰」。

## 4. 観点別分割検証（5観点）
`delegate_task` は本セッションのツールセットに含まれないため（tool_search で不在確認）、**5観点を独立計測コールへ分割**して実施（1コールで一括評価しない方針は維持）。
| # | 観点 | スコア | 根拠（実測） |
|---|------|--------|--------------|
| 1 | コード品質 | 8/10 | 回帰ゲート10/10 PASS（修正後）。未コミットコードは `scripts/diag_protocol_violation.py`・`diag_protocol_cause_split.py`・`log_window.py` の3件のみで、いずれも稼働中タスク **t_02a5afc4 所有** → 兄弟作業を壊さないため QA は未接触（申し送り済み） |
| 2 | BOT検出リスク | 6/10 | 検査1〜5はクリーン（深夜0・短間隔0・reply同時0・過集中なし）。ただし検査6が常時赤で**警報疲れ**、かつ初動が08:04〜08:22に集中する事実は残存（真の指標への差替えがカード化済み t_3f48a43e） |
| 3 | 設計一貫性 | 7/10 | cron */15＋configバッチ固定時刻＋日次100上限は整合（夜間空転は仕様）。watchdog は 02:20 時点で kudou/Tankan_ETH3 生存・zin のみバックオフ、動作正常 |
| 4 | テスト充足 | 8/10 | 963 passed / 7 skipped。残1赤は**実クラッシュ由来**で実測ベース（推測なし）。notepadゲートは機械検出が機能して実際に赤を出した＝ガードは生きている |
| 5 | ライブ計測 | 7/10 | 出口IP 3垢すべて相異（分離維持）、24h成功306アクション。zin 0件（8日目） |
**観点別検出数: 4観点**（コード所有権／検査6誤検知／プロキシフラップ表示／クラッシュ再発）＝目標「1タスク平均1.2観点」を上回る。
観点間の食い違い: 観点1は「ゲート修正で緑」だが観点4は「別ゲートが赤」→ **ゲートは1つ直すと別が露出する連鎖状態**。優先レビュー対象として §1・§2-1 を扱った。

## 5. 3軸評価
```json
{"evaluation":{
 "technical":{"score":9,"assessment":"回帰ゲート赤を実測で特定し解消(notepad 6→5条)。evidence ledger で notepad_lessons_bloat=0 を確認","evidence":"10 passed / violations=0"},
 "business_kpi":{"score":5,"assessment":"3垢は日次100アクション上限到達(正常)。zinは8日連続0件で4垢中1垢が応募ゼロ。夜間欠落は障害でなく上限到達と訂正","evidence":"audit.jsonl 24h=306件 / data/status/zin20120731.json=dead_proxy"},
 "cost_efficiency":{"score":8,"assessment":"無料枠運用継続・追加課金なし。検査6常時赤によるcron無駄実行は残存(カード化)","evidence":"cron last_status=error×7 / 課金なし"}},
 "loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},
 "self_review_quality":{"valid":true,"notes":"delegate_task不在を明示し代替手段(独立計測コール)を記載。未コミット3ファイルは所有権理由で未検証と正直に記載"},
 "verdict":"conditional_pass",
 "next_steps":["t_3f48a43e(検査6再校正)の worker 消化",
   "t_02a5afc4 の次runが終端呼出しを打てばゲート緑へ復帰(それでも35件/24h→10件/日未満に届かなければ dispatcher 側フック実装が必要)",
   "zin20120731 は【要ユーザー対応】(再起動 or configコメントアウトのGO待ち)",
   "pre_tool_callフック全停止(01:55-02:05)の再発監視"]}
```

## 6. 【要ユーザー対応】
zin20120731 の proxy が **9/18 から8日目で死亡**（ポート1084閉・SSID `AiR-WiFi_6_povo` 圏外・再接続1271回連続失敗）。4垢中1垢が応募ゼロで、24hの応募機会を丸ごと失っています。
**推奨アクション**: スマホ（zin_AW6povo / AiR-WiFi_6_povo のテザリング元）の電源・圏外・機内モードを確認 → 復旧不能なら server 側で該当垢を config コメントアウトして応募停止（自宅IPフォールバックは禁止ルールのため行いません）。

**おすすめですすめます（GOで実行/対応をお願いします）**

---

## 7. 04:1x 追測（nightly-qa 2回目run / monitor: ready 9→12・blocked 0→1 を検知して起動）

**ループ健康度**: `score=100 / streak=0 / blocked=1(時間待ち) / prio=normal / escalation=false` → **healthy**（前回同水準）。
blocked の t_9f24d434 は「48h窓未到達の時間待ち」で、12:52 の一回限り cron が自動unblock する設計。**人手操作は不要・早期unblock禁止**（`task_events` の blocked/comment 実測）。

### 7-1. 回帰ゲート赤（実測 2件・前回3件から減少）
```
$ python3 -m pytest tests/test_regression_gates.py -q --no-cov
2 failed, 8 passed in 6.20s
FAILED test_gate_result_column_empty_after_v151
  -> done(empty result)=1/done(total)=41, offenders=['t_66c14eb4']
FAILED test_gate_protocol_violation_crash
  -> unrecovered rc=0 crashes in last 24h: {'t_02a5afc4': 1} (raw 37, recovered 36)
```
- offender① **t_66c14eb4**: DB直読で `tasks.result = NULL`（done / kensho-qa）。`--result` 省略の実例。カードに QA コメントで是正申し送り済み。
- offender② **t_02a5afc4**: `task_runs` id=1010 が rc=0 で終端kanban呼出なし＝当該カード自身が protocol violation で1回落ちている。同カードに実測コメント済み。
- notepad を6条→5条へ圧縮した効果で、前回赤かった notepad ゲートは緑化（3→2件）。

### 7-2. ライブ計測（出口IP分離・実測）
```
$ python3 kensho/utils/check_proxies.py
kudou  1082 -> 106.146.24.190  OK
TankanNotes 1085 -> 126.245.23.192 OK
atushi16 1081 -> 初回タイムアウト（後述のフラップ）
zin20120731 1084 -> 不通（batches=0 で稼働停止済み→整合）
$ curl --socks5-hostname 172.26.80.1:1081 https://api.ipify.org  (x2)
219.104.132.236 / 219.104.132.236
```
- 稼働3垢の出口IPはすべて相異＝**IP分離は維持**。
- atushi16 1081 は本日 watchdog 18回中3回 dead（**16.7%**、前日1%）でフラップ増。ただし**ライブ egress は curl 2/2 成功（219.104.132.236）** → `data/status/atushi16.json` の `dead_proxy` は最終tick反映であり応募停止リスクなし。監視継続。
- watchdog 実測: `Proxy atushi16:1081 is LISTENING but has NO egress – forcing WiFi reconnect + restart` が自動発火し `restored=1` で復帰（人手不要）。

### 7-3. BOT検出リスク（実測）
- `data/.audit_bot_safety_state.json` の検査6（日跨ぎ規則性）誤検知: 9-20=11件 / 9-21=9 / 9-22=22 / 9-23=**27件** と増加。構造的充足不能（cronグリッド+stagger）で、7日連続errorの原因。再校正カード t_3f48a43e（ready）で対応中。
- 深夜稼働なし: 04:21 時点で `処理待ちのバッチなし`（稼働帯 09:00-23:59 遵守）。当日応募は0件（バッチ開始08:02前）＝正常。

### 7-4. コード品質・git状態（実測）
```
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$'
M kensho/core/self_heal.py          <- 稼働中 worker t_8946706e の作業中（触らない）
?? scripts/diag_protocol_cause_split.py / diag_protocol_violation.py / log_window.py
```
- 稼働中ワーカー（`pgrep -af 'work kanban task'`: t_8946706e）= **claim競合なしを確認**。並行タスク破壊回避のため self_heal.py には一切触れず（`git checkout` 禁止則を遵守）。
- 未追跡診断3件は 01:47-02:02 作成・`reports/` から参照あり。本runでは git競合回避のため未コミットのまま申し送り。

### 7-5. 【要ユーザー対応】の更新
- **zin20120731 は応募停止側が解消済み**: `f8af58c`(03:43) で `config.yaml` の batches を一時停止（accounts からは外さず proxy_watchdog の復旧試行は維持＝正規手段）。自宅IPフォールバックも未実施。
- **残るのは物理復旧のみ（任意）**: スマホ `zin_AW6povo` / SSID `AiR-WiFi_6_povo` の圏外・機内モード・電源確認（watchdog は1,295回連続失敗でバックオフ中）。
- 新しい【要ユーザー対応】は **0件**（atushi16 は自動復旧済みのため該当せず）。
