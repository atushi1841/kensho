# Revenue Worker t_20c9c446 — cron配置drift検出 恒久化+monitor統合 (2026-09-16)

## 実施内容（QA run508起票・assignee=kensho-revenue-worker）

起票文面は新規 `scripts/cron_sync_check.py` への恒久化を想定していたが、
走査結果は既存 `scripts/kensho_script_drift_check.py`（v74・t_e971e85a・毎朝08:50 no_agent
8c1271fd2158・git追跡済み・env変数テストフック付き）が同一機能を持つ。新規作成は
機能重複のため行わず、**既存の欠陥2点を塞ぐ方向**で恒久化した。

### 1. 既存 check の monitor_script 未走査を修正（真の穴）
- `check_profile()` / `_rows_from_jobs()` が `script` 参照しか走査しておらず、
  `monitor_script`（board_state_monitor*.sh / apify_visibility_watch.py /
  hotpepper_observe.py の5件）が drift 検査対象外だった。run508型事故（=5f32176不発）が
  monitor側に再現しても従来は検出不可能。→ 両キー走査+同一名dedup（`ref_kind` カラム追加）。
- 実測: fixtureで monitor_script 参照の漂移を DRIFT 検出（テストケース1）。

### 2. 5分粒度監視として ai-context-monitor.sh に統合
- 新 `scripts/kensho_script_drift_watch.py`（通知dedupラッパ）: check --json を呼び、
  DRIFT/MISSING 行を stdout（=monitorログに1行出現）+ 新発生時のみ notify.sh 経由で
  Telegram 通知。state=`state/script_drift_watch_state.json`、log=`logs/script_drift_watch.log`。
  go_gate_watch.sh（v155）と同形式。check側異常でも exit 0（monitorを止めない）。
- `ai-context-monitor.sh`（crontab 5分毎・repo未追跡だったためリポジトリ
  `scripts/ai-context-monitor.sh` へ初git追跡化）の GO_GATE_SH 直後へ統合ブロック追加。
  プロファイル配置とは md5 一致（bf6784b5…）。skip_fast 慣例なしの常時監視（read-only）。
- 事故盲点の解消: 朝1回 → **5分毎**（5f32176型は最大約1日不発だった）。

### 3. guard条件追加の検討（起票項目3）→ 今回合流しない判断
- `scripts/` 直下の `kanban_done_guard.py` はプロファイル側の単一ソース（repo未追跡・
  80KB・selftest同梱）で **hotspot**（run55申し送り: next着地カードと競合時 rebase 必須）。
- 5分監視が「done後に配置が漂移して不発」の検出遅延を 24h→5min に短縮済みのため、
  guard強化（=done時点のmd5一致要求）の限界効用は低下。guard変更は次回着地カードへ
  委譲（本レポートが申し送り）。検出自体は done_guard 条件(d)「未コミットコードなし」で
  repo側は担保済み。

## 検証エビデンス（実測のみ）

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_script_drift_watch.py -q
7 passed in 10.74s

$ cd /mnt/d/Project2/kensho && python3 -m pytest -q -p no:cacheprovider
1 failed, 617 passed, 5 skipped in 61.33s   ← 唯一の赤=既知ゲート t_c6b4e3ed(protocol_violation、本タスク非関与・9/18窓rollで自然解消見込み)

$ DRIFT_JOBS=$T/profiles/testprof/cron/jobs.json PROFILE_SCRIPTS_ROOT=$T/profiles KENSHO_ROOT=$T/repo python3 /mnt/d/Project2/kensho/scripts/kensho_script_drift_watch.py --no-notify --state $T/state.json --log $T/log.txt
DRIFT-WATCH [DRIFT] dummy_job.py job=dummy (kensho-sweeps/j1)      ← 意図的漂移で1行出現

$ (cp同期後 再実行)
                                                      ← 無出力（サイレント監視）確認

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/ai-context-monitor.sh; echo rc=$?
rc=0                                                    ← 統合後もmonitor正常・全ジョブOK行のみ

$ python3 /mnt/d/Project2/kensho/scripts/kensho_script_drift_check.py   (実プロファイル・全一致)
                                                      ← 無出力 rc=0。5f32176事故driftは検出自体は
   既存ジョブが09:16 08:50に FAIL 1件（apify_run_monitor.py profile 4fd98a25 vs repo f12cf125）を
   出力済み（cron/output/8c1271fd2158/2026-09-16_08-50-43.md 実測）。QA 09:2xのcpで現在は解消。
```

## 混源メモ（起票制約条款どおり報告のみ・同期不要）
- jobs.json 参照48スクリプトのうち **repo未追跡（UNTRACKED）39件**（kensho-revenue-report.sh、
  kensho-cron-watchdog.sh、board_state_monitor*.sh、apify_visibility_watch.py 等）。
  drift事故は git管理外ファイルで起き得ない代わりに**消失リスク**がある。恒久化は別案件推奨。
- allowlist 1件（kensho-env-audit-cron.sh・意図的差分）は従来どおり FAIL 化しない。

## 自己レビュー（Reflexion）
```json
{"self_review":{"what_was_done":"kensho_script_drift_check.py にmonitor_script走査を追加し、新kensho_script_drift_watch.py（5分監視+notify dedup）をai-context-monitor.shへ統合。テスト7件追加、pytest 617 passed（既知ゲート1赤のみ）、profile配置へcp同期+git commit/push。","what_well":[] ,"what_went_well":["新規cron_sync_check.py作成を避け既存ツール強化に統合（機能重複防止）","run508の実データ（08:50出力ファイル）で『検出は効いていたが遅い』を実証し仕様変更の根拠にした","通知dedup+解消時state除去で再漂移再通知までテスト網羅"],"mistakes_or_risks":["ai-context-monitor.shはjobs.json非参照なのでdrift check ownの対象外（今回repo追跡化でgit管理には乗る）","guard条件追加は次カード委譲=done時点の即時検証は未強化"],"learned":"『QA起票の新規スクリプト名』に釣られず既存実装を先に探す（drift検査はv74で既存。真の穴はmonitor_script未走査と粒度だった）","confidence":9,"verification_evidence":"pytest 7 passed+617 passed実測、fixture漂移→DRIFT行→cp→無出力→再漂移→再WARNの一連出力、monitor rc=0"}}
```

## 変更ファイル
- `scripts/kensho_script_drift_check.py`（monitor_script走査+ref_kind、repo/profile md5一致）
- `scripts/kensho_script_drift_watch.py`（新規、profile配置済）
- `scripts/ai-context-monitor.sh`（新規git追跡・統合ブロック追加、profileとmd5一致）
- `tests/test_script_drift_watch.py`（新規7ケース）
