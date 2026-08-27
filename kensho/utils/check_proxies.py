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

import sys
import time
from typing import Any

# プロキシ定義（browser.py と同じ構造）
PROXY_MAP: dict[str, str] = {
    "atushi16": "socks5h://172.26.80.1:1081",
    "kudou": "socks5h://172.26.80.1:1082",
    "chugakujuken": "socks5h://172.26.80.1:1083",
    "zin20120731": "socks5h://172.26.80.1:1084",
    "TankanNotes": "socks5h://172.26.80.1:1085",
    "inobase1-4": "socks5h://172.26.80.1:1089",
    "royalkensho": "socks5h://172.26.80.1:1087",
}


def check_one(account_key: str, proxy_url: str, timeout: int = 10) -> dict[str, Any]:
    """1アカウントのプロキシをチェック。戻り値: {key, proxy, ip, ok, elapsed, error}"""
    import socks

    start = time.time()
    result: dict[str, Any] = {
        "key": account_key,
        "proxy": proxy_url,
        "ip": None,
        "ok": False,
        "elapsed": 0.0,
        "error": None,
    }

    try:
        # URLパース
        clean = proxy_url.replace("socks5h://", "").replace("socks5://", "")
        host, port_str = clean.rsplit(":", 1)
        port = int(port_str)

        # SOCKS5接続（逐次: 1回だけ）
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
        result["ip"] = body if body else None
        result["ok"] = bool(body)
    except Exception as e:
        result["error"] = str(e)[:80]

    result["elapsed"] = round(time.time() - start, 1)
    return result


def main() -> int:
    import sys

    targets: list[str] = []
    timeout: int = 10

    # 引数パース
    for arg in sys.argv[1:]:
        if arg.startswith("--timeout="):
            timeout = int(arg.split("=")[1])
        elif arg.startswith("--"):
            print(f"[WARN] 未知のオプション: {arg}")
        else:
            targets.append(arg)

    if not targets:
        targets = list(PROXY_MAP.keys())

    print(f"🔍 プロキシチェック: {len(targets)}アカウント（逐次実行、timeout={timeout}s）")
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
