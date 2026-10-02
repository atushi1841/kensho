#!/usr/bin/env python3
"""scripts/gumroad_cross_post_trigger.py — Gumroad views=0が3週連続ならクロス投稿を起動.

設計:
  - data/gumroad_views_history.json の履歴から直近3週分の views を確認
  - 全て 0（または null/欠損=実質0）なら True
  - 週単位は ISO 週（ISO 8601）で集計
  - 実行済みキャンペーンは data/gumroad_cross_post_state.json で dedup（同週重複防止）
  - トリガー時: Reddit r/animefigures へ投稿 + X 既存アカウント群（kudou, zin20120731, TankanNotes）へ販促投稿
  - 投稿後 7 日後に再計測 → 改善ループへ

使い方:
  python scripts/gumroad_cross_post_trigger.py           # 判定・実行
  python scripts/gumroad_cross_post_trigger.py --dry-run # 判定のみ表示
  python scripts/gumroad_cross_post_trigger.py --force   # 週次dedup無視（検証用）

退出コード: 0=実行/スキップ(正常)  2=dry-run  1=依存/実行失敗
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, UTC
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "gumroad_cross_post_state.json"
VIEWS_HISTORY = DATA_DIR / "gumroad_views_history.json"
KPI_STATE = DATA_DIR / "gumroad_promo_kpi_state.json"

# X アカウント設定（config.yaml accounts に準拠）
ACCOUNTS = [
    {"key": "atushi16", "display": "@atushi16", "session": "data/x_session.json"},
    {"key": "kudou", "display": "@kudou_aoshi", "session": "data/x_session_kudou.json"},
    {"key": "zin20120731", "display": "@zin20120731", "session": "data/x_session_c.json"},
    {"key": "TankanNotes", "display": "@TankanNotes", "session": "data/x_session_TankanNotes.json"},
]

# 商品 URL（短縮 ID）
FREE_SAMPLE_URL = "https://atushi5.gumroad.com/l/kutuxe"
PAID_DATASET_URL = "https://atushi5.gumroad.com/l/agyhq"
WEEKLY_REPORT_URL = "https://atushi5.gumroad.com/l/qdyyyi"

# Reddit 投稿先
REDDIT_SUBREDDIT = "animefigures"

# クロス投稿用文言ローテーション（週×アカウントで独立選択）
CROSS_POST_TWEETS: list[str] = [
    "Japanese anime figure & collectibles price dataset — weekly CSV updated. "
    "Free sample: {free} #animefigures #datasets",
    "Tracking Japan hobby market prices every week. Free 30-row sample: {free} "
    "Full dataset: {paid} #reselling #marketdata",
    "New weekly price data for Japanese anime figures & collectibles. "
    "Preview for free: {free} #figures #priceguide",
    "Weekly CSV of Japanese collectibles market prices is out. "
    "Grab the free sample: {free} #collectibles #hobby",
    "Resellers: Japan anime figure price trends updated weekly. "
    "Start with the free sample: {free} #anime #pricedata",
    "Japanese hobby & collectibles price intelligence, delivered weekly. "
    "Free sample: {free} Full: {paid} #dataanalytics",
    "This week's Japan anime figure price snapshot is live. "
    "Free preview: {free} Deep dive: {report} #priceguide",
    "Build your price model on Japanese collectibles data. "
    "Weekly CSV — free sample: {free} #animefigures #datasets",
]


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W39）"""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_views_history() -> dict[str, Any]:
    return _load_json(VIEWS_HISTORY)


def check_three_weeks_zero_views(history: dict[str, Any], today: date) -> tuple[bool, list[str]]:
    """
    直近3週間の views が全て 0 か判定。
    戻り値: (triggers, week_keys)
    """
    # 過去3週間の ISO 週キーを生成（今週含む）
    week_keys = []
    for i in range(3):
        d = today - timedelta(weeks=i)
        week_keys.append(week_key(d))

    zero_weeks = []
    for wk in week_keys:
        # その週に属する日の views をチェック
        week_views = []
        for day_key, day_data in history.items():
            try:
                day_date = date.fromisoformat(day_key)
                if week_key(day_date) == wk:
                    v = day_data.get("views")
                    if isinstance(v, int):
                        week_views.append(v)
            except ValueError:
                continue
        # 週内の最大 views（1日でも >0 ならその週は非ゼロ）
        max_views = max(week_views) if week_views else 0
        if max_views == 0:
            zero_weeks.append(wk)

    return (len(zero_weeks) == 3, zero_weeks)


def load_cross_post_state() -> dict[str, Any]:
    return _load_json(STATE_FILE)


def save_cross_post_state(state: dict[str, Any]) -> None:
    _save_json(STATE_FILE, state)


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    log_dir = REPO / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "gumroad_cross_post_trigger.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def promo_url(base: str, campaign: str) -> str:
    """Gumroad 商品URLに utm パラメータ付与"""
    short = campaign.replace("cross_post_", "c").replace("-", "")
    return f"{base}?utm_source=tw&utm_medium=s&utm_campaign={short}"


def pick_tweet_for_account(week: int, account_idx: int, campaign: str) -> str:
    """週×アカウントインデックスで独立した文言を選択"""
    idx = (week * len(ACCOUNTS) + account_idx) % len(CROSS_POST_TWEETS)
    raw = CROSS_POST_TWEETS[idx]
    return raw.format(
        free=promo_url(FREE_SAMPLE_URL, campaign),
        paid=promo_url(PAID_DATASET_URL, campaign),
        report=promo_url(WEEKLY_REPORT_URL, campaign),
    )


def load_x_session(account: dict) -> dict[str, str]:
    """X セッションクッキーを読み込み"""
    session_path = REPO / account["session"]
    data = json.loads(session_path.read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    pool = {c["name"]: c.get("value", "") for c in cookies if isinstance(c, dict) and c.get("name")}
    auth, ct0 = pool.get("auth_token", ""), pool.get("ct0", "")
    if not auth or not ct0:
        raise RuntimeError(f"sessionファイルに auth_token/ct0 がない: {session_path}")
    return {"auth_token": auth, "ct0": ct0}


def post_to_x(account: dict, text: str, log_fn) -> str:
    """X に GraphQL CreateTweet で投稿（gumroad_x_post.py の create_tweet を再利用）"""
    sys.path.insert(0, str(REPO / "scripts"))
    import gumroad_x_post as gxp

    session = load_x_session(account)
    pairs = json.loads((REPO / "kensho" / "application" / "transaction_pairs.json").read_text(encoding="utf-8"))
    tweet_id = gxp.create_tweet(session, pairs, text, log_fn)
    return tweet_id


def post_to_reddit(text: str, log_fn) -> str | None:
    """Reddit に投稿（reddit-posting-automation スキルのパターン：CDP + ブラウザ内 fetch）"""
    # cookie ファイル確認
    cookie_file = DATA_DIR / "reddit" / ".cookie.txt"
    if not cookie_file.exists():
        log_fn(f"Reddit cookie file not found: {cookie_file}")
        return None

    cookie = cookie_file.read_text(encoding="utf-8").strip()
    if not cookie:
        log_fn("Reddit cookie empty")
        return None

    # CDP 一時 Chrome 起動（powershell 経由）
    import subprocess

    cdp_dir = Path(os.environ.get("TEMP", "/mnt/c/temp")) / "reddit-cdp"
    cdp_dir.mkdir(parents=True, exist_ok=True)

    # 既存プロセス確認
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -like '*reddit-cdp*'} | Stop-Process -Force"],
                       capture_output=True, timeout=5)
    except Exception:
        pass

    # Chrome 起動
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    start_cmd = [
        "powershell.exe", "-NoProfile", "-Command",
        f"Start-Process '{chrome_path}' -ArgumentList '--remote-debugging-port=9222',"
        f"'--user-data-dir={cdp_dir}',"
        f"'--no-first-run','--no-default-browser-check','--window-size=1280,900','about:blank' "
        f"; Start-Sleep -Seconds 3"
    ]
    subprocess.run(start_cmd, capture_output=True, timeout=30)
    time.sleep(3)

    # CDP 接続確認
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "curl.exe -s -o NUL -w '%{http_code}' http://127.0.0.1:9222/json/version"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip() != "200":
            log_fn(f"CDP not ready: {result.stdout}")
            return None
    except Exception as e:
        log_fn(f"CDP check failed: {e}")
        return None

    # Cookie 注入 + 投稿 JS
    import json as json_lib

    js = f"""
(() => {{
  const cookie = `{cookie}`;
  const parts = cookie.split('; ').map(s => s.split('='));
  for (const [name, value] of parts) {{
    if (name) {{
      document.cookie = `${{name}}=${{value}}; domain=.reddit.com; path=/; Secure; SameSite=Lax`;
    }}
  }}
  return 'cookies set';
}})();
"""
    # cookie 注入
    inject_cmd = [
        "powershell.exe", "-NoProfile", "-Command",
        f"cd {cdp_dir}; node -e \"const CDP = require('chrome-remote-interface'); "
        f"(async () => {{ const client = await CDP(); await client.Runtime.enable(); "
        f"const js = {json_lib.dumps(js)}; await client.Runtime.evaluate({{expression: js}}); "
        f"await client.close(); }})()\""
    ]
    subprocess.run(inject_cmd, capture_output=True, timeout=30)

    # Reddit ページへ遷移してログイン確認
    nav_js = """
(() => {
  window.location.href = 'https://www.reddit.com/r/animefigures';
  return 'navigating';
})();
"""
    subprocess.run([
        "powershell.exe", "-NoProfile", "-Command",
        f"cd {cdp_dir}; node -e \"const CDP = require('chrome-remote-interface'); "
        f"(async () => {{ const client = await CDP(); await client.Page.enable(); "
        f"await client.Runtime.enable(); const js = {json_lib.dumps(nav_js)}; "
        f"await client.Runtime.evaluate({{expression: js}}); await new Promise(r => setTimeout(r, 5000)); "
        f"await client.close(); }})()\""
    ], capture_output=True, timeout=30)
    time.sleep(5)

    # 投稿実行
    title = "Japanese Anime Figure & Collectibles Price Dataset — Weekly CSV"
    # 自己宣伝は最小限・データ主体の構成
    post_text = (
        "I compile weekly CSV datasets of Japanese anime figure & collectibles market prices "
        "(from Surugaya, Mandarake, Yahoo Auctions, Yahoo Shopping, etc.). "
        "This week's update is out — 650+ records with price history, release dates, and condition data.\n\n"
        "Free 30-row sample: https://atushi5.gumroad.com/l/kutuxe\n"
        "Full weekly dataset: https://atushi5.gumroad.com/l/agyhq\n\n"
        "Data sources: Surugaya, Mandarake, Yahoo Auctions, OffMall, Kitamura, Jackroad, Komehyo, Digimart, etc. "
        "Updated every Monday. Useful for resale research, pricing benchmarks, and market analysis.\n\n"
        "#animefigures #collectibles #pricedata #Japan"
    )

    csrf_js = """
(() => {
  const m = document.cookie.match(/csrf_token=([^;]+)/);
  return m ? m[1] : '';
})();
"""
    # CSRF トークン取得
    csrf_result = subprocess.run([
        "powershell.exe", "-NoProfile", "-Command",
        f"cd {cdp_dir}; node -e \"const CDP = require('chrome-remote-interface'); "
        f"(async () => {{ const client = await CDP(); await client.Runtime.enable(); "
        f"const js = {json_lib.dumps(csrf_js)}; const r = await client.Runtime.evaluate({{expression: js}}); "
        f"console.log(r.result?.result?.value || ''); await client.close(); }})()\""
    ], capture_output=True, text=True, timeout=30)
    csrf = csrf_result.stdout.strip()

    # /api/submit 実行
    import urllib.parse
    body = urllib.parse.urlencode({
        "api_type": "json",
        "sr": REDDIT_SUBREDDIT,
        "title": title,
        "kind": "self",
        "text": post_text,
        "resubmit": "true",
        "r": REDDIT_SUBREDDIT,
    })

    submit_js = f"""
(() => {{
  const csrf = `{csrf}`;
  const body = `{body}`;
  return fetch('/api/submit?raw_json=1', {{
    method: 'POST',
    credentials: 'include',
    headers: {{
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Reddit-Session': csrf
    }},
    body: body
  }}).then(r => r.text()).then(t => {{ console.log(t); return t; }});
}})();
"""
    submit_result = subprocess.run([
        "powershell.exe", "-NoProfile", "-Command",
        f"cd {cdp_dir}; node -e \"const CDP = require('chrome-remote-interface'); "
        f"(async () => {{ const client = await CDP(); await client.Runtime.enable(); "
        f"const js = {json_lib.dumps(submit_js)}; const r = await client.Runtime.evaluate({{expression: js}}); "
        f"console.log(r.result?.result?.value || ''); await client.close(); }})()\""
    ], capture_output=True, text=True, timeout=60)

    log_fn(f"Reddit submit result: {submit_result.stdout[:500]}")
    try:
        resp = json_lib.loads(submit_result.stdout.strip().splitlines()[-1])
        if resp.get("json", {}).get("data", {}).get("url"):
            post_url = resp["json"]["data"]["url"]
            log_fn(f"Reddit post success: {post_url}")
            return post_url
    except Exception as e:
        log_fn(f"Reddit response parse failed: {e}")
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad views=0 3週連続でクロス投稿起動")
    ap.add_argument("--dry-run", action="store_true", help="判定のみ表示")
    ap.add_argument("--force", action="store_true", help="週次dedup無視")
    ap.add_argument("--date", default="", help="基準日 YYYY-MM-DD（省略=今日）")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    wk = week_key(today)

    state = load_cross_post_state()
    if not args.force and state.get("campaign_week") == wk:
        log(f"スキップ: 今週(wk={wk})はクロス投稿実行済み")
        sys.exit(0)

    history = load_views_history()
    triggers, zero_weeks = check_three_weeks_zero_views(history, today)

    if not triggers:
        log(f"トリガー未達: 直近3週のゼロ週={zero_weeks}/3 (基準日={today})")
        sys.exit(0)

    log(f"トリガー成立: 直近3週連続 views=0 {zero_weeks} → クロス投稿起動")

    if args.dry_run:
        log("DRY-RUN: クロス投稿は実行していません。")
        sys.exit(2)

    campaign = f"cross_post_{wk}"
    results = {"campaign_week": wk, "triggered_at": datetime.now(UTC).isoformat(), "posts": []}

    # 1. Reddit 投稿
    log("=== Reddit r/animefigures 投稿 ===")
    reddit_url = post_to_reddit(campaign, log)
    if reddit_url:
        results["posts"].append({"platform": "reddit", "subreddit": REDDIT_SUBREDDIT, "url": reddit_url})
        log(f"Reddit 投稿成功: {reddit_url}")
    else:
        log("Reddit 投稿失敗（継続）")

    # 2. X アカウント群へ投稿（atushi16 は gumroad_promo_weekly.py で既に実施済みなので除外）
    for idx, account in enumerate(ACCOUNTS[1:], start=1):  # atushi16 をスキップ
        try:
            log(f"=== X {account['display']} 投稿 ===")
            text = pick_tweet_for_account(today.isocalendar().week, idx, campaign)
            if len(text) > 280:
                log(f"WARN: {account['display']} 文字数超過 {len(text)}/280")
            tweet_id = post_to_x(account, text, log)
            results["posts"].append({
                "platform": "x", "account": account["key"], "tweet_id": tweet_id, "text": text
            })
            log(f"{account['display']} 投稿成功 tweet_id={tweet_id}")
            # アカウント間ランダム遅延（BOT対策）
            time.sleep(random.uniform(30, 90))
        except Exception as e:
            log(f"{account['display']} 投稿失敗: {e}")
            results["posts"].append({"platform": "x", "account": account["key"], "error": str(e)})

    # 3. 再計測スケジュール登録（7日後）
    remeasure_date = today + timedelta(days=7)
    results["remeasure_date"] = remeasure_date.isoformat()

    # 4. 状態保存
    save_cross_post_state(results)
    log(f"クロス投稿キャンペーン完了: {results}")

    # 5. KPI state にキャンペーン記録を追加（改善ループ用）
    kpi = _load_json(KPI_STATE)
    campaigns = kpi.setdefault("cross_post_campaigns", [])
    campaigns.append({"week": wk, "date": today.isoformat(), "posts": results["posts"], "remeasure_date": remeasure_date.isoformat()})
    _save_json(KPI_STATE, kpi)

    log("クロス投稿 + 再計測スケジュール登録 完了")


if __name__ == "__main__":
    main()