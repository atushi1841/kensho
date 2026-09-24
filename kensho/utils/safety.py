"""
Kensho Safety — 安全チェック機能
- IP分離検証: 各アカウントのSOCKS5プロキシ経由で異なるIPが出ているか確認
- プロキシ死骸検出: data/status/<acct>.json が dead_proxy の垢は応募を試行しない（t_8946706e）
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# チェック結果のキャッシュ（プロセス内で1回だけ実行）
_ip_verified: tuple[bool, list[str], float] | None = None  # (result, blocked_accounts, timestamp)


def dead_proxy_reason(cfg: dict[str, Any], account_key: str) -> str:
    """`data/status/<acct>.json` を見て、その垢のプロキシが死骸なら理由文字列を返す（健全/未検査なら ""）。

    ★ t_8946706e: 死骸プロキシの垢を「警告のみ」で応募処理へ進めると、goto失敗→ログイン再試行が
    繰り返され BOTシグナルを増幅する（実測 goto failed 63→227件/日）。status ファイルは
    proxy_watchdog が「最終成功」「最終エラー種別」「停止理由」付きで書く唯一のオフライン信号なので、
    これを blocked 判定の一次入力にする（追加のネットワーク試行はしない）。
    無効化は config `safety.dead_proxy_check: false`。

    鮮度ガード: status 生成が止まると死骸のまま永久ブロックになるため、`updated` が
    `safety.dead_proxy_max_age_hours`（既定6時間）より古い場合は判定不能として扱う
    （生死の最終防衛線は実行時の check_ip_separation 側にある）。
    """
    if not cfg.get("safety", {}).get("dead_proxy_check", True):
        return ""
    project_dir = str((cfg.get("general") or {}).get("project_dir") or "")
    if not project_dir:
        return ""
    status_path = Path(project_dir) / "data" / "status" / f"{account_key}.json"
    if not status_path.exists():
        return ""
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    if str(data.get("status", "")).strip() != "dead_proxy":
        return ""
    max_age_h = float(cfg.get("safety", {}).get("dead_proxy_max_age_hours", 6) or 0)
    updated = str(data.get("updated") or "")
    if max_age_h > 0 and updated:
        try:
            from datetime import datetime
            age_h = (datetime.now() - datetime.fromisoformat(updated.replace("Z", ""))).total_seconds() / 3600
            if age_h > max_age_h:
                return ""
        except Exception:
            pass
    detail = str(data.get("stop_reason") or data.get("last_error_type") or "proxy unreachable")
    return f"{detail} / 最終確認 {updated}" if updated else detail


def network_outage_reason(cfg: dict[str, Any], account_key: str) -> str:
    """`data/account_wifi_map.json` から WiFi 状態をチェックし、
    SSID圏外/電源OFF/バックOFFの状態を検出する。

    戻り値: ネットワーク出区なら理由文字列、正常時は空文字列
    """
    wifi_map_path = Path(
        str((cfg.get("general") or {}).get("project_dir", ""))
        + "/data/account_wifi_map.json"
    )
    if not wifi_map_path.exists():
        return ""
    try:
        wifi_map = json.loads(wifi_map_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    account_entry = None
    for entry in wifi_map.get("accounts", []):
        if entry.get("key") == account_key:
            account_entry = entry
            break

    if not account_entry:
        return ""

    state = account_entry.get("adapter_state", "")
    proxy_state = account_entry.get("proxy_state", "")
    # "切断" or "未検出"でもプロキシがlisten中なら圏外扱いしない
    if state in ("切断", "未検出") and proxy_state != "listen":
        return f"ネットワーク出区: アカウント '{account_key}' のWiFiが{state}状態"
    # "有線(NIC)" は有線LAN接続 → WiFi出区ではない
    if state == "有線(NIC)":
        return ""
    # その他（接続中など）→ 正常
    return ""


def dead_proxy_accounts(cfg: dict[str, Any], accounts: list[str] | None = None) -> list[str]:
    """プロキシ死骸と判定されている垢の一覧（ブロック対象）。"""
    keys = accounts if accounts is not None else [str(a.get("key", "")) for a in cfg.get("accounts", [])]
    return sorted(k for k in keys if k and dead_proxy_reason(cfg, k))


def _get_ip_via_socks5(host: str, port: int, timeout: int = 10) -> str | None:
    """SOCKS5プロキシ経由で出口IPを取得"""
    import socks

    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, host, port)
        s.settimeout(timeout)
        s.connect(("api.ipify.org", 80))
        s.send(b"GET / HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n")
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        body = resp.split(b"\r\n\r\n", 1)[-1].decode().strip()
        return body if body else None
    except Exception:
        return None


def check_ip_separation(cfg: dict[str, Any], log: Any = None) -> tuple[bool, list[str], list[str]]:
    """
    全アカウントのプロキシ経由IPが全て異なることを確認。

    Returns:
        (success, messages, blocked_accounts)
        success=True: 続行可能（重複アカウントがある場合はblocked_accountsにリスト）
        success=False: 全停止（全アカウント不通など）
    """
    from kensho.application.browser import PROXY_MAP, USE_PROXY

    messages: list[str] = []

    if not USE_PROXY:
        messages.append("[SAFETY] USE_PROXY=False → IP分離チェックスキップ")
        return (True, messages, [])

    if not PROXY_MAP:
        messages.append("[SAFETY] PROXY_MAPが空 → チェックスキップ")
        return (True, messages, [])

    timeout: int = cfg.get("safety", {}).get("ip_check_timeout", 10)

    messages.append(f"[SAFETY] IP分離チェック開始 ({len(PROXY_MAP)}アカウント)")

    results: dict[str, str | None] = {}
    for name, proxy_url in PROXY_MAP.items():
        # proxy_url = "socks5://host:port" or "socks5h://host:port"
        try:
            clean = proxy_url.replace("socks5h://", "").replace("socks5://", "")
            host, port_str = clean.rsplit(":", 1)
            port = int(port_str)
        except Exception:
            messages.append(f"  {name}: プロキシURL解析失敗: {proxy_url}")
            results[name] = None
            continue

        ip = _get_ip_via_socks5(host, port, timeout)
        results[name] = ip
        if ip:
            messages.append(f"  {name}: {ip} (via {host}:{port})")
        else:
            messages.append(f"  {name}: 不通 ({host}:{port})")

    # 重複チェック + 不通は個別スキップ
    seen_ips: dict[str, str] = {}
    unreachable: list[str] = []
    duplicates: list[str] = []
    blocked_by_ip: list[str] = []

    # 自宅インターネット回線を使う正規アカウントのIPを収集
    home_accts: list[str] = cfg.get("safety", {}).get("home_internet_accounts", [])
    home_ips: set[str] = set()
    for name, ip in results.items():
        if ip and name in home_accts:
            home_ips.add(ip)

    for name, ip in results.items():
        if ip is None:
            unreachable.append(name)
            continue
        # 自宅IPと一致するが、自宅回線の正規アカウントではない → ブロック
        if ip in home_ips and name not in home_accts:
            msg = f"  [ブロック] {name}: {ip}（自宅IPと同じ → 応募停止）"
            messages.append(msg)
            duplicates.append(msg)
            blocked_by_ip.append(name)
            continue
        if ip in seen_ips:
            dup_msg = f"  [重複] {name} = {seen_ips[ip]} = {ip}"
            messages.append(dup_msg)
            duplicates.append(dup_msg)
        else:
            seen_ips[ip] = name

    # 不通があっても他が正常なら続行（不通垢だけスキップ）
    # ★ t_8946706e: 不通垢を「警告のみ」で応募処理へ進めていたため、死骸プロキシの垢が
    #   応募を試行し続けた（実測 zin20120731 は dead_proxy なのに apply 試行が記録され続けた）。
    #   不通＝その垢は blocked 扱いにして停止する（自宅IPへフォールバックはさせない）。
    if unreachable:
        messages.append(
            f"  ⚠️ 不通アカウント（ブロック→応募を試行しない）: {', '.join(unreachable)}"
        )

    # ★ t_8946706e: status/<acct>.json が dead_proxy の垢もブロック（オフライン信号での多重防御）
    offline_dead = dead_proxy_accounts(cfg)
    if offline_dead:
        messages.append(
            f"  [ブロック] プロキシ死骸（status=dead_proxy）: {', '.join(offline_dead)} → 応募を試行しない"
        )

    if duplicates:
        messages.append("  ❌ IP重複あり → 先着優先で最初のアカウントのみ許可、他はブロック")
        # 最初に見つかったアカウントを保持し、それ以外の重複アカウントをブロック
        first_seen: dict[str, str] = {}  # ip -> first account name
        for name in results:
            ip = results[name]
            if ip is None:
                continue
            if ip not in first_seen:
                first_seen[ip] = name
        # IP重複で最初以外のアカウントをブロック
        blocked = sorted(
            set(name for name, ip in results.items() if ip is not None and first_seen.get(ip) != name)
            | set(blocked_by_ip)
        )
        messages.append(f"  → ブロックするアカウント（IP重複）: {', '.join(blocked)}")
        all_ok = True
    else:
        all_ok = True
        blocked = []
        ok_count = len([v for v in results.values() if v is not None])
        if ok_count > 0:
            msg_ok = f"[SAFETY] ✅ IP分離OK: {ok_count}アカウント（不通{len(unreachable)}スキップ）"
            messages.append(msg_ok)
            if log:
                log.write(msg_ok)
            else:
                print(msg_ok, flush=True)
        else:
            messages.append("  ❌ 全アカウント不通 → 応募不可")
            all_ok = False
            blocked = []

    # ★ t_8946706e: 不通垢・プロキシ死骸垢を blocked に合流させる（呼出側 applier がこのリストで当該垢だけスキップ）
    blocked = sorted(set(blocked) | set(unreachable) | set(offline_dead))
    if blocked:
        messages.append(f"  → blocked（応募を試行しない）: {', '.join(blocked)}")

    return (all_ok, messages, blocked)


def verify_ip_separation(cfg: dict[str, Any], log: Any = None, force: bool = False) -> tuple[bool, list[str]]:
    """
    IP分離チェックのエントリポイント（キャッシュ付き）。

    初回成功後は30分間キャッシュする。
    失敗時は毎回再チェックする。

    Args:
        cfg: 設定
        log: LogWriter
        force: Trueなら強制的に再チェック

    Returns:
        (ok, blocked_accounts)
        ok=True: 続行可能
        ok=False: 全停止
        blocked_accounts: ブロックすべきアカウント名リスト（重複IPがある場合）
    """
    global _ip_verified

    now = time.time()
    cache_ttl: int = cfg.get("safety", {}).get("cache_ttl_seconds", 1800)

    # キャッシュ有効
    if not force and _ip_verified is not None:
        result, blocked, timestamp = _ip_verified
        if result and (now - timestamp) < cache_ttl:
            return (True, blocked)

    ok, msgs, blocked = check_ip_separation(cfg, log)

    # 結果をキャッシュ（成功も失敗もキャッシュするが、失敗は短めに）
    _ip_verified = (ok, blocked, now)

    return (ok, blocked)
