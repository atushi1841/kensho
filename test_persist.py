#!/usr/bin/env python3
import json
import os
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho/scripts')
from kensho_revenue_collect import _persist_last_success_at, GUMROAD_STATE, GUMROAD_BUNDLE
# We need to mock the constants
import kensho_revenue_collect as krc

# Backup original constants
original_state = krc.GUMROAD_STATE
original_bundle = krc.GUMROAD_BUNDLE

# Create a temporary directory for testing
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    state_file = os.path.join(tmpdir, 'gumroad_state.json')
    # Set the constants to our temp file
    krc.GUMROAD_STATE = state_file
    krc.GUMROAD_BUNDLE = os.path.join(tmpdir, 'bundle_info.json')  # dummy
    
    # Test case 1: login_ok = True -> should update last_success_at
    state = {"state_exists": True, "login_ok": True}
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    print("Test 1: login_ok=True")
    print(f"Before: {json.dumps(state, indent=2)}")
    _persist_last_success_at()
    with open(state_file, 'r') as f:
        after = json.load(f)
    print(f"After:  {json.dumps(after, indent=2)}")
    print(f"last_success_at updated: {'last_success_at' in after}")
    print()
    
    # Test case 2: login_ok = False -> should NOT update last_success_at, but update last_attempt_at and print login-mark
    state = {"state_exists": True, "login_ok": False, "last_success_at": "2026-09-01T00:00:00"}
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    print("Test 2: login_ok=False")
    print(f"Before: {json.dumps(state, indent=2)}")
    _persist_last_success_at()
    with open(state_file, 'r') as f:
        after = json.load(f)
    print(f"After:  {json.dumps(after, indent=2)}")
    print(f"last_success_at unchanged: {after.get('last_success_at') == '2026-09-01T00:00:00'}")
    print(f"last_attempt_at present: {'last_attempt_at' in after}")
    print()

# Restore constants
krc.GUMROAD_STATE = original_state
krc.GUMROAD_BUNDLE = original_bundle