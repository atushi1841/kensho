#!/usr/bin/env python3
"""data/account_wifi_map.json の「live」項目をWindows実測で更新する。

測るもの（すべてWindows側 powershell.exe 経由・失敗時は既存値を保持）:
  - Get-NetIPAddress  : アダプタ名 → IPv4
  - netsh wlan show interfaces : アダプタ名 → SSID / 接続状態 / シグナル
  - Get-NetTCPConnection -State Listen : プロキシポート(1081-1089)の待受有無
  - curl（プロキシ経由）: 出口IPの実測。自宅IPと一致したら警告フラグ（自宅IPフォールバック検知）

静的な対応（垢↔アダプタ↔ポート）は JSON 側が正で、このスクリプトは書き換えない。
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
from pathlib import Path

MAP = Path("/mnt/d/Project2/kensho/data/account_wifi_map.json")


def _ps(cmd: str, timeout: int = 25) -> str:
    """powershell.exe を実行して stdout を返す（失敗時は空文字）。"""
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout, errors="replace",
        )
        return r.stdout or ""
    except Exception:
        return ""


def collect_ips() -> dict[str, str]:
    out = _ps("Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $_.InterfaceAlias + '\t' + $_.IPAddress }")
    ips: dict[str, str] = {}
    for line in out.replace("\r", "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            ips[parts[0].strip()] = parts[1].strip()
    return ips


def collect_wlan() -> dict[str, dict[str, str]]:
    """netsh wlan show interfaces → {アダプタ名: {state, ssid, signal}}"""
    out = _ps("netsh wlan show interfaces").replace("\r", "")
    res: dict[str, dict[str, str]] = {}
    cur: str | None = None
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("\u540d\u524d", "Name")) and ":" in line:
            cur = line.split(":", 1)[1].strip()
            if cur:
                res.setdefault(cur, {})
            continue
        if cur is None or ":" not in line:
            continue
        k, v = (p.strip() for p in line.split(":", 1))
        if k.startswith(("\u72b6\u614b", "State")):
            res[cur]["state"] = v
        elif k.startswith("SSID"):
            res[cur]["ssid"] = v
        elif k.startswith(("\u30b7\u30b0\u30ca\u30eb", "Signal")):
            res[cur]["signal"] = v
    return res


def collect_ports() -> set[int]:
    out = _ps("Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -ge 1081 -and $_.LocalPort -le 1089 } | ForEach-Object { $_.LocalPort }")
    return {int(m) for m in re.findall(r"\d+", out)}



def _curl_ip(args: list[str], timeout: int = 14) -> str:
    """curl でグローバルIPを取る（失敗・非IPは空文字）。"""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout)] + args + ["https://api.ipify.org"],
            capture_output=True, text=True, timeout=timeout + 5, errors="replace",
        )
        ip = (r.stdout or "").strip()
        return ip if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip) else ""
    except Exception:
        return ""


def egress_ip(port: int) -> str:
    """プロキシ経由の出口IP（WSL→Windows SOCKS5）。"""
    return _curl_ip(["-x", f"socks5h://172.26.80.1:{port}"])


def main() -> int:
    try:
        data = json.loads(MAP.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[warn] {MAP} を読めません: {exc}")
        return 1

    ips, wlan, ports = collect_ips(), collect_wlan(), collect_ports()
    home = _curl_ip([])  # 自宅回線のグローバルIP（プロキシ未使用）
    changed = 0
    for ent in data.get("accounts", []):
        adapter = str(ent.get("adapter", "")).strip()
        port = ent.get("port")
        # ローカルIP（アダプタ名で引く。有線IP直指定(192.168.1.220)は静的値のまま）
        ip = ips.get(adapter)
        if ip and not ip.startswith("169.254.") and ent.get("local_ip") != ip:
            ent["local_ip"] = ip
            changed += 1
        # Wi-Fiアダプタの状態
        wired = "\u6709\u7dda" in str(ent.get("transport", ""))
        w = wlan.get(adapter)
        if w:
            st = w.get("state", "")
            connected = "\u63a5\u7d9a" in st and "\u5207\u65ad" not in st
            ent["adapter_state"] = "\u63a5\u7d9a" if connected else "\u5207\u65ad"
            # 切断中はシグナル値が残骸なので消す（「切断 82%」のような矛盾表示の防止）
            ent["signal"] = w.get("signal", "") if connected else ""
            if w.get("ssid"):
                ent["ssid"] = w["ssid"]
            changed += 1
        elif wired or (adapter and adapter in ips):
            ent["adapter_state"] = "\u6709\u7dda(NIC)" if wired else ent.get("adapter_state", "")
            ent["signal"] = ""
        elif adapter and adapter not in ips and not adapter.startswith("("):
            ent["adapter_state"] = "\u672a\u691c\u51fa"
            ent["signal"] = ""
        # プロキシ待受 + 出口IP実測（自宅IPと一致したら警告）
        new_state = "listen" if (isinstance(port, int) and port in ports) else "\u505c\u6b62"
        if ent.get("proxy_state") != new_state:
            ent["proxy_state"] = new_state
            changed += 1
        if new_state == "listen":
            eg = egress_ip(port)
            ent["egress_ip"] = eg
            # 自宅IPは atushi16 のみ許可（絶対ルール）。他垢が自宅IPで出たら重大違反。
            ent["egress_warn_home"] = bool(
                eg and home and eg == home and str(ent.get("key", "")) != "atushi16"
            )
            ent["egress_ok"] = bool(eg)
            changed += 1
        else:
            ent["egress_ip"] = ""
            ent["egress_ok"] = False
            ent["egress_warn_home"] = False
    data["home_ip"] = home

    data["updated_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    MAP.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] account_wifi_map.json 更新 ({changed} fields, ports={sorted(ports)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
