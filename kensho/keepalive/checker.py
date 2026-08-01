"""
Kensho Keepalive Checker — インターフェース状態確認・復旧
"""

from __future__ import annotations

from kensho.core.encoding import guard_stdio

guard_stdio()

import subprocess  # noqa: E402
from typing import Any  # noqa: E402

from keepalive import wifi_manager  # noqa: E402

from kensho.utils.network import get_adapter_ipv4, is_adapter_up  # noqa: E402


def ping_src(src_ip: str, dst: str = "8.8.8.8", timeout: int = 15) -> bool:
    """特定IPからping（3回中2回成功でOK。誤検知耐性）"""
    try:
        r = subprocess.run(["ping", "-n", "3", "-S", src_ip, "-w", "3000", dst], capture_output=True, timeout=timeout)
        output = r.stdout.decode("cp932", errors="replace")
        # 'Received = N' をカウント
        import re

        match = re.search(r"Received\s*=\s*(\d+)", output)
        if match:
            received = int(match.group(1))
            return received >= 2  # 3回中2回以上成功でOK
        return r.returncode == 0
    except Exception:
        return False


def _resolve_interface_from_profile(profile: str) -> str:
    """WiFiプロファイル名からインターフェース名を解決"""
    import re

    try:
        # netsh wlan show interfaces の出力から該当プロファイルのインターフェース名を取得
        r = subprocess.run(
            [
                "powershell.exe",
                "-Command",
                f'$found=$false; netsh wlan show interfaces | ForEach-Object {{ if ($_ -match "^\\s+名前\\s+:\\s+(.+)$") {{ $iface=$matches[1] }}; if ($_ -match "^\\s+プロファイル\\s+:\\s+{re.escape(profile)}$") {{ $found=$iface }} }}; if ($found) {{ Write-Output $found }}',
            ],
            capture_output=True,
            timeout=15,
            text=True,
        )
        iface = r.stdout.strip()
        return iface if iface else ""
    except Exception:
        return ""


def check_interface(cfg: dict[str, Any], log: Any = None) -> tuple[str, bool, str]:
    """
    1つのインターフェースを確認。
    戻り値: (label, ok:bool, message:str)
    """
    label = cfg.get("label", "?")
    iface = cfg.get("network_interface", "")
    itype = cfg.get("type", "")

    if itype == "ping":
        # USBテザリング: IP取得 → ping
        ip = get_adapter_ipv4(iface)
        if not ip:
            return (label, False, f"アダプター '{iface}' が見つからないかIPなし")
        if not ping_src(ip):
            return (label, False, f"Ping不通（IP: {ip}）")
        return (label, True, "")

    elif itype == "wifi_monitor":
        # WiFi: アダプター状態確認 → pingで接続維持 → 切断時は復旧試行
        # wifi_profileが設定されていれば、それを元にインターフェース名を解決
        wifi_profile = cfg.get("wifi_profile", "")
        if not iface and wifi_profile:
            iface = _resolve_interface_from_profile(wifi_profile)
        if iface:
            if is_adapter_up(iface):
                ip = get_adapter_ipv4(iface)
                if ip:
                    if not ping_src(ip):
                        if log:
                            log.write(f"[!] {label}: Ping不通（IP: {ip}）→ 復旧試行中...")
                        ok = wifi_manager.reconnect_adapter(iface, wifi_profile)
                        if ok:
                            return (label, True, "再接続成功（ping回復）")
                        else:
                            return (label, False, f"再接続失敗（{iface}）— 手動接続が必要")
                return (label, True, "")
            # 切断 → 復旧試行
            if log:
                log.write(f"[!] {label}: 切断検出 → 復旧試行中...")
            ok = wifi_manager.reconnect_adapter(iface, wifi_profile)
            if ok:
                return (label, True, f"再接続成功（{iface}）")
            else:
                return (label, False, f"再接続失敗（{iface}）— 手動接続が必要")
        else:
            return (
                label,
                False,
                f"WiFiインターフェース '{cfg.get('wifi_profile', '')}' が見つかりません（スマホ側がテザリングオフかも）",
            )

    else:
        return (label, False, f"不明なtype: {itype}")


def check_all(cfg: dict[str, Any], log: Any = None) -> tuple[list[tuple[str, str]], bool]:
    """
    設定された全インターフェースを確認。
    戻り値: (issues:[(label, message)], all_ok:bool)
    """
    interfaces: list[dict[str, Any]] = cfg.get("keepalive", {}).get("interfaces", [])
    issues: list[tuple[str, str]] = []
    all_ok = True

    for iface_cfg in interfaces:
        label, ok, msg = check_interface(iface_cfg, log)
        if not ok:
            all_ok = False
            issues.append((label, msg))

    return (issues, all_ok)


if __name__ == "__main__":
    """スタンドアロン実行用"""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from kensho.core.config import load as load_config
    from kensho.core.logger import LogWriter, make_path

    log_path = make_path("keepalive")
    log = LogWriter(log_path, echo=True)
    cfg = load_config()

    issues, all_ok = check_all(cfg, log)
    if not all_ok:
        for label, msg in issues:
            log.write(f"[!] {label}: {msg}")

    log.close()
    sys.exit(0 if all_ok else 1)
