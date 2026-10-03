#!/usr/bin/env python3
"""external_traffic_tracker — UTM経由/Gumroad無料サンプルクリック等の外部流入を記録.

背景:
- Gumroad referrers は 'Direct, email, IM' のみで Twitter/X キー欠損
- X GraphQL に url_clicks/user_clicks/impression が存在しない（構造的計測不能）
- 既存の gumroad_promo_kpi.py は sales/views のみで、どの外部導線から来たか不明

本スクリプトの役割:
- cron の X 販促投稿（gumroad_promo_weekly.py）実行時に UTM キーを記録
- devto 記事公開時に記事URL＋CTAリンクを記録
- Apify Store 外部SEO監視（apify_visibility_watch.py）結果を記録
- 「どこから来たか」が分かる状態ファイルを作成

使用方法:
  python scripts/external_traffic_tracker.py --track devto --article-id 4760098
  python scripts/external_traffic_tracker.py --track x-post --campaign w2026W40_a --tweet-id 2104355452087882033
  python scripts/external_traffic_tracker.py --track apify-seo --actor surugaya-japan-hobby-prices --rank 12
  python scripts/external_traffic_tracker.py --show           # 全記録表示
  python scripts/external_traffic_tracker.py --kpi           # KPI要約（stdout出力）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_DIR / "data" / "external_traffic_state.json"


def _now_iso() -> str:
    return datetime.now().isoformat()


def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"events": [], "summary": {}, "updated_at": None}


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _now_iso()
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def track_devto_article(article_id: int, title: str, url: str, cta_links: list[str] | None = None) -> dict[str, Any]:
    """devto 記事公開を記録。CTA(Gumroad)リンクも併記。"""
    state = load_state()
    event = {
        "type": "devto_publish",
        "article_id": article_id,
        "title": title,
        "url": url,
        "cta_links": cta_links or [],
        "recorded_at": _now_iso(),
    }
    state["events"].append(event)
    # 重複チェック
    existing_ids = {e.get("article_id") for e in state["events"] if e.get("type") == "devto_publish"}
    if article_id in existing_ids and len(state["events"]) > 1:
        state["events"].pop()  # 直前のものを除去（直前が重複）
        state["events"].append(event)
    save_state(state)
    print(f"[TRACKED] devto article #{article_id}: {url}")
    return event


def track_x_post(campaign: str, tweet_id: str, actor_names: list[str] | None = None) -> dict[str, Any]:
    """X 販売促進投稿を記録。"""
    state = load_state()
    event = {
        "type": "x_promo_post",
        "campaign": campaign,
        "tweet_id": tweet_id,
        "actor_names": actor_names or [],
        "recorded_at": _now_iso(),
    }
    state["events"].append(event)
    save_state(state)
    print(f"[TRACKED] X post campaign={campaign} tweet={tweet_id}")
    return event


def track_apify_seo(actor_name: str, rank: int, query: str | None = None) -> dict[str, Any]:
    """Apify Store SEO ランク変動を記録。"""
    state = load_state()
    event = {
        "type": "apify_seo_watch",
        "actor_name": actor_name,
        "rank": rank,
        "query": query,
        "recorded_at": _now_iso(),
    }
    state["events"].append(event)
    save_state(state)
    print(f"[TRACKED] Apify SEO: {actor_name} rank={rank}")
    return event


def show_events() -> None:
    state = load_state()
    events = state.get("events", [])
    if not events:
        print("No events recorded.")
        return
    print(f"Total events: {len(events)}")
    by_type: dict[str, int] = {}
    for e in events:
        t = e.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    print(f"By type: {json.dumps(by_type, ensure_ascii=False)}")
    print("---")
    for e in events[-20:]:
        print(f"  [{e.get('recorded_at','?')}] {e.get('type')}")
        if e.get("type") == "devto_publish":
            print(f"    id={e.get('article_id')} url={e.get('url')}")
            print(f"    CTAs: {e.get('cta_links', [])}")
        elif e.get("type") == "x_promo_post":
            print(f"    campaign={e.get('campaign')} tweet={e.get('tweet_id')}")
        elif e.get("type") == "apify_seo_watch":
            print(f"    actor={e.get('actor_name')} rank={e.get('rank')}")


def compute_kpi() -> dict[str, Any]:
    state = load_state()
    events = state.get("events", [])
    devto_count = sum(1 for e in events if e.get("type") == "devto_publish")
    x_post_count = sum(1 for e in events if e.get("type") == "x_promo_post")
    seo_count = sum(1 for e in events if e.get("type") == "apify_seo_watch")
    # カンペーン別 X 投稿数
    campaigns = {}
    for e in events:
        if e.get("type") == "x_promo_post":
            c = e.get("campaign", "unknown")
            campaigns[c] = campaigns.get(c, 0) + 1
    return {
        "total_events": len(events),
        "devto_articles_published": devto_count,
        "x_promo_posts": x_post_count,
        "apify_seo_watches": seo_count,
        "campaigns": campaigns,
        "last_updated": state.get("updated_at"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="外部流入トラッカー")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_devto = sub.add_parser("devto", help="devto記事公開を記録")
    p_devto.add_argument("--article-id", type=int, required=True)
    p_devto.add_argument("--title", required=True)
    p_devto.add_argument("--url", required=True)
    p_devto.add_argument("--cta-links", nargs="*", default=[], help="Gumroad等CTA URL")

    p_x = sub.add_parser("x", help="X販売促進投稿を記録")
    p_x.add_argument("--campaign", required=True)
    p_x.add_argument("--tweet-id", required=True)
    p_x.add_argument("--actors", nargs="*", default=[])

    p_seo = sub.add_parser("seo", help="Apify SEO ランクを記録")
    p_seo.add_argument("--actor", required=True)
    p_seo.add_argument("--rank", type=int, required=True)
    p_seo.add_argument("--query", default=None)

    sub.add_parser("show", help="全イベントを表示")
    sub.add_parser("kpi", help="KPI要約を出力")

    args = ap.parse_args()

    if args.cmd == "devto":
        track_devto_article(args.article_id, args.title, args.url, args.cta_links)
    elif args.cmd == "x":
        track_x_post(args.campaign, args.tweet_id, args.actors)
    elif args.cmd == "seo":
        track_apify_seo(args.actor, args.rank, args.query)
    elif args.cmd == "show":
        show_events()
    elif args.cmd == "kpi":
        kpi = compute_kpi()
        print(json.dumps(kpi, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
