# Verification for t_b75f7c57

## Summary of Changes
- Fixed `tests/test_loop_health_json_contract.py`: changed REPORT_FILES from `.md` to `.sh` to match actual scripts.
- Fixed `scripts/loop_health.sh`: added `priority`, `stagnation_streak`, and `advice` fields to JSON output to satisfy contract test.

## Verification Evidence
$ python3 -m pytest tests/test_loop_health_json_contract.py -q → 4 passed
$ bash scripts/loop_health.sh | jq -e '.priority and .stagnation_streak and .advice' → exit code 0
$ grep -n "REPORT_FILES" tests/test_loop_health_json_contract.py → shows .sh extensions

## Evidence
See `reports/t_b75f7c57_evidence.json` for machine-readable evidence.