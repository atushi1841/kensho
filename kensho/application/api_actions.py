"""
X Internal API Actions — page.evaluate() → fetch() でX内部APIを直接呼ぶ
ページ遷移不要、Bot検出バイパス。
"""

from __future__ import annotations

import json
import random
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
import hashlib
import base64
import math
import time as _time

# Xの既知のBearer Token（X Webアプリが使っているものと同一）
_X_BEARER_TOKEN: str = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# ── QueryId 自動解決 ──
# 参考: https://github.com/fa0311/TwitterInternalAPIDocument
_QUERY_ID_RESOLVE_URL: str = (
    "https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument"
    "/master/docs/json/API.json"
)
_QUERY_ID_CACHE: dict[str, str] = {}
_KNOWN_QUERY_IDS: dict[str, list[str]] = {
    "CreateRetweet": [
        "mbRO74GrOvSfRcJnlMapnQ",  # ★ 最新（2026-07-02 GitHub確認）★
        "ojPdsZsimiJrUGLR1sjUtA",  # 旧
    ],
}

_X_CLIENT_KEYWORD: str = "obfiowerehiring"
# Precomputed transaction ID pairs (animationKey + verification) from fa0311
_TRANSACTION_PAIRS: list[dict[str, str]] = []
try:
    import json as _json
    import pathlib

    _pairs_path = pathlib.Path(__file__).parent / "transaction_pairs.json"
    if _pairs_path.exists():
        _TRANSACTION_PAIRS = _json.loads(_pairs_path.read_text())
except Exception:
    pass


def _resolve_query_id(name: str) -> str | None:
    """GitHub上のAPI.jsonからqueryIdを取得。キャッシュ済みならキャッシュ。"""
    if name in _QUERY_ID_CACHE:
        return _QUERY_ID_CACHE[name]
    try:
        req = urllib.request.Request(
            _QUERY_ID_RESOLVE_URL,
            headers={"User-Agent": "Kensho/1.0", "Accept": "application/json"},
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        qid = data.get("graphql", {}).get(name, {}).get("queryId")
        if qid:
            _QUERY_ID_CACHE[name] = qid
            return qid
    except Exception:
        pass
    return None


def _get_query_id(name: str) -> str:
    """queryId取得。優先順: キャッシュ > GitHub > 既知の最新。"""
    qid = _resolve_query_id(name)
    if qid:
        return qid
    known = _KNOWN_QUERY_IDS.get(name, [])
    return known[0] if known else ""


def _try_fallback_query_id(name: str, failed_qid: str) -> str | None:
    """失敗したqueryIdの次の既知IDを試す。"""
    known = _KNOWN_QUERY_IDS.get(name, [])
    try:
        idx = known.index(failed_qid)
        if idx + 1 < len(known):
            return known[idx + 1]
    except ValueError:
        pass
    return None


def _generate_transaction_id(method: str, path: str) -> str | None:
    """Generate X-Client-Transaction-Id for GraphQL mutations using precomputed pairs."""
    if not _TRANSACTION_PAIRS:
        return None
    pair = random.choice(_TRANSACTION_PAIRS)
    key_bytes = list(base64.b64decode(pair["verification"]))
    animation_key = pair["animationKey"]
    time_now = math.floor((_time.time() * 1000 - 1682924400 * 1000) / 1000)
    time_now_bytes = [(time_now >> (i * 8)) & 0xFF for i in range(4)]
    hash_val = hashlib.sha256(
        f"{method}!{path}!{time_now}{_X_CLIENT_KEYWORD}{animation_key}".encode()
    ).digest()
    hash_bytes = list(hash_val)
    random_num = random.randint(0, 255)
    bytes_arr = [*key_bytes, *time_now_bytes, *hash_bytes[:16], 3]
    out = bytearray([random_num, *[item ^ random_num for item in bytes_arr]])
    return base64.b64encode(out).decode().rstrip("=")


def _make_js_fetch(
    method: str,
    url: str,
    body: str | None = None,
    delay_before: float = 0.0,
    delay_after: float = 0.0,
    content_type: str = "application/x-www-form-urlencoded",
    transaction_id: str | None = None,
) -> str:
    """page.evaluate()に渡すJavaScript文字列を生成。

    人間らしい遅延（delay_before/after）を先頭/末尾に埋め込み、
    レスポンスのstatus + body をJSONで返す。
    """
    if content_type == "application/json":
        # bodyはjson.dumps()済みのJSON文字列。JSで文字列として扱うためにJSON.stringifyでラップ。
        # 例: body='{"variables":...}' → JS: JSON.stringify({"variables":...}) → '{"variables":...}' (string)
        body_line: str = f"JSON.stringify({body})" if body else "null"
    else:
        body_line: str = json.dumps(body) if body else "null"
    tid_line = ""
    if transaction_id:
        tid_line = f"                'x-client-transaction-id': '{transaction_id}',\n"
    return f"""(() => {{
    const delay = ms => new Promise(r => setTimeout(r, ms));
    // ★ BOT対策: 呼び出し前に人間らしい遅延
    const t0 = Date.now();
    return delay({delay_before * 1000:.0f}).then(() => {{
        const ct0 = document.cookie.match(/(?:^|;\\\\s*)ct0=([^;]*)/);
        const csrf = ct0 ? ct0[1].trim() : '';
        return fetch('{url}', {{
            method: '{method}',
            headers: {{
                'authorization': 'Bearer {_X_BEARER_TOKEN}',
                'x-csrf-token': csrf,
                'content-type': '{content_type}',
                'x-twitter-auth-type': 'OAuth2Session',
                'x-client-uuid': crypto.randomUUID(),
                'x-twitter-active-user': 'yes',
                'referer': 'https://x.com/',
{tid_line}            }},
            credentials: 'include',
            body: {body_line},
        }})
        .then(async r => {{
            const text = await r.text();
            // ★ BOT対策: 呼び出し後にも遅延
            const elapsed = Date.now() - t0;
            const remaining = {delay_after * 1000:.0f} - elapsed;
            if (remaining > 0) {{
                await delay(remaining);
            }}
            return JSON.stringify({{status: r.status, body: text.substring(0, 5000)}});
        }})
        .catch(err => {{
            const elapsed2 = Date.now() - t0;
            const remaining2 = {delay_after * 1000:.0f} - elapsed2;
            if (remaining2 > 0) {{
                return delay(remaining2).then(() => JSON.stringify({{status: 0, body: err.message}}));
            }}
            return JSON.stringify({{status: 0, body: err.message}});
        }});
    }});
}})()"""


def _run_js(page: Any, js: str) -> dict[str, Any]:
    """page.evaluate()を実行し、結果をパース。エラー時は空dict。"""
    try:
        raw: str = page.evaluate(js)
        return json.loads(raw)
    except Exception:
        return {"status": 0, "body": "evaluate_failed"}


def verify_x_api_works(page: Any) -> bool:
    """X内部APIが使えるか確認。トップページからの軽いGETで疎通確認する。"""
    js: str = _make_js_fetch(
        "GET",
        "https://x.com/i/api/1.1/statuses/show.json?id=0",
        delay_before=0.5,
        delay_after=0.0,
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    # 401=認証OKだがID=0でエラー（正常動作）、403=CSRF問題
    if status == 401 or status == 404:
        return True
    if status == 403:
        # CSRFトークン不足の可能性
        return False
    if status == 200:
        return True
    return False


def api_get_tweet_text(page: Any, tweet_id: str) -> str:
    """ツイート本文をX内部API経由で取得（NGワードチェック用）。"""
    js: str = _make_js_fetch(
        "GET",
        f"https://x.com/i/api/1.1/statuses/show.json?id={tweet_id}&tweet_mode=extended",
        delay_before=0.3,
        delay_after=0.0,
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    body: str = result.get("body", "")
    if status != 200 or not body:
        return ""
    try:
        data: dict[str, Any] = json.loads(body)
        # extended_tweet または full_text を取得
        text: str = (
            data.get("extended_tweet", {}).get("full_text", "")
            or data.get("full_text", "")
            or data.get("text", "")
        )
        return text
    except (json.JSONDecodeError, TypeError):
        return ""


def api_like(
    page: Any,
    tweet_id: str,
    account_key: str,
    out: Callable[[str], None],
) -> bool:
    """X内部API経由で「いいね」を実行。"""
    from kensho.application.rate_limiter import increment_daily_count

    # BOT対策: アクション前に人間らしい小遅延
    pre_delay: float = random.uniform(0.5, 2.0)
    js: str = _make_js_fetch(
        "POST",
        "https://x.com/i/api/1.1/favorites/create.json",
        body=f"id={tweet_id}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    if status == 200:
        out("  [OK] いいね（API）")
        increment_daily_count(account_key, "like")
        return True
    elif status == 401:
        out("  [WARN] いいねAPI: 認証エラー（セッション切れかも）")
        return False
    else:
        out(f"  [WARN] いいねAPI: HTTP {status}")
        return False


def api_rt(
    page: Any,
    tweet_id: str,
    account_key: str,
    out: Callable[[str], None],
) -> bool:
    """X内部API経由でリポスト（RT）を実行。"""
    from kensho.application.rate_limiter import increment_daily_count

    pre_delay: float = random.uniform(0.5, 2.0)

    # ★ 複数のqueryIdを順番に試す ★
    known_ids: list[str] = _KNOWN_QUERY_IDS.get("CreateRetweet", [])
    if not known_ids:
        out("  [WARN] RT API: queryId一覧が空")
        return False

    body_preview: str = ""
    for attempt_idx, query_id in enumerate(known_ids):
        js_body: str = json.dumps(
            {
                "variables": {"tweet_id": tweet_id, "dark_request": False},
                "queryId": query_id,
                "features": {},
            }
        )
        url: str = f"https://x.com/i/api/graphql/{query_id}/CreateRetweet"
        tid = _generate_transaction_id(
            "POST", f"/i/api/graphql/{query_id}/CreateRetweet"
        )
        js: str = _make_js_fetch(
            "POST",
            url,
            body=js_body,
            delay_before=pre_delay if attempt_idx == 0 else random.uniform(0.3, 0.8),
            delay_after=random.uniform(0.3, 0.8),
            content_type="application/json",
            transaction_id=tid,
        )
        result: dict[str, Any] = _run_js(page, js)
        status: int = result.get("status", 0)

        if status == 200:
            out("  [OK] RT（API）")
            increment_daily_count(account_key, "rt")
            return True
        elif status == 403:
            out("  [i] RT API: 403（既にリポスト済みかも）")
            increment_daily_count(account_key, "rt")
            return True
        elif status in (429, 420):
            out("  [WARN] RT API: レート制限（HTTP %d）、スキップ" % status)
            return False

        body_preview = result.get("body", "")[:200]
        if attempt_idx < len(known_ids) - 1:
            out(
                f"  [i] RT GraphQL (queryId={query_id[:8]}…): HTTP {status} [{body_preview[:80]}] → 次を試す"
            )

    out(
        f"  [i] RT API: 全queryId失敗 → REST フォールバック (last body: {body_preview[:150]})"
    )

    # REST fallback
    rest_url: str = f"https://x.com/i/api/1.1/statuses/retweet/{tweet_id}.json"
    rest_js: str = _make_js_fetch(
        "POST",
        rest_url,
        body=f"id={tweet_id}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
        content_type="application/x-www-form-urlencoded",
    )
    rest_result: dict[str, Any] = _run_js(page, rest_js)
    rest_status: int = rest_result.get("status", 0)

    if rest_status == 200:
        out("  [OK] RT（REST API）")
        increment_daily_count(account_key, "rt")
        return True
    elif rest_status == 401:
        out("  [WARN] RT REST API: 認証エラー")
        return False
    elif rest_status == 403:
        out("  [i] RT REST API: 403（既にリポスト済みかも）")
        increment_daily_count(account_key, "rt")  # treat as success
        return True
    else:
        out(f"  [WARN] RT REST API: HTTP {rest_status}")
        return False


def api_follow_by_screen_name(
    page: Any,
    screen_name: str,
    account_key: str,
    out: Callable[[str], None],
) -> bool:
    """X内部API経由でscreen_name指定でフォロー。"""
    from kensho.application.rate_limiter import increment_daily_count

    # フォロー実行
    pre_delay: float = random.uniform(0.5, 1.5)
    js: str = _make_js_fetch(
        "POST",
        "https://x.com/i/api/1.1/friendships/create.json",
        body=f"screen_name={screen_name}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    if status == 200:
        out("  [OK] フォロー（API）")
        increment_daily_count(account_key, "follow")
        return True
    elif status == 401:
        out("  [WARN] フォローAPI: 認証エラー")
        return False
    elif status == 403:
        # フォロー済み等
        increment_daily_count(account_key, "follow")
        out("  [i] フォローAPI: 403（既にフォロー済みかも）")
        return True
    else:
        out(f"  [WARN] フォローAPI: HTTP {status}")
        return False


def extract_tweet_id_and_screen_name(x_url: str) -> tuple[str | None, str | None]:
    """XツイートURLからtweet_idとscreen_nameを抽出。

    例: https://x.com/username/status/123456 → ("123456", "username")
    """
    clean: str = x_url.split("#")[0].split("?")[0]
    parts: list[str] = clean.rstrip("/").split("/")
    # .../screen_name/status/tweet_id
    try:
        idx: int = parts.index("status")
        if idx >= 1 and idx + 1 < len(parts):
            tweet_id: str = parts[idx + 1]
            screen_name: str = parts[idx - 1].lstrip("@")
            return tweet_id, screen_name
    except ValueError:
        pass
    return None, None
