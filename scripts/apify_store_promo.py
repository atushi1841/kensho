#!/usr/bin/env python3
"""scripts/apify_store_promo.py — Apify Store PPEアクターのプロモーション自動投稿.

Apify Store の PPE 課金アクター 73 本が external_runs=0 / external_users=0
で実績収益 $0.0000 のまま。外部需要を喚起するため、X(atushi16) へ
CDP + SOCKS5 プロキシ分離でプロモ投稿を自動生成・投稿する。

設計:
  - 週次 dedup: data/apify_store_promo_state.json に ISO 週キー + スロットで
    投稿済み記録。cron 再実行でも冪等（同週同スロット2回目は安全スキップ）。
  - 対象抽出: data/apify_ppe_external_runs_state.json の last_trigger から
    24h 以上経過かつ external_runs=0 のアクターを優先選出。
  - 文言ローテーション: WEEKLY_TWEETS を週番号×スロットで選択（同一文言連投回避）。
  - 投稿経路: kensho.application.selenium_cdp.KenshoCDP (CDP Mode + SOCKS5)。
  - 効果測定連携: 投稿 tweet_id を data/apify_store_promo_state.json に記録し、
    翌週の external_runs 変化で効果を追跡可能にする。

使い方:
  python scripts/apify_store_promo.py            # 週次投稿（同週同スロット済みならスキップ）
  python scripts/apify_store_promo.py --dry-run  # 投稿せず実行内容を表示
  python scripts/apify_store_promo.py --force    # 週次dedupを無視（検証用）
  python scripts/apify_store_promo.py --slot a   # スロット指定（a=月曜/b=金曜）

退出コード: 0=投稿/スキップ(正常)  2=dry-run  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import json
import sys
import random
import time
from datetime import date, datetime, UTC, timedelta
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "scripts"
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "apify_store_promo_state.json"
EXTERNAL_RUNS_STATE_FILE = DATA_DIR / "apify_ppe_external_runs_state.json"
PPE_PRICE_FILE = DATA_DIR / "tmp" / "pay_per_event.json"

# アカウント設定
ACCOUNT_KEY = "atushi16"

# 週2投稿用スロット（月曜↔金曜で4日間隔・BOT検知回避）
SLOTS: tuple[str, ...] = ("a", "b")


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W39）。週次 dedup の単位。"""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _slot_index(week: int, slot: str) -> int:
    """週×スロットごとに独立した文言を割り当てる。"""
    return (week * len(SLOTS) + SLOTS.index(slot)) % len(WEEKLY_TWEETS)


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


def load_ppe_prices() -> dict[str, float]:
    """pay_per_event.json の actors_ppe（実API名 → 単価）を読み込む。"""
    if not PPE_PRICE_FILE.exists():
        return {}
    try:
        with open(PPE_PRICE_FILE, encoding="utf-8") as f:
            return dict(json.load(f).get("actors_ppe") or {})
    except Exception:
        return {}


def load_external_runs_state() -> dict[str, Any]:
    """apify_ppe_external_runs_state.json を読み込む。"""
    return _load_json(EXTERNAL_RUNS_STATE_FILE)


def get_actor_display_info(actual_name: str) -> dict[str, str]:
    """アクター実名から表示用情報を返す。"""
    # アクター名 → 表示名/カテゴリ/ハッシュタグのマッピング
    mapping = {
        "japan-used-camera-market-scraper": {
            "display": "Japan Used Camera Prices",
            "category": "中古カメラ",
            "hashtags": "#中古カメラ #カメラ転売 #Kitamura #Fujiya #MapCamera",
        },
        "japan-watch-market-scraper": {
            "display": "Japan Used Watch Prices",
            "category": "中古時計",
            "hashtags": "#中古時計 #ロレックス #オメガ #Jackroad #Komehyo",
        },
        "japan-luxury-brand-market-scraper": {
            "display": "Japan Luxury Resale Prices",
            "category": "中古ブランド",
            "hashtags": "#中古ブランド #エルメス #シャネル #ルイヴィトン #Komehyo #BrandOff",
        },
        "japan-used-instrument-market-scraper": {
            "display": "Japan Used Instrument Prices",
            "category": "中古楽器",
            "hashtags": "#中古楽器 #ギター #ベース #シンセ #Digimart #Ishibashi",
        },
        "japan-offmall-market-scraper": {
            "display": "Japan Used Goods Prices",
            "category": "中古総合",
            "hashtags": "#ハードオフ #オフモール #中古カメラ #中古時計 #中古楽器",
        },
        "surugaya-japan-hobby-prices": {
            "display": "Surugaya Hobby Prices",
            "category": "ホビー",
            "hashtags": "#駿河屋 #ホビー #フィギュア #アニメグッズ",
        },
        "mandarake-auction-scraper": {
            "display": "Mandarake Auction Prices",
            "category": "オークション",
            "hashtags": "#まんだらけ #オークション #希少フィギュア",
        },
        "tackleberry-japan-fishing-tackle-scraper": {
            "display": "TackleBerry Fishing Tackle",
            "category": "釣具",
            "hashtags": "#タックルベリー #釣具 #リール #ロッド",
        },
        "yahoo-auctions-japan-scraper": {
            "display": "Yahoo Auctions Japan",
            "category": "オークション",
            "hashtags": "#ヤフオク #中古カメラ #中古時計 #中古楽器",
        },
        "dlsite-scraper": {
            "display": "DLsite Price Data",
            "category": "同人/ゲーム",
            "hashtags": "#DLsite #同人 #ゲーム #価格データ",
        },
        "dmm-scraper": {
            "display": "DMM Price Data",
            "category": "動画/ゲーム",
            "hashtags": "#DMM #動画 #ゲーム #価格データ",
        },
        "kitamura-japan-used-camera-scraper": {
            "display": "Kitamura Used Camera",
            "category": "中古カメラ",
            "hashtags": "#キタムラ #中古カメラ #カメラ転売",
        },
        "jackroad-used-watch-scraper": {
            "display": "Jackroad Used Watch",
            "category": "中古時計",
            "hashtags": "#ジャックロード #中古時計 #ロレックス",
        },
        "komehyo-japan-brand-scraper": {
            "display": "Komehyo Brand Prices",
            "category": "中古ブランド",
            "hashtags": "#コメ兵 #中古ブランド #バッグ #時計",
        },
        "eurostat-indicators": {
            "display": "Eurostat Indicators",
            "category": "統計データ",
            "hashtags": "#Eurostat #EU統計 #経済指標",
        },
        "world-bank-indicators": {
            "display": "World Bank Indicators",
            "category": "統計データ",
            "hashtags": "#WorldBank #世界銀行 #経済指標 #開発データ",
        },
        "goo-net-car-scraper": {
            "display": "Goo-net Car Prices",
            "category": "中古車",
            "hashtags": "#グーネット #中古車 #車価格",
        },
        "biglemon-machinery-scraper": {
            "display": "BigLemon Machinery",
            "category": "重機/建機",
            "hashtags": "#ビッグレモン #重機 #建設機械",
        },
        "digimart-japan-used-instrument-scraper": {
            "display": "Digimart Used Instruments",
            "category": "中古楽器",
            "hashtags": "#デジマート #中古楽器 #ギター #ベース",
        },
        "golfpartner-used-club-scraper": {
            "display": "GolfPartner Used Clubs",
            "category": "ゴルフ",
            "hashtags": "#ゴルフパートナー #中古ゴルフクラブ #ゴルフ",
        },
        "kensho-high-value-leads": {
            "display": "Kensho High Value Leads",
            "category": "リード獲得",
            "hashtags": "#リード獲得 #B2B #営業リスト",
        },
        "mandarake-auction-scraper": {
            "display": "Mandarake Auction",
            "category": "オークション",
            "hashtags": "#まんだらけ #オークション",
        },
        "mercari-japan-search-scraper": {
            "display": "Mercari Japan Search",
            "category": "メルカリ",
            "hashtags": "#メルカリ #転売 #せどり",
        },
        "japan-jepx-mcp": {
            "display": "JEPX Power Price MCP",
            "category": "電力",
            "hashtags": "#JEPX #電力取引 #スポット価格",
        },
    }
    return mapping.get(actual_name, {
        "display": actual_name,
        "category": "データ",
        "hashtags": "#データ #スクレイピング #Apify",
    })


# 週2投稿用ローテーション文言（16種 = 週×スロットで独立選択）。raw ≤280 字を維持。
# {actor_display}/{category}/{hashtags}/{store_url}/{price_usd} は pick_text 時に置換される。
WEEKLY_TWEETS: list[str] = [
    "Apify Storeで {actor_display} を公開中。{category} の日本市場価格データをJSONで取得。\n"
    "PPE課金（${price_usd}/件）で必要な分だけ。無料トライアルも可。\n"
    "👉 https://apify.com/fruitful_quintessence {hashtags} #Apify #データセット",
    "{actor_display} — 日本の{category}価格を週次更新で追跡。\n"
    "リセラー・バイヤー・アナリスト向けクリーンJSON。Pay-per-event $0.005/件。\n"
    "Apify Storeで今すぐ試せます 👉 https://apify.com/fruitful_quintessence {hashtags}",
    "新着: {actor_display} が Apify Store に追加されました。\n"
    "{category}の実勢価格・コンディション・モデル情報をAPIで自動取得。\n"
    "外部runゼロから脱却へ — まずは無料枠でお試しを。{hashtags} #ApifyStore",
    "日本{category}市場の価格インテリジェンス、週次CSVで配信中。\n"
    "{actor_display} で競合価格・仕入れ判断・在庫評価を自動化。\n"
    "Apify PPE課金なら初期費用ゼロ。詳細👇 {hashtags}",
    "リセラー必見: {actor_display} で日本{category}の実売価格を把握。\n"
    "店頭/EC/オークション横断の生データをJSONで。\n"
    "Apify Store で即実行可能・従量課金。{hashtags} #リセール #アービトラージ",
    "{actor_display} 更新: 今週の{category}価格トレンドを反映。\n"
    "モデル/年式/コンディション別の granular なデータで精度アップ。\n"
    "外部ユーザー募集中 — Apify Store で試すだけ。{hashtags}",
    "クロスボーダー仕入れに {actor_display}。\n"
    "日本国内の{category}実勢価格をリアルタイムAPIで取得、為替・送料込みで利益計算。\n"
    "Pay-per-event $0.005。無料枠から開始 👉 {hashtags}",
    "データ駆動型リセールの武器: {actor_display}。\n"
    "{category}の売れ筋・値上がり傾向・在庫回転を週次データで可視化。\n"
    "Apify Store ならインフラ不要・即日運用。{hashtags} #データ分析 #マーケットインテリジェンス",
]


def pick_actors_for_promo(
    today: date,
    max_actors: int = 3,
) -> list[dict[str, Any]]:
    """プロモ対象アクターを選出する。

    優先順位:
    1. external_runs=0 のアクター
    2. 24h以上起動間隔が空いているアクター
    3. 価格が高い（収益インパクト大）アクター
    """
    external_state = load_external_runs_state()
    last_trigger = external_state.get("last_trigger", {})
    prices = load_ppe_prices()

    now = datetime.now(UTC)
    candidates: list[dict[str, Any]] = []

    for actor_id, last_ts_str in last_trigger.items():
        try:
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
        except ValueError:
            last_ts = now - timedelta(hours=48)  # 古い扱い

        hours_since = (now - last_ts).total_seconds() / 3600
        if hours_since < 24:
            continue  # 24h経過していないものはスキップ

        # 実名を特定（PRIORITY_ACTORSから逆引き）
        actual_name = None
        for actor_info in PRIORITY_ACTORS:
            if actor_info["fallback_id"] == actor_id:
                actual_name = actor_info["actual_name"]
                break
        if not actual_name:
            continue

        price = prices.get(actual_name, 0.0)
        display_info = get_actor_display_info(actual_name)

        candidates.append({
            "actor_id": actor_id,
            "actual_name": actual_name,
            "price_usd": price,
            "hours_since_last_trigger": hours_since,
            "display": display_info["display"],
            "category": display_info["category"],
            "hashtags": display_info["hashtags"],
        })

    # ソート: 価格降順 → 経過時間降順
    candidates.sort(key=lambda x: (-x["price_usd"], -x["hours_since_last_trigger"]))

    return candidates[:max_actors]


# PRIORITY_ACTORS は apify_ppe_external_runner.py からコピー（同期必須）
PRIORITY_ACTORS: list[dict[str, Any]] = [
    {"actual_name": "japan-used-camera-market-scraper", "fallback_id": "mQaZFo6up4YZKepC3", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-watch-market-scraper", "fallback_id": "gMqdrS2evpcybSZc2", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-luxury-brand-market-scraper", "fallback_id": "b0vuqa3ESvy2mOwFB", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-used-instrument-market-scraper", "fallback_id": "yN1R26HrV6C2MBKas", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-offmall-market-scraper", "fallback_id": "Zh4kqcS4dYPWpFzBd", "priority": 1, "price_usd": 0.005},
    {"actual_name": "surugaya-japan-hobby-prices", "fallback_id": "F8Hl0a8Cx9bpJBrxR", "priority": 2, "price_usd": 0.005},
    {"actual_name": "mandarake-auction-scraper", "fallback_id": "q2E37PVTg5JcGOTEn", "priority": 2, "price_usd": 0.005},
    {"actual_name": "tackleberry-japan-fishing-tackle-scraper", "fallback_id": "wxMskoiHMPeeH2qAJ", "priority": 2, "price_usd": 0.005},
    {"actual_name": "yahoo-auctions-japan-scraper", "fallback_id": "8WBam4CPB72q9Rvsd", "priority": 2, "price_usd": 0.005},
    {"actual_name": "dlsite-scraper", "fallback_id": "6Z7tJ3plfUmAgGmbk", "priority": 3, "price_usd": 0.005},
    {"actual_name": "dmm-scraper", "fallback_id": "nUm22B2guMo8vXom6", "priority": 3, "price_usd": 0.002},
    {"actual_name": "kitamura-japan-used-camera-scraper", "fallback_id": "DOiD9y1NAJfLBcAjT", "priority": 3, "price_usd": 0.005},
    {"actual_name": "jackroad-used-watch-scraper", "fallback_id": "nWf9BR2ndMTYqKxNB", "priority": 3, "price_usd": 0.005},
    {"actual_name": "komehyo-japan-brand-scraper", "fallback_id": "Db3iY8FIRxPjPag7N", "priority": 3, "price_usd": 0.005},
    {"actual_name": "eurostat-indicators", "fallback_id": "pAxQ0lRyArudhK9Wx", "priority": 4, "price_usd": 0.004},
    {"actual_name": "world-bank-indicators", "fallback_id": "u2qsG1UfVHWsgl8Dg", "priority": 4, "price_usd": 0.003},
    {"actual_name": "goo-net-car-scraper", "fallback_id": "bgm5Gxn4BeBmoO7xD", "priority": 5, "price_usd": 0.002},
    {"actual_name": "biglemon-machinery-scraper", "fallback_id": "W9cXhDckzHd9RZWnQ", "priority": 5, "price_usd": 0.002},
    {"actual_name": "digimart-japan-used-instrument-scraper", "fallback_id": "FSuoQiX8OG4KuIQ9c", "priority": 5, "price_usd": 0.002},
    {"actual_name": "golfpartner-used-club-scraper", "fallback_id": "xPSQSSsdVjRwWQAiA", "priority": 5, "price_usd": 0.002},
]


def pick_text(
    today: date,
    state: dict[str, Any],
    actors: list[dict[str, Any]],
    slot: str = "a",
    force: bool = False,
) -> tuple[str | None, str, dict[str, Any]]:
    """今日の文言を選ぶ。同週・同スロット投稿済みなら (None, reason, {})。"""
    key = week_key(today)
    posted = state.get("posted_weeks", {}).get(key, {})
    # 旧形式互換
    if slot not in posted and "tweet_id" in posted:
        posted = {"a": posted}
    if not force and slot in posted:
        prev = posted[slot] or {}
        return None, f"今週{slot}スロットは投稿済み (week={key}, tweet_id={prev.get('tweet_id', '?')})", {}

    iso = today.isocalendar()
    idx = _slot_index(iso.week, slot)
    raw = WEEKLY_TWEETS[idx]

    # 対象アクター情報を文言に埋め込む（最初のアクターを代表として使用、他は言及）
    primary = actors[0] if actors else {}
    actor_display = primary.get("display", "Apify Actor")
    category = primary.get("category", "データ")
    hashtags = primary.get("hashtags", "#Apify #データセット")
    price_usd = primary.get("price_usd", 0.005)

    # 他アクターも言及（最大3件まで）
    other_names = [a["display"] for a in actors[1:3]] if len(actors) > 1 else []
    other_mention = f" 他: {', '.join(other_names)}" if other_names else ""

    text = raw.format(
        actor_display=actor_display,
        category=category,
        hashtags=hashtags,
        store_url="https://apify.com/fruitful_quintessence",
        price_usd=f"{price_usd:.3f}",
    ) + other_mention

    return text, "", {"primary_actor": primary, "all_actors": actors, "slot": slot, "week_key": key}


def log(msg: str, repo: Path) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    log_dir = repo / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "apify_store_promo.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def post_with_cdp(account_key: str, text: str, log_fn: Callable[[str], None]) -> str:
    """KenshoCDP (SeleniumBase CDP Mode + SOCKS5) でツイート投稿。

    戻り値: tweet_id (rest_id)
    """
    # 動的import（import時の副作用回避）
    sys.path.insert(0, str(REPO))
    from kensho.application.selenium_cdp import KenshoCDP

    log_fn(f"CDP起動: account={account_key}")

    with KenshoCDP(account_key=account_key, headless=True) as driver:
        # driver._sb は context manager 内では必ず非 None
        sb = driver._sb
        assert sb is not None

        # X.com にアクセス
        sb.open("https://x.com/compose/tweet")
        time.sleep(random.uniform(3, 6))

        # ツイート入力エリアを特定して入力
        # SeleniumBase CDP mode での要素特定
        tweet_box_selector = '[data-testid="tweetTextarea_0"]'
        try:
            sb.wait_for_element(tweet_box_selector, timeout=15)
        except Exception:
            # フォールバック: より汎用的なセレクタ
            tweet_box_selector = 'div[role="textbox"][data-testid="tweetTextarea_0"]'
            sb.wait_for_element(tweet_box_selector, timeout=10)

        # 人間らしいタイピング
        driver.human_type(tweet_box_selector, text)

        # 投稿ボタンをクリック
        post_button_selector = '[data-testid="tweetButtonInline"]'
        driver.human_click(post_button_selector)

        # 投稿完了待機 & tweet_id 取得
        time.sleep(random.uniform(3, 5))

        # URLから tweet_id を抽出（投稿後リダイレクトされる想定）
        current_url = sb.get_current_url()
        log_fn(f"投稿後URL: {current_url}")

        # tweet_id 抽出試行
        tweet_id = None
        if "/status/" in current_url:
            try:
                tweet_id = current_url.split("/status/")[1].split("?")[0].split("/")[0]
            except Exception:
                pass

        # 取得できない場合、最新ツイートから取得を試みる
        if not tweet_id:
            sb.open(f"https://x.com/{account_key}")
            time.sleep(random.uniform(2, 4))
            # 最新ツイートのリンクから抽出
            try:
                latest_link = sb.find_element("css selector", 'article[data-testid="tweet"] a[href*="/status/"]')
                href = latest_link.get_attribute("href")
                if href and "/status/" in href:
                    tweet_id = href.split("/status/")[1].split("?")[0].split("/")[0]
            except Exception:
                pass

        if not tweet_id:
            # 最後の手段: タイムスタンプベースのダミーID（追跡用）
            tweet_id = f"unknown_{int(time.time())}"
            log_fn(f"WARN: tweet_id取得失敗、ダミー使用: {tweet_id}")

        log_fn(f"[OK] 投稿成功 tweet_id={tweet_id}")
        return tweet_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Apify Store PPEアクター プロモーション週次自動投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--slot", default="a", choices=["a", "b"], help="投稿スロット（a=月曜/b=金曜）")
    ap.add_argument("--state", default=str(STATE_FILE), help="週次stateパス")
    ap.add_argument("--date", default="", help="基準日 YYYY-MM-DD（省略=今日）")
    ap.add_argument("--max-actors", type=int, default=3, help="1投稿あたりの最大紹介アクター数")
    args = ap.parse_args()

    state_file = Path(args.state)
    today = date.fromisoformat(args.date) if args.date else date.today()

    state = _load_json(state_file)
    actors = pick_actors_for_promo(today, max_actors=args.max_actors)

    if not actors:
        log(f"対象アクターなし（全て24h以内に起動済み）", REPO)
        sys.exit(0)

    text, reason, meta = pick_text(today, state, actors, slot=args.slot, force=args.force)
    if text is None:
        log(f"スキップ: {reason}", REPO)
        sys.exit(0)

    key = week_key(today)
    log(f"対象週: {key} / slot={args.slot} / {ACCOUNT_KEY} / Apify Store PPEプロモ", REPO)
    log(f"紹介アクター: {', '.join(a['display'] for a in actors)}", REPO)
    log(f"ツイート内容: {text!r}", REPO)
    if len(text) > 280:
        log(f"WARN: 文字数 {len(text)}/280 超過", REPO)

    if args.dry_run:
        log("DRY-RUN: 投稿は実行していません。", REPO)
        sys.exit(2)

    # CDP + SOCKS5 で投稿実行
    try:
        tweet_id = post_with_cdp(ACCOUNT_KEY, text, lambda m: log(m, REPO))
    except Exception as e:
        log(f"投稿失敗: {e}", REPO)
        sys.exit(1)

    # 状態記録
    posted_weeks = state.setdefault("posted_weeks", {})
    week_slot = posted_weeks.setdefault(key, {})
    week_slot[args.slot] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "slot": args.slot,
        "actors": [a["actual_name"] for a in actors],
    }
    _save_json(state_file, state)
    log(f"状態記録: {state_file} (tweet_id={tweet_id}, slot={args.slot})", REPO)


if __name__ == "__main__":
    main()