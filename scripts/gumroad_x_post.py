#!/usr/bin/env python3
"""
scripts/gumroad_x_post.py — v21-C Gumroad agyhq X 自動投稿（日次1ツイート・9/5〜9/11）

atushi16 のXセッション (config.yaml accounts[].session) から、Gumroad商品 agyhq
(https://atushi5.gumroad.com/l/agyhq, $29.99 "Japanese Anime Figure & Collectibles
Market Price Dataset (Weekly CSV)") を宣伝するツイートを、期間中 1日1本だけ自然に投稿する。

設計:
  - 対象ウィンドウ: 2026-09-05 .. 2026-09-11（7日）。外れた日は何もしない（--force 除く）。
  - 日次 dedup: data/gumroad_x_post_state.json に投稿済み日付と tweet_id を記録し、
    同日の再投稿を防ぐ（cron再実行でも安全・冪等）。
  - 7日分の異なる文言をローテーション（同一文言連投によるBOT検知を回避）。
  - 投稿経路: X 内部 GraphQL CreateTweet（curl_cffi + transaction_pairs、ブラウザレス）。
    Browserless GraphQL クライアント参照（skill: x-graphql-api-debugging）。

使い方:
  python scripts/gumroad_x_post.py            # 投稿（ウィンドウ内+未投稿日のみ）
  python scripts/gumroad_x_post.py --dry-run  # 投稿せず実行内容を表示
  python scripts/gumroad_x_post.py --force    # ウィンドウ外でも強制（検証用）
  python scripts/gumroad_x_post.py --state PATH --repo ROOT   # 明示指定

退出コード: 0=成功/スキップ(正常)  2=ウィンドウ外(--forceなし)  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "gumroad_x_post_state.json"

# ── 対象ウィンドウ（9/5〜9/11）──
WINDOW_START = date(2026, 9, 5)
WINDOW_END = date(2026, 9, 11)

PRODUCT_URL = "https://atushi5.gumroad.com/l/agyhq"
ACCOUNT_KEY = "atushi16"

_X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_QUERY_ID_URL = "https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument/master/docs/json/API.json"
_KEYWORD = "obfiowerehiring"

# 7日分ローテーション（1日1本・自然に、同一文言連投回避）
TWEETS: list[str] = [
    "New weekly dataset: Japanese anime figures & collectibles market prices, "
    "delivered as CSV with price history. Useful for resale research, Power BI, "
    "and AI/ML price modeling. \u2192 " + PRODUCT_URL + " #animefigures #datasets",
    "Tracking hobby & collectibles prices in Japan got easier. Weekly-updated CSV "
    "price dataset now available \u2014 covers anime figures, kits, and more. "
    "See sample: " + PRODUCT_URL + " #collectibles #pricedata",
    "I compile Japanese market price data for anime figures & collectibles into a "
    "weekly CSV. Buyers, sellers and researchers use it for pricing benchmarks. "
    "More here: " + PRODUCT_URL + " #figures #marketdata",
    "Weekly Japanese collectibles price dataset update. Historical CSV tracks "
    "market trends for figure resale & valuation. Quick preview at " + PRODUCT_URL + " #priceguide #animecollectibles",
    "Anime figure & hobby market price reference, refreshed every week as a CSV. "
    "Built for collectors, resellers and analysts. Preview: " + PRODUCT_URL + " #anime #trading",
    "If you study the Japanese anime figure market, this weekly CSV gives you "
    "consistent price data to work with. New dataset posted: " + PRODUCT_URL + " #dataanalytics #figures",
    "Weekly price dataset for Japanese anime figures & collectibles \u2014 updated "
    "again this week. See what's inside: " + PRODUCT_URL + " #revolvingfigures #hobby",
]

# 投稿本文の長さを検出（予防）
_WARN_BLOCKED = "Please check your spam setting"


def _load_config_session() -> Path:
    """config.yaml から atushi16 の session パスを解決する。"""
    try:
        import yaml  # type: ignore
    except ImportError:
        return DATA_DIR / "x_session.json"
    cfg = yaml.safe_load((REPO / "config.yaml").read_text(encoding="utf-8"))
    for acct in cfg.get("accounts", []):
        if acct.get("key") == ACCOUNT_KEY and acct.get("session"):
            return REPO / acct["session"]
    return DATA_DIR / "x_session.json"


def _load_session_cookies(session_path: Path) -> dict[str, str]:
    data = json.loads(session_path.read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    pool: dict[str, str] = {}
    for c in cookies:
        if isinstance(c, dict) and c.get("name"):
            pool[c["name"]] = c.get("value", "")
    auth, ct0 = pool.get("auth_token", ""), pool.get("ct0", "")
    if not auth or not ct0:
        raise RuntimeError(f"sessionファイルに auth_token/ct0 がない: {session_path}")
    return {"auth_token": auth, "ct0": ct0}


def _gen_transaction_id(pairs: list[dict], method: str, path: str, now_ms: int) -> str:
    """X-Client-Transaction-Id（Kensho方式・事前計算ペア署名）。"""
    pair = random.choice(pairs)
    key_bytes = list(base64.b64decode(pair["verification"]))
    t = math.floor((now_ms - 1682924400 * 1000) / 1000)
    tb = [(t >> (i * 8)) & 0xFF for i in range(4)]
    h = list(hashlib.sha256(f"{method}!{path}!{t}{_KEYWORD}{pair['animationKey']}".encode()).digest())
    rn = random.randint(0, 255)
    b = bytearray([rn, *[x ^ rn for x in [*key_bytes, *tb, *h[:16], 3]]])
    return base64.b64encode(b).decode().rstrip("=")


def _load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_tweet(today: date, state: dict, dry_run: bool, log) -> tuple[str | None, str]:
    """今日のツイート文言を選ぶ。既に投稿済みなら (None, reason)。"""
    day_number = (today - WINDOW_START).days  # 0-indexed
    day_index = day_number % len(TWEETS) if day_number >= 0 else 0
    text = TWEETS[day_index]
    posted_dates = state.get("posted", {})
    if today.isoformat() in posted_dates:
        prev = posted_dates[today.isoformat()]
        return None, f"既に投稿済み (tweet_id={prev.get('tweet_id')})"
    return text, ""


def create_tweet(session: dict[str, str], pairs: list[dict], text: str, log) -> str:
    """CreateTweet GraphQL を実行し、tweet_id を返す。"""
    from curl_cffi import requests as curl_requests

    api = curl_requests.get(_QUERY_ID_URL, timeout=15, impersonate="chrome")
    qid = api.json()["graphql"]["CreateTweet"]["queryId"]
    features = api.json()["graphql"]["CreateTweet"].get("features", {})
    path = f"/i/api/graphql/{qid}/CreateTweet"

    auth = session["auth_token"]
    ct0 = session["ct0"]
    now_ms = int(time.time() * 1000)
    headers = {
        "authorization": f"Bearer {_X_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "cookie": f"auth_token={auth}; ct0={ct0}",
        "referer": "https://x.com/",
        "content-type": "application/json",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"),
        "x-client-transaction-id": _gen_transaction_id(pairs, "POST", path, now_ms),
    }
    payload = {
        "variables": {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
            "disallowed_reply_options": None,
        },
        "features": features,
    }
    # BOT対策: 自然なランダム遅延
    time.sleep(random.uniform(1.5, 4.0))
    r = curl_requests.post(f"https://x.com{path}", headers=headers, json=payload, impersonate="chrome", timeout=25)
    try:
        body = r.json()
    except Exception:
        raise RuntimeError(f"CreateTweet 非JSONレスポンス: HTTP {r.status_code} body={r.text[:300]!r}")

    if r.status_code != 200:
        raise RuntimeError(f"CreateTweet HTTP {r.status_code}: {json.dumps(body)[:300]}")
    if body.get("errors"):
        errs = json.dumps(body["errors"])
        raise RuntimeError(f"CreateTweet errors: {errs[:300]}")

    reste = body.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
    tid = reste.get("rest_id") or reste.get("id_str")
    if not tid:
        raise RuntimeError(f"CreateTweet 200 だが tweet_id が無い: {json.dumps(body)[:300]}")
    if _WARN_BLOCKED in json.dumps(body):
        raise RuntimeError("スパム警告（Please check your spam setting）— 投稿を中止")
    log(f"[OK] 投稿成功 tweet_id={tid}")
    return str(tid)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad agyhq X 日次自動投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="ウィンドウ外でも投稿（検証用）")
    ap.add_argument("--state", default=str(STATE_FILE), help="状態ファイルパス")
    ap.add_argument("--repo", default=str(REPO), help="kensho リポジトリルート")
    args = ap.parse_args()

    repo = Path(args.repo)
    state_file = Path(args.state)
    today = (
        date.today()
        if not os.environ.get("GUMROAD_X_POST_DATE")
        else date.fromisoformat(os.environ["GUMROAD_X_POST_DATE"])
    )

    def log(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        log_dir = repo / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "gumroad_x_post.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ウィンドウガード
    if not (WINDOW_START <= today <= WINDOW_END) and not args.force:
        log(f"対象ウィンドウ外 ({today})。9/5〜9/11 の間だけ動作します。--force で強制。")
        sys.exit(2)

    state = _load_state(state_file)
    text, reason = pick_tweet(today, state, args.dry_run, log)
    if text is None:
        log(f"スキップ: {reason}")
        return

    log(f"対象: {ACCOUNT_KEY} / {PRODUCT_URL} / 日#{(today - WINDOW_START).days + 1}/7")

    # 文言ログ（BOT検知・運用監視のため内容はログに記録）
    log(f"ツイート内容: {text!r}")
    if len(text) > 280:
        log(f"WARN: 文字数 {len(text)}/280 超過")

    session_path = _load_config_session()
    if args.dry_run:
        log("DRY-RUN: 投稿は実行していません。")
        return

    session = _load_session_cookies(session_path)
    pairs_file = repo / "kensho" / "application" / "transaction_pairs.json"
    pairs = json.loads(pairs_file.read_text(encoding="utf-8"))
    tid = create_tweet(session, pairs, text, log)

    posted = state.setdefault("posted", {})
    posted[today.isoformat()] = {"tweet_id": tid, "text": text, "posted_at": datetime.now().isoformat()}
    _save_state(state_file, state)
    log(f"状態記録: {state_file} (tweet_id={tid})")


if __name__ == "__main__":
    main()
