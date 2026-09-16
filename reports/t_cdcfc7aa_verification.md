# t_cdcfc7aa verification evidence — apifyエラー対応（monitor再実行統一+MCP常駐除外+retry budget）

日時: 2026-09-16 12:25 JST / 実施: nightly-worker (run519) / commit: 2516bab（push済）

## 原因特定（run54先行調査の実測更新・Bearer認証で再確認）

- MCP常駐actorのTIMED-OUTがApifyエラーメールの再発源（実行モデル不一致。コードバグではなく構造的）。
- 再検証: `japan-market-mcp` 最新run=TIMED-OUT(9/12 22:13)、`japan-fuel-price-mcp` 最新=SUCCEEDED(9/13)。`GET /acts/{id}/runs` 実測で opts_timeout=None を確認。
- プラン=FREE / monthlyUsageCreditsUsd=5 / maxMonthlyUsageUsd=10。429・402・quota枯渇の証拠は無し（`/v2/users/me` 200）。

## 実装（scripts/apify_run_monitor.py）

1. `queue_run` を `/acts/{id}/runs` へ統一 — timeout未指定時に `/builds` しか叩かず「最新run失敗」に対しrunが再生成されないギャップ（run54申し送り）を解消。
2. `is_resident_mcp()` — 名前末尾 `-mcp` / 常駐IDリストのactorは自動再試行対象外（TIMED-OUT→メール再生成のループ断ち切り）。
3. retry budget — `RETRY_LIMIT=3` を24h窓のstateファイル（`data/apify_monitor_state.json`、`APIFY_MONITOR_STATE`で差し替え可）で実カウント強制。
4. 402/quota-exceeded検出時【要ユーザー対応】行で即打ち切り。応答の `data` 入れ子からrun_id抽出するよう修正。

## 検証コマンド実測

$ python3 -m pytest tests/test_apify_run_monitor_retry.py -q --no-cov
============================== 6 passed in 0.74s ===============================

$ timeout 200 python3 scripts/apify_run_monitor.py --dry-run
=== Apify Monitor Summary ===
Total: 81 | Retried: 0 | Skipped (ok): 81 | Errors: 0
[DRY-RUN MODE] No changes made.

$ python3 -m ruff check scripts/apify_run_monitor.py tests/test_apify_run_monitor_retry.py
All checks passed!

$ git push   →  To https://github.com/atushi1841/kensho.git  922974c..2516bab  main -> main

## 全テスト

$ python3 -m pytest -q --no-cov → 1 failed, 640 passed, 5 skipped
唯一の赤は test_gate_protocol_violation_crash（既知: t_c6b4e3ed、9/18窓rollで自然解消見込み・不干渉）。

## mypy

新規導入エラーゼロを確認: HEAD比較で type-arg 差分は自身の編集分のみ修正済（残12件はHEAD既存のuntyped dict注釈で、pyproject check_untyped_defs=false 方針どおり本タスク範囲外）。

## Reflexion

{"self_review":{"what_was_done":"apify_run_monitor.pyの再実行ギャップ統一(/runs)+MCP常駐自動再試行除外+RETRY_LIMIT実効化+402ガード、テスト6件追加、push 2516bab","what_went_well":["run54先行調査コメントをそのまま消化でき再調査を節約","dry-run+Bearer再検証で原因の再現確認","pre-commit auto-fix失敗→再add再commitの教訓どおり対応"],"what_could_improve":["amend時にindex.lock衝突（他ワーカーと共有repo）→待機ループで recover できたが遅延","mypy note: 型注釈を新規関数だけ直してもHEAD既存13件は残る（gate対象外だが誤解を招く）"],"mistakes_or_risks":["他ワーカーのQAレポート1件が自分のコミットに混入→git rm --cachedで除去amend済（ファイルはuntrackedでQAに戻した）"],"learned":"MCP常駐actorのTIMED-OUTメールはコードバグでなく実行モデル不一致。監視側で『再試行しない』ことが正しい対処","confidence":9,"verification_evidence":"pytest 6 passed / dry-run 81actors Errors:0 / push 2516bab 実測ログ上"}}
