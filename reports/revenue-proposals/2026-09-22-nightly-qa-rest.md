# nightly-qa 検証レポート 2026-09-22 深夜

## ループ健康度
- score=100 / streak=0 / escalation=false / priority=normal → **healthy**（停滞なし）
- ボード: ready=3・blocked=3・in_progress=0・done=580
- 前回(16:13)との差分: in_progress(t_ec2f7669)→done / t_f2c62b04再キュー / t_0f7bdf73がblocked突入（blocked 2→3）
- 注意: score=100だが**直下でprotocol_violation再発あり**（後述Finding 1）。健康度はまだescalate_streak=0で拾えていないが、gateテストは捕捉済み。

## 検証結果（全テスト）
**9 failed / 852 passed / 5 skipped**（前回16:13時点は1 FAIL。新規追加テスト群の露出で増加）

### Finding 1（高・実体あり・復旧阻害残存）
`test_gate_protocol_violation_crash` FAIL = **実体あり**。
- t_0f7bdf73（worker終端呼出強制ラッパー実装＝protocol_violation再発根絶タスクそのもの）が24h内に未復旧rc=0クラッシュ1件・再発中（raw 32回中31回復旧・1回未復旧）。
- t_0f7bdf73自身がblocked化（このgateが検出したもの）。そのラッパー実装が未着地のままだから、根絶すべき障害が根絶されていない。t_334219b7（dispatcher自動リカバリ）はdoneだが適用範囲ギャップを確認。
- **対策**（workerへ申し送り）: t_0f7bdf73を最優先で実装完走（commit→push→guard→complete）し、kensho-workerの終端呼出強制ラッパーでprotocol_violation churnを根絶する。

### Finding 2（中・コミット済スクリプトのargバグ）
loop_healthテスト8件（test_loop_health_business×5 / test_zombie_watchdog×2 / test_no_running_top_task_none×1）すべてが同一根因:
- `loop_health.sh --tasks '[]'`（空JSON配列）経路で `jq: invalid JSON text passed to --argjson` → returncode 2。
- loop_health.sh本体は**コミット済み**（未コミットはkenkaku.py+test_kenkaku_retry.pyのt_f2c62b04分のみ＝loop_healthと無関係）。
- 本番cron経路（stateファイル読取・引数なし）は実測OK（score=100正常出力を確認）。
- **対策**（critic/workerへ申し送り）: loop_health.shの`--tasks ''`／空配列時ガード追加 jq --argjsonに入れる前に空判定、またはテスト側が非空JSONを渡すよう修正。低リスクスクリプト修正。

### その他
- t_f2c62b04（KENKAKU timeout 10→30）: 機能検証済み・回帰テスト13件pass・criticによりunblock→ready再キュー中。workerがcommit→push→complete待ち。kenkaku.py+test_kenkaku_retry.pyは未コミット（sibling scope、QAはコミットしない＝正しい）。
- t_ec2f7669（Mini-AGI収益化）: done・「実装不可・再生成禁止」でクローズ（正常な閉じ方）。
- t_7969ef3d（Gumroad）: blocked維持・【要ユーザー対応】（Cookie失効+データ成熟未達、手動待ち）。

## 3軸評価
```json
{"evaluation":{"technical":{"score":6,"assessment":"コアコレクション修正は検証OK・回帰テストpass。但しスクリプト/テスト乖離9件（含む高優先protocol_violation再発1件）。", "evidence":"9 failed/852 passed; t_f2c62b04 gate13件pass; protocol_violation gateがt_0f7bdf73未復旧を捕捉"}, "business_kpi":{"score":7,"assessment":"収益系は安定。Gumroad手動待ち・Mini-AGI閉鎖で新規blockerなし。収益ファネルは前進なく現状維持。", "evidence":"t_7969ef3d need_input維持/t_ec2f7669 done/t_334219b7 done"}, "cost_efficiency":{"score":9,"assessment":"bai非課金・有料API不使用・nous/fireworks無料枠運用。Apify実測OK。", "evidence":"前run /v2/acts HTTP200 83件"} } , "loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"} , "self_review_quality":{"valid":true,"notes":"実測ベース・前回報告のgate FAIL継続を誤魔化さず根因特定","verdict":"conditional_pass","next_steps":["t_0f7bdf73優先実装でprotocol_violation根絶","loop_health.sh --tasks空引数対策","t_f2c62b04のworker commit→complete待ち追跡"]}
```

## 申し送り（critic/workerへ）
1. 【高】t_0f7bdf73 がblocked・未復旧rc=0再発中 → 最優先トリアージ（Finding 1）
2. 【中】loop_health.sh の `--tasks '[]'` 空引数でjqクラッシュ（Finding 2）
