#!/usr/bin/env python3
"""scripts/gumroad_x_xanalytics.py — v26-2 Gumroad agyhq X impression/anaytics collector.

kanban t_3556cdc6 の中間測定(day2)用。X投稿パイプライン(gumroad_x_post.py)が
data/gumroad_x_post_state.json に記録した各 tweet について、認証付き内部GraphQL
TweetResultByRestId で view_count(インプレッション) を取得し、data/gumroad_x_analytics.json
へ日次スナップショットを保存する。ブラウザレス・curl_cffi（skill: x-graphql-api-debugging）。

使用法:
  python scripts/gumroad_x_xanalytics.py [--out data/gumroad_x_analytics.json] [--no-cdn]

出力: data/gumroad_x_analytics.json — {tweet_id: {date, views, fav, conv, snapshots[]}}
即時コンソールには「tweet_date | views | fav | conv」のサマリを出す。

注意:
  - インプレッションは所有者(=atushi16)セッションでのみ閲覧可。public CDN や未認証では取れない。
  - 詳細(特典/metrics)はログに出さない。data/ への上書きのみ。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import random
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "gumroad_x_post_state.json"
DEFAULT_OUT = DATA_DIR / "gumroad_x_analytics.json"
SESSION_FILE = DATA_DIR / "x_session.json"

_X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_QUERY_ID_URL = "https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument/master/docs/json/API.json"
_KEYWORD = "obfiowerehiring"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_session() -> dict[str, str]:
    data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    pool = {c.get("name", ""): c.get("value", "") for c in data.get("cookies", [])}
    auth, ct0 = pool.get("auth_token", ""), pool.get("ct0", "")
    if not auth or not ct0:
        raise RuntimeError(f"sessionファイルに auth_token/ct0 が無い: {SESSION_FILE}")
    return {"auth_token": auth, "ct0": ct0}


def gen_tid(method: str, path: str) -> str:
    pairs = json.loads((REPO / "kensho" / "application" / "transaction_pairs.json").read_text())
    p = random.choice(pairs)
    key = list(base64.b64decode(p["verification"]))
    t = math.floor((time.time() * 1000 - 1682924400 * 1000) / 1000)
    tb = [(t >> (i * 8)) & 0xFF for i in range(4)]
    h = list(hashlib.sha256(f"{method}!{path}!{t}{_KEYWORD}{p['animationKey']}".encode()).digest())
    rn = random.randint(0, 255)
    b = bytearray([rn, *[x ^ rn for x in [*key, *tb, *h[:16], 3]]])
    return base64.b64encode(b).decode().rstrip("=")


def fetch_views(session: dict[str, str], tweet_id: str) -> dict:
    """TweetResultByRestId で view_count + 補助的にエンゲージメントを取得。"""
    from curl_cffi import requests as curl_requests

    api = curl_requests.get(_QUERY_ID_URL, timeout=15, impersonate="chrome").json()["graphql"]
    name = "TweetResultByRestId"
    qid = api[name]["queryId"]
    feats = api[name].get("features", {})
    path = f"/i/api/graphql/{qid}/{name}"
    headers = {
        "authorization": f"Bearer {_X_BEARER}",
        "x-csrf-token": session["ct0"],
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "cookie": f"auth_token={session['auth_token']}; ct0={session['ct0']}",
        "referer": "https://x.com/",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "x-client-transaction-id": gen_tid("POST", path),
    }
    payload = {
        "variables": {"tweetId": tweet_id, "withCommunity": False, "includePromotedContent": False, "withVoice": False},
        "features": feats,
    }
    time.sleep(random.uniform(0.8, 2.0))
    r = curl_requests.post(f"https://x.com{path}", headers=headers, json=payload, impersonate="chrome", timeout=25)
    body = r.json()
    res = (body.get("data", {}).get("tweetResult", {}) or {}).get("result", {})
    if res.get("__typename") != "Tweet":
        raise RuntimeError(f"HTTP {r.status_code} / result 不在: {json.dumps(body)[:200]}")
    views = res.get("views", {}) or {}
    try:
        count = int(views.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return {"views": count}


def cdn_engagement(tweet_id: str) -> dict:
    """補助: 公開CDN syndication から favorite/conversation 数を取得（認証不要・低コスト）。"""
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=ja&token=a"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        conv = data.get("conversation_count", 0)
        # リツイート等は syndication に無い場合がある。favorite のみ補助。
        fav = int(data.get("favorite_count") or 0)
        return {"fav": fav, "conv": int(conv or 0)}
    except Exception:
        return {"fav": None, "conv": None}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def load_analytics(out: Path) -> dict:
    if out.exists():
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad agyhq X インプレッション収集")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-cdn", action="store_true", help="CDN補助取得を省略")
    args = ap.parse_args()
    out = Path(args.out)

    state = load_state()
    posted = state.get("posted", {})
    if not posted:
        print("gumroad_x_post_state.json に投稿実績なし")
        return

    session = load_session()
    analytics = load_analytics(out)
    changed = False
    for date, rec in sorted(posted.items()):
        tid = (rec or {}).get("tweet_id")
        if not tid:
            continue
        entry = analytics.setdefault(tid, {"date": date, "snapshots": []})
        snap = {"viewed_at": _now()}
        try:
            m = fetch_views(session, tid)
            snap["views"] = m["views"]
        except Exception as e:
            snap["views"] = None
            snap["error"] = str(e)[:120]
        if not args.no_cdn:
            c = cdn_engagement(tid)
            snap.update(c)
        entry["snapshots"].append(snap)
        entry["views_latest"] = snap.get("views")
        changed = True
        row = f"{date} | views={snap.get('views')} | fav={snap.get('fav')!r} | conv={snap.get('conv')!r}"
        if snap.get("error"):
            row += f" | ERR {snap['error']}"
        print(row)

    if changed:
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(analytics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"保存: {out}")
    else:
        print("変更なし")


if __name__ == "__main__":
    sys.exit(main())
