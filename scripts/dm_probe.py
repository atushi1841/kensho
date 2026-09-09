"""DMプローブ（読み取り専用・一回もの検証用）
X DM inbox をブラウザレス（curl_cffi）で取得できるか検証する。
認証情報の値は出力しない。会話数と当選キーワードヒット数のみ報告。
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

from curl_cffi import requests as crq

ROOT = Path("/mnt/d/Project2/kensho")
X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_KEYWORD = "obfiowerehiring"
_pairs = json.load(open(ROOT / "kensho" / "application" / "transaction_pairs.json"))


def _gen_tid(method: str, path: str) -> str:
    p = random.choice(_pairs)
    key_bytes = list(base64.b64decode(p["verification"]))
    t = math.floor((time.time() * 1000 - 1682924400 * 1000) / 1000)
    tb = [(t >> (i * 8)) & 0xFF for i in range(4)]
    h = list(hashlib.sha256(f"{method}!{path}!{t}{_KEYWORD}{p['animationKey']}".encode()).digest())
    rn = random.randint(0, 255)
    b = bytearray([rn, *[x ^ rn for x in [*key_bytes, *tb, *h[:16], 3]]])
    return base64.b64encode(b).decode().rstrip("=")


def load_session(key: str) -> tuple[str, str]:
    if key == "atushi16":
        f = ROOT / "data" / "x_session.json"
    else:
        f = ROOT / "data" / f"x_session_{key}.json"
    d = json.load(open(f))
    cs = {c["name"]: c["value"] for c in d.get("cookies", [])}
    return cs.get("auth_token", ""), cs.get("ct0", "")


def get(url: str, auth: str, ct0: str) -> dict:
    path = url.replace("https://x.com", "")
    headers = {
        "authorization": f"Bearer {X_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "ja",
        "cookie": f"auth_token={auth}; ct0={ct0}",
        "x-client-transaction-id": _gen_tid("GET", path),
        "referer": "https://x.com/messages",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }
    r = crq.get(url, headers=headers, timeout=25, impersonate="chrome")
    out: dict = {"status": int(r.status_code)}
    try:
        out["data"] = r.json()
    except Exception:
        out["body_head"] = r.text[:120]
    return out


def summarize(tag: str, res: dict) -> None:
    st = res.get("status")
    print(f"[{tag}] status={st}")
    if st != 200 or "data" not in res:
        print(f"  body_head={res.get('body_head', '')!r}")
        return
    d = res["data"]
    # init_all / inbox_initial_state 共通: conversation_modules + entries
    entries = d.get("entries", {})
    if not entries and "data" in d:
        entries = d["data"].get("entries", {})
    print(f"  entries(conv)={len(entries)}")
    keys = list(d.keys())
    print(f"  top_keys={keys[:8]}")
    # 各会話の最終メッセージを当選キーワードで簡易判定
    win_kw = ["当選", "おめでとうございます", "発送", "抽選結果", "当たり", "受け取り"]
    hits = 0
    for cid, e in list(entries.items())[:30]:
        ae = e.get("initial_state", {}).get("aems", []) or e.get("aems", []) or []
        last_text = ""
        if ae:
            try:
                last = sorted(ae, key=lambda x: x.get("sort_index", 0))[-1]
                dd = json.loads(last.get("message_data", "{}"))
                last_text = dd.get("text", "") or dd.get("rendered_text", "") or ""
            except Exception:
                pass
        if any(k in last_text for k in win_kw):
            hits += 1
            print(f"  ★WIN? conv={cid[:12]}… text={last_text[:60]!r}")
    print(f"  win_keyword_hits={hits}")


def main() -> None:
    acct = sys.argv[1] if len(sys.argv) > 1 else "atushi16"
    auth, ct0 = load_session(acct)
    print(f"account={acct} session={'OK' if auth and ct0 else 'MISSING'}")
    if not auth or not ct0:
        return
    urls = {
        "init_all": "https://x.com/i/api/1.1/dm/init_all.json",
        "inbox_initial_state": "https://x.com/i/api/1.1/dm/inbox_initial_state.json?count=20",
    }
    for tag, u in urls.items():
        try:
            res = get(u, auth, ct0)
        except Exception as e:
            print(f"[{tag}] EXCEPTION {type(e).__name__}: {e}")
            continue
        summarize(tag, res)
        time.sleep(random.uniform(1.5, 3.0))


if __name__ == "__main__":
    main()
