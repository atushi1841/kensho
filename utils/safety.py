"""
Kensho Safety — 安全チェック機能
- IP分離検証: 各アカウントのSOCKS5プロキシ経由で異なるIPが出ているか確認
"""
from __future__ import annotations

import time
import socket
from typing import Any

# チェック結果のキャッシュ（プロセス内で1回だけ実行）
_ip_verified: tuple[bool, float] | None = None  # (result, timestamp)


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
    except Exception as e:
        return None


def check_ip_separation(cfg: dict[str, Any],
                        log: Any = None) -> tuple[bool, list[str]]:
    """
    全アカウントのプロキシ経由IPが全て異なることを確認。

    Returns:
        (success, messages)
        success=True: IP分離OK
        success=False: IP分離NG（重複または不通）
    """
    from application.browser import PROXY_MAP, USE_PROXY

    messages: list[str] = []

    if not USE_PROXY:
        messages.append("[SAFETY] USE_PROXY=False → IP分離チェックスキップ")
        return (True, messages)

    if not PROXY_MAP:
        messages.append("[SAFETY] PROXY_MAPが空 → チェックスキップ")
        return (True, messages)

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

    # 重複チェック
    seen_ips: dict[str, str] = {}
    all_ok = True
    for name, ip in results.items():
        if ip is None:
            all_ok = False
            continue
        if ip in seen_ips:
            messages.append(f"  [重複] {name} = {seen_ips[ip]} = {ip}")
            all_ok = False
        else:
            seen_ips[ip] = name

    if all_ok:
        ok_count = len([v for v in results.values() if v is not None])
        msg_ok = f"[SAFETY] ✅ IP分離OK: {ok_count}アカウント全て異なるIP"
        messages.append(msg_ok)
        if log:
            log.write(msg_ok)
        else:
            print(msg_ok, flush=True)
    else:
        messages.append("  ❌ IP分離NG: 重複または不通あり")
        if log:
            for msg in messages:
                log.write(msg)

    return (all_ok, messages)


def verify_ip_separation(cfg: dict[str, Any],
                         log: Any = None,
                         force: bool = False) -> bool:
    """
    IP分離チェックのエントリポイント（キャッシュ付き）。

    初回成功後は30分間キャッシュする。
    失敗時は毎回再チェックする。

    Args:
        cfg: 設定
        log: LogWriter
        force: Trueなら強制的に再チェック

    Returns:
        True: IP分離OK（またはチェック不要）
        False: IP分離NG
    """
    global _ip_verified

    now = time.time()
    cache_ttl: int = cfg.get("safety", {}).get("cache_ttl_seconds", 1800)

    # キャッシュ有効
    if not force and _ip_verified is not None:
        result, timestamp = _ip_verified
        if result and (now - timestamp) < cache_ttl:
            return True

    ok, msgs = check_ip_separation(cfg, log)

    # 結果をキャッシュ（成功も失敗もキャッシュするが、失敗は短めに）
    _ip_verified = (ok, now)

    return ok
