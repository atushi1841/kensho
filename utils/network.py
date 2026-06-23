"""
Kensho Utils — ネットワーク情報取得
"""
from __future__ import annotations

from utils.process import run_pwsh
from typing import Any


def get_all_adapters() -> list[str]:
    """Up状態の全アダプター名一覧"""
    out: dict[str, Any] = run_pwsh(
        "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object { $_.Name }"
    )
    if out['success']:
        return [line.strip() for line in out['stdout'].splitlines() if line.strip()]
    return []


def get_adapter_ipv4(name: str) -> str | None:
    """指定アダプターのIPv4アドレス"""
    out: dict[str, Any] = run_pwsh(
        f"(Get-NetIPAddress -InterfaceAlias '{name}' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress"
    )
    if out['success']:
        ip: str = out['stdout'].strip()
        return ip if ip and ip != 'None' else None
    return None


def is_adapter_up(name: str) -> bool:
    """アダプターがUpか"""
    out: dict[str, Any] = run_pwsh(f"(Get-NetAdapter -Name '{name}').Status")
    return 'Up' in out['stdout'] if out['success'] else False
