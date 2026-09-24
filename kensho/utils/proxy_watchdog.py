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
    # 2026-08-28(提案58): フラッピング監視対象 — Galaxy S10系アダプタ(RM10JE_S)で
    #   royalkensho(air-tra1)と同系構成。watchdog復旧ログ頻発・http_0増加が出たら
    #   要ユーザー対応(提案49方式)へ格上げすること。
    "zin20120731": (1084, "zin_AW6povo"),
    # 2026-09-10: HR01 Wi-Fi(RTL8188EU#2 / 10_ymo_HR01)不良（アソシエーション拒否・APIPA）→
    #   ワイモバイルHR01ルーターのLANポートからUSB有線LAN(Tankan_ETH3 / Realtek USB FE)へ直結切替。
    #   旧 Tankan_HR01 は運用除外。回線自体は同じワイモバイルなので出口IPは126.133系のはず。
    "TankanNotes": (1085, "Tankan_ETH3"),
    # 2026-09-24: inobase1-4(1089) は垢バン確定（@inobase128508）→ マップから削除。
    #   accounts からも外れているため watchdog の復旧対象にしない（復旧試行＝BOTシグナル増幅の元）。
    # 2026-09-24: @toushiwatch を RM10JE_S 回線（旧 chugakujuken 用アダプタ。垢バンで解放）へ載せ替え。
    #   実測: 出口IP 106.133.45.122 / egress OK / X API healthy。アダプタ名も chugakujuken_RM10JE_S→RM10JE_S に改名済。
    "toushiwatch": (1087, "RM10JE_S"),
}

# ── WiFi SSID マップ（自動再接続用）──
# 2026-08-27: TankanNotes → ワイモバイルHR01(10_ymo_HR01)へ切替
# 2026-09-10: TankanNotesはLAN直結(Tankan_ETH3)へ移行。netsh wlanが通らないためマップから除去
#   （有線リンクDOWN時の復旧はWindows DHCP側で自動。watchdogはプロキシ再起動のみ行う）
WIFI_SSID_MAP: dict[str, str] = {
    "kudou": "RM10JE_B",
    "zin20120731": "AiR-WiFi_6_povo",
    # 2026-09-24: inobase1-4 は垢バンで削除。toushiwatch は RM10JE_S へ載せ替え。
    "toushiwatch": "RM10JE_S",
}

PROXY_HOST = "172.26.80.1"
PROXY_TIMEOUT = 5  # seconds

# --no-bind 必須アカウント（2026-08-27: ワイモバイルHR01はbind方式で解決したため
#   TankanNotesを除外。--no-bindは全垢で不使用）

# cron環境（PATH=/usr/bin:/bin）では powershell.exe が解決不能のためフルパス指定。
# 2026-08-20 に wifi_watchdog で修正済みの既知パターン。proxy_watchdog への適用。
PS = r"/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe"


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


def _check_egress(port: int, timeout: int = 8) -> bool:
    """SOCKS5経由で実際にインターネットへ出られるか確認（出口IP取得）。

    2026-08-25 追加: kensho-proxy-adapter-fix の「_port_reachable は TCP 疎通のみ
    見るため、WiFi半死（アダプタUp・プロキシLISTENINGでも実データが流れない）を
    『生きてる』と誤判定し、watchdog が復旧しない」盲点を補う。
    例: TankanNotes(1085) はポートOPENなのに出口IP取得がタイムアウトしていた。
    """
    try:
        import socks  # PySocks
    except ImportError:
        # PySocksが無い環境ではポート疎通のみで判定（従来挙動）
        return True
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, PROXY_HOST, port)
        s.settimeout(timeout)
        s.connect(("api.ipify.org", 80))
        s.send(b"GET / HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n")
        data = b""
        while True:
            chunk = s.recv(512)
            if not chunk:
                break
            data += chunk
            if len(data) > 2048:
                break
        s.close()
        return len(data) > 0
    except Exception:
        return False


def _kill_listeners(port: int) -> int:
    """Kill all kensho_proxy processes bound to the given port (Windows).

    2026-08-27追加・強化: 単にLISTENING PIDを殺すだけでは、kensho_proxy.pyが複数
    プロセスで並行稼働してLISTENING PIDが次々と入れ替わるため(1085型で13+プロセス
    積み上がる)取り残しが生じる。CommandLineに `kensho_proxy` + ポート番号を含む
    プロセスを全部killする方が確実。skill「プロキシ多重起動の掃除方法」の方式を採用。
    """
    cmd = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'kensho_proxy' "
        f"-and $_.CommandLine -match ' {port}\\s*$' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
        "| Select-Object -ExpandProperty OwningProcess -Unique "
        "| ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
    )
    cmd_list = [
        PS,
        "-NoProfile",
        "-Command",
        cmd,
    ]
    try:
        subprocess.run(cmd_list, capture_output=True, text=True, errors="replace", timeout=15)
        return 1
    except (subprocess.TimeoutExpired, OSError):
        return 0


def _adapter_ipv4(adapter: str) -> str | None:
    """Return the first usable (non-APIPA) IPv4 of a Windows adapter, else None."""
    cmd = [
        PS,
        "-NoProfile",
        "-Command",
        f"(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias '{adapter}' -ErrorAction SilentlyContinue).IPAddress",
    ]
    try:
        ps = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=10)
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
        # 1. Check whether the proxy is already alive (TCP + egress)
        # ------------------------------------------------------------------
        _need_wifi_reconnect = False
        if _port_reachable(port, 3):
            if _check_egress(port, 6):
                log.debug("Proxy %s:%d is alive – skip", account, port)
                continue
            # ★ 2026-08-25: ポートはLISTENINGだが実疎通なし（WiFi半死）
            #   → 従来は「生きてる」と誤判定してスキップしていた。強制復旧する。
            log.warning(
                "Proxy %s:%d is LISTENING but has NO egress – forcing WiFi reconnect + restart",
                account,
                port,
            )
            _need_wifi_reconnect = True
        else:
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
                PS,
                "-Command",
                f"(Get-NetAdapter -Name '{adapter}').Status",
            ]
            ps_result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=10)
            status = ps_result.stdout.strip()
            if status == "Disabled":
                log.warning(
                    "Adapter %s for %s is '%s' – cannot restart",
                    adapter,
                    account,
                    status,
                )
                continue
            if status != "Up" or _need_wifi_reconnect:
                # ── アダプタDisconnected or 疎通なし → WiFi再接続を試す ──
                ssid = WIFI_SSID_MAP.get(account)
                if ssid:
                    if _need_wifi_reconnect:
                        # 2026-08-25: アダプタUpでも疎通なし（WiFi半死）→ 一旦切断して
                        # 再接続しリンクをリセットする
                        log.info(
                            "Adapter %s is Up but no egress – forcing WiFi reconnect to '%s'",
                            adapter,
                            ssid,
                        )
                        subprocess.run(
                            [
                                PS,
                                "-Command",
                                f"netsh wlan disconnect interface='{adapter}'",
                            ],
                            timeout=10,
                            capture_output=True,
                            text=True,
                            errors="replace",
                        )
                        time.sleep(2)
                    else:
                        log.info(
                            "Adapter %s is '%s' – trying WiFi reconnect to '%s'",
                            adapter,
                            status,
                            ssid,
                        )
                    connect_cmd = [
                        PS,
                        "-Command",
                        f"netsh wlan connect name='{ssid}' interface='{adapter}'",
                    ]
                    subprocess.run(connect_cmd, timeout=15, capture_output=True, text=True, errors="replace")
                    time.sleep(3)
                    # 再接続後、再度アダプタ状態を確認
                    retry_ps = subprocess.run(
                        [PS, "-Command", f"(Get-NetAdapter -Name '{adapter}').Status"],
                        capture_output=True,
                        text=True,
                        errors="replace",
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
                    # 2026-09-10 QA修正(edb8a02回帰): TankanNotesはLAN直結(Tankan_ETH3)で
                    #   WIFI_SSID_MAPから除去済み。アダプタUpなのにegressなし（LAN一時的断・
                    #   ルーター再起動・DHCP変更）はプロキシプロセス再起動で復旧できるため、
                    #   「No SSID mapping」でcontinueして自動復旧を放棄してはいけない（旧バグ）。
                    #   ※ アダプタ自体がDownの有線はソフトウェア復旧不可なので従来どおりskip。
                    if status == "Up":
                        log.warning(
                            "No SSID mapping for %s but adapter %s is Up (wired) – restarting proxy directly",
                            account,
                            adapter,
                        )
                    else:
                        log.warning(
                            "No SSID mapping for %s and adapter not Up – skipping",
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

            # ── 再起動前に既存LISTENINGプロセスをkill（多重LISTENING積み上がり防止。2026-08-27追加）──
            _kill_listeners(port)

            # ------------------------------------------------------------------
            # 3. Restart via Start-Process (hidden)
            #    Pass the adapter name so that kensho_proxy.py resolves the
            #    current IPv4 at startup (auto-handles DHCP changes).
            #    # 2026-08-29: Changed from IP bind to adapter name bind (提案62)
            # ------------------------------------------------------------------
            no_bind_arg = ""
            restart_script = (
                f"Start-Process "
                f"-FilePath 'C:\\Users\\1F\\AppData\\Local\\Programs\\Python\\Python311\\python.exe' "
                f"-ArgumentList 'C:\\tools\\kensho-proxy\\kensho_proxy.py'{no_bind_arg},'{adapter}','{port}' "
                f"-WindowStyle Hidden"
            )
            restart_cmd = [PS, "-Command", restart_script]
            subprocess.run(restart_cmd, timeout=10, capture_output=True, text=True, errors="replace")
            restored_count += 1
            log.info("Proxy for %s restarted successfully (restored %d)", account, restored_count)

            # Short delay to let the process start
            time.sleep(1.5)

        except subprocess.TimeoutExpired:
            log.error("PowerShell command timed out for adapter %s", adapter)
        except Exception as exc:
            log.error("Failed to restart proxy for %s: %s", account, exc)

    return restored_count


# ── 2026-09-18 (t_9e8a1b2c) プロキシ死骸の原因明記 ──────────────────────
# 各垢のステータスを「最終成功」「最終エラー種別」「停止理由」で構造化する純関数。
# gen_status_data.py が data/status/*.json を生成する際に使う。テスト容易性のため
# ログ/IO 依存を一切持たせず、渡された値だけから判定する。
PROXY_STATUS = ["alive", "dead_proxy", "unchecked"]


def account_proxy_status(
    port: int,
    alive_ports: list[int],
    dead_ports: list[int],
    success_ts: str = "",
    success_action: str = "",
    last_error_type: str = "",
    stop_reason: str = "",
    dead_reason: str = "",
) -> dict:
    """1垢ぶんのプロキシ状態を構造化して返す。

    Parameters
    ----------
    port : その垢のプロキシポート
    alive_ports / dead_ports : check_proxy_health の判定結果
    success_ts / success_action : 最終成功（audit の最終 success エントリ）
    last_error_type : 最終エラー種別（audit の最終 fail エントリの error 値）
    stop_reason : 応募停止理由（config コメントアウト等）。無ければ空文字列
    dead_reason : プロキシ死骸の具体原因（アダプタ切断/復旧不可等）

    Returns
    -------
    dict（JSON 化して status/<acct>.json に書き出す想定）
      - status: "alive" | "dead_proxy" | "unchecked"
      - status_schema: PROXY_STATUS 列挙（grep 'dead_proxy' 検証用に常時付与）
      - last_success / last_error_type / stop_reason
    """
    is_dead = port in dead_ports
    is_alive = port in alive_ports
    if is_dead:
        status = "dead_proxy"
        reason = stop_reason or dead_reason or "プロキシ死骸（TCP疎通 or 出口IP確認失敗）"
    elif is_alive:
        status = "alive"
        reason = stop_reason or ""
    else:
        status = "unchecked"
        reason = stop_reason or "当該垢は現在の稼働対象外（config外）または未チェック"
    return {
        "status": status,
        "status_schema": PROXY_STATUS,
        "port": port,
        "last_success": f"{success_ts} {success_action}".strip(),
        "last_error_type": last_error_type,
        "stop_reason": reason,
    }


def build_proxy_panel(
    alive_ports: list[int],
    dead_ports: list[int],
    restored: int,
    per_account: dict[str, dict],
    ts: str = "",
) -> dict:
    """全垢のプロキシ概要パネル（ダッシュボード表示用）を組み立てる純関数。"""
    dead_accts = [(acct, d.get("port")) for acct, d in per_account.items() if d.get("status") == "dead_proxy"]
    if dead_accts:
        status_ok = False
        reason = "プロキシ不通（アダプタ切断または復旧不可）。firewatch/手動確認が必要"
    else:
        status_ok = True
        reason = "全プロキシ正常"
    return {
        "ok": status_ok,
        "checked": True,
        "alive": sorted(acct for acct, d in per_account.items() if d.get("status") == "alive"),
        "dead": sorted(dead_accts),
        "restored": restored,
        "reason": reason,
        "ts": ts,
        "accounts": per_account,
    }


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
        # 2026-08-25: TCP疎通に加えて出口IP確認（WiFi半死の誤判定防止）
        if _port_reachable(port, 3) and _check_egress(port, 6):
            alive.append(port)
        else:
            dead.append(port)

    restored = 0
    if dead:
        log.info("Dead proxy ports detected: %s – attempting recovery", dead)
        restored = restore_dead_proxies(config, log=log)

    return {"alive_ports": alive, "dead_ports": dead, "restored_ports": restored}
