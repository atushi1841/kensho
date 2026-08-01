"""
Kensho Utils — ネットワーク情報取得
"""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Any

from kensho.utils.process import run_pwsh


def _get_linux_adapters() -> list[str]:
    """Linux: ip -brief addr show からUp状態のアダプター名一覧"""
    try:
        r = subprocess.run(["ip", "-brief", "addr", "show"], capture_output=True, timeout=10, text=True)
        adapters: list[str] = []
        for line in r.stdout.splitlines():
            # 書式: lo               UNKNOWN        127.0.0.1/8 ...
            parts = line.split()
            if len(parts) >= 2 and parts[1].upper() == "UP":
                adapters.append(parts[0])
        return adapters
    except Exception:
        return []


def _get_linux_adapter_ipv4(name: str) -> str | None:
    """Linux: ip addr show <iface> からIPv4を取得"""
    try:
        r = subprocess.run(["ip", "addr", "show", name], capture_output=True, timeout=10, text=True)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                # inet 192.168.1.100/24 brd ...
                m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
        return None
    except Exception:
        return None


def _is_linux_adapter_up(name: str) -> bool:
    """Linux: ip addr show <iface> で状態確認"""
    try:
        r = subprocess.run(["ip", "-brief", "addr", "show", name], capture_output=True, timeout=10, text=True)
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].upper() == "UP":
                return True
        return False
    except Exception:
        return False


def get_all_adapters() -> list[str]:
    """Up状態の全アダプター名一覧"""
    if platform.system() == "Linux":
        return _get_linux_adapters()

    out: dict[str, Any] = run_pwsh("Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object { $_.Name }")
    if out["success"]:
        return [line.strip() for line in out["stdout"].splitlines() if line.strip()]
    return []


def get_adapter_ipv4(name: str) -> str | None:
    """指定アダプターのIPv4アドレス"""
    if platform.system() == "Linux":
        return _get_linux_adapter_ipv4(name)

    out: dict[str, Any] = run_pwsh(
        f"(Get-NetIPAddress -InterfaceAlias '{name}' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress"
    )
    if out["success"]:
        ip: str = out["stdout"].strip()
        return ip if ip and ip != "None" else None
    return None


def is_adapter_up(name: str) -> bool:
    """アダプターがUpか"""
    if platform.system() == "Linux":
        return _is_linux_adapter_up(name)

    out: dict[str, Any] = run_pwsh(f"(Get-NetAdapter -Name '{name}').Status")
    return "Up" in out["stdout"] if out["success"] else False
