#!/usr/bin/env python3
"""
kensho_daily_health_check.py — 日次シャドウバン/凍結チェック（読み取り専用・垢別SOCKS5経由）

背景:
  - 旧 scripts/kensho_shadowban_checker.py(Playwright版)はcron環境でfirefoxパスが
    通らず2026-06-27以来成功していなかった(account_health.json凍結)。
  - 本スクリプトはブラウザ不要のGraphQL(UserByScreenName)1発/垢で
    tombstoned(=シャドウバン)/suspended/protected を判定する。
  - 垢別SOCKS5プロキシ経由で照会 = 適用側と同じ出口IP（IP分離ルール準拠）。
    プロキシ死時は自宅IPへフォールバックせず proxy_down として前回statusを保持。
  - accounts.db(twscrape)へは一切書き込まない（読み取り専用）。
  - フォロワー数急変アラート: 前回記録された followers から ±10% 超の変動で
    critical 通知（シャドウバン/凍結の早期シグナル。t_34decbc2 系 KPI と独立）。

出力:
  - data/account_health.json — 既存スキーマ {"accounts": {...}, "last_check": ...} を維持
  - stdout: 1行/垢のサマリ（cron通知でそのまま届く）
  - shadowbanned/suspended検出時は exit 1（cron失敗通知で気づける）

使い方:
  /home/atushi/kensho-venv/bin/python scripts/kensho_daily_health_check.py [--dry-run]
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import yaml

BASE = Path(__file__).resolve().parent.parent
HEALTH_FILE = BASE / "data" / "account_health.json"
CONFIG_FILE = BASE / "config.yaml"
BROWSER_PY = BASE / "kensho" / "application" / "browser.py"

# GraphQL: UserByScreenName（twscrape OP_UserByScreenName と同一queryId・実測200確認済）
USER_BY_SCREEN_NAME = "https://x.com/i/api/graphql/2qvSHpkWTMS9i0zJAwDNiA/UserByScreenName"
PUBLIC_BEARER = (
    "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


def load_proxies() -> dict[str, str]:
    """browser.py の PROXY_MAP をテキストから読む（実行しない＝副作用なし）。"""
    src = BROWSER_PY.read_text(encoding="utf-8")
    m = re.search(r"PROXY_MAP: dict\[str, str\] = \{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"([^"]+)":\s*"(socks5h://[^"]+)"', m.group(1)))


def load_accounts() -> list[dict]:
    """config.yaml の有効垢: key/display/session を返す。"""
    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    out = []
    for a in cfg.get("accounts", []):
        if not a.get("key") or not a.get("display") or not a.get("enabled", True):
            continue
        out.append({
            "key": a["key"],
            "handle": str(a["display"]).lstrip("@"),
            "session": a.get("session", ""),
        })
    return out


def load_tokens(acct: dict) -> tuple[str, str]:
    """セッションファイル(storage_state形式)から auth_token/ct0 を取得（値は出力しない）。"""
    p = BASE / acct["session"] if acct["session"] else None
    if not p or not p.exists():
        return "", ""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        ck = {c["name"]: c["value"] for c in d.get("cookies", [])}
        return ck.get("auth_token", ""), ck.get("ct0", "")
    except Exception:
        return "", ""


FOLLOWER_DELTA_PCT = 10.0  # 前日比 ±10% 超で急変アラート


def follower_delta_pct(prev: int | None, curr: int | None) -> float | None:
    """前回→今回のフォロワー変動率(%)。前回値が無い/0以下/同値未達なら None。"""
    if prev is None or not isinstance(prev, int) or prev <= 0:
        return None
    if curr is None or not isinstance(curr, int):
        return None
    return (curr - prev) / prev * 100.0


def check_one(handle: str, auth: str, ct0: str, proxy: str | None) -> dict:
    """UserByScreenName 1発照会。tombstoned/suspended/protected を読む。"""
    headers = {
        "Authorization": PUBLIC_BEARER,
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "ja",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    }
    if auth:
        headers["Authorization"] = PUBLIC_BEARER
        headers["x-twitter-auth-type"] = "OAuth2Session"
        headers["x-csrf-token"] = ct0
        headers["Cookie"] = f"auth_token={auth}; ct0={ct0}"
    variables = json.dumps({"screen_name": handle, "withSafetyModeUserFields": True}, separators=(",", ":"))
    features = json.dumps(
        {
            "hidden_profile_subscriptions_enabled": {"enabled": True},
            "subs_at_upvoting": {"enabled": True},
            "responsive_web_edit_post": {"enabled": True},
        },
        separators=(",", ":"),
    )
    client_kwargs = {"timeout": 30, "verify": False, "follow_redirects": False}
    if proxy:
        client_kwargs["proxy"] = proxy
    with httpx.Client(**client_kwargs) as c:
        r = c.get(
            USER_BY_SCREEN_NAME,
            params={"variables": variables, "features": features},
            headers=headers,
        )
    if r.status_code in (401, 403):
        return {"status": "login_failed", "detail": f"HTTP {r.status_code}"}
    if r.status_code != 200:
        return {"status": "error", "detail": f"HTTP {r.status_code}"}
    j = r.json()
    res = (j.get("data") or {}).get("user", {}).get("result") or {}
    typename = res.get("__typename", "")
    if "Suspended" in typename or typename == "UserUnavailable" or not res:
        return {"status": "suspended", "detail": typename or "no result"}
    legacy = res.get("legacy", {})
    if res.get("tombstoned"):
        return {"status": "shadowbanned", "detail": "tombstoned=true"}
    if legacy.get("restricted"):
        return {"status": "restricted", "detail": "restricted flag"}
    return {
        "status": "healthy",
        "detail": "",
        "followers": int(legacy.get("followers_count", 0) or 0),
        "friends": int(legacy.get("friends_count", 0) or 0),
        "protected": bool(legacy.get("protected", False)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="account_health.jsonへ書かない")
    args = ap.parse_args()

    accounts = load_accounts()
    proxies = load_proxies()

    try:
        health = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
        if "accounts" not in health:
            health = {"accounts": {}, "last_check": ""}
    except Exception:
        health = {"accounts": {}, "last_check": ""}
    old_accounts = health.get("accounts", {})

    now = datetime.now().isoformat(timespec="seconds")
    critical: list[str] = []
    icon = {
        "healthy": "✅",
        "shadowbanned": "🔇",
        "suspended": "🚫",
        "restricted": "⚠️",
        "login_failed": "🔑",
        "proxy_down": "📡",
        "error": "❓",
        "no_session": "🔑",
    }

    for acct in accounts:
        key, handle = acct["key"], acct["handle"]
        proxy = proxies.get(key)
        prev = old_accounts.get(key, {})
        prev_sb = int(prev.get("consecutive_shadowbans", 0) or 0)
        prev_err = int(prev.get("consecutive_errors", 0) or 0)

        auth, ct0 = load_tokens(acct)
        if not auth:
            entry = {
                **prev,
                "account": key,
                "status": "no_session",
                "search_ok": False,
                "checked_at": now,
                "consecutive_shadowbans": prev_sb,
                "consecutive_errors": prev_err + 1,
                "error": "session file has no auth_token",
            }
            health["accounts"][key] = entry
            print(f"  {icon['no_session']} {key}: no_session（セッション要再取得）")
            critical.append(f"{key}=no_session")
            continue

        if not proxy:
            # プロキシ設定なし = 自宅IP照会になる → IP分離ルール違反なので照会しない
            entry = {
                **prev,
                "account": key,
                "status": "proxy_down",
                "checked_at": now,
                "consecutive_shadowbans": prev_sb,
                "consecutive_errors": prev_err + 1,
                "error": "no proxy in PROXY_MAP (skipped to respect IP separation)",
            }
            health["accounts"][key] = entry
            print(f"  {icon['proxy_down']} {key}: proxy_down（PROXY_MAP未設定→照会スキップ）")
            continue

        res: dict = {}
        try:
            res = check_one(handle, auth, ct0, proxy)
            status, detail = res["status"], res.get("detail", "")
        except httpx.ProxyError:
            status, detail = "proxy_down", "proxy connect failed (回線断/proキシ死)"
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            status, detail = "proxy_down", f"network timeout ({type(e).__name__})"
        except Exception as e:
            status, detail = "error", f"{type(e).__name__}: {str(e)[:80]}"

        # ストライク計算（proxy_down/errorは一時的障害: statusは前回維持、連続失敗のみ加算）
        if status == "shadowbanned":
            sb_strikes, err_strikes = prev_sb + 1, 0
        elif status in ("suspended", "restricted", "login_failed"):
            sb_strikes, err_strikes = 0, prev_err + 1
        elif status in ("proxy_down", "error"):
            sb_strikes = prev_sb
            err_strikes = prev_err + 1
            status = prev.get("status", "unknown")  # 前回status保持（判定はlast_errorに記録）
        else:
            sb_strikes, err_strikes = 0, 0

        entry = {
            "account": key,
            "status": status,
            "search_ok": status == "healthy",
            "checked_at": now,
            "consecutive_shadowbans": sb_strikes,
            "consecutive_errors": err_strikes,
            "last_detail": detail,
            "followers": res.get("followers", prev.get("followers")),
            "friends": res.get("friends", prev.get("friends")),
        }
        health["accounts"][key] = entry

        # フォロワー数急変アラート（前日比 ±10% 超）— シャドウバン/凍結の早期シグナル
        delta = follower_delta_pct(prev.get("followers"), res.get("followers")) if status == "healthy" else None
        if delta is not None and abs(delta) >= FOLLOWER_DELTA_PCT:
            entry["follower_delta_pct"] = round(delta, 1)
            msg = (
                f"  ⚠️ {key}: フォロワー数急変 "
                f"{prev.get('followers')}→{res.get('followers')} ({delta:+.1f}%、閾値±{FOLLOWER_DELTA_PCT:g}%)"
            )
            print(msg)
            critical.append(f"{key}=follower_delta{delta:+.1f}%")

        print(
            f"  {icon.get(status, '❓')} {key}: {status}"
            + (f" ({detail})" if detail else "")
            + (f" followers={entry['followers']}" if status == "healthy" else "")
        )

        if status in ("shadowbanned", "suspended", "restricted", "login_failed"):
            critical.append(f"{key}={status}")
        if sb_strikes >= 2:
            critical.append(f"{key}=shadowban{sb_strikes}連続(応募停止対象)")
        if err_strikes >= 3:
            critical.append(f"{key}=連続失敗{err_strikes}(要確認)")

        time.sleep(random.uniform(4, 9))  # 人間らしいランダム間隔

    health["last_check"] = now
    if not args.dry_run:
        HEALTH_FILE.parent.mkdir(exist_ok=True)
        HEALTH_FILE.write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[SAVE] {HEALTH_FILE}")
    else:
        print("[DRY-RUN] 保存スキップ")

    a = health["accounts"]
    print(
        f"健全={sum(1 for x in a.values() if x.get('status') == 'healthy')} "
        f"shadowban={sum(1 for x in a.values() if x.get('status') == 'shadowbanned')} "
        f"他異常={sum(1 for x in a.values() if x.get('status') not in ('healthy', 'shadowbanned'))}"
    )
    if critical:
        print("⚠️ CRITICAL: " + " | ".join(critical))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
