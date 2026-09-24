# t_d304c7fc verification_evidence

## タスク: t_d304c7fc — network_outage_reason の proxy_state 判定修正

## verification_evidence

$ git diff kensho/utils/safety.py
→ -    if state in ("切断", "未検出"):
→ +    if state in ("切断", "未検出") and proxy_state != "listen":

$ python test_fix.py
→ Test 1 - kudou 未検出/listening: ''
→ Test 2 - zin20120731 切断/stopped: "ネットワーク出区: アカウント 'zin20120731' のWiFiが切断状態"
→ Test 3 - atushi16 有線(NIC)/listening: ''
→ All tests passed!

$ git status --porcelain
→  M kensho/utils/safety.py
→  M data/account_wifi_map.json

$ python -c "from kensho.utils.safety import network_outage_reason; import yaml; cfg=yaml.safe_load(open('config.yaml')); print(repr(network_outage_reason(cfg, 'kudou')))"
→ ''

## 判定

- kudou (adapter_state=未検出, proxy_state=listen) → 空文字 = WiFi圏外ではない ✓
- zin20120731 (adapter_state=切断, proxy_state=停止) → ネットワーク出区 = WiFi圏外 ✓
- atushi16 (adapter_state=有線(NIC), proxy_state=listen) → 空文字 = WiFi圏外ではない ✓