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

# 商品リンク（Gumroad API /v2/products 実測 2026-09-27）。
# SNS投稿用は短縮IDを使用（文字数制限対応）。SEO用は custom_permalink が適用済み。
# 両方アクセス可能（短縮IDは301リダイレクトでSEO URLへ）。
FREE_SAMPLE_URL = "https://atushi5.gumroad.com/l/kutuxe"  # FREE Sample ($0) - 短縮ID
PAID_DATASET_URL = "https://atushi5.gumroad.com/l/agyhq"  # Weekly CSV dataset - 短縮ID
WEEKLY_REPORT_URL = "https://atushi5.gumroad.com/l/qdyyyi"  # 週次レポート ($10) - 短縮ID

# Apify Store クロスプロモーション用
APIFY_STORE_BASE = "https://apify.com/fruitful_quintessence"
APIFY_ACTOR_URLS = {
    "japan-used-camera-market-scraper": "https://apify.com/fruitful_quintessence/japan-used-camera-market-scraper",
    "japan-watch-market-scraper": "https://apify.com/fruitful_quintessence/japan-watch-market-scraper",
    "japan-luxury-brand-market-scraper": "https://apify.com/fruitful_quintessence/japan-luxury-brand-market-scraper",
    "japan-used-instrument-market-scraper": "https://apify.com/fruitful_quintessence/japan-used-instrument-market-scraper",
    "japan-offmall-market-scraper": "https://apify.com/fruitful_quintessence/japan-offmall-market-scraper",
    "surugaya-japan-hobby-prices": "https://apify.com/fruitful_quintessence/surugaya-japan-hobby-prices",
    "mandarake-auction-scraper": "https://apify.com/fruitful_quintessence/mandarake-auction-scraper",
    "tackleberry-japan-fishing-tackle-scraper": "https://apify.com/fruitful_quintessence/tackleberry-japan-fishing-tackle-scraper",
    "yahoo-auctions-japan-scraper": "https://apify.com/fruitful_quintessence/yahoo-auctions-japan-scraper",
    "dlsite-scraper": "https://apify.com/fruitful_quintessence/dlsite-scraper",
    "dmm-scraper": "https://apify.com/fruitful_quintessence/dmm-scraper",
    "kitamura-japan-used-camera-scraper": "https://apify.com/fruitful_quintessence/kitamura-japan-used-camera-scraper",
    "jackroad-used-watch-scraper": "https://apify.com/fruitful_quintessence/jackroad-used-watch-scraper",
    "komehyo-japan-brand-scraper": "https://apify.com/fruitful_quintessence/komehyo-japan-brand-scraper",
    "eurostat-indicators": "https://apify.com/fruitful_quintessence/eurostat-indicators",
    "world-bank-indicators": "https://apify.com/fruitful_quintessence/world-bank-indicators",
    "goo-net-car-scraper": "https://apify.com/fruitful_quintessence/goo-net-car-scraper",
    "biglemon-machinery-scraper": "https://apify.com/fruitful_quintessence/biglemon-machinery-scraper",
    "digimart-japan-used-instrument-scraper": "https://apify.com/fruitful_quintessence/digimart-japan-used-instrument-scraper",
    "golfpartner-used-club-scraper": "https://apify.com/fruitful_quintessence/golfpartner-used-club-scraper",
}

# Apify アクターをランダムに選んで言及（クロスプロモーション用）
import random
APIFY_PROMO_ACTORS = list(APIFY_ACTOR_URLS.keys())

# 短縮URL（Apifyクロスプロモーション用は短くする）
# Gumroad短縮URLはUTM付きで約70字。Apify URLは約90字。
# ツイート280字制限内に収めるため、{free}または{paid}のどちらか1つのみ使用するテンプレートにする
def promo_url(base: str, campaign: str, short: str | None = None) -> str:
    """Gumroad 商品URL に utm_source=tw&utm_medium=s を付与（t_b8ec048a）。

    X 販促からの流入を Gumroad referrer 表で区別できるようにする。
    campaign は短縮キー（例: w2026W39）。文字数制限（280字）を守るため
    パラメータ名を短縮: utm_source=tw / utm_medium=s / utm_campaign=w...
    
    short が指定された場合は campaign キーとしてそれを使用（短縮用）。
    """
    # campaign キーを短縮: weekly_promo_2026-W39 -> w2026W39
    if short:
        campaign_key = short
    else:
        campaign_key = campaign.replace("weekly_promo_", "w").replace("-", "")
    return f"{base}?utm_source=tw&utm_medium=s&utm_campaign={campaign_key}"


# 週2投稿用ローテーション文言（16種 = 週×スロットで独立選択）。
# {free}/{paid}/{report} は pick_text 時に promo_url() で utm 付与置換される。
# ※クロスプロモーション時（33%確率）に Apify URL (~90字) が追加されるため、
#   テンプレート本体は190字以内に抑制（{free}または{paid}の片方のみ + Apify = 258字以内）。
WEEKLY_TWEETS: list[str] = [
    "Japanese anime figure & collectibles price data, updated weekly. Free sample: {free} #animefigures #datasets",
    "Resellers: track Japanese hobby market prices weekly. Free sample: {free} #reselling",
    "New week, new price data for anime figures in Japan. Preview: {free} #marketdata #collectibles",
    "Weekly Japan hobby market report — what moved, what didn't. {report} Sample CSV: {free} #pricedata",
    "Building a price model on Japanese collectibles? Start free: {free} Full weekly dataset: {paid} #dataanalytics",
    "Sold-comps price history for anime figures/kits — weekly CSV. Sample: {free} #figures #hobby",
    "Free 30-row sample of Japan hobby & collectibles price dataset: {free} Full version updates weekly. #anime #datasets",
    "This week's Japanese collectibles price snapshot live. Free sample: {free} Deep-dive report: {report} #priceguide",
    # ── 週2投稿拡大（t_e6968f4f）: 新增8種 ──
    "Weekly CSV of Japanese anime figure prices, fresh off the press. Grab free sample: {free} #animefigures",
    "Track Japan's hobby market weekly. Free sample: {free} Paid dataset: {paid} #marketdata",
    "Price intelligence for Japanese collectibles, delivered weekly. Start free: {free} #pricedata",
    "What's hot in Japan's anime market this week? Free sample: {free} Full report: {report} #anime",
    "Resellers: your weekly Japan hobby price sheet. Sample: {free} Full CSV: {paid} #reselling",
    "Japanese collectibles price trends, updated weekly. Preview free: {free} #figures #hobby",
    "One weekly CSV, all Japanese anime figure & collectibles prices. Free sample: {free} #datasets",
    "Stay ahead of the Japan hobby market. Free sample: {free} Deep dive: {report} #priceguide",
]

# 週2投稿のスロット（BOT検知回避のため月曜↔金曜で4日間隔）。
# a=月曜 cron（08:40 既存）、b=金曜 cron（08:40 新規追加 t_e6968f4f）。
SLOTS: tuple[str, ...] = ("a", "b")


def _slot_index(week: int, slot: str) -> int:
    """週×スロットごとに独立した文言を割り当てる（週2投稿で同一文言連投を回避）。"""
    return (week * len(SLOTS) + SLOTS.index(slot)) % len(WEEKLY_TWEETS)


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


def pick_text(today: date, state: dict[str, Any], slot: str = "a", force: bool = False) -> tuple[str | None, str]:
    """今日の文言を選ぶ。同週・同スロット投稿済みなら (None, reason)。

    {free}/{paid}/{report} プレースホルダーは utm 付与済み URL に展開する
    （t_b8ec048a: X 販促経由流入を Gumroad referrer 表で区別するため）。

    slot は "a"（月曜既存）/ "b"（金曜新增 t_e6968f4f）。
    週2投稿でも同一文言連投を避けるため、週×スロットで独立文言を割り当てる。
    
    クロスプロモーション: 3分の1の確率で Apify Store アクターへの言及を追加。
    """
    key = week_key(today)
    posted = state.get("posted_weeks", {}).get(key, {})
    # 旧 t_3848cbde 形式（スロットなし平構造）の互換処理
    if slot not in posted and "tweet_id" in posted:
        posted = {"a": posted}
    if not force and slot in posted:
        prev = posted[slot] or {}
        return None, f"今週{slot}スロットは投稿済み (week={key}, tweet_id={prev.get('tweet_id', '?')})"
    iso = today.isocalendar()
    idx = _slot_index(iso.week, slot)
    campaign = f"weekly_promo_{key}_{slot}"
    # 短縮キー（クロスプロモーション時のApify URL追加対応）
    short_key = campaign.replace("weekly_promo_", "w").replace("-", "")
    raw = WEEKLY_TWEETS[idx]

    # クロスプロモーション: 3分の1の確率で Apify アクターをランダム選択
    apify_mention = ""
    if random.random() < 0.33:
        promo_actor = random.choice(APIFY_PROMO_ACTORS)
        apify_mention = f" 関連データ: {APIFY_ACTOR_URLS[promo_actor]} #ApifyStore"
        # クロスプロモーション時は短縮キーを使用してURLを短くする
        text = raw.format(
            free=promo_url(FREE_SAMPLE_URL, campaign, short=short_key),
            paid=promo_url(PAID_DATASET_URL, campaign, short=short_key),
            report=promo_url(WEEKLY_REPORT_URL, campaign, short=short_key),
        ) + apify_mention
    else:
        text = raw.format(
            free=promo_url(FREE_SAMPLE_URL, campaign),
            paid=promo_url(PAID_DATASET_URL, campaign),
            report=promo_url(WEEKLY_REPORT_URL, campaign),
        )
    return text, ""


def record_xpost_state(today: date, tweet_id: str, text: str, slot: str = "a") -> None:
    """既存 gumroad_x_post_state.json へ追記（日次 impression 収集の連携先）。"""
    state = _load_json(XPOST_STATE_FILE)
    posted = state.setdefault("posted", {})
    posted[today.isoformat()] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "source": "gumroad_promo_weekly",
        "slot": slot,
    }
    _save_json(XPOST_STATE_FILE, state)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad 販促 X 週次自動投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--slot", default="a", choices=["a", "b"], help="投稿スロット（a=月曜既存/b=金曜新增 t_e6968f4f）")
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
    text, reason = pick_text(today, state, slot=args.slot, force=args.force)
    if text is None:
        log(f"スキップ: {reason}")
        sys.exit(0)

    key = week_key(today)
    log(f"対象週: {key} / slot={args.slot} / atushi16 / 週次販促投稿")
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
    week_slot = posted_weeks.setdefault(key, {})
    week_slot[args.slot] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "slot": args.slot,
    }
    _save_json(state_file, state)
    try:
        record_xpost_state(today, tweet_id, text, slot=args.slot)
        log("impression追跡連携: gumroad_x_post_state.json へ記録済み")
    except OSError as e:
        log(f"WARN: impression連携記録に失敗（投稿自体は成功）: {e}")
    log(f"状態記録: {state_file} (tweet_id={tweet_id}, slot={args.slot})")


if __name__ == "__main__":
    main()
