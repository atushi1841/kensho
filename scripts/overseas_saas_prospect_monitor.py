#!/usr/bin/env python3
"""
scripts/overseas_saas_prospect_monitor.py

海外indie hacker / SaaS 関連の「需要投稿」を日次収集し、自分の商品
(Gumroad agyhq データセット + Apify 日本中古市場価格スクレイパ群) とマッチして
提案DM の下書きを自動生成する。

設計原則 (タスク t_13381de5):
  - TOS 遵守: 収集は HN Algolia 公式API (無料・認証不要・レート制限遵守) が主ソース。
    Reddit 公式API / X 自アカウントのみ は別チャネルとして拡張可能にしておく。
  - 決して自動送信しない。生成するのは「提案DM下書き」のみ。
    送信は人間(ユーザー)が最終判断して手動で行う。スパムにならないよう
    1投稿あたり1下書き、自然な文言で、過剰なリンクは避ける。
  - 収益目標: 3-5千円/契約 × 5-10件 = 月1-3万円。

分類できない/低品質の投稿はスキップ。マッチ度スコアで上位のみ下書き化。

出力:
  - stdout サマリ
  - data/overseas_prospects/_leads_YYYYMMDD.json  生ヒット
  - data/overseas_prospects/_drafts_YYYYMMDD.json 提案DM下書き
  - reports/revenue-proposals/2026-09-05-overseas-saas-monitor.md レポート

使い方:
  python scripts/overseas_saas_prospect_monitor.py            # HN Algolia 収集+下書き生成
  python scripts/overseas_saas_prospect_monitor.py --dry-run  # 下書きファイル書き出しなし
  python scripts/overseas_saas_prospect_monitor.py --limit 25
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data" / "overseas_prospects"
REPORTS_DIR = REPO / "reports" / "revenue-proposals"

USER_AGENT = "kensho-overseas-prospect-monitor/1.0 (research; TOS-compliant rate-limited)"


# ── 商品カタログ ──
# 自分の売っているもの。提案DMはこのカタログにマッチさせて下書き化される。
@dataclass
class Product:
    name: str
    description: str
    url: str
    price: str
    # マッチ用キーワード (小文字で判定)
    keywords: list[str] = field(default_factory=list)
    # 提案DMの「1行ピッチ」
    pitch: str = ""


def _build_products() -> list[Product]:
    """実商品リスト (URL を一意に、かつ正確に)。

    キーワードは「高精度(狭義)」に徹底。'dataset' 'scrape' 'tool' 'japan' 'price'
    のような一般語は単独では使わない(無関係投稿への偽陽性=スパムになる)。
    """
    return [
        Product(
            name="Japanese Anime Figure & Collectibles Market Price Dataset (Weekly CSV)",
            description="Japanese figures, hobby & collectibles used-market price "
            "data as a weekly CSV with price history.",
            url="https://atushi5.gumroad.com/l/agyhq",
            price="$29.99 flat",
            keywords=[
                "anime figure",
                "figure market",
                "collectible price",
                "collectibles price",
                "anime price",
                "toy resale",
                "figure resale",
                "hobby market price",
                "collector price guide",
                "japanese figures",
            ],
            pitch="a weekly Japanese anime figure & collectibles price dataset (CSV) with price history",
        ),
        Product(
            name="Mercari Japan Search Scraper",
            description="Search Mercari Japan listings; used prices in JPY with condition & seller data.",
            url="https://apify.com/apitor/mercari-japan-search-scraper",
            price="$0.002 / result",
            keywords=["mercari", "mercari japan"],
            pitch="a Mercari Japan listings scraper (used prices in JPY)",
        ),
        Product(
            name="Yahoo Auctions Japan Scraper",
            description="Yahoo! Auctions Japan listing prices and data as clean JSON.",
            url="https://apify.com/apitor/yahoo-auctions-japan-scraper",
            price="$0.002 / result",
            keywords=["yahoo auctions", "yahoo auction japan", "auction japan pricing"],
            pitch="a Yahoo Auctions Japan scraper (live bid/listing prices)",
        ),
        Product(
            name="Surugaya Japan Hobby Prices",
            description="Hobby/used goods price data from Suruga-ya (Japanese hobby marketplace).",
            url="https://apify.com/apitor/surugaya-japan-hobby-prices",
            price="$0.002 / result",
            keywords=["surugaya", "suruga-ya"],
            pitch="a Suruga-ya (Japanese hobby marketplace) price scraper",
        ),
        Product(
            name="Japan Used Camera Market Scraper",
            description="Used camera prices from Kitamura, Fujiya & Map Camera in JPY.",
            url="https://apify.com/apitor/japan-used-camera-market-scraper",
            price="$0.005 / result",
            keywords=[
                "used camera price",
                "used camera japan",
                "camera resale japan",
                "fujiya camera",
                "kitamura price",
                "map camera",
                "secondhand camera japan",
            ],
            pitch="a Japanese used-camera price scraper (Kitamura / Fujiya / Map Camera)",
        ),
        Product(
            name="Japan Watch Market Scraper",
            description="Used luxury watch prices from Jackroad, Kitamura & Komehyo.",
            url="https://apify.com/apitor/japan-watch-market-scraper",
            price="$0.005 / result",
            keywords=[
                "used watch price",
                "luxury watch resale",
                "grand seiko price",
                "rolex used price",
                "jackroad",
                "watch japan market",
                "secondhand watch japan",
            ],
            pitch="a Japanese used-luxury-watch price scraper (Jackroad / Kitamura / Komehyo)",
        ),
        Product(
            name="Japan Luxury Brand Market Scraper",
            description="Pre-owned luxury prices from Komehyo, Jackroad & Brand Off (bags, wallets, watches).",
            url="https://apify.com/apitor/japan-luxury-brand-market-scraper",
            price="$0.005 / result",
            keywords=[
                "luxury bag resale",
                "used hermes price",
                "pre-owned luxury japan",
                "brand off japan",
                "komehyo",
                "chanel used price",
                "designer bag resale japan",
            ],
            pitch="a Japanese pre-owned luxury/bag price scraper (Komehyo / Jackroad / Brand Off)",
        ),
        Product(
            name="Japan Used Instrument Market Scraper",
            description="Used musical instrument prices from Digimart & Ishibashi (guitars, synths, audio).",
            url="https://apify.com/apitor/japan-used-instrument-market-scraper",
            price="$0.005 / result",
            keywords=[
                "used guitar price",
                "guitar japan price",
                "used synth",
                "digimart",
                "ishibashi",
                "secondhand instrument japan",
                "fender used japan",
            ],
            pitch="a Japanese used-instrument price scraper (Digimart / Ishibashi)",
        ),
        Product(
            name="Japan Used Goods Prices via OffMall (Hard Off)",
            description="Used-goods prices across 800+ Hard Off / OffMall second-hand stores.",
            url="https://apify.com/apitor/japan-offmall-market-scraper",
            price="$0.005 / result",
            keywords=[
                "hard off",
                "offmall",
                "hardoff japan",
                "second hand japan",
                "recycle shop japan",
                "used goods japan",
            ],
            pitch="a Japan-wide used-goods price scraper (Hard Off OffMall, 800+ stores)",
        ),
    ]


# 需要シグナル (投稿タイトル/本文に見えたら「探してる/助けて/tool 需要」と判定)
DEMAND_PATTERNS = [
    "looking for",
    "look for",
    "need a tool",
    "need help",
    "need to find",
    "is there a",
    "any tool",
    "which tool",
    "recommend",
    "how do i find",
    "how to scrape",
    "scraping tool",
    "price data",
    "dataset",
    "api for",
    "track prices",
    "price monitor",
    "resale",
    "arbitrage",
    "japan market",
    "help me build",
    "anyone know",
    "better way to",
    "tool to",
]


def proposal_template(p: Product) -> str:
    """商品ごとの再利用可能な提案DMテンプレート (下書き生成用・人が使う基盤)。

    投稿にマッチしたときは build_draft() がこのテンプレに投稿固有の冒頭を被せる。
    需要シグナルが弱い週でも、テンプレは常に出力され「いつでも使える下書き」として残る。
    """
    return (
        f"If you're researching {p.description.lower().rstrip('.')}, "
        f"I have {p.pitch} — {p.price}. It returns clean JSON/CSV, "
        f"and it's live today. Happy to send a small sample: {p.url}"
    )


def now_jst() -> datetime:
    return datetime.now(JST)


def http_get(url: str, timeout: int = 20) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def fetch_hn_algolia(query: str, tags: str, hits: int) -> list[dict[str, Any]]:
    """HN Algolia 公式API (無料・認証不要)。需要キーワード検索で投稿を拾う。

    日次モニタのため created_at_i (epoch seconds) で直近 RECENT_DAYS 以内に絞り込む。
    Algolia の検索は関連度順なので、API側で日付フィルタしないと古い投稿ばかり返る。
    """
    import urllib.parse

    q = urllib.parse.quote(query)
    cutoff = int((datetime.now(UTC) - timedelta(days=RECENT_DAYS)).timestamp())
    numeric = f"created_at_i>{cutoff}"
    url = f"https://hn.algolia.com/api/v1/search?query={q}&tags={tags}&hitsPerPage={hits}&numericFilters={numeric}"
    body = http_get(url)
    if not body:
        return []
    try:
        return json.loads(body).get("hits") or []
    except json.JSONDecodeError:
        return []


def hn_story_to_item(hit: dict[str, Any]) -> dict[str, Any] | None:
    text = (hit.get("title") or "") + " " + (hit.get("story_text") or "")
    if not text.strip():
        return None
    oid = hit.get("objectID", "")
    return {
        "source": "HN Algolia",
        "source_id": f"HN:{oid}",
        "title": hit.get("title") or "",
        "text": (hit.get("story_text") or "")[:1200],
        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
        "author": hit.get("author") or "",
        "points": hit.get("points") or 0,
        "comments": hit.get("num_comments") or 0,
        "created_at": hit.get("created_at") or "",
        "tags": hit.get("_tags") or [],
    }


def is_demand(item: dict[str, Any]) -> bool:
    hay = f"{item.get('title', '')} {item.get('text', '')}".lower()
    return any(p in hay for p in DEMAND_PATTERNS)


def match_products(item: dict[str, Any]) -> list[Product]:
    hay = f"{item.get('title', '')} {item.get('text', '')}".lower()
    scored: list[tuple[float, Product]] = []
    for p in _build_products():
        score = 0.0
        for kw in p.keywords:
            if kw in hay:
                score += 1.0
        # 汎用だけ引っかかったもの(price/dataset/scrape/japan 単体)は除外。
        # 商品固有キーワードが1つも当たらなければマッチしない(=スパム防止)。
        # list 内の 'japan' 等は商品固有キーとの複合表現に限るため、ここでは使わない。
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:2]]


# 日次モニタなので「直近N日以内」に限定 (HN Algolia の created_at は UTC)
RECENT_DAYS = 7


def _parse_created(created: str) -> datetime | None:
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_recent(item: dict[str, Any]) -> bool:
    dt = _parse_created(item.get("created_at") or "")
    if not dt:
        return False
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_DAYS)
    return dt >= cutoff


def build_draft(item: dict[str, Any], products: list[Product]) -> str | None:
    """1投稿→1提案DM下書き。自然な文言・リンク1件のみ。"""
    if not products:
        return None
    author = (item.get("author") or "").strip() or "there"
    top = products[0]
    # 投稿タイトルをコンパクトに
    title = (item.get("title") or "").strip()
    if len(title) > 90:
        title = title[:87] + "…"
    extra = ""
    if len(products) > 1:
        extra = f" (and if you go wider, I also have {', '.join(p.name for p in products[1:])})"
    return (
        f'Hi {author} — saw your post "{title}". If you\'re still looking, I have '
        f"{top.pitch} — fits a lot of the {', '.join(top.keywords[:2])} use cases you "
        f"mentioned. It's {top.price}. Here's the link if you want to check it out: "
        f"{top.url}. Happy to share a sample too if useful{extra}. "
        f"No pressure, just figured it might save you the build."
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="下書きファイル書き出しなし")
    ap.add_argument("--limit", type=int, default=30, help="1クエリあたりのヒット上限")
    args = ap.parse_args()

    ts = now_jst()
    stamp = ts.strftime("%Y%m%d")

    # ── 1) 収集: HN Algolia (需要キーワード検索) ──
    # タグ: story / ask_hn / show_hn を組み合わせて広めに拾う。
    # 再現率(recall)は広く、精度は match_products() の高精度キーワードで担保。
    queries = [
        ("looking for", "ask_hn"),
        ("need a tool", "ask_hn"),
        ("price data", "ask_hn"),
        ("scrape", "ask_hn"),
        ("japan market", "ask_hn"),
        ("mercari", "story"),
        ("yahoo auctions", "story"),
        ("price scraper", "ask_hn"),
        ("price tracking", "ask_hn"),
        ("resale automation", "ask_hn"),
        ("data scraping", "ask_hn"),
        ("marketplace api", "ask_hn"),
        ("collectibles market", "ask_hn"),
        ("japan import", "ask_hn"),
        ("used goods", "ask_hn"),
        ("ecommerce scraper", "ask_hn"),
        ("how do you source", "ask_hn"),
        ("pricing data", "ask_hn"),
    ]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for query, tag in queries:
        hits = fetch_hn_algolia(query, tag, args.limit)
        for h in hits:
            item = hn_story_to_item(h)
            if not item or item["source_id"] in seen:
                continue
            seen.add(item["source_id"])
            items.append(item)

    # 需要シグナルで絞り、直近N日以内の投稿に限定。マッチしてないものは下書き化しない
    candidates = [it for it in items if is_demand(it) and is_recent(it)]
    # 新しい順にソート
    candidates.sort(key=lambda it: it.get("created_at") or "", reverse=True)

    drafts: list[dict[str, Any]] = []
    for it in candidates:
        prods = match_products(it)
        draft = build_draft(it, prods)
        if draft:
            drafts.append({
                "lead": {
                    "source": it["source"],
                    "source_id": it["source_id"],
                    "title": it["title"],
                    "url": it["url"],
                    "author": it["author"],
                    "created_at": it["created_at"],
                },
                "matched_products": [p.name for p in prods],
                "draft": draft,
            })

    # ── 2) 出力 ──
    print("=" * 72)
    print(f"Overseas SaaS 需要モニタ {ts.isoformat()}")
    print("=" * 72)
    print(f"  収集ヒット: {len(items)}  |  需要シグナル: {len(candidates)}  |  提案下書き: {len(drafts)}")
    print()
    for d in drafts:
        lead = d["lead"]
        print(f"◆ [{lead['source_id']}] {lead['created_at']}")
        print(f"    {lead['title']}")
        print(f"    {lead['url']}")
        print(f"    match: {', '.join(d['matched_products'])}")
        print("    --- 下書き ---")
        print(f"    {d['draft']}")
        print()

    if args.dry_run:
        return 0

    # ファイル保存
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(candidates, open(DATA_DIR / f"_leads_{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(drafts, open(DATA_DIR / f"_drafts_{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 再利用可能なテンプレート型ファイル (需要が少ない週でも常に最新化される)
    templates_out = [
        {"product": p.name, "price": p.price, "url": p.url, "template": proposal_template(p)} for p in _build_products()
    ]
    json.dump(templates_out, open(DATA_DIR / "_templates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # レポート
    report = build_report(ts, items, candidates, drafts)
    report_path = REPORTS_DIR / "2026-09-05-overseas-saas-monitor.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n保存: {DATA_DIR / f'_leads_{stamp}.json'} / _drafts_{stamp}.json / _templates.json")
    print(f"レポート: {report_path}")
    return 0


def build_report(
    ts: datetime, items: list[dict[str, Any]], candidates: list[dict[str, Any]], drafts: list[dict[str, Any]]
) -> str:
    lines: list[str] = []
    lines.append("# 海外SaaS 需要モニタ & 提案DM 下書き (2026-09-05)")
    lines.append("")
    lines.append("- 生成: " + ts.isoformat())
    lines.append(f"- 収集ヒット: {len(items)} / 需要シグナル: {len(candidates)} / 提案下書き: {len(drafts)}")
    lines.append("- 収集源: HN Algolia 公式API (無料・レート制限遵守)。Reddit公式API/X自垢は次フェーズで拡張")
    lines.append("- 方針: すべて【下書きのみ】。自動送信はしない。送信可否はユーザー最終判断。")
    lines.append("")
    lines.append("## 商品カタログ (マッチ対象)")
    lines.append("")
    lines.append("| 商品 | 価格 | URL |")
    lines.append("|------|------|-----|")
    for p in _build_products():
        lines.append(f"| {p.name} | {p.price} | {p.url} |")
    lines.append("")
    lines.append("## 再利用可能な提案DMテンプレート (商品別・常備)")
    lines.append("")
    lines.append("需要投稿に直接マッチしなくても、人がいつでも使える下書きを常備している。")
    lines.append("")
    for p in _build_products():
        lines.append(f"### {p.name} ({p.price})")
        lines.append("")
        lines.append(f"- URL: {p.url}")
        lines.append("```")
        lines.append(proposal_template(p))
        lines.append("```")
        lines.append("")
    lines.append("## 提案DM 下書き一覧 (本日ヒット)")
    lines.append("")
    for d in drafts:
        lead = d["lead"]
        lines.append(f"### {lead['title']}")
        lines.append("")
        lines.append(f"- ソース: {lead['source_id']} / {lead['created_at']}")
        lines.append(f"- URL: {lead['url']}")
        lines.append(f"- マッチ: {', '.join(d['matched_products'])}")
        lines.append("")
        lines.append("```")
        lines.append(d["draft"])
        lines.append("```")
        lines.append("")
    if not drafts:
        lines.append("(本日、直近7日の需要投稿に十分なマッチなし。テンプレートは上記から手動利用可能)")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
