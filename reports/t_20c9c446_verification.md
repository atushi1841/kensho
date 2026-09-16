# t_20c9c446 検証証跡 — cron配置drift検出 恒久化+monitor統合（5分監視）

実施: kensho-revenue-worker / 2026-09-16 run56（nightly-worker 5e8ec4984bba）
タスク: t_20c9c446（QA run508起票 / 元案件 t_d7a37e26の5f32176不発を受けての恒久化）

## 変更内容（t_20c9c446対応）

起票文面は新規 `scripts/cron_sync_check.py` 作成を想定していたが、同一機能の既存
`scripts/kensho_script_drift_check.py`（v74・毎朝08:50 no_agent 8c1271fd2158）が走査結果で
確認できたため、**既存強化**で恒久化（t_20c9c446の新規ファイル作成は機能重複と判断）。

1. **check本体の monitor_script 未走査を修正**（t_20c9c446で発覚した真の穴）:
   `check_profile()`/`_rows_from_jobs()` が `script` 参照のみ検査し `monitor_script`
   （board_state_monitor*.sh×3、apify_visibility_watch.py、hotpepper_observe.py）が
   検査対象外だった。両キー走査+同一名dedup+`ref_kind`追加。
2. **5分監視統合**: 新 `scripts/kensho_script_drift_watch.py`（check --json呼び出し、
   DRIFT/MISSING行をstdout出力+新発生時のみnotify.shでTelegram通知、state dedup、
   check異常でもexit 0）を `scripts/ai-context-monitor.sh`（crontab 5分毎）の
   GO_GATE_SHブロック直後へ統合。ai-context-monitor.sh は従来repo未追跡だったため
   t_20c9c446でgit追跡化。検出遅延が最大約24h→5分に短縮（5f32176型事故の盲点解消）。
3. **done_guard条件追加（起票項目3）は合流見送り**: kanban_done_guard.py は hotspot
   （run55申し送り）で5分監視が限界効用を下げたため、次回着地カードへ委譲。
   検出自体は条件(d)未コミットコード検査でrepo側担保済み。

応募ロジック・垢設定・モデル切替・GALLERIAには無関係（監視スクリプトのみ）。

## verification_evidence

$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_script_drift_watch.py -q
→ 7 passed in 10.74s（t_20c9c446用の新規回帰テスト: monitor_script DRIFT検出/cp同期後無出力/通知dedup+解消後再漂移再通知/check破損時exit 0）

$ cd /mnt/d/Project2/kensho && python3 -m pytest -q -p no:cacheprovider
→ 1 failed, 617 passed, 5 skipped in 61.33s（唯一の赤=既知ゲートtest_gate_protocol_violation_crash。notepad申し送り通り9/18窓rollで自然解消・本t_20c9c446非関与）

$ DRIFT_JOBS=$T/profiles/testprof/cron/jobs.json PROFILE_SCRIPTS_ROOT=$T/profiles KENSHO_ROOT=$T/repo python3 /mnt/d/Project2/kensho/scripts/kensho_script_drift_watch.py --no-notify --state $T/state.json --log $T/log.txt
→ `DRIFT-WATCH [DRIFT] dummy_job.py job=dummy (kensho-sweeps/j1)`（成功指標①: 意図的漂移で監視出力にDRIFT 1行）

$ cp $T/repo/scripts/dummy_job.py $T/profiles/testprof/scripts/dummy_job.py && (同上watch再実行)
→ 無出力（成功指標②: cp同期後は無出力=サイレント監視。stateの該当キー除去も確認）

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/ai-context-monitor.sh; echo rc=$?
→ rc=0、ログに既存5ジョブOK行のみ（統合後のt_20c9c446退行なし実測。md5: repo=profile=bf6784b50c66debe73aad67fdd2f2035）

$ python3 /mnt/d/Project2/kensho/scripts/kensho_script_drift_check.py; echo rc=$?
→ 無出力 rc=0（実プロファイル全48+monitor5件一致。run508事故 drift は元々 08:50 の既存検出で FAIL 1件=apify_run_monitor.py を出力済み: cron/output/8c1271fd2158/2026-09-16_08-50-43.md 実読。QA 09:2x cp で解消済、md5一致 f12cf125…）

## 混源メモ（起票制約条項どおり報告のみ）
jobs.json参照スクリプト48件のうちrepo未追跡(UNTRACKED)39件（kensho-revenue-report.sh、
kensho-cron-watchdog.sh、board_state_monitor*等）。driftは起き得ないが消失リスクあり=別案件推奨。
allowlist 1件（kensho-env-audit-cron.sh）は意図的差分として従来どおりFAIL化しない。

## 変更ファイル（t_20c9c446）
- `scripts/kensho_script_drift_check.py`（monitor_script走査+ref_kind、profile配置とmd5一致 69a0712f…）
- `scripts/kensho_script_drift_watch.py`（新規、profile配置とmd5一致 c6023a3c…）
- `scripts/ai-context-monitor.sh`（新規git追跡・統合ブロック、profileとmd5一致 bf6784b5…）
- `tests/test_script_drift_watch.py`（新規7ケース）
- `reports/revenue-proposals/2026-09-16-revenue-worker-t_20c9c446-v1.md`（実施レポート）

## 自己レビュー（Reflexion）
{"self_review":{"what_was_done":"t_20c9c446: 既存kensho_script_drift_check.pyへmonitor_script走査を追加し、新kensho_script_drift_watch.py（5分監視+notify dedup）をai-context-monitor.shへ統合。テスト7件追加、pytest 617 passed（既知ゲート1赤のみ）、profile配置へcp同期、git commit+push。guard条件追加はhotspot配慮で次カード委譲。","what_went_well":["新規cron_sync_check.py作成を避け既存ツール強化に集約（機能重複防止）","run508の実データ（08:50出力ファイル）で『検出は効いていたが遅い』を実証し粒度変更の根拠に","通知dedup+解消時state除去+再漂移再通知までテストで固定"],"what_could_improve":["done時点のmd5一致要求（guard条件化）は未実施=次回着地カードへ申し送り"],"mistakes_or_risks":["ai-context-monitor.shはcron非参照のためdrift check ownの対象外（repo追跡化でgit管理には乗った）"],"learned":"QA起票が指定する『新規スクリプト名』に釣られず既存実装を先に探す。真の穴はファイル名でなくmonitor_script未走査と検出粒度だった","confidence":9,"verification_evidence":"上方$コマンド6件の実測出力のみ"}}
