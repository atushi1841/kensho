# QA検証レポート（nightly-qa run5 / 2026-09-25 07:15–07:45）

> 本ファイルは **QA ジョブの観測記録**であり、いずれのタスクの worker 証跡でもない。
> guard の own_file は「最多言及ID」ヒューリスティクスで帰属するため、本レポートを
> 特定カードの完了証跡として使ってはならない（下記 §2 がその実例）。

## 0. 結論
- **【高・新規】ループは「健康に見える停止」**: `score=100/streak=0/prio=normal` の一方で
  worker スロットは実質停止（ready=0 / running=0 / blocked=9、06:00以降の 23 run 中
  crashed 7＋timed_out 2＝39% が成果ゼロ）。monitor はこの停止を通知できない。
- **【高・新規】done_guard の偽陽性を実測**: `t_47a5b3fe` は **実装ゼロで guard PASS**。
  証跡が他タスク（QA観測レポート）に誤帰属しているため。完了判定を guard PASS に
  委ねると偽doneが通る（t_20f49e54 の条件(k) と同根）。
- blocked 3件を復活（unblock＋回避策コメント）、`t_4624904b` を done。要ユーザー対応は**なし**。

## 1. ループ健康度（実測）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
{"score": 100, "streak": 0, "running": 0, "blocked": 9, "alert": "OK", "escalation": false, ...}
$ sqlite3 .../kensho-ai-team/kanban.db "select status,count(*) from tasks group by status"
triage 1 / todo 0 / ready 0 / running 0 / blocked 9 / done 653
$ # task_runs started_at > 06:00
23 runs → crashed 7 (rc=0 protocol violation) / completed 7 / blocked 5 / timed_out 2 / gave_up 1 / reclaimed 1
```
- 減点は running過剰・blocked-with-done-parent・ゾンビ・同一エラー反復のみ。**blocked 9・runnable 0・
  crash 30% でも 100点**。loop_health JSON 25キーに degraded/verdict 系キーは無い。
- 提案（critic向け・検証可能）: `worker_starvation=(ready==0 && running==0 && blocked>=5)` と
  `protocol_violation_runs_2h>=3` を新シグナル化し score 減点 or alert=WARN。
  成功指標: 現盤面で `bash scripts/loop_health.sh | jq '.worker_starvation,.score'` → true かつ score<100。
  失敗時: 1ファイル・加算的変更のみなので `git revert` で即戻る。

## 2. done_guard 偽陽性（実測・新規）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_47a5b3fe --workdir /mnt/d/Project2/kensho
-> PASS (all conditions satisfied)
   own_file: True (owner_task_id=t_47a5b3fe)  worker_output_file: reports/qa-observe-2026-09-25-run4.md
$ grep -c "HEALTH_DEGRADED" scripts/loop_health.sh                 -> 0
$ ls tests/test_loop_health_json_contract.py                       -> No such file or directory
$ git log --all --oneline --grep='t_47a5b3fe'                      -> 0件
```
- 原因: own_file が「証跡内で最多言及されたタスクID」で決まるため、**他タスクの観測レポート**が
  自タスク証跡として受理される（(h)(j) は skip）。→ 修正提案: 証跡受理に「artifact_paths /
  変更ファイルが当該タスクの diff に実在」を要求（t_20f49e54 条件(k) の強化として実装）。
- 併せて: 旧WIP `reports/wip/test_loop_health_json_contract.py.SYNTAXERR-20260925` は**既に消滅**
  （untracked のまま退避したため git 管理外）。untracked 資産の保全は `git add -f` が必須。

## 3. 観点別分割検証（5観点・各観点を個別記録）
1. **コード品質 7/10**: 本runの差分は `92ba1bd`（テスト1本）のみで実装経路 import 済。ただし blocked 9件の
   実装は未達（`grep -c HEALTH_DEGRADED`=0 等）。死んだimport・秘密情報混入なし。
2. **BOT検出リスク 8/10**: 深夜〜早朝に新規アクションなし。出口IP分離 `1081=219.104.132.236(自宅=atushi16のみ)`
   / `1082=106.146.21.233` / `1085=126.245.23.252`、`egress_warn_home` 違反0。
3. **設計一貫性 8/10**: wifi map の静的契約（adapter/port）を 07:15 時点でも保持（run4 修正の恒久性を再確認）。
4. **テスト充足 6/10**: `pytest tests/ -q --co` → **1127 tests collected / error 0**（run4 の SyntaxError 全断は解消）。
   ただし t_47a5b3fe の契約テストは不在（§2）。
5. **ライブ計測 7/10**: `network_outage_reason`: atushi16/kudou/TankanNotes = `''`、zin/toushiwatch = 「WiFi切断」
   （バッチ停止済みで正当）。orchestrator 07:15 正常終了、応募0行は 08:00 前なので正常。

## 4. blocked トリアージ（実測ベース）
- `t_4624904b` → **done**: guard PASS＋実測 `pytest tests/test_knshow_cloudflare.py -q` → 26 passed、
  実装 `bc19101`＋証跡 `52e789c`（reports/t_4624904b_verification.md）。
- `t_47a5b3fe` → **unblock**: blocked理由（by_age未定義）は誤診（L271定義・bash -n OK・score=100出力中）。残工3点を提示。
- `t_164a4556` → **unblock**: 受入(1)(3)充足済（`grep -c "def _filter"`=0 / `_gen_start`=2 / 8 passed）。残工は反証テスト1本。
- `t_1570eca6` → **unblock**: 回避策＝一時リポジトリを `tmp_path` 完結（scratch直下の自己消失が原因）。
- blocked維持: `t_de7d7e84`(needs_input/予算90枯渇)・`t_20f49e54`(rc=0 protocol violation 3連)・
  `t_757b8b5d`(予算枯渇)・`t_5ecf88bf`/`t_26812b2a`(hermes core / tai gateway＝別領域)。

## 5. 3軸評価
```json
{"evaluation":{"technical":{"score":7,"assessment":"偽陽性guard経路とループ停止の盲点を実測で特定し、blocked 3件を復活・1件をdoneまで到達させた。blocked 9件の実装自体は未達","evidence":"guard t_47a5b3fe=PASS だが grep HEALTH_DEGRADED=0 / git log --grep=0件。pytest 1127 collected error0。unblock3・complete1 をDBで確認"},"business_kpi":{"score":8,"assessment":"稼働3垢（atushi16/kudou/TankanNotes）の応募経路は維持。kudou圏外誤判定の修正は 07:15 時点でも保持","evidence":"network_outage_reason: atushi16/kudou/TankanNotes=''・出口IP 3本生存・egress_warn_home違反0・orchestrator 07:15正常終了"},"cost_efficiency":{"score":5,"assessment":"06:00以降 23 run 中 7 crashed（成果ゼロ）＋2 timed_out＝39%が浪費。t_20f49e54 は同一作業を3連でcrash。boardがrunnable 0でworkerを遊ばせていた","evidence":"task_runs集計 crashed7/completed7/blocked5/timed_out2/gave_up1/reclaimed1・ready0/running0/blocked9"},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"5観点を個別記録（delegate_task は本ジョブのツールセット外→規定の代替案どおり単一QAパスで観点別に個別記録）"},"verdict":"conditional_pass","next_steps":["t_47a5b3fe: 契約テスト＋HEALTH_DEGRADED 実装（カードコメント#1270の3点）","t_164a4556: 反証テスト1本（コメント#1271）","t_1570eca6: tmp_path完結で再実装（コメント#1272）","critic: worker_starvation シグナル＋証跡diff結線（§1§2）","09:00以降の応募ログで kudou の成立行を実測（run4修正の効果測定）"]}
```

## verification_evidence
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
=> score=100 / alert=OK / blocked=9 / running=0 / streak=0
$ python3 -m pytest tests/ -q --co
=> 1127 tests collected in 78.29s (error 0)
$ python3 -m pytest tests/test_knshow_cloudflare.py -q --no-cov
=> 26 passed in 11.13s
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_4624904b --workdir /mnt/d/Project2/kensho
=> PASS (all conditions satisfied)
$ timeout 15 curl -s --socks5-hostname 172.26.80.1:1082 https://api.ipify.org
=> 106.146.21.233   (kudou: 出口IP分離OK)
$ grep -c "HEALTH_DEGRADED" scripts/loop_health.sh ; git log --all --oneline --grep='t_47a5b3fe' | wc -l
=> 0 / 0            (t_47a5b3fe は実装ゼロ＝guard PASS は偽陽性)
```
