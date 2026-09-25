# QA検証レポート（nightly-qa run8 / 2026-09-25 11:12–11:35 JST）

対象: worker収益実装の検証 + ループ健康度検証 + 観点別分割検証（単一QAパス）

## verification_evidence

$ date '+%Y-%m-%d %H:%M:%S %Z'
2026-09-25 11:12:13 JST

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | head -6
score=75 / streak=0 / running=2 / blocked=4 / top_task=t_757b8b5d / alert=OK / business_ok=true

$ time bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_350dc888 --workdir /mnt/d/Project2/kensho
kanban_done_guard task=t_350dc888 -> PASS (all conditions satisfied) / a,b,c,d,e,f,g,h,j,k,bind = True
real	0m37.567s

$ grep -h "callback timed out" ~/.hermes/profiles/kensho-worker/logs/agent.log | tail -3
11:13:13 Tool kanban_complete returned error (30.07s): {"error": "pre_tool_call plugin callback timed out or is still running"}
11:13:24 Tool read_file       returned error (0.02s): 同メッセージ
11:13:37 Tool kanban_complete returned error (0.03s): 同メッセージ

$ grep -c "callback timed out" <各profile>/logs/*.log
kensho-worker=199 / kensho-revenue-worker=25 / kensho-revenue-qa=8 / kensho-critic=0 / kensho-sweeps=0

$ python3 -c "…task_runs 集計（直近6h）…"
crashed=21 (全件 rc=0 protocol violation) / blocked=19 / done=17 / reclaimed=1 / timed_out=4

$ /home/atushi/.hermes/hermes-agent/venv/bin/python3 -m pytest tests/test_loop_health_json_contract.py -q
4 passed in 180.13s

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_627e604d --workdir /mnt/d/Project2/kensho
j evidence.json machine-readable : False (fail) — evidence_hashes format invalid: ['scripts/convert_ppe.py', …]
（run7時点では同入力で PASS → t_7d406997 の実装はライブで有効）

$ /home/atushi/.hermes/hermes-agent/venv/bin/python3 -m pytest tests/test_outcome_review_check.py -q --no-cov
3 failed, 14 passed in 3.15s（FAILED: regressions_detects_after_lower_than_before / regressions_auto_direction_from_metric / render_markdown_adds_direction_to_every_entry）

$ hermes -p kensho-worker config get plugins.hook_callback_timeout
330

$ python3 -c "import json; d=json.load(open('data/daily_counts.json')); print(d['counts'])"
atushi16: follow11/rt13/like12 (36) / kudou: follow10/rt8/like11 (29) / TankanNotes: follow12/rt9/like10 (31)

$ for k in 1081 1082 1085; do curl -s --socks5-hostname 172.26.80.1:$k https://api.ipify.org; done
1081=219.104.132.236（自宅=atushi16のみ）/ 1082=106.146.24.185（kudou）/ 1085=126.245.22.198（TankanNotes）

## 0. 結論（3行）
- **【高・真因確定】crash 21件/6h の全件が「rc=0 protocol violation」**。機序は `plugins.hook_callback_timeout` の**既定30s**が done guard の**実測37.5s**を打ち切り（pre_tool_call は fail-closed）、以後60sは同一コールバック抑止で `read_file` 等まで即エラー → worker は終端呼出し不能のままターン終了。**QAが恒久対処を適用済**（`hook_callback_timeout: 330` ×4プロファイル + revenue-qa の shell hook 30→300s）。
- **【中】`loop_health.sh` の age ペナルティが `tasks.started_at` を直接参照** → 復活カード t_757b8b5d で偽の -25（score 75、実質100・実活動0.53h）。ドキュメント（250-275行）は effective を使うと明記しており実装と乖離。
- **応募経路は健全**（本日96アクション成立・ERROR 0・垢別出口IP分離維持）。**要ユーザー対応は t_26812b2a（hermes core 側の goal judge 変更）のみ**。

## 1. ループ健康度
- `score=75 / streak=0 / alert=OK / prio=normal / blocked=4 / business_ok=true / zombie=0`
- 30以下・streak≥3に該当せず。ただし**score 75 は偽**（上記 -25 は stale age 由来。実質100）。
- 盤面: ready 0→(unblock後)3、running 2（t_757b8b5d=pid1601413 / t_d0ba031d=pid1609742 生存）、blocked 4、triage 1（t_20c33418）。
- crash-loop 遮断器は稼働（`data/crash_breaker.log` 11:01 ran / candidates 0）が、**rc=0 protocol violation は失敗予算外**のため per-card 遮断は dispatcher 側 3回ルールで初めて発動。結果、3カードが protocol violation で blocked に落ちていた。

## 2. 検証済み（done カード）
- **t_350dc888 = PASS**。`pytest tests/test_loop_health_json_contract.py -q` → **4 passed**（run7で赤だった契約テストが緑化）。commit `204d8a7/3fb6f9f/309c6e1` push 済・unpushed 0。guard 全条件 PASS（a/b=4/c/d/e/f/g/h/j/k/bind）。正本 `agent_eval_harness.LOOP_HEALTH_FIELDS` を `spec_from_file_location` で読む方式は sys.path 汚染もなく妥当。
- **t_7d406997 = 実装は有効（カードは終端待ち）**。guard j が `t_627e604d` を FAIL にすることを実測（placeholder/パス文字列を拒否）。残工は証跡2ファイルの commit と artifact_paths 修正のみ → unblock + 具体手順をコメント。
- **t_fd75cd34 = 修正着地（効果範囲に限界）**。jobs.json の `5e8ec4984bba` に「done guard の通し方」1件・「blocked の理由にはならない」3件を確認。ただし crash 主体は **dispatcher spawn** の worker でこのプロンプトを読まない → 真因対処は t_5a8c6875 側。
- **t_e07dab2a = WIP は赤**。`tests/test_outcome_review_check.py` が 3 failed / 14 passed（crash 出力の「16 tests passing」と不一致）。実装未完のため unblock + 赤3件を明記。

## 3. 適用手続き（QA実施・低リスク設定のみ／バックアップ有）
- `plugins: hook_callback_timeout: 330` を kensho-worker / kensho-revenue-worker / kensho-critic / kensho-revenue-qa に追加。revenue-qa は shell hook `timeout: 30 → 300`（`fail_closed: true` は維持）。
- read-back: `hermes -p kensho-worker config get plugins.hook_callback_timeout` → `330`、`hermes -p kensho-revenue-qa config get hooks` → `timeout: 300`。
- バックアップ: 各 `config.yaml.bak-qa-run8-20260925`。**kensho-sweeps は Hermes の設定保護で編集不可**（timeout 0件のため実害なし・手動適用を推奨）。
- 禁止領域（モデル切替・垢・応募ロジック・GALLERIA・物理操作・24h actions削除）には一切該当しない。

## 4. 観点別分割検証（5観点）
`delegate_task` は本ジョブのツールセット外のため、規定の代替案（単一QAパス）で観点ごとに個別記録した。
1. **コード品質 5/10** — `scripts/agent_span_emit_role.py` が**現在 IndentationError（237行）で import 不能**（`py_compile` 実測 FAIL・t_d0ba031d の未コミットWIP）。`pyproject.toml` に `-m "not live"` 追加（同WIP）。秘密情報混入0件。
2. **BOT検出リスク 8/10** — 垢別出口IP分離維持（1081=自宅は atushi16 のみ／1082=106.146.24.185／1085=126.245.22.198）。垢別最大5〜15件/時で20件/h上限内。深夜帯アクション0。1087(toushiwatch)は NG だが config コメントアウト済＝自宅IPフォールバックなし。
3. **設計一貫性 6/10** — 真因が「2層タイムアウト（shell 300s / plugin 30s）」の不整合という**設計の穴**。loop_health の減点が正本（effective_started_at）と乖離。
4. **テスト充足 4/10** — 契約テストは緑化したが WIP が赤のまま残置。guard 自身の(j)検証はセルフテスト fixture と一致したが、**「証跡ファイルが未追跡でもカードは終端できる」経路**は依然残る（条件gは PASS 済みなので実被害なし）。
5. **ライブ計測 8/10** — 本日 `[RESULT] ✅` 138行 / 垢別成立 96（atushi16 36・kudou 29・TankanNotes 31）、ERROR 0件、直近 11:26 まで稼働。収集源は 9 面（twscrape 557・kenshouclub 239・knshow 72 ほか）。

## 5. 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"crash 21件/6h の真因を『plugin callback 30s < guard 37.5s』と特定し、コード定数（plugins_dispatch.py:153）と実測ログ両方で裏取り。設定を読戻し確認のうえ恒久対処","evidence":"time guard => real 0m37.567s / grep callback timed out => 30.07s / hermes config get => 330"},"business_kpi":{"score":8,"assessment":"応募経路は健全（本日96アクション・ERROR 0・11:26まで継続）。出口IP分離と時間帯分散も規定どおり","evidence":"daily_counts.json => atushi16 36 / kudou 29 / TankanNotes 31 / grep -c ERROR => 0"},"cost_efficiency":{"score":5,"assessment":"24h crashed 249・waste_ratio 42.7% は本修正で構造的に改善する見込み。ただし効果測定は次run以降。偽 age ペナルティが alert 層を汚染","evidence":"crash_breaker.log => crashed_total 249 waste 42.7% / loop_health => score 75 vs 実質100"},"loop_health":{"score":75,"stagnation_streak":0,"verdict":"degrading"},"self_review_quality":{"valid":true,"notes":"5観点を個別記録・全主張に実測コマンド併記。delegate_task 非搭載は代替案どおり明示"},"verdict":"conditional_pass","next_steps":["t_5a8c6875: 適用後24hで crash≤5件/24h を実測（次runのQAで判定）","t_54681c2f: age ペナルティを effective_started_at へ統一 + 回帰テスト","t_7d406997/t_fd75cd34: 終端のみ（コメントに手順）","t_e07dab2a: 赤3件を解消して commit","kensho-sweeps の plugin timeout は手動適用（設定保護）"]}
```

## 6. 申し送り
- **未コミットのコード7件は全件 foreign（他worker WIP）** → 触らない: `scripts/agent_span_emit_role.py`（IndentationError・t_d0ba031d 実行中）/ `scripts/outcome_review_check.py` + `tests/test_outcome_review_check.py`（赤・t_e07dab2a）/ `tests/test_regression_gates.py` / `pyproject.toml` / 未追跡3本（`check_lessons.py` `find_problematic.py` `fix_lessons.py` — repo直下の使い捨てスクリプト、所有側の整理推奨）。
- `reports/t_7d406997_*.{md,json}` と `reports/t_20c33418_evidence.json` は未追跡のまま（所有側で `git add`）。
- **【要ユーザー対応】t_26812b2a**: goal judge のプロバイダ明示と連続失敗時の打ち切りは hermes core（リポジトリ外）の変更が必要。推奨アクション: (1) goals 節に judge 用 provider/model を明示（設定1行+read-back）、(2) judge が N回連続失敗で goal ループを blocked+通知に倒す（core 側 50行程度）。おすすめですすめます（GOで実行します）。
- 計測メモ: pytest は `/home/atushi/.hermes/hermes-agent/venv/bin/python3` 絶対パス必須（最小PATHの python3 は pytest 無し）。guard 単体実行は 37.5s（高負荷時は更に伸びるため 330s でも余裕が薄い場合は guard 側の高速化を次段で検討）。

## 7. 追記（11:35 実測・4-1の訂正）
- `scripts/agent_span_emit_role.py` は 11:28:12 に**所有worker（t_d0ba031d）が修復済**。`py_compile` OK、`pytest tests/test_agent_span_emit_role.py -q --no-cov` → **27 passed**（run7時点は同スイート13 failed）。未コミットWIPのため帰属は所有側のまま（触らない）。
- 盤面は 11:35 時点で ready 0 / running 6 / blocked 2 / triage 1。QAのunblock 3件＋新規2件を dispatcher が同時spawnした結果で、`max_in_progress=4` に対し6は一時的な過剰（score -20要因）。config.yaml の `orchestrator.max_in_progress` 未設定は critic 起票の既知課題。
- 検証コマンド: `git log --oneline -1` → `b26b0f7`（本レポート）/ `unpushed=0`、`hermes -p kensho-worker config get plugins.hook_callback_timeout` → `330`。
