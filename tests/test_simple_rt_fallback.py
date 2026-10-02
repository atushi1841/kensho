#!/usr/bin/env python3
"""Test simple_rt_classifier fallback logic."""

import sys

sys.path.insert(0, ".")
import datetime
import json
import pathlib

from kensho.scraping.simple_rt_classifier import FALLBACK_MODEL, SECOND_FALLBACK_MODEL, _log_openrouter_usage

# 1. Verify constants
assert FALLBACK_MODEL == "auto", f"Unexpected FALLBACK_MODEL: {FALLBACK_MODEL}"
assert SECOND_FALLBACK_MODEL == "auto", (
    f"Unexpected SECOND_FALLBACK_MODEL: {SECOND_FALLBACK_MODEL}"
)
print("Constants OK")

# 2. Test _log_openrouter_usage creates file
#    冪等性: 前回実行の残留カウンタを起点でリセット（/tmp に共有されるため）。
test_root = pathlib.Path("/tmp/test_or_usage")
test_usage_file = test_root / "data" / "openrouter_usage.json"
if test_usage_file.exists():
    test_usage_file.unlink()
(test_root / "data").mkdir(parents=True, exist_ok=True)
_log_openrouter_usage(test_root)
usage_file = test_root / "data" / "openrouter_usage.json"
assert usage_file.exists(), "Usage file not created"
with open(usage_file) as f:
    data = json.load(f)
today = datetime.date.today()
key = f"{today.year}-{today.month:02d}"
assert key in data, f"Key {key} not found in {data}"
print(f"Usage logging OK: {data}")

# 3. Increment again and verify
_log_openrouter_usage(test_root)
with open(usage_file) as f:
    data2 = json.load(f)
assert data2[key] == 2, f"Expected 2, got {data2[key]}"
print("Increment OK")

print("All tests passed!")
