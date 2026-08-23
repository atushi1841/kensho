"""
Watchdog module for Kensho proxy processes.

Provides PROXY_ADAPTER_MAP, restore_dead_proxies, and check_proxy_health.
"""

import logging
import socket
import subprocess
import time
from typing import Any

# ============================================================================
# Proxy map
# ============================================================================
PROXY_ADAPTER_MAP: dict[str, tuple[int, str]] = {
    "atushi16": (1081, "192.168.1.220"),  # wired ethernet – no restart
    "kudou": (1082, "kudou_RM10JE_B"),
    "chugakujuken": (1083, "chugakujuken_RM10JE_S"),
    "zin20120731": (1084, "zin_AW6povo"),
    "TankanNotes": (1085, "Tankan_2_redmi_n9s"),
    "inobase1-4": (1089, "inobase1-4"),
}

# ── WiFi SSID マップ（自動再接続用）──
WIFI_SSID_MAP: dict[str, str] = {
    "kudou": "RM10JE_B",
    "chugakujuken": "RM10JE_S",
    "zin20120731": "AiR-WiFi_6_povo",
    "TankanNotes": "2_redmi_n9s",
    "inobase1-4": "ino1_4_oppo_r5a",
}

PROXY_HOST = "172.26.80.1"
PROXY_TIMEOUT = 5  # seconds


def _port_reachable(port: int, timeout: int = PROXY_TIMEOUT) -> bool:
    """Return True if there is a TCP listener at PROXY_HOST:port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((PROXY_HOST, port))
        return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _adapter_ipv4(adapter: str) -> str | None:
    """Return the first usable (non-APIPA) IPv4 of a Windows adapter, else None."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        f"(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias '{adapter}' -ErrorAction SilentlyContinue).IPAddress",
    ]
    try:
        ps = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return None
    for line in ps.stdout.splitlines():
        ip = line.strip()
        # 169.254.x.x (APIPA) = no real network. Skip it.
        if ip and not ip.startswith("169.254."):
            return ip
    return None


def _wait_for_adapter_ipv4(adapter: str, wait_seconds: int = 20) -> str | None:
    """Poll for a usable IPv4 up to wait_seconds.

    Fixes a startup race: Get-NetAdapter may report ``Up`` while the WiFi
    link is still establishing (no DHCP address yet). Restarting the proxy in
    that window makes kensho_proxy.py resolve no IPv4 and ``exit(2)``, so the
    proxy silently never binds. Wait for a real non-APIPA address first.
    """
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        ip = _adapter_ipv4(adapter)
        if ip:
            return ip
        time.sleep(1)
    return None


def restore_dead_proxies(config: dict, log: Any = None) -> int:
    """
    Try to restart dead proxy processes for active accounts.

    Parameters
    ----------
    config : dict
        Global configuration, must contain key ``accounts`` (list of active
        account keys).  Frozen/disabled accounts are not present in that list.
    log : optional logger

    Returns
    -------
    int
        Number of successfully restarted proxies.
    """
    if log is None:
        log = logging.getLogger(__name__)

    active_accounts: list[str] = [a["key"] for a in config.get("accounts", [])]
    active_set = set(active_accounts)

    restored_count = 0

    for account, (port, adapter) in PROXY_ADAPTER_MAP.items():
        if account not in active_set:
            continue

        # ------------------------------------------------------------------
        # 1. Check whether the proxy is already alive
        # ------------------------------------------------------------------
        if _port_reachable(port, 3):
            log.debug("Proxy %s:%d is alive – skip", account, port)
            continue

        log.warning("Proxy %s:%d is dead", account, port)

        # ------------------------------------------------------------------
        # atushi16 uses a wired ethernet IP – cannot be restarted via adapter
        # ------------------------------------------------------------------
        if account == "atushi16":
            log.info("Skipping %s (wired ethernet – no adapter to restart)", account)
            continue

        # ------------------------------------------------------------------
        # 2. Check Windows adapter status
        # ------------------------------------------------------------------
        try:
            cmd = [
                "powershell.exe",
                "-Command",
                f"(Get-NetAdapter -Name '{adapter}').Status",
            ]
            ps_result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            status = ps_result.stdout.strip()
            if status == "Disabled":
                log.warning(
                    "Adapter %s for %s is '%s' – cannot restart",
                    adapter,
                    account,
                    status,
                )
                continue
            elif status != "Up":
                # ── アダプタがDisconnected → WiFi再接続を試す ──
                ssid = WIFI_SSID_MAP.get(account)
                if ssid:
                    log.info(
                        "Adapter %s is '%s' – trying WiFi reconnect to '%s'",
                        adapter,
                        status,
                        ssid,
                    )
                    connect_cmd = [
                        "powershell.exe",
                        "-Command",
                        f"netsh wlan connect name='{ssid}' interface='{adapter}'",
                    ]
                    subprocess.run(connect_cmd, timeout=15, capture_output=True, text=True)
                    time.sleep(3)
                    # 再接続後、再度アダプタ状態を確認
                    retry_ps = subprocess.run(
                        ["powershell.exe", "-Command", f"(Get-NetAdapter -Name '{adapter}').Status"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    status = retry_ps.stdout.strip()
                    if status != "Up":
                        log.warning(
                            "WiFi reconnect failed – adapter %s still '%s'",
                            adapter,
                            status,
                        )
                        continue
                    log.info("WiFi reconnect succeeded for %s on %s", account, adapter)
                else:
                    log.warning(
                        "No SSID mapping for %s – skipping",
                        account,
                    )
                    continue

            # ── IPv4付与を待つ（WiFi確立の遅延で、アダプタUpでもIP未付与だと
            #    kensho_proxy.py が resolve 失敗で exit(2) し bind しない → 再発防止）──
            ip = _wait_for_adapter_ipv4(adapter, wait_seconds=20)
            if not ip:
                log.warning(
                    "Adapter %s is up but has no non-APIPA IPv4 yet for %s – skipping proxy restart",
                    adapter,
                    account,
                )
                continue

            log.info(
                "Adapter %s is up (IPv4 %s) – restarting proxy for %s",
                adapter,
                ip,
                account,
            )

            # ------------------------------------------------------------------
            # 3. Restart via Start-Process (hidden)
            #    Pass the resolved real IPv4 (not the adapter name) so that
            #    kensho_proxy.py skips its fragile `ipconfig /all` parsing.
            # ------------------------------------------------------------------
            restart_script = (
                f"Start-Process "
                f"-FilePath 'C:\\Users\\1F\\AppData\\Local\\Programs\\Python\\Python311\\python.exe' "
                f"-ArgumentList 'C:\\tools\\kensho-proxy\\kensho_proxy.py','{ip}','{port}' "
                f"-WindowStyle Hidden"
            )
            restart_cmd = ["powershell.exe", "-Command", restart_script]
            subprocess.run(restart_cmd, timeout=10, capture_output=True, text=True)
            restored_count += 1
            log.info("Proxy for %s restarted successfully (restored %d)", account, restored_count)

            # Short delay to let the process start
            time.sleep(1.5)

        except subprocess.TimeoutExpired:
            log.error("PowerShell command timed out for adapter %s", adapter)
        except Exception as exc:
            log.error("Failed to restart proxy for %s: %s", account, exc)

    return restored_count


def check_proxy_health(config: dict, log: Any = None) -> dict:
    """
    Return a summary dictionary of proxy statuses.

    Parameters
    ----------
    config : dict
        Global configuration (must contain ``accounts`` list).
    log : optional logger

    Returns
    -------
    dict
        Keys:
        - ``alive_ports`` – list of ports on which the proxy is currently alive.
        - ``dead_ports`` – list of ports on which the proxy is unresponsive.
        - ``restored_ports`` – number of proxies that were successfully restarted
          during this call.
    """
    if log is None:
        log = logging.getLogger(__name__)

    active_accounts: list[str] = [a["key"] for a in config.get("accounts", [])]
    active_set = set(active_accounts)

    alive: list[int] = []
    dead: list[int] = []

    for account, (port, adapter) in PROXY_ADAPTER_MAP.items():
        if account not in active_set:
            continue
        if _port_reachable(port, 3):
            alive.append(port)
        else:
            dead.append(port)

    restored = 0
    if dead:
        log.info("Dead proxy ports detected: %s – attempting recovery", dead)
        restored = restore_dead_proxies(config, log=log)

    return {"alive_ports": alive, "dead_ports": dead, "restored_ports": restored}
