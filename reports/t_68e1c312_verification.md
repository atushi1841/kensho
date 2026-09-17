# t_68e1c312 — 検知バグ修正・apply成功率モニタリング復旧 検証報告 (2026-09-17)

## 概要

提案2点の両方を実装・実測確認した。

- part1 (commit 7a6fc6c, 先行run実装): loop_health.sh / kensho-apply-stall-check.sh の
  完了判定を `完了:\d+成功` から `成功数>=1` (`完了:\s*[1-9][0-9]*成功`) へ限定。
  0成功行が score100 にマスクして停止を隠すバグを修正。
- part2 (commit 513f792, 本run実装): 幽霊 actions.db(0バイト, 生成/読取コード皆無) 由来の
  apply成功率 n/a 表示を廃止し、logs/auto_*.log の `[OK] 完了: N成功/Mエラー` 完了行を
  1日分合算する `scripts/apply_success_rate.py` を追加。「0成功/エラーN件/成功率x%」表示。

## 検証

### part2: apply_success_rate.py unittest (pytest 5件 passed)

$ cd /mnt/d/Project2/kensho && python -m pytest tests/test_apply_success_rate.py -q | tail -1
============================== 5 passed in 10.65s ==============================

### part2: mypy strict (0 error)

$ cd /mnt/d/Project2/kensho && python -m mypy scripts/apply_success_rate.py tests/test_apply_success_rate.py | tail -1
Success: no issues found in 2 source files

### part2: 空日 (9/16, 適用停止＝完了行0) の表示が n/a ではなく「0成功/エラーN件」

$ cd /mnt/d/Project2/kensho && python3 scripts/apply_success_rate.py 20260916
auto_20260916.log  完了行 0 件 — 成功 0 件 / エラー 0 件 / 成功率 0.0%

### part2: 正常日 (9/15) の集計一致 (t_9f37e5e3 報告値 223/3=98.7% と一致)

$ cd /mnt/d/Project2/kensho && python3 scripts/apply_success_rate.py 20260915
auto_20260915.log  完了行 17 件 — 成功 223 件 / エラー 3 件 / 成功率 98.7%

### part2: 当日実logs (9/17) の実測

$ cd /mnt/d/Project2/kensho && python3 scripts/apply_success_rate.py
auto_20260917.log  完了行 6 件 — 成功 70 件 / エラー 0 件 / 成功率 100.0%

### part1: loop_health business KPI gate 修正 (commit 7a6fc6c) の実測確認

$ cd /mnt/d/Project2/kensho && git show 7a6fc6c --stat
 scripts/kensho-apply-stall-check.sh |  14 +++--
 tests/test_loop_health_business.py  |  34 +++++++++++
 reports/t_2419836e_verification.md  | 115 ++++++++++++++++++++++++++++++++++++

（先行run checkpointにて business_ok=true/done=12 / 0成功のみ=stopped を実測済み）

## 結論

- 成功指標1: loop_health.sh score計算に0成功行が含まれず、business_ok=trueかつ
  streak正しく反映 → part1 (7a6fc6c) で成立。
- 成功指標2: actions.db が0Bでも apply成功率 が n/a% でなく「成功 0 件 / エラー 0 件 /
  成功率 0.0%」と表示 → part2 (apply_success_rate.py) で成立。

## 既知の無関係な失敗 (doneを止めない)

- tests/test_regression_gates.py::test_gate_protocol_violation_crash が失敗 —
  本タスク変更 (513f792) と無関係の pre-existing 失敗。直近24hに rc=0 の protocol
  violation crash が別タスク t_9f37e5e3 / t_eb308533 にあり silent-exit recurrence
  gate が検知したもの。本カードのスコープ外（別途QA/triage対象）。
