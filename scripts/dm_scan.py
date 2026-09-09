"""
Kensho DM Winner Scanner (browserless) — 当選DMトラッカー v2.0

Playwright版dm_monitor.pyの代替。curl_cffi + X内部REST
(x.com/i/api/1.1/dm/inbox_initial_state.json) を直接叩き、
全垢のDM inboxを数秒で巡回して当選通知を検出・dm_wins.jsonへ
追記記録する。読み取り専用（送信・既読操作なし＝BOT検出リスク最小）。

使い方:
    python scripts/dm_scan.py            # 全垢スキャン→dm_wins.json更新→サマリー出力
    python scripts/dm_scan.py --backfill # 初回: 過去当選も全部記録に含める
    python scripts/dm_scan.py atushi16   # 指定垢のみ

設計上の注意:
- 出口IPはPROXY_MAP（socks5h://172.26.80.1:108x）に合わせて垢ごとに分離
  （atushi16のみ自宅IP例外でプロキシ経由。ルール: IP分離絶対条件）
- 垢間はランダム遅延(4-9秒)。1回のスキャンで書くのはGETのみ。
- 認証情報の値は出力しない。
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from curl_cffi import requests as crq

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WINS_PATH = DATA_DIR / "dm_wins.json"
STATE_PATH = DATA_DIR / "dm_scan_state.json"

X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_KEYWORD = "obfiowerehiring"
_pairs = json.load(open(ROOT / "kensho" / "application" / "transaction_pairs.json"))

# 当選判定キーワード（dm_monitor.py v1と同じ系譜＋精緻化）
_WIN_KEYWORDS = [
    "当選",
    "ご当選",
    "当選者",
    "おめでとうございます",
    "抽選結果",
    "発送",
    "景品",
    "賞品",
    "受け取り",
    "PayPay",
    "d払い",
    "au PAY",
    "振込",
    "あたり",
]
# 応募自動返信・スパム等を除外
_SKIP_KEYWORDS = [
    "RTで",
    "フォローで",
    "ご応募ありがとうございます",
    "応募ありがとうございます",
    "How’s it going",
    "part-time job",
    "Linkに",
    "リアクションしました",
    "タリタリ",
    "口座を開設",
    "ブログを経由",
    "副業",
    "friends",
]


def _gen_tid(method: str, path: str) -> str:
    p = random.choice(_pairs)
    key_bytes = list(base64.b64decode(p["verification"]))
    t = math.floor((time.time() * 1000 - 1682924400 * 1000) / 1000)
    tb = [(t >> (i * 8)) & 0xFF for i in range(4)]
    h = list(hashlib.sha256(f"{method}!{path}!{t}{_KEYWORD}{p['animationKey']}".encode()).digest())
    rn = random.randint(0, 255)
    b = bytearray([rn, *[x ^ rn for x in [*key_bytes, *tb, *h[:16], 3]]])
    return base64.b64encode(b).decode().rstrip("=")


def load_accounts() -> list[dict]:
    """config.yaml の有効垢 [key, display, session] を返す（コメントアウト=停止垢は除外）"""
    import yaml

    cfg = yaml.safe_load(open(ROOT / "config.yaml", encoding="utf-8"))
    out = []
    for a in cfg.get("accounts", []):
        out.append({
            "key": a["key"],
            "display": a.get("display", a["key"]),
            "session": a.get("session", "data/x_session.json"),
        })
    return out


PROXY_MAP = {
    "atushi16": "socks5h://172.26.80.1:1081",
    "kudou": "socks5h://172.26.80.1:1082",
    "chugakujuken": "socks5h://172.26.80.1:1083",
    "zin20120731": "socks5h://172.26.80.1:1084",
    "TankanNotes": "socks5h://172.26.80.1:1085",
    "inobase1-4": "socks5h://172.26.80.1:1089",
    "toushiwatch": "socks5h://172.26.80.1:1087",
}


def _proxy_for(key: str) -> str | None:
    if os.environ.get("USE_PROXY", "true").lower() != "true":
        return None
    return PROXY_MAP.get(key)


def load_session(rel: str) -> tuple[str, str] | None:
    f = ROOT / rel
    if not f.exists():
        return None
    try:
        d = json.load(open(f, encoding="utf-8"))
        cs = {c["name"]: c["value"] for c in d.get("cookies", [])}
        auth, ct0 = cs.get("auth_token", ""), cs.get("ct0", "")
        if auth and ct0:
            return auth, ct0
    except Exception:
        pass
    return None


def fetch_inbox(auth: str, ct0: str, proxy: str | None) -> dict:
    path = "/i/api/1.1/dm/inbox_initial_state.json"
    url = f"https://x.com{path}?count=20"
    headers = {
        "authorization": f"Bearer {X_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "ja",
        "cookie": f"auth_token={auth}; ct0={ct0}",
        "x-client-transaction-id": _gen_tid("GET", path),
        "referer": "https://x.com/messages",
    }
    kwargs: dict = {"headers": headers, "timeout": 45, "impersonate": "chrome"}
    if proxy:
        kwargs["proxy"] = proxy
    r = crq.get(url, **kwargs)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def _is_win(text: str) -> bool:
    if not text or len(text) < 5:
        return False
    for s in _SKIP_KEYWORDS:
        if s.lower() in text.lower():
            return False
    return any(k.lower() in text.lower() for k in _WIN_KEYWORDS)


def parse_inbox(resp: dict, my_user_id: str) -> list[dict]:
    """entriesからメッセージを抽出し、当選候補（自分以外の送信者）を返す"""
    iis = resp.get("inbox_initial_state", {})
    entries = iis.get("entries", [])
    users = iis.get("users", {})
    convs = iis.get("conversations", {})
    found = []
    seen_ids = set()
    for e in entries:
        m = e.get("message") if isinstance(e, dict) else None
        if not m:
            continue
        mid = str(m.get("id", ""))
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        md = m.get("message_data", {})
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except Exception:
                md = {"text": md}
        if not isinstance(md, dict):
            continue
        sender = str(md.get("sender_id", ""))
        text = md.get("text", "") or ""
        if not text or sender == my_user_id:
            continue
        if not _is_win(text):
            continue
        u = users.get(sender, {}) if isinstance(users, dict) else {}
        screen = u.get("screen_name", sender)
        cid = str(m.get("conversation_id", ""))
        c = convs.get(cid, {}) if isinstance(convs, dict) else {}
        participants = c.get("participants", [])
        if screen == sender and participants:
            for pid in participants:
                if str(pid) != my_user_id:
                    pu = users.get(str(pid), {})
                    if isinstance(pu, dict) and pu.get("screen_name"):
                        screen = pu["screen_name"]
                        break
        try:
            ts = int(m.get("time", "0")) / 1000
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            dt = ""
        found.append({
            "message_id": mid,
            "sender": f"@{screen}",
            "message_text": text[:600],
            "message_time": dt,
            "conversation_id": cid,
        })
    # conversation_id -> my_user_id 推定（54196675形式が自分のID接頭辞になることが多い）
    return found


def load_json(p: Path, default):
    if p.exists():
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    return default


def main() -> int:
    args = [a for a in sys.argv[1:]]
    backfill = "--backfill" in args
    only = [a for a in args if not a.startswith("--")]
    accounts = load_accounts()
    if only:
        accounts = [a for a in accounts if a["key"] in only]

    wins = load_json(WINS_PATH, {})
    state = load_json(STATE_PATH, {})
    new_all = 0
    report = []
    errors = []

    for i, acct in enumerate(accounts):
        key = acct["key"]
        sess = load_session(acct["session"])
        if not sess:
            errors.append(f"{key}: セッションなし/読込失敗")
            continue
        proxy = _proxy_for(key)
        try:
            resp = fetch_inbox(sess[0], sess[1], proxy)
        except Exception as e:
            errors.append(f"{key}: 取得失敗 {type(e).__name__} {str(e)[:60]}")
            continue
        # 自分のuser ID: conversation_id "MYID-PEERID" の最頻プレフィックスから推定
        iis = resp.get("inbox_initial_state", {})
        prefixes: dict[str, int] = {}
        for e in iis.get("entries", []):
            m = e.get("message", {}) if isinstance(e, dict) else {}
            cid = str(m.get("conversation_id", ""))
            if "-" in cid:
                pfx = cid.split("-", 1)[0]
                if pfx.isdigit():
                    prefixes[pfx] = prefixes.get(pfx, 0) + 1
        my_uid = max(prefixes, key=prefixes.get) if prefixes else ""
        found = parse_inbox(resp, my_uid)
        known_ids = {w.get("message_id") for w in wins.get(key, [])}
        added = []
        for f in found:
            if not backfill and f["message_id"] in known_ids:
                continue
            # 重複(同一sender+text)も回避
            if any(
                w.get("sender") == f["sender"] and w.get("message_text", "")[:80] == f["message_text"][:80]
                for w in wins.get(key, [])
            ):
                continue
            f["account_key"] = key
            f["detected_at"] = datetime.now().isoformat(timespec="seconds")
            added.append(f)
        if added:
            wins.setdefault(key, []).extend(added)
            new_all += len(added)
        report.append({
            "account": key,
            "status": "ok",
            "conv_messages_win": len(found),
            "new": len(added),
            "new_senders": [f"{f['sender']}({f['message_time'][:10]})" for f in added],
        })
        if i < len(accounts) - 1:
            time.sleep(random.uniform(4, 9))

    # 状態・記録保存
    tmp = WINS_PATH.with_suffix(".tmp")
    json.dump(wins, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, WINS_PATH)
    state["last_scan"] = datetime.now().isoformat(timespec="seconds")
    state["accounts_ok"] = [r["account"] for r in report]
    state["accounts_fail"] = errors
    json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    total_recorded = sum(len(v) for v in wins.values())
    out = {
        "scanned_at": state["last_scan"],
        "per_account": report,
        "errors": errors,
        "new_wins_this_run": new_all,
        "total_recorded": total_recorded,
        "total_by_account": {k: len(v) for k, v in wins.items()},
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not errors or report else 1


if __name__ == "__main__":
    sys.exit(main())
