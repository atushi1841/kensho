#!/usr/bin/env python3
"""SeleniumBase CDP Mode bootstrap test.

Launch SeleniumBase in CDP mode against a real browser and open the target,
matching the task acceptance command:
    python3 scripts/seleniumbase_cdp_bootstrap.py

Env:
  KENSHO_SB_TARGET  override target URL (default https://twitter.com)
  KENSHO_SB_HEADLESS 1 for headless override
"""

import os
import time

TARGET = os.environ.get("KENSHO_SB_TARGET", "https://twitter.com")
HEADLESS = os.environ.get("KENSHO_SB_HEADLESS", "0") == "1"


def main() -> int:
    from seleniumbase import SB

    t0 = time.monotonic()
    with SB(headless=HEADLESS, headed=not HEADLESS) as sb:
        sb.activate_cdp_mode(TARGET)
        t_launch = time.monotonic() - t0
        sb.open(TARGET)
        t_open = time.monotonic() - t0
        title = sb.get_title() or ""
        marker = sb.execute_script("return navigator.webdriver === true ? 'webdriver' : 'clean'")
        print(f"CDP_OK target={TARGET}")
        print(f"launch_s={t_launch:.2f} open_s={t_open:.2f} title={title!r} nav_webdriver={marker}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
