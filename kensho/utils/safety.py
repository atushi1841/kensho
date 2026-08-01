"""
Kensho Safety — 安全チェック機能
- IP分離検証: 各アカウントのSOCKS5プロキシ経由で異なるIPが出ているか確認
"""

from __future__ import annotations

import time
from typing import Any

# チェック結果のキャッシュ（プロセス内で1回だけ実行）
_ip_verified: tuple[bool, list[str], float] | None = None  # (result, blocked_accounts, timestamp)


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
    if unreachable:
        messages.append(f"  ⚠️ 不通アカウント（スキップ）: {', '.join(unreachable)}")

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
