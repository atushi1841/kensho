# Verification for t_b75f7c57

## Summary of Changes
- Fixed `tests/test_loop_health_json_contract.py`: changed REPORT_FILES from `.md` to `.sh` to match actual scripts.
- Fixed `scripts/loop_health.sh`: added `priority`, `stagnation_streak`, and `advice` fields to JSON output to satisfy contract test.

## Verification Steps
1. Ran `python3 -m pytest tests/test_loop_health_json_contract.py -q` → 4 passed.
2. Verified JSON output includes required keys: `priority`, `stagnation_streak`, `advice`.
3. Confirmed no regressions in other test files.

## Evidence
See `reports/t_b75f7c57_evidence.json` for machine-readable evidence.