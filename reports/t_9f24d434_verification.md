# t_9f24d434 — self_heal 検証レポート（summary）

**Verification Date**: 2026-09-24

## Overview
Self-healing loop verification for Kensho automatic application pipeline. The self_heal mechanism was introduced on 2026-09-22 and has since shown significant improvement in stability.

## Key Metrics

- **Total self_heal failures**: 32 (all within observation period)
- **Failure rate (window A: intro → collector fix)**: 0.2081 per operation (31 failures / 149 starts)
- **Failure rate (window B: collector fix → now)**: 0.0303 per operation (1 failure / 33 starts)
- **Failure rate (window C: last failure → now)**: 0.0333 per operation (1 failure / 30 starts)
- **Hours since last failure**: 20.48 hours

## KPI Improvement Summary

| Window | Period | Failure Rate | Operations | Successes |
|--------|--------|-------------|------------|-----------|
| A | 2026-09-22 12:52:20 → 2026-09-23 21:27:04 | 0.2081 | 149 | 651 |
| B | 2026-09-23 21:27:04 → 2026-09-24 18:48:13 | 0.0303 | 33 | 341 |
| C | 2026-09-23 22:19:25 → 2026-09-24 18:48:13 | 0.0333 | 30 | 341 |

**Improvement**: Failure rate reduced from 20.81% (window A) to ~3% (windows B/C) after collector fix commit 290c480.

## Retry Trace Cross-Check

- **Total failures with retry trace**: 32
- **Attempts reported matching retry trace**: 19 (59.4%)
- **Mismatches**: 13 failures where attempts_reported ≠ trace count

**Key pattern**: Most failures show 3 attempts reported with 3 trace entries (same account within 30 min). Notable mismatches include:
- 2026-09-23 08:41:27 — attempts_reported: 3, trace_count: 6 (extra trace entries from same account)
- 2026-09-23 11:17:12 — attempts_reported: 3, trace_count: 6
- 2026-09-23 16:26:26 — attempts_reported: 3, trace_count: 6
- 2026-09-23 17:00:34 — attempts_reported: 3, trace_count: 12

## Account Distribution of Failures

- **zin20120731**: 29 failures (90.6%)
- **atushi16**: 1 failure (3.1%)
- **TankanNotes**: 2 failures (6.3%)

All failures reported `attempts=3`, meaning 3 retry attempts per failure event.

## Self-Heal Code Reality (from self_heal analyzer)

**Critical findings**:
1. `SelfHealingLoop.__init__` receives `logger` argument but `self.logger` is **never used** — healing events are not logged
2. Only the final `value_or_raise()` failure is observable in logs
3. `retry` mechanism, when triggered, doubles BOT signals (approximately 2x increase)
4. `apply_final_failure` logs to `logs/auto_*.log`; `collection` failures log to `logs/collect_*.log`

## Key Observations

1. **30-minute window tracing**: Retry traces within 30 minutes correctly account for most failures (19/32 = 59.4% match rate)
2. **Account concentration**: zin20120731 accounts for 90.6% of all failures — targeted mitigation needed
3. **Post-collector-fix stability**: After commit 290c480, failure rate dropped dramatically from 20.81% to ~3%
4. **Self-heal is read-only in terms of logging**: Healing events themselves do not appear in logs; only final application results are observable

## Recommendations

1. **Logger integration**: Add `self.logger` usage to SelfHealingLoop to make healing events observable
2. **Retry signal mitigation**: The retry mechanism approximately doubles BOT detection signals — consider reducing retry frequency or adding delays
3. **zin20120731 focus**: This account experiences disproportionate failures — investigate account-specific issues
4. **Continue monitoring**: Current ~3% failure rate is acceptable; maintain observation

## Evidence Files

- `reports/t_9f24d434_evidence.json` — machine-readable verification data
- `reports/t_9f24d434_verification.md` — this summary report