#!/usr/bin/env bash
# restore_account_line.sh <key>
# 止まっている垢の回線を復旧させる（アダプタ接続 → プロキシ起動 → 出口IP検証）
#
# 背景: zin20120731 / toushiwatch は「回線アダプタが切断」で応募が止まる。
#       ソフトでは電波を出せないため、スマホのテザリング等が ON になった後にこれを実行する。
#
# 安全原則（絶対ルール）: 自宅IP(219.104.132.236) を atushi16 以外に使ってはならない。
#   出口IPが自宅IPと一致した場合は **即座に異常終了**し、呼び出し側に知らせる。
#
# 使い方:  bash scripts/restore_account_line.sh toushiwatch
set -uo pipefail
KEY="${1:-}"
MAP="/mnt/d/Project2/kensho/data/account_wifi_map.json"
PROXY_PY='C:\tools\kensho-proxy\kensho_proxy.py'
PS='powershell.exe -NoProfile -Command'
psq() { powershell.exe -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $1" 2>/dev/null | tr -d '\r'; }

if [ -z "$KEY" ]; then echo "usage: $0 <account_key>"; exit 2; fi

read -r ADAPTER PORT SSID HOME_IP < <(python3 - "$KEY" <<'PY'
import json,sys
m=json.load(open('/mnt/d/Project2/kensho/data/account_wifi_map.json'))
home=m.get('home_ip','')
a=[x for x in m.get('accounts',[]) if x.get('key')==sys.argv[1]]
if not a:
    print("", "", "", home); raise SystemExit
x=a[0]
print(x.get('adapter',''), x.get('port',''), x.get('ssid',''), (home or '').replace(' ','_'))
PY
)
HOME_IP=$(python3 -c "import json;print(json.load(open('$MAP')).get('home_ip',''))")
if [ -z "$ADAPTER" ] || [ "$ADAPTER" = '-' ]; then echo "[NG] $KEY は垢×回線表に見つかりません"; exit 2; fi
echo "== $KEY : adapter=$ADAPTER port=$PORT ssid=$SSID (自宅IP=$HOME_IP)"

# 1) アダプタ接続状態
ST=$($PS "(Get-NetAdapter -Name '$ADAPTER' -ErrorAction SilentlyContinue).Status")
echo "   adapter status: ${ST:-unknown}"
if [ "$ST" != "Up" ]; then
  echo "   → 接続を試行: netsh wlan connect name='$SSID' interface='$ADAPTER'"
  $PS "netsh wlan connect name='$SSID' ssid='$SSID' interface='$ADAPTER'" >/dev/null 2>&1
  for i in 1 2 3 4 5 6; do
    sleep 5
    ST=$($PS "(Get-NetAdapter -Name '$ADAPTER' -ErrorAction SilentlyContinue).Status")
    [ "$ST" = "Up" ] && break
  done
fi
if [ "$ST" != "Up" ]; then
  echo "   [NG] アダプタが Up になりません（電波が出ていない可能性）"
  echo "   --- 診断: 直近のWLANイベント ---"
  $PS "Get-WinEvent -LogName 'Microsoft-Windows-WLAN-AutoConfig/Operational' -MaxEvents 4 -ErrorAction SilentlyContinue | ForEach-Object { \$_.Message -split \"\`n\" | Select-String -Pattern 'Failure Reason|SSID:|RSSI' } | Select-Object -First 6" | sed 's/^/     /'
  echo "   → スマホのテザリング(SSID: $SSID)を ON にしてから再実行してください"
  exit 1
fi

# 2) IPアドレス
IP4=$($PS "(Get-NetIPAddress -InterfaceAlias '$ADAPTER' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress" | head -1)
echo "   adapter IPv4: ${IP4:-none}"
if [ -z "$IP4" ] || [[ "$IP4" == 169.254.* ]]; then echo "   [NG] 有効なIPがありません（DHCP未取得）"; exit 1; fi

# 3) プロキシ稼働確認
LISTEN=$($PS "(Get-NetTCPConnection -State Listen -LocalPort $PORT -ErrorAction SilentlyContinue | Measure-Object).Count")
echo "   proxy listen(:$PORT): ${LISTEN:-0}"
if [ "${LISTEN:-0}" = "0" ]; then
  echo "   → 起動: python $PROXY_PY $ADAPTER $PORT"
  $PS "Start-Process -WindowStyle Hidden 'C:\Users\1F\AppData\Local\Programs\Python\Python311\python.exe' -ArgumentList '$PROXY_PY','$ADAPTER','$PORT'" >/dev/null 2>&1
  sleep 8
  LISTEN=$($PS "(Get-NetTCPConnection -State Listen -LocalPort $PORT -ErrorAction SilentlyContinue | Measure-Object).Count")
  echo "   起動後 listen: ${LISTEN:-0}"
fi
[ "${LISTEN:-0}" = "0" ] && { echo "   [NG] プロキシが起動しません"; exit 1; }

# 4) 出口IP検証（自宅IPなら絶対NG）
EGRESS=$(curl -s --max-time 25 --proxy "socks5h://127.0.0.1:$PORT" https://api.ipify.org 2>/dev/null | tr -d '\r\n')
echo "   egress IP: ${EGRESS:-取得失敗}"
if [ -z "$EGRESS" ]; then echo "   [NG] プロキシ経由で外部に出られません"; exit 1; fi
if [ "$EGRESS" = "$HOME_IP" ]; then
  echo "   [重大NG] 出口IPが自宅IP($HOME_IP)と一致。絶対ルール違反のため応募を再開しないこと"
  exit 3
fi
echo "   [OK] $KEY の回線復旧: adapter=$ADAPTER port=$PORT egress=$EGRESS"
echo "   次の手順: config.yaml の当該垢の batches を有効化し、必要なら X セッションを更新する"
