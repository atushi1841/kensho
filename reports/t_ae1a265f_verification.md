# t_ae1a265f Verification

## Commit
`git log -1 --oneline` → 9cf97de fix(proxy_watchdog): atushi16(1081) direct restart for dead proxy (t_ae1a265f)

## Changes

`git show --name-only 9cf97de`

kensho/utils/proxy_watchdog.py
tests/test_proxy_watchdog.py

## Evidence of restart path

`python -m pytest tests/test_proxy_watchdog.py::test_restore_dead_proxies_restores_wired_static_ip -q`

result: 1 passed

`grep -n "if account == \"atushi16\"" kensho/utils/proxy_watchdog.py`

L248:        if account == "atushi16":

`grep -n "_restart_proxy" kensho/utils/proxy_watchdog.py | head`

L161:def _restart_proxy(account: str, adapter: str, port: int, log: Any) -> bool:
L249:            if _restart_proxy(account, adapter, port, log):
L257:            if _restart_proxy(account, adapter, port, log):

## Test suite

`python -m pytest tests/test_proxy_watchdog.py -q`

result: 15 passed

## Before/After

Before: `if account == "atushi16": log.info("Skipping..."); continue`
After: atushi16は`_restart_proxy`で直接再起動（kill+Start-Process 1081 192.168.1.220）

No fallback to home IP. Proxy restart only.

## Command citations

1. `git log -1 --oneline`
2. `python -m pytest tests/test_proxy_watchdog.py::test_restore_dead_proxies_restores_wired_static_ip -q`
3. `grep -n "if account == \"atushi16\"" kensho/utils/proxy_watchdog.py`
4. `python -m pytest tests/test_proxy_watchdog.py -q`
