#!/usr/bin/env python3
"""
Kensho Proxy Checker — 全アカウントのSOCKS5プロキシを逐次チェック（直列実行）
v1.0: メモリ節約のため1ポートずつ順次チェック、curl/並列呼び出し不要

使い方:
  python utils/check_proxies.py                  # 全垢チェック
  python utils/check_proxies.py atushi16         # 特定垢のみ
  python utils/check_proxies.py --timeout 15     # タイムアウト変更

戻り値: 全てOK=0, 不通あり=1
"""

from __future__ import annotations

import json
import socket
import sys
import time
from typing import Any

# プロキシ定義（browser.py と同じ構造）
PROXY_MAP: dict[str, str] = {
    "atushi16": "socks5h://172.26.80.1:1081",
    "kudou": "socks5h://172.26.80.1:1082",
    "zin20120731": "socks5h://172.26.80.1:1084",
    "TankanNotes": "socks5h://172.26.80.1:1085",
    "toushiwatch": "socks5h://172.26.80.1:1087",
}

# 各アカウントの期待ASNパターン（ipinfo.io org フィールドに部分一致・大文字小文字無視）
# 2026-08-31提案99: 出口IP/ASN検証。空文字=チェック対象外（自宅有線等）
EXPECTED_ASN: dict[str, str] = {
    "atushi16": "",  # 自宅有線（固定IP・ASN非チェック）
    "kudou": "KDDI",  # POVO → au/KDDI系（実測 AS2516 KDDI）
    "zin20120731": "楽天",  # 楽天モバイル
    "TankanNotes": "SoftBank",  # ワイモバイル → SoftBank系（実測 AS17676 SoftBank）
    "toushiwatch": "KDDI",  # POVO → au/KDDI系
}


def _recv_exact(s: socket.socket, n: int) -> bytes:
    """ちょうどnバイト読み切る（SOCKS5ヘッダ用）。"""
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise RuntimeError("SOCKS5: connection closed")
        data += chunk
    return data


def _socks5_connect(host: str, port: int, timeout: int, target_host: str = "api.ipify.org") -> socket.socket:
    """生SOCKS5ハンドシェイク（stdlibのみ、PySocks不要）。接続済みsocketを返す。

    socks5h 相当: CONNECT要求はドメイン名のまま送り、DNS解決はプロキシ側に任せる。
    target_host: CONNECT先（デフォルト api.ipify.org。ASN検証では ipinfo.io）。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))

    # 挨拶: SOCKS5, 1メソッド, 認証なし
    s.sendall(b"\x05\x01\x00")
    resp = _recv_exact(s, 2)
    if resp[0] != 0x05 or resp[1] != 0x00:
        raise RuntimeError(f"SOCKS5 auth method rejected: {resp[1]!r}")

    # CONNECT要求（ドメイン名 → リモートDNS）
    target = target_host.encode()
    req = b"\x05\x01\x00\x03" + bytes([len(target)]) + target + (80).to_bytes(2, "big")
    s.sendall(req)
    resp = _recv_exact(s, 4)
    if resp[1] != 0x00:
        raise RuntimeError(f"SOCKS5 connect failed: code={resp[1]!r}")

    # BND.ADDR + BND.PORT を読み捨て
    atyp = resp[3]
    if atyp == 0x01:  # IPv4
        _recv_exact(s, 4 + 2)
    elif atyp == 0x03:  # ドメイン
        ln = _recv_exact(s, 1)[0]
        _recv_exact(s, ln + 2)
    elif atyp == 0x04:  # IPv6
        _recv_exact(s, 16 + 2)
    return s


def check_one(account_key: str, proxy_url: str, timeout: int = 10) -> dict[str, Any]:
    """1アカウントのプロキシをチェック。戻り値: {key, proxy, ip, ok, elapsed, error}"""
    start = time.time()
    result: dict[str, Any] = {
        "key": account_key,
        "proxy": proxy_url,
        "ip": None,
        "asn": None,  # 2026-08-31提案99: ipinfo.io org
        "ok": False,
        "elapsed": 0.0,
        "error": None,
    }

    try:
        # URLパース
        clean = proxy_url.replace("socks5h://", "").replace("socks5://", "")
        host, port_str = clean.rsplit(":", 1)
        port = int(port_str)

        # SOCKS5接続（逐次: 1回だけ、stdlibハンドシェイク）
        s = _socks5_connect(host, port, timeout)
        s.send(b"GET / HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n")
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()

        body = resp.split(b"\r\n\r\n", 1)[-1].decode().strip()
        result["ip"] = body if body else None
        result["ok"] = bool(body)
    except Exception as e:
        result["error"] = str(e)[:80]

    result["elapsed"] = round(time.time() - start, 1)
    return result


def _fetch_asn(proxy_url: str, exit_ip: str, timeout: int = 10) -> str | None:
    """SOCKS5プロキシ経由で ipinfo.io にASN照会。戻り値: org（例: 'AS17676 au one net'）。

    2026-08-31提案99: 出口IP/ASN検証。誤SSID接続や転売品モバイル混入でASNが
    期待キャリア（povo/au等）と異なるのを早期検出する。
    注: SOCKS5接続自体が該当プロキシ経由のため `GET /json` で現在の出口IPの
    ASNが返る（`/{ip}/json` は無料版で409 Conflictになるため不可）。
    """
    try:
        clean = proxy_url.replace("socks5h://", "").replace("socks5://", "")
        host, port_str = clean.rsplit(":", 1)
        port = int(port_str)

        s = _socks5_connect(host, port, timeout, target_host="ipinfo.io")
        s.send(b"GET /json HTTP/1.0\r\nHost: ipinfo.io\r\n\r\n")
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()

        body = resp.split(b"\r\n\r\n", 1)[-1]
        data = json.loads(body)
        return data.get("org")  # type: ignore[no-any-return]
    except Exception:
        return None


def main() -> int:
    import sys

    targets: list[str] = []
    timeout: int = 10
    check_asn: bool = False  # 2026-08-31提案99

    # 引数パース
    for arg in sys.argv[1:]:
        if arg.startswith("--timeout="):
            timeout = int(arg.split("=")[1])
        elif arg == "--asn":
            check_asn = True
        elif arg.startswith("--"):
            print(f"[WARN] 未知のオプション: {arg}")
        else:
            targets.append(arg)

    if not targets:
        targets = list(PROXY_MAP.keys())

    print(
        f"🔍 プロキシチェック: {len(targets)}アカウント（逐次実行、timeout={timeout}s）"
        + (" + ASN検証" if check_asn else "")
    )
    print(f"   {'垢':<16} {'プロキシ':<30} {'IP':<16} {'時間':>5} {'結果'}")
    print(f"   {'─' * 16} {'─' * 30} {'─' * 16} {'─' * 5} {'─' * 8}")

    all_ok = True
    seen_ips: dict[str, str] = {}

    for key in targets:
        proxy = PROXY_MAP.get(key)
        if not proxy:
            print(f"   {key:<16} {'(未登録)':<30} {'':<16} {'':>5} ❌")
            all_ok = False
            continue

        # ★ 逐次: 1アカウントずつチェック
        res = check_one(key, proxy, timeout)

        ip_str = res["ip"] or "(不通)"
        elapsed_str = f"{res['elapsed']}s"
        ok_mark = "✅" if res["ok"] else "❌"
        print(f"   {key:<16} {proxy:<30} {ip_str:<16} {elapsed_str:>5} {ok_mark}")

        # ★ 2026-08-31提案99: ASN検証（--asn指定時のみ）
        if check_asn and res["ok"] and res["ip"]:
            asn = _fetch_asn(proxy, res["ip"], timeout)
            if asn:
                expected = EXPECTED_ASN.get(key, "")
                if expected:
                    matched = expected.lower() in asn.lower()
                    asn_mark = "✅" if matched else "⚠️"
                    print(f"   {'':<16} {'':<30} {'':<16} {'':>5} {asn_mark} ASN: {asn}")
                    if not matched:
                        print(f"   {'':<16} {'':<30} {'':<16} {'':>5}   └─ 期待 '{expected}' 不一致")
                else:
                    print(f"   {'':<16} {'':<30} {'':<16} {'':>5}   · ASN: {asn}")
            else:
                print(f"   {'':<16} {'':<30} {'':<16} {'':>5}   · ASN取得失敗")

        if res["error"]:
            print(f"   {'':<16} {'':<30} {'':<16} {'':>5}   └─ {res['error']}")

        # IP重複チェック
        if res["ok"] and res["ip"]:
            if res["ip"] in seen_ips:
                print(f"   {'':<16} {'':<30} {'':<16} {'':>5}   ⚠ 重複: {seen_ips[res['ip']]} と同じIP")
                all_ok = False
            else:
                seen_ips[res["ip"]] = key

        if not res["ok"]:
            all_ok = False

        # ★ 1垢ごとに100ms待機（バースト防止）
        time.sleep(0.1)

    print()
    if all_ok:
        print(f"✅ 全{len(targets)}アカウント: IP分離OK")
        return 0
    else:
        print("❌ 不通または重複あり")
        return 1


if __name__ == "__main__":
    sys.exit(main())
