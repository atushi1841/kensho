#!/usr/bin/env python3
"""scripts/tweet_devto.py — dev.to 記事を X(atushi16) へ自動投稿で拡散する。

設計:
  - 投稿経路: scripts/x_post_driver.js（Windows Chrome + CDP + node）を既定とする。
    WSL から動くのは win 経路のみ（2026-10-03 実測）。
  - 週次 dedup: data/devto_x_tweet_state.json に ISO 週キー + スロットで投稿済み記録。
    cron 再実行でも冪等（同週同スロット2回目は安全スキップ）。
  - 対象抽出: dev.to API /api/articles/me?per_page=20 で最新20件を取得し、
    未投稿のものから最大 N 件をランダム選択。
  - 効果測定連携: 投稿 tweet_id を state に記録し、後日 X analytics 収集時に参照可。

使い方:
  python scripts/tweet_devto.py                  # 週次投稿（同週同スロット済みならスキップ）
  python scripts/tweet_devto.py --dry-run        # 投稿せず実行内容を表示
  python scripts/tweet_devto.py --force          # 週次dedupを無視（検証用）
  python scripts/tweet_devto.py --slot a         # スロット指定（a=月曜/b=金曜）
  python scripts/tweet_devto.py --max 1          # 1記事のみ（既定2）

退出コード:
  0=投稿/スキップ(正常)  2=dry-run  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, UTC
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "scripts"
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "devto_x_tweet_state.json"
WIN_TEMP = Path("/mnt/c/temp")
X_DRIVER_JS = REPO / "scripts" / "x_post_driver.js"

# dev.to API（User-Agent 必須、ないと 403）
DEVTO_API = "https://dev.to/api"
DEVTO_ARTICLES_ME = f"{DEVTO_API}/articles/me"
MAX_PER_PAGE = 20

# X アカウント
ACCOUNT_KEY = "atushi16"

# 投稿スロット（BOT検知回避のため月曜↔金曜で4日間隔）
SLOTS: tuple[str, ...] = ("a", "b")

# dev.to 記事から tweet 本文を生成する際の文言テンプレート（自然な日本語）
TWEET_TEMPLATES: list[dict[str, str]] = [
    # カテゴリ別の自然な日本語ツイート
    {
        "tech": ("「{title}」という技術を調べてみました。\n"
                 "詳しくは → {url}\n\n"
                 "#開発 #プログラミング #テクノロジー"),
        "data": ("市場データを無料で取得できる方法をまとめました。\n"
                 "{title}\n\n"
                 "詳細 → {url}\n\n"
                 "#データサイエンス #スクレイピング #Apify"),
        "general": ("技術ブログを投稿しました。\n{title}\n\n"
                    "読んでいただけると嬉しいです → {url}\n\n"
                    "#tech #blog #開発"),
    },
    {
        "tech": ("今日の記事: {title}\n\n"
                 "開発のヒントになるかもしれません。\n"
                 "→ {url} #programming #developers"),
        "data": ("フリーミアムAPIで日本市場のデータを取得できる方法について書きました。\n"
                 "{title}\n\n"
                 "→ {url} #apify #data #scraping"),
        "general": ("新しいブログ記事を書きました。\n{title}\n\n"
                    "詳しくはこちら → {url} #dev #tech"),
    },
]


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W42）。"""
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


def get_devto_articles(token: str, per_page: int = MAX_PER_PAGE) -> list[dict]:
    """dev.to API でユーザーの公開記事を per_page 件取得する。"""
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
    cmd = [
        "curl", "-s", "-A", ua, "-w", "\n%{http_code}",
        "-H", f"Api-Key: {token}",
        f"{DEVTO_ARTICLES_ME}?per_page={per_page}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    body, sep, code = (proc.stdout or "").rpartition("\n")
    try:
        http_code = int(code.strip())
    except ValueError:
        http_code = 0
    if http_code != 200:
        raise RuntimeError(f"dev.to API HTTP {http_code}: {body[:300]}")
    try:
        articles = json.loads(body or "[]")
    except json.JSONDecodeError:
        raise RuntimeError(f"dev.to API 非JSON応答: {body[:200]}")
    if not isinstance(articles, list):
        raise RuntimeError(f"dev.to API 予期せぬ応答形式: type={type(articles).__name__}")
    return articles


def pick_articles(articles: list[dict], state: dict, max_pick: int = 2) -> list[dict]:
    """未投稿記事を max_pick 件ランダム選択（同じ週・同じスロットの投稿済みは除外）。"""
    posted_keys: set[str] = set()
    for wk, slots in state.get("posted_weeks", {}).items():
        for sl, info in slots.items():
            tid = info.get("tweet_id", "")
            if tid and str(tid).isdigit():
                posted_keys.add(tid)
            # 記事IDでも追加（同じ記事を2週続けて投稿しないため）
            aid = info.get("article_id")
            if aid:
                posted_keys.add(f"a_{aid}")

    available = []
    for art in articles:
        aid = art.get("id")
        if not aid:
            continue
        # 既存stateで投稿済みチェック
        key = f"a_{aid}"
        if key in posted_keys:
            continue
        available.append(art)

    # ランダムシャッフルして最大 max_pick 件
    random.shuffle(available)
    return available[:max_pick]


def generate_tweet(article: dict) -> str:
    """記事から自然な日本語 tweet を生成する。"""
    title = article.get("title", "Untitled")
    url = article.get("url", "")
    tags = article.get("tag_list", []) or []
    description = (article.get("description") or "").strip()[:80]

    # カテゴリ判定（簡易）
    tag_str = " ".join(tags).lower()
    if any(k in tag_str for k in ["data", "apify", "scrape", "market", "price"]):
        cat = "data"
    elif any(k in tag_str for k in ["code", "api", "mcp", "dev", "ai"]):
        cat = "tech"
    else:
        cat = "general"

    template_pool = TWEET_TEMPLATES[random.randint(0, len(TWEET_TEMPLATES) - 1)]
    tmpl = template_pool.get(cat, template_pool["general"])
    text = tmpl.format(title=title, url=url)

    # 280字制限チェック（超過時は description を削る）
    if len(text) > 280:
        excess = len(text) - 280
        # description が長い場合は削る
        if len(description) > excess:
            description = description[:len(description) - excess]
            tmpl2 = template_pool.get(cat, template_pool["general"])
            text = tmpl2.format(title=title, url=url)
        # それでも超えていれば最後に省略記号を追加
        if len(text) > 280:
            text = text[:277] + "…"

    return text


def post_via_cdp(text: str, log_fn: Callable[[str], None]) -> str:
    """Windows Chrome + CDP で X へ投稿し tweet_id を返す。

    x_post_driver.js を /mnt/c/temp/ へコピーして powershell 経由で実行する。
    """
    if not X_DRIVER_JS.exists():
        raise RuntimeError(f"driver が見つからない: {X_DRIVER_JS}")
    WIN_TEMP.mkdir(parents=True, exist_ok=True)
    (WIN_TEMP / "x_body.txt").write_text(text, encoding="utf-8")
    shutil.copyfile(X_DRIVER_JS, WIN_TEMP / "x_post_driver.js")
    out_json = WIN_TEMP / "x_post_out.json"
    if out_json.exists():
        out_json.unlink()

    log_fn("Windows Chrome + CDP 経路で投稿します")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "cd C:\\temp; node x_post_driver.js x_body.txt C:\\temp\\x_post_out.json"],
            capture_output=True, text=True, timeout=420,
        )
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-5:]
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"CDP タイムアウト: {e}") from e

    if not out_json.exists():
        raise RuntimeError(f"driver が結果を書かなかった: {tail}")
    res = json.loads(out_json.read_text(encoding="utf-8"))
    tweet_id = str(res.get("tweet_id") or "")
    if not tweet_id.isdigit():
        status = res.get("status", "unknown")
        raise RuntimeError(f"実IDが取れなかった (status={status}, log={tail})")
    log_fn(f"投稿成功: tweet_id={tweet_id} permalink={res.get('permalink','')}")
    return tweet_id


def main() -> None:
    ap = argparse.ArgumentParser(description="dev.to 記事 → X 自動拡散投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--slot", default="a", choices=["a", "b"], help="投稿スロット（a=月曜/b=金曜）")
    ap.add_argument("--max", type=int, default=2, help="1回あたりの最大投稿記事数")
    args = ap.parse_args()

    def log(msg: str) -> None:
        line = f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        log_dir = REPO / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "devto_x_tweet.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # 1. API キー取得
    token = os.environ.get("DEVTO_API_KEY", "")
    if not token:
        env_path = REPO / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("DEVTO_API_KEY="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token or len(token) < 8:
        log("ERROR: DEVTO_API_KEY が見つかりません（.env または環境変数）。")
        sys.exit(1)
    masked = token[:4] + "...[REDACTED]" + token[-4:] if len(token) > 8 else "[REDACTED]"
    log(f"APIキー取得: {masked}")

    # 2. 記事を API から取得
    try:
        articles = get_devto_articles(token, per_page=MAX_PER_PAGE)
    except Exception as e:
        log(f"ERROR: dev.to API 取得失敗: {e}")
        sys.exit(1)
    log(f"API記事取得: {len(articles)}件")
    if not articles:
        log("対象記事なし。スキップ。")
        sys.exit(0)

    # 3. state 読み込み・未投稿記事を絞り込み
    state = _load_json(STATE_FILE)
    today = date.today()
    key = week_key(today)

    picked = pick_articles(articles, state, max_pick=args.max)
    if not picked:
        log("未投稿記事なし（全記事既に投稿済み）。スキップ。")
        sys.exit(0)

    log(f"対象記事: {len(picked)}件 / 週={key} / slot={args.slot}")
    for i, art in enumerate(picked):
        log(f"  [{i+1}] {art.get('title','?')[:60]} → {art.get('url','?')}")

    if args.dry_run:
        for art in picked:
            txt = generate_tweet(art)
            log(f"DRY-RUN tweet[{len(txt)}chars]: {txt!r}")
        log("DRY-RUN: 投稿は実行していません。")
        sys.exit(2)

    # 4. 投稿実行（ランダム遅延付き）
    state.setdefault("posted_weeks", {})
    week_slot = state["posted_weeks"].setdefault(key, {})
    if args.force or args.slot not in week_slot:
        for i, art in enumerate(picked):
            text = generate_tweet(art)
            log(f"ツイート[{i+1}/{len(picked)}] ({len(text)}chars): {text[:100]}…")
            if len(text) > 280:
                log(f"WARN: 文字数 {len(text)}/280 超過 → 切り捨て")
            try:
                tweet_id = post_via_cdp(text, log)
            except Exception as e:
                log(f"ERROR: 投稿失敗: {e}")
                sys.exit(1)
            # 同じ週のスロットに投稿済みとして記録
            if args.slot not in week_slot:
                week_slot[args.slot] = {}
            week_slot[args.slot][str(art.get("id", ""))] = {
                "tweet_id": tweet_id,
                "article_title": art.get("title", ""),
                "article_url": art.get("url", ""),
                "posted_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "date": today.isoformat(),
                "slot": args.slot,
            }
            # BOT検知回避のため投稿間にランダム遅延（3〜8秒）
            if i < len(picked) - 1:
                delay = random.uniform(3.0, 8.0)
                log(f"  BOT検知回避: {delay:.1f}s 待機")
                time.sleep(delay)
    else:
        log(f"WARN: slot={args.slot} は既に今週投稿済み（forceなし）。スキップ。")
        sys.exit(0)

    # 5. state 保存
    _save_json(STATE_FILE, state)
    log(f"状態記録: {STATE_FILE}")
    log(f"完了: {key}/{args.slot} に {len(picked)} 件投稿")


if __name__ == "__main__":
    main()
