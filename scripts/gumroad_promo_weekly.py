#!/usr/bin/env python3
"""scripts/gumroad_promo_weekly.py — t_3848cbde Gumroad 販促週次自動投稿.

Gumroad 売上ゼロ継続への販促施策自動化: 週1回、X(atushi16) へ商品リンク付き
プロモ投稿を自動生成して投稿する。

設計:
  - 週次 dedup: data/gumroad_promo_weekly_state.json に ISO 週キー (2026-W39) で
    投稿済み記録。cron 再実行でも冪等（同週2回目は安全スキップ）。
  - 文言ローテーション: WEEKLY_TWEETS を週番号で選択（同一文言連投の BOT 検知回避）。
  - 投稿経路: gumroad_x_post.create_tweet を再利用（GraphQL CreateTweet /
    curl_cffi / transaction_pairs — v21-C 実績経路）。
  - 効果測定連携: 投稿 tweet_id を data/gumroad_x_post_state.json の posted にも
    記録し、既存の日次 X analytics 収集 (gumroad_x_xanalytics.sh 08:50) で
    impressions が自動追跡される。
  - 効果は Referrer 表の Twitter 経由 views で判定
    (data/gumroad_views_history.json → scripts/gumroad_promo_kpi.py)。

使い方:
  python scripts/gumroad_promo_weekly.py            # 週次投稿（同週済みならスキップ）
  python scripts/gumroad_promo_weekly.py --dry-run  # 投稿せず実行内容を表示
  python scripts/gumroad_promo_weekly.py --force    # 週次dedupを無視（検証用）

退出コード: 0=投稿/スキップ(正常)  2=dry-run  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "scripts"
DATA_DIR = REPO / "data"
WEEKLY_STATE_FILE = DATA_DIR / "gumroad_promo_weekly_state.json"
# 既存の日次 impression 収集 (gumroad_x_xanalytics.py) が読む state。ここに追記すると
# 新規投稿も翌日から views 追跡される。
XPOST_STATE_FILE = DATA_DIR / "gumroad_x_post_state.json"

# 商品リンク（Gumroad API /v2/products 実測 2026-09-26）。base は utm 無し。
FREE_SAMPLE_URL = "https://atushi5.gumroad.com/l/kutuxe"  # FREE Sample ($0)
PAID_DATASET_URL = "https://atushi5.gumroad.com/l/agyhq"  # Weekly CSV dataset
WEEKLY_REPORT_URL = "https://atushi5.gumroad.com/l/qdyyyi"  # 週次レポート ($10)


def promo_url(base: str, campaign: str) -> str:
    """Gumroad 商品URL に utm_source=tw&utm_medium=s を付与（t_b8ec048a）。

    X 販促からの流入を Gumroad referrer 表で区別できるようにする。
    campaign は短縮キー（例: w2026W39）。文字数制限（280字）を守るため
    パラメータ名を短縮: utm_source=tw / utm_medium=s / utm_campaign=w...
    """
    # campaign キーを短縮: weekly_promo_2026-W39 -> w2026W39
    short = campaign.replace("weekly_promo_", "w").replace("-", "")
    return f"{base}?utm_source=tw&utm_medium=s&utm_campaign={short}"


# 週次ローテーション文言（週番号 % N で選択）。raw ≤280 字を維持。
# {free}/{paid}/{report} は pick_text 時に promo_url() で utm 付与置換される。
WEEKLY_TWEETS: list[str] = [
    "Japanese anime figure & collectibles price data, updated weekly. "
    "Try the free sample CSV first: {free} #animefigures #datasets",
    "Resellers: track Japanese hobby market prices with a weekly CSV. "
    "Free sample: {free} Full dataset: {paid} #reselling",
    "New week, new price data for anime figures & collectibles in Japan. "
    "Preview: {free} #marketdata #collectibles",
    "Weekly Japan hobby market report is out — what moved, what didn't. "
    + "{report} Sample CSV: {free} #pricedata",
    "Building a price model on Japanese collectibles? Start with the free sample: "
    + "{free} Full weekly dataset: {paid} #dataanalytics",
    "Sold-comps style price history for anime figures, kits and hobby items — "
    "weekly CSV. Sample: {free} #figures #hobby",
    "Free 30-row sample of the Japan hobby & collectibles price dataset: "
    + "{free} Full version updates every week. #anime #datasets",
    "This week's Japanese collectibles price snapshot is live. "
    + "Free sample: {free} Deep-dive report: {report} #priceguide",
]


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W39）。週次 dedup の単位。"""
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


def pick_text(today: date, state: dict[str, Any], force: bool = False) -> tuple[str | None, str]:
    """今日の文言を選ぶ。同週投稿済みなら (None, reason)。

    {free}/{paid}/{report} プレースホルダーは utm 付与済み URL に展開する
    （t_b8ec048a: X 販促経由流入を Gumroad referrer 表で区別するため）。
    """
    key = week_key(today)
    posted = state.get("posted_weeks", {})
    if not force and key in posted:
        prev = posted[key] or {}
        return None, f"今週は投稿済み (week={key}, tweet_id={prev.get('tweet_id', '?')})"
    idx = today.isocalendar().week % len(WEEKLY_TWEETS)
    campaign = f"weekly_promo_{key}"
    raw = WEEKLY_TWEETS[idx]
    text = raw.format(
        free=promo_url(FREE_SAMPLE_URL, campaign),
        paid=promo_url(PAID_DATASET_URL, campaign),
        report=promo_url(WEEKLY_REPORT_URL, campaign),
    )
    return text, ""


def record_xpost_state(today: date, tweet_id: str, text: str) -> None:
    """既存 gumroad_x_post_state.json へ追記（日次 impression 収集の連携先）。"""
    state = _load_json(XPOST_STATE_FILE)
    posted = state.setdefault("posted", {})
    posted[today.isoformat()] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "source": "gumroad_promo_weekly",
    }
    _save_json(XPOST_STATE_FILE, state)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad 販促 X 週次自動投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--state", default=str(WEEKLY_STATE_FILE), help="週次stateパス")
    ap.add_argument("--date", default="", help="基準日 YYYY-MM-DD（省略=今日）")
    args = ap.parse_args()

    state_file = Path(args.state)
    today = date.fromisoformat(args.date) if args.date else date.today()

    def log(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        log_dir = REPO / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "gumroad_promo_weekly.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    state = _load_json(state_file)
    text, reason = pick_text(today, state, force=args.force)
    if text is None:
        log(f"スキップ: {reason}")
        sys.exit(0)

    key = week_key(today)
    log(f"対象週: {key} / atushi16 / 週次販促投稿")
    log(f"ツイート内容: {text!r}")
    if len(text) > 280:
        log(f"WARN: 文字数 {len(text)}/280 超過")
    if args.dry_run:
        log("DRY-RUN: 投稿は実行していません。")
        sys.exit(2)

    # 依存 import（gumroad_x_post は main-guard 付き・import 安全）
    sys.path.insert(0, str(SCRIPTS_DIR))
    import gumroad_x_post as gxp  # noqa: E402

    session_path = gxp._load_config_session()
    session = gxp._load_session_cookies(session_path)
    pairs = json.loads((REPO / "kensho" / "application" / "transaction_pairs.json").read_text(encoding="utf-8"))
    tweet_id = gxp.create_tweet(session, pairs, text, log)

    posted_weeks = state.setdefault("posted_weeks", {})
    posted_weeks[key] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "date": today.isoformat(),
    }
    _save_json(state_file, state)
    try:
        record_xpost_state(today, tweet_id, text)
        log("impression追跡連携: gumroad_x_post_state.json へ記録済み")
    except OSError as e:
        log(f"WARN: impression連携記録に失敗（投稿自体は成功）: {e}")
    log(f"状態記録: {state_file} (tweet_id={tweet_id})")


if __name__ == "__main__":
    main()
