"""
X Internal API Actions — page.evaluate() → fetch() でX内部APIを直接呼ぶ
ページ遷移不要、Bot検出バイパス。
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import random
import ssl
import time as _time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from kensho.application.audit_ledger import audit_ledger
from kensho.application.policy_engine import PolicyDecision, policy_engine

# ── Config cache (30秒) ──
_cfg_cache: dict[str, Any] = {}
_cfg_loaded_at: float = 0.0


def _ensure_cfg() -> dict[str, Any]:
    global _cfg_cache, _cfg_loaded_at
    now = _time.time()
    if now - _cfg_loaded_at > 30:
        from kensho.core.config import load as _load_config

        _cfg_cache = _load_config()
        _cfg_loaded_at = now
    return _cfg_cache


# Xの既知のBearer Token（X Webアプリが使っているものと同一）
_X_BEARER_TOKEN: str = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# ── QueryId 自動解決 ──
# 参考: https://github.com/fa0311/TwitterInternalAPIDocument
_QUERY_ID_RESOLVE_URL: str = (
    "https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument/master/docs/json/API.json"
)
_QUERY_ID_CACHE: dict[str, str] = {}
_KNOWN_QUERY_IDS: dict[str, list[str]] = {
    "CreateRetweet": [
        "mbRO74GrOvSfRcJnlMapnQ",  # ★ 最新（2026-07-02 GitHub確認）★
        "ojPdsZsimiJrUGLR1sjUtA",  # 旧
    ],
    "FavoriteTweet": [
        "lI07N6Otwv1PhnEgXILM7A",  # ★ 最新（2026-07-08 fa0311/API.json確認）★
        "lI07N61twFgted2EgXILM7A",  # 旧
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
    hash_val = hashlib.sha256(f"{method}!{path}!{time_now}{_X_CLIENT_KEYWORD}{animation_key}".encode()).digest()
    hash_bytes = list(hash_val)
    random_num = random.randint(0, 255)
    bytes_arr = [*key_bytes, *time_now_bytes, *hash_bytes[:16], 3]
    out = bytearray([random_num, *[item ^ random_num for item in bytes_arr]])
    return base64.b64encode(out).decode().rstrip("=")


def _is_api_error(body_str: str) -> bool:
    try:
        data = json.loads(body_str)
        if isinstance(data.get("errors"), list) and len(data["errors"]) > 0:
            return True
    except (json.JSONDecodeError, TypeError):
        pass
    return False


# ── Error 226（automated request block）検知＋自動一時停止（提案76・2026-08-29）──
# Xは速度検知（2〜3分で15〜20アクション）でError 226を返す。
# 再試行するたびにブロック延長されるため、検出時は即セッション停止＋15〜60分待機。
_AUTOMATION_BLOCK_FILE: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "automation_block.json")


def _is_automation_block(body_str: str) -> bool:
    """Error 226（automated request block）判定。"""
    if not body_str:
        return False
    if '"code":226' in body_str or 'code":226' in body_str:
        return True
    low = body_str.lower()
    return any(
        s in low
        for s in (
            "looks like it might be automated",
            "automated request",
            "this request looks automated",
        )
    )


def _is_temp_lock_326(body_str: str) -> bool:
    """code 326（一時ロック・temporarily locked）判定。フォローAPIでのみ使用。"""
    if not body_str:
        return False
    if '"code":326' in body_str or 'code":326' in body_str:
        return True
    return False


def _load_automation_blocks() -> dict[str, float]:
    try:
        with open(_AUTOMATION_BLOCK_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_automation_blocks(blocks: dict[str, float]) -> None:
    try:
        os.makedirs(os.path.dirname(_AUTOMATION_BLOCK_FILE), exist_ok=True)
        tmp = _AUTOMATION_BLOCK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False)
        os.replace(tmp, _AUTOMATION_BLOCK_FILE)
    except OSError:
        pass  # 記録失敗しても応募継続


def mark_automation_block(account_key: str, out: Callable[[str], None] | None = None) -> None:
    """Error 226（automated request block）検出 → 15〜60分ブロック（自動再開）。"""
    _now = _time.time()
    until = _now + random.uniform(15 * 60, 60 * 60)
    blocks = _load_automation_blocks()
    blocks[account_key] = until
    _save_automation_blocks(blocks)
    if out:
        out(
            f"  [AUTOBLOCK] {account_key}: Error 226（automated block）検出 → "
            f"約{int((until - _now) // 60)}分後に自動再開"
        )


def is_automation_blocked(account_key: str) -> bool:
    """ブロック中ならTrue（期限切れは自動クリア＝自動再開）。"""
    blocks = _load_automation_blocks()
    until = blocks.get(account_key)
    if until is None:
        return False
    if _time.time() >= until:
        blocks.pop(account_key, None)
        _save_automation_blocks(blocks)
        return False
    return True


def get_automation_block_minutes(account_key: str) -> int:
    """ブロック残り分数（0=非ブロック）。"""
    blocks = _load_automation_blocks()
    until = blocks.get(account_key)
    if until is None:
        return 0
    rem = int((until - _time.time()) // 60)
    return max(1, rem) if rem > 0 else 0


def _make_js_fetch(
    method: str,
    url: str,
    body: str | None = None,
    delay_before: float = 0.0,
    delay_after: float = 0.0,
    content_type: str = "application/x-www-form-urlencoded",
    transaction_id: str | None = None,
    csrf_token: str | None = None,
) -> str:
    """page.evaluate()に渡すJavaScript文字列を生成。

    人間らしい遅延（delay_before/after）を先頭/末尾に埋め込み、
    レスポンスのstatus + body をJSONで返す。

    csrf_tokenが指定された場合はそれをx-csrf-tokenに使う。
    指定されていない場合は document.cookie からct0を抽出する。
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
    # csrf_token 行を生成
    if csrf_token:
        csrf_line = f"        const csrf = {json.dumps(csrf_token)};\n"
    else:
        csrf_line = (
            "        const ct0 = document.cookie.match(/(?:^|;\\\\s*)ct0=([^;]*)/);\n"
            "        const csrf = ct0 ? ct0[1].trim() : '';\n"
        )
    return f"""(() => {{
    const delay = ms => new Promise(r => setTimeout(r, ms));
    // ★ BOT対策: 呼び出し前に人間らしい遅延
    const t0 = Date.now();
    return delay({delay_before * 1000:.0f}).then(() => {{
{csrf_line}        return fetch('{url}', {{
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


def _get_csrf_token(page: Any) -> str:
    """HttpOnlyなct0をPlaywrightのcontext.cookies()から取得。空文字の場合は取得失敗。"""
    try:
        cookies = page.context.cookies()
        for c in cookies:
            if c.get("name") == "ct0":
                return c.get("value", "")
    except Exception:
        pass
    return ""


def verify_x_api_works(page: Any) -> bool:
    """X内部APIが使えるか確認。トップページからの軽いGETで疎通確認する。"""
    token: str = _get_csrf_token(page)
    js: str = _make_js_fetch(
        "GET",
        "https://x.com/i/api/1.1/statuses/show.json?id=0",
        delay_before=0.5,
        delay_after=0.0,
        csrf_token=token if token else None,
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


def _cdn_get_tweet_text(tweet_id: str, log_fn: Callable[[str], None] | None = None) -> str:
    """認証不要の公開CDNからツイート本文を取得（REST v1.1死のフォールバック）。

    cdn.syndication.twimg.com はX公式の公開エンドポイント。認証・CSRF不要。
    削除済みツイートは404。レート制限に注意（大量アクセスは控える）。
    """
    url: str = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=ja&token=a"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw: str = resp.read().decode("utf-8", errors="replace")
        if resp.status != 200:
            if log_fn:
                log_fn(f"  [CDN] status={resp.status}")
            return ""
        data: dict[str, Any] = json.loads(raw)
        text: str = data.get("text", "") or ""
        if log_fn:
            log_fn(f"  [CDN] ✓ 本文取得（{len(text)}文字）")
        return text
    except Exception as e:
        if log_fn:
            log_fn(f"  [CDN] エラー: {e}")
        return ""


def api_get_tweet_text(page: Any, tweet_id: str, log_fn: Callable[[str], None] | None = None) -> str:
    """ツイート本文を取得（NGワードチェック用）。REST v1.1 → CDNフォールバック。"""
    # 1) REST v1.1 (statuses/show.json) — 2026-08現在 403/404で死んでいることが多い
    js: str = _make_js_fetch(
        "GET",
        f"https://x.com/i/api/1.1/statuses/show.json?id={tweet_id}&tweet_mode=extended",
        delay_before=0.3,
        delay_after=0.0,
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    body: str = result.get("body", "")
    if status == 200 and body:
        try:
            data: dict[str, Any] = json.loads(body)
            text: str = (
                data.get("extended_tweet", {}).get("full_text", "") or data.get("full_text", "") or data.get("text", "")
            )
            if text:
                return text
        except (json.JSONDecodeError, TypeError):
            pass
    if log_fn:
        log_fn(f"  [API] REST status={status}, body_len={len(body)} → CDNフォールバック")

    # 2) CDNフォールバック（認証不要・公開エンドポイント）
    return _cdn_get_tweet_text(tweet_id, log_fn)


def api_like(
    page: Any,
    tweet_id: str,
    account_key: str,
    out: Callable[[str], None],
) -> bool:
    """X内部API経由で「いいね」を実行（GraphQL → REST フォールバック）。"""
    from kensho.application.rate_limiter import increment_daily_count

    _t0 = _time.time()
    _cfg_here = _ensure_cfg()
    _decision, _reason = policy_engine.evaluate(account_key, "like", _cfg_here)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] いいね拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", tweet_id, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return False

    pre_delay: float = random.uniform(0.5, 2.0)
    token: str = _get_csrf_token(page)

    # ★ GraphQL FavoriteTweet ★
    # 自動 queryId 解決を優先
    qid = _get_query_id("FavoriteTweet")
    known_ids: list[str] = _KNOWN_QUERY_IDS.get("FavoriteTweet", [])
    if qid and qid not in known_ids:
        known_ids.insert(0, qid)
    if known_ids:
        _auth_error: bool = False
        body_preview: str = ""
        for attempt_idx, query_id in enumerate(known_ids):
            js_body: str = json.dumps({
                "variables": {"tweet_id": tweet_id, "dark_request": False},
                "queryId": query_id,
                "features": {},
            })
            url: str = f"https://x.com/i/api/graphql/{query_id}/FavoriteTweet"
            tid = _generate_transaction_id("POST", f"/i/api/graphql/{query_id}/FavoriteTweet")
            js: str = _make_js_fetch(
                "POST",
                url,
                body=js_body,
                delay_before=pre_delay if attempt_idx == 0 else random.uniform(0.3, 0.8),
                delay_after=random.uniform(0.3, 0.8),
                content_type="application/json",
                transaction_id=tid,
                csrf_token=token if token else None,
            )
            result: dict[str, Any] = _run_js(page, js)
            status: int = result.get("status", 0)
            body_str: str = result.get("body", "")

            if status == 200:
                if not body_str:
                    out(f"  [WARN] FavoriteTweet GraphQL (queryId={query_id}…): 空レスポンス")
                    continue
                if _is_api_error(body_str):
                    # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
                    if _is_automation_block(body_str):
                        mark_automation_block(account_key, out)
                        _delay = int((_time.time() - _t0) * 1000)
                        audit_ledger.log(
                            account_key,
                            "like",
                            tweet_id,
                            "allow",
                            "failed",
                            error="automation_blocked",
                            delay_ms=_delay,
                        )
                        return False
                    # ★ 2026-08-26提案13: 200 with errorsでもAuthorizationError検出を通す。
                    #   従来はここでcontinueしてしまい_auth_errorが立たず、RESTフォールバック
                    #   (200空body自動失敗)に落ちていた。→ empty_response 30件/日の主因。
                    #   code139=「既にいいね済み」・code327=権限エッジ（生存ツイート確認済み）。
                    #   RT経路(2026-08-25)と同一ロジックでfail fast化。
                    if '"code":139' in body_str or '"code":327' in body_str or "AuthorizationError" in body_str:
                        _auth_error = True
                        out("  [i] いいねAPI: AuthorizationError → スキップ")
                        body_preview = body_str[:200]
                        continue
                    out(f"  [WARN] FavoriteTweet GraphQL (queryId={query_id}…): 200 with errors: {body_str[:200]}")
                    continue
                # 200 かつ body に "favorite_tweet" キーがあれば成功
                if '"favorite_tweet"' in body_str:
                    out("  [OK] いいね（GraphQL）")
                    increment_daily_count(account_key, "like")
                    policy_engine.mark_executed(account_key, "like")
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(account_key, "like", tweet_id, "allow", "success", delay_ms=_delay)
                    return True
                else:
                    out(
                        f"  [WARN] FavoriteTweet GraphQL (queryId={query_id}…): 200 but no favorite_tweet key: {body_str[:200]}"  # noqa: E501
                    )
                    continue
            elif status == 403:
                if _is_automation_block(body_str):
                    # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
                    mark_automation_block(account_key, out)
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(
                        account_key,
                        "like",
                        tweet_id,
                        "allow",
                        "failed",
                        error="automation_blocked",
                        delay_ms=_delay,
                    )
                    return False
                if body_str and ("AlreadyLiked" in body_str or "already liked" in body_str.lower()):
                    out("  [i] いいね GraphQL: 403（既にいいね済み）")
                    increment_daily_count(account_key, "like")
                    policy_engine.mark_executed(account_key, "like")
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(
                        account_key, "like", tweet_id, "allow", "success", reason="already_liked", delay_ms=_delay
                    )
                    return True
                out(f"  [WARN] いいね GraphQL (queryId={query_id}…): HTTP 403 (body: {body_str[:200]})")
                body_preview = body_str[:200]
                continue
            elif status in (429, 420):
                out("  [WARN] いいね GraphQL: レート制限（HTTP %d）、スキップ" % status)
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(
                    account_key, "like", tweet_id, "allow", "failed", error="rate_limited", delay_ms=_delay
                )
                return False

            # AuthorizationError detection
            if '"code":327' in body_str or "AuthorizationError" in body_str:
                _auth_error = True
                out("  [i] いいねAPI: AuthorizationError → スキップ")
                body_preview = body_str[:200]
                continue

            # その他 → 次のqueryIdへ
            body_preview = body_str[:200]
            if attempt_idx < len(known_ids) - 1:
                out(f"  [i] いいね GraphQL (queryId={query_id[:8]}…): HTTP {status} [{body_str[:80]}] → 次を試す")

        if _auth_error:
            # ★ 2026-08-26提案13: AuthorizationError(139/327)は「既にいいね済み」→ 成功扱いでスキップ
            #   RT経路(2026-08-25)と同一ロジック。生存ツイートがCDNで確認できるのにGraphQLが
            #   Authエラーを返すのは「自分が既にいいねしたツイートへの再いいね」が主因。
            #   新規アクション不要なので成功扱いで返す（empty_response RESTフォールバック廃止）。
            out("  [i] いいねAPI: AuthorizationError → 既にいいね済みとして成功扱い（RESTフォールバック省略）")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "like", tweet_id, "allow", "success", reason="already_liked", delay_ms=_delay)
            return True

        out(f"  [i] いいね GraphQL: 全queryId失敗 → REST フォールバック (last body: {body_preview[:150]})")

    # REST fallback (既存コード)
    js: str = _make_js_fetch(
        "POST",
        "https://x.com/i/api/1.1/favorites/create.json",
        body=f"id={tweet_id}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
        csrf_token=token if token else None,
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    body_str: str = result.get("body", "")
    if status == 200:
        if not body_str:
            out("  [WARN] いいねREST API: 空レスポンス（失敗？）")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "like", tweet_id, "allow", "failed", error="empty_response", delay_ms=_delay)
            return False
        if _is_api_error(body_str):
            out(f"  [WARN] いいねREST API: 200 エラー応答（errors）: {body_str[:200]}")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "like", tweet_id, "allow", "failed", error="errors_in_response", delay_ms=_delay
            )
            return False
        out("  [OK] いいね（REST API）")
        increment_daily_count(account_key, "like")
        policy_engine.mark_executed(account_key, "like")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", tweet_id, "allow", "success", delay_ms=_delay)
        return True
    elif status == 403:
        if _is_automation_block(body_str):
            # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
            mark_automation_block(account_key, out)
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key,
                "like",
                tweet_id,
                "allow",
                "failed",
                error="automation_blocked",
                delay_ms=_delay,
            )
            return False
        if body_str and ("AlreadyLiked" in body_str or "already liked" in body_str.lower()):
            out("  [i] いいねREST API: 403（既にいいね済み）")
            increment_daily_count(account_key, "like")
            policy_engine.mark_executed(account_key, "like")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "like", tweet_id, "allow", "success", reason="already_liked", delay_ms=_delay)
            return True
        out(f"  [WARN] いいねREST API: HTTP 403 (body: {body_str[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", tweet_id, "allow", "failed", error="http_403", delay_ms=_delay)
        return False
    elif status == 401:
        out("  [WARN] いいねREST API: 認証エラー（セッション切れかも）")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", tweet_id, "allow", "failed", error="unauthorized", delay_ms=_delay)
        return False
    else:
        out(f"  [WARN] いいねREST API: HTTP {status} (body: {body_str[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", tweet_id, "allow", "failed", error=f"http_{status}", delay_ms=_delay)
        return False


def api_rt(
    page: Any,
    tweet_id: str,
    account_key: str,
    out: Callable[[str], None],
) -> bool | None:
    """X内部API経由でリポスト（RT）を実行。

    戻り値: True=成功 / False=一時的失敗(UI確認可) / None=ツイート消失(stale)。
    """
    from kensho.application.rate_limiter import increment_daily_count

    _t0 = _time.time()
    _cfg_here = _ensure_cfg()
    _decision, _reason = policy_engine.evaluate(account_key, "rt", _cfg_here)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] RT拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return False

    pre_delay: float = random.uniform(0.5, 2.0)
    token: str = _get_csrf_token(page)

    # ★ 複数のqueryIdを順番に試す ★
    # 自動 queryId 解決を優先
    qid = _get_query_id("CreateRetweet")
    known_ids: list[str] = _KNOWN_QUERY_IDS.get("CreateRetweet", [])
    if qid and qid not in known_ids:
        known_ids.insert(0, qid)
    if not known_ids:
        out("  [WARN] RT API: queryId一覧が空")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error="no_query_ids", delay_ms=_delay)
        return False

    _auth_error: bool = False
    body_preview: str = ""
    for attempt_idx, query_id in enumerate(known_ids):
        js_body: str = json.dumps({
            "variables": {"tweet_id": tweet_id, "dark_request": False},
            "queryId": query_id,
            "features": {},
        })
        url: str = f"https://x.com/i/api/graphql/{query_id}/CreateRetweet"
        tid = _generate_transaction_id("POST", f"/i/api/graphql/{query_id}/CreateRetweet")
        js: str = _make_js_fetch(
            "POST",
            url,
            body=js_body,
            delay_before=pre_delay if attempt_idx == 0 else random.uniform(0.3, 0.8),
            delay_after=random.uniform(0.3, 0.8),
            content_type="application/json",
            transaction_id=tid,
            csrf_token=token if token else None,
        )
        result: dict[str, Any] = _run_js(page, js)
        status: int = result.get("status", 0)
        body_str: str = result.get("body", "")

        if status == 200:
            if _is_api_error(body_str):
                # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
                if _is_automation_block(body_str):
                    mark_automation_block(account_key, out)
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(
                        account_key,
                        "rt",
                        tweet_id,
                        "allow",
                        "failed",
                        error="automation_blocked",
                        delay_ms=_delay,
                    )
                    return False
                out(f"  [WARN] RT GraphQL (queryId={query_id}…): 200 with errors: {body_str[:200]}")
                # ★ 2026-08-25 バグ修正: 200 with errorsでもAuthorizationError検出を通す。
                #   従来はここでcontinueしてしまい_auth_errorが立たず、RESTフォールバック(404→
                #   stale誤判定→DEFER)に落ちていた。RT API不通が「削除済みツイート」扱いになり、
                #   生存ツイートまで14日スキップされ続けていた（8/23〜25 RT成功率13-24%の主因）。
                if '"code":327' in body_str or "AuthorizationError" in body_str:
                    _auth_error = True
                    out("  [i] RT API: AuthorizationError → スキップ")
                    body_preview = body_str[:200]
                continue
            out("  [OK] RT（API）")
            increment_daily_count(account_key, "rt")
            policy_engine.mark_executed(account_key, "rt")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "rt", tweet_id, "allow", "success", delay_ms=_delay)
            return True
        elif status == 403:
            if _is_automation_block(body_str):
                # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
                mark_automation_block(account_key, out)
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(
                    account_key,
                    "rt",
                    tweet_id,
                    "allow",
                    "failed",
                    error="automation_blocked",
                    delay_ms=_delay,
                )
                return False
            if body_str and (
                "AlreadyRetweeted" in body_str
                or "already retweeted" in body_str.lower()
                or "AlreadyRetweet" in body_str
            ):
                out("  [i] RT API: 403（既にリポスト済み）")
                # ★ 2026-08-25: 既にRT済みは「新規行動」ではないので日次カウント/期限実行に加算しない。
                #   従来: increment_daily_count("rt")+mark_executed → 既存58件が新規RTと同列に数えられ、
                #   実新規RTが数件なのに「上限到達」で応募が早まって止まる(8/24実測 68/68時点で頭打ち)。
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(
                    account_key, "rt", tweet_id, "allow", "success", reason="already_retweeted", delay_ms=_delay
                )
                return True
            out(f"  [WARN] RT GraphQL (queryId={query_id}…): HTTP 403 (body: {body_str[:200]})")
            body_preview = body_str[:200]
            continue
        elif status in (429, 420):
            out("  [WARN] RT API: レート制限（HTTP %d）、スキップ" % status)
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error="rate_limited", delay_ms=_delay)
            return False

        # AuthorizationError detection
        if '"code":327' in body_str or "AuthorizationError" in body_str:
            _auth_error = True
            out("  [i] RT API: AuthorizationError → スキップ")
            body_preview = body_str[:200]
            continue

        # その他のステータスコード → 次のqueryIdへ
        body_preview = body_str[:200]
        if attempt_idx < len(known_ids) - 1:
            out(f"  [i] RT GraphQL (queryId={query_id[:8]}…): HTTP {status} [{body_str[:80]}] → 次を試す")

    if _auth_error:
        # ★ 2026-08-25 修正: 327(AuthorizationError)は既RT済み → 即成功扱いでスキップ
        #   従来: CDN生存確認→UIフォールバック(goto 25秒タイムアウトで失敗の無駄)。
        #   327は「自分が既にRTしたツイートへの再RT」でしか発生しない（前ターン調査で確認）。
        #   新規アクション不要なので、成功扱いで返す。
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "success", reason="already_retweeted", delay_ms=_delay)
        return True

    out(f"  [i] RT API: 全queryId失敗 → REST フォールバック (last body: {body_preview[:150]})")

    # REST fallback
    rest_url: str = f"https://x.com/i/api/1.1/statuses/retweet/{tweet_id}.json"
    rest_js: str = _make_js_fetch(
        "POST",
        rest_url,
        body=f"id={tweet_id}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
        content_type="application/x-www-form-urlencoded",
        csrf_token=token if token else None,
    )
    rest_result: dict[str, Any] = _run_js(page, rest_js)
    rest_status: int = rest_result.get("status", 0)
    rest_body: str = rest_result.get("body", "")

    if rest_status == 200:
        out("  [OK] RT（REST API）")
        increment_daily_count(account_key, "rt")
        policy_engine.mark_executed(account_key, "rt")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "success", delay_ms=_delay)
        return True
    elif rest_status == 401:
        out("  [WARN] RT REST API: 認証エラー")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error="unauthorized", delay_ms=_delay)
        return False
    elif rest_status == 404:
        # ★ 2026-08-25: 404=削除済みツイート確定。None(stale)を返し、
        #   UIフォールバックの無駄なgotoを省き、applier側でDEFER(14日スキップ)させる。
        out("  [i] RT REST API: 404（ツイート削除済み → stale扱い）")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error="http_404", delay_ms=_delay)
        return None
    elif rest_status == 403:
        if rest_body and (
            "AlreadyRetweeted" in rest_body or "already retweeted" in rest_body.lower() or "AlreadyRetweet" in rest_body
        ):
            out("  [i] RT REST API: 403（既にリポスト済み）")
            # ★ 2026-08-25: already_retweetedは新規行動でないので加算しない（GraphQL側と同じ）。
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "rt", tweet_id, "allow", "success", reason="already_retweeted", delay_ms=_delay
            )
            return True
        out(f"  [WARN] RT REST API: HTTP 403 (body: {rest_body[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error="http_403", delay_ms=_delay)
        return False
    else:
        out(f"  [WARN] RT REST API: HTTP {rest_status} (body: {rest_body[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", tweet_id, "allow", "failed", error=f"http_{rest_status}", delay_ms=_delay)
        return False


def api_follow_by_screen_name(
    page: Any,
    screen_name: str,
    account_key: str,
    out: Callable[[str], None],
) -> tuple[bool, str | None]:
    """X内部API経由でscreen_name指定でフォロー。

    Returns:
        (success, error_code) — error_code は失敗時の短い識別子
        （http_403, unauthorized, automation_blocked, errors_in_response, http_<status>）。
        成功時は (True, None)。呼び出し側がフォロー制限検出（提案90）に使う。
    """
    from kensho.application.rate_limiter import increment_daily_count

    _t0 = _time.time()
    _cfg_here = _ensure_cfg()
    _decision, _reason = policy_engine.evaluate(account_key, "follow", _cfg_here)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] フォロー拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", screen_name, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return (False, "policy_denied")

    token: str = _get_csrf_token(page)

    # フォロー実行
    pre_delay: float = random.uniform(0.5, 1.5)
    js: str = _make_js_fetch(
        "POST",
        "https://x.com/i/api/1.1/friendships/create.json",
        body=f"screen_name={screen_name}",
        delay_before=pre_delay,
        delay_after=random.uniform(0.5, 1.5),
        csrf_token=token if token else None,
    )
    result: dict[str, Any] = _run_js(page, js)
    status: int = result.get("status", 0)
    body_str: str = result.get("body", "")
    if status == 200:
        if _is_api_error(body_str):
            # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
            if _is_automation_block(body_str):
                mark_automation_block(account_key, out)
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(
                    account_key,
                    "follow",
                    screen_name,
                    "allow",
                    "failed",
                    error="automation_blocked",
                    delay_ms=_delay,
                )
                return (False, "automation_blocked")
            out(f"  [WARN] フォローAPI: 200 エラー応答: {body_str[:200]}")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "follow", screen_name, "allow", "failed", error="errors_in_response", delay_ms=_delay
            )
            return (False, "errors_in_response")
        out("  [OK] フォロー（API）")
        increment_daily_count(account_key, "follow")
        policy_engine.mark_executed(account_key, "follow")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", screen_name, "allow", "success", delay_ms=_delay)
        return (True, None)
    elif status == 401:
        out("  [WARN] フォローAPI: 認証エラー")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", screen_name, "allow", "failed", error="unauthorized", delay_ms=_delay)
        return (False, "unauthorized")
    elif status == 403:
        if _is_automation_block(body_str):
            # ★ 2026-08-29提案76: Error 226（automated block）→ 即停止＋待機
            mark_automation_block(account_key, out)
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key,
                "follow",
                screen_name,
                "allow",
                "failed",
                error="automation_blocked",
                delay_ms=_delay,
            )
            return (False, "automation_blocked")
        if _is_temp_lock_326(body_str):
            # ★ 2026-08-30提案93: code 326（一時ロック）→ フォロー停止マーカー用エラーコード
            #   凍結（code 64）ではなく一時ロックのため、FROZEN_ABORT（提案90/91）ではなく
            #   applier側で「フォローのみスキップ・like/RTは継続」の分岐に使う。
            out(f"  [WARN] フォローAPI: HTTP 403 code 326（一時ロック: {body_str[:200]})")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "follow", screen_name, "allow", "failed", error="temp_lock_326", delay_ms=_delay
            )
            return (False, "temp_lock_326")
        if body_str and (
            "already follows" in body_str.lower()
            or "AlreadyFollowing" in body_str
            or "already followed" in body_str.lower()
        ):
            out("  [i] フォローAPI: 403（既にフォロー済み）")
            increment_daily_count(account_key, "follow")
            policy_engine.mark_executed(account_key, "follow")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "follow", screen_name, "allow", "success", reason="already_followed", delay_ms=_delay
            )
            return (True, None)
        out(f"  [WARN] フォローAPI: HTTP 403 (body: {body_str[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", screen_name, "allow", "failed", error="http_403", delay_ms=_delay)
        return (False, "http_403")
    else:
        out(f"  [WARN] フォローAPI: HTTP {status} (body: {body_str[:200]})")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", screen_name, "allow", "failed", error=f"http_{status}", delay_ms=_delay)
        return (False, f"http_{status}")


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
            # ★ 2026-08-26: x.com/status/123 や x.com/i/web/status/123 形式（screen_nameなし）では
            #   "x.com" / "web" を screen_name と誤抽出しない（フォローAPIの誤爆防止）
            if screen_name.lower() in ("x.com", "twitter.com", "mobile.twitter.com", "www.x.com", "web"):
                screen_name = ""
            return tweet_id, screen_name or None
    except ValueError:
        pass
    return None, None
