#!/usr/bin/env python3
"""
Kensho SeleniumBase CDP Mode テストスクリプト
- import確認
- headless Chrome起動確認（WSL環境下ではGUI制限によりスキップ）
- BOT検出テスト
"""

import sys
import os

sys.path.insert(0, "/mnt/d/Project2/kensho")

def test_import() -> bool:
    """SeleniumBase import確認"""
    try:
        from seleniumbase import SB
        print("[PASS] SeleniumBase import OK")
        return True
    except ImportError as e:
        print(f"[FAIL] SeleniumBase import error: {e}")
        return False


def test_module_import() -> bool:
    """KenshoCDPモジュールimport確認"""
    try:
        from kensho.application.selenium_cdp import (
            KenshoCDP, FINGERPRINTS, PROXY_MAP,
            quick_launch_test, cdp_session, BOT_FLAGS
        )
        print(f"[PASS] KenshoCDP module import OK")
        print(f"  - Fingerprint accounts: {len(FINGERPRINTS)}")
        print(f"  - Proxy accounts: {len(PROXY_MAP)}")
        print(f"  - BOT flag checks: {len(BOT_FLAGS)}")
        return True
    except ImportError as e:
        print(f"[FAIL] Module import error: {e}")
        return False


def test_cdp_launch(account_key: str = "atushi16") -> dict:
    """CDPモード起動テスト（WSL環境対応）"""
    print(f"\n[TEST] CDP launch test: account={account_key}")

    # WSL環境チェック
    display = os.environ.get("DISPLAY", "")
    if not display:
        print("[SKIP] WSL環境: DISPLAY未設定（Chrome GUI起動不可）")
        print("  → モジュールコードは正常（import/構文検証済み）")
        return {"launch_ok": "skipped", "reason": "WSL no DISPLAY"}

    from kensho.application.selenium_cdp import quick_launch_test
    result = quick_launch_test(account_key)

    if result["error"]:
        print(f"[FAIL] Error: {result['error']}")
        return result

    if result["launch_ok"]:
        print(f"[PASS] CDP launch OK (exit_code={result['exit_code']})")
    else:
        print(f"[FAIL] CDP launch failed (exit_code={result['exit_code']})")

    if result["bot_flags"]:
        print(f"[WARN] Bot flags detected: {result['bot_flags']}")
    else:
        print(f"[PASS] No bot flags detected")

    return result


def main() -> int:
    print("=" * 60)
    print("Kensho SeleniumBase CDP Mode Test Suite")
    print("=" * 60)

    all_pass = True

    # 1. Import test
    if not test_import():
        all_pass = False

    # 2. Module import test
    if not test_module_import():
        all_pass = False

    # 3. CDP launch test (WSL-aware)
    launch_result = test_cdp_launch("atushi16")
    if launch_result.get("launch_ok") == False:
        all_pass = False

    # 4. Environment summary
    print(f"\n[INFO] Environment:")
    print(f"  - Python: {sys.version}")
    print(f"  - DISPLAY: {os.environ.get('DISPLAY', '(not set)')}")
    print(f"  - WSL: {os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower()}")

    print("\n" + "=" * 60)
    if all_pass:
        print("RESULT: ALL TESTS PASSED (WSL launch skipped - env limitation)")
        return 0
    else:
        print("RESULT: SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())