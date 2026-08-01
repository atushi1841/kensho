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
    "atushi1840": (1083, "Atushi1840_RM10JE_S"),
    "zin20120731": (1084, "zin_AiRWiFi"),
    "TankanNotes": (1085, "Tankan_8iP6s"),
    "inobase1-4": (1089, "inobase1-4"),
}

# ── WiFi SSID マップ（自動再接続用）──
WIFI_SSID_MAP: dict[str, str] = {
    "kudou": "RM10JE_B",
    "atushi1840": "RM10JE_S",
    "zin20120731": "AiR-WiFi_B8W38T_ino",
    "TankanNotes": "8_iP6s",
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

            log.info("Adapter %s is up – restarting proxy for %s", adapter, account)

            # ------------------------------------------------------------------
            # 3. Restart via Start-Process (hidden)
            # ------------------------------------------------------------------
            restart_script = (
                f"Start-Process "
                f"-FilePath 'C:\\Users\\1F\\AppData\\Local\\Programs\\Python\\Python311\\python.exe' "
                f"-ArgumentList 'C:\\tools\\kensho-proxy\\kensho_proxy.py','{adapter}','{port}' "
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
