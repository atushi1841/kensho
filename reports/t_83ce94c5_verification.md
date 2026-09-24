# Task t_83ce94c5 Verification Evidence

## Task Description
[監視精度・偽ALERT 39連続] loop_health の age 減点が tasks.started_at(初回attempt値) を参照 → 再dispatch済み稼働カードを16h超と誤判定し score45固定/escalation常時true/auto-park対象化

## Implementation Status
1. `scripts/loop_health.sh` in HEAD already contains the fix (`v137b (t_83ce94c5)`):
   - `effective_started_at` / `runs_started_at` obtains latest `started_at` from `task_runs` where `status='running'`.
   - Age calculation and sorting now use `task_runs` latest `started_at` instead of stale `tasks.started_at`.

## Verification & Command Evidence

# Verification Evidence

### Command 1: Code Verification in `scripts/loop_health.sh`
```
$ grep -n "v137b (t_83ce94c5)" scripts/loop_health.sh
213:# v137b (t_83ce94c5): tasks.started_at = 初回 attempt 時刻で dispatch 後更新されない。
```

### Command 2: Execution Output Verification
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | head -1
{"score": 90, "streak": 0, "priority": "NORMAL", "alert": "OK", ...}
```

### Command 3: Pytest Regression Test Pass
```
$ python -m pytest -q tests/test_loop_health.py
============================== 3 passed in 59.07s ==============================
```

## Conclusion
The bug fix is verified in HEAD and operating correctly with score 90, streak 0, alert OK, and tests passing.
