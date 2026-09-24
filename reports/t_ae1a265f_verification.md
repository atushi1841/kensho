# t_ae1a265f

## verification_evidence

**Command 1**
```bash
git log -1 --oneline
```
Output:
9cf97de fix(proxy_watchdog): atushi16(1081) direct restart for dead proxy (t_ae1a265f)

**Command 2**
```bash
python -m pytest tests/test_proxy_watchdog.py::test_restore_dead_proxies_restores_wired_static_ip -q
```
Output:
1 passed

**Command 3**
```bash
grep -n 'if account == "atushi16"' kensho/utils/proxy_watchdog.py
```
Output:
248:        if account == "atushi16":

**Command 4**
```bash
python -m pytest tests/test_proxy_watchdog.py -q
```
Output:
15 passed
