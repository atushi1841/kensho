# t_ae1a265f

# verification_evidence

$ git log -1 --oneline
9cf97de fix(proxy_watchdog): atushi16(1081) direct restart for dead proxy (t_ae1a265f)

$ python -m pytest tests/test_proxy_watchdog.py::test_restore_dead_proxies_restores_wired_static_ip -q
1 passed

$ grep -n 'if account == "atushi16"' kensho/utils/proxy_watchdog.py
248:        if account == "atushi16":

$ python -m pytest tests/test_proxy_watchdog.py -q
15 passed
