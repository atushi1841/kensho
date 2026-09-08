#!/usr/bin/env python3
"""
kensho-non-api-revenue-hunter.py

Apify/RapidAPI 以外の「自動収益の種」を探索する。
ターゲット領域:
  - ノート/電子書籍(note.com, Kindle Direct Publishing, Booth, Lemon8)
  - アプリ(App Store, Google Play, indie devs の独自動画)
  - ゲーム(Roblox, itch.io, Game Jolt, Steam Direct)
  - TikTok 物販(中国OEM, Print on Demand, アフィリエイト)
  - マーケットプレイス手数料系(自動出品ツール需要)

既存の kensho-research-agent/kensho-research-agent-monetize と補完関係。
それらが「Apify/RapidAPI 周辺の最適化」を担当するのに対し、
本スクリプトは「 Kensho の既存スキルで自動化できる非API収益の種」を担当する。

出力: cron 経由でレポートを profiles/kensho-sweeps/cron/output/<job_id>/ に書き出し、
    重要度中以上なら Kanban に kensho-revenue-worker 宛で投入する。
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
PROFILE = "kensho-sweeps"
JOB_ID = os.environ.get("HERMES_JOB_ID", "non-api-hunter")


# HOME環境変数はWSL/profileで違う場合がある。/etc/passwdの実homeを優先。
def _real_home() -> Path:
    import pwd

    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, ImportError):
        return Path(os.environ.get("HOME") or str(Path.home()))


OUT_DIR = _real_home() / ".hermes" / "profiles" / PROFILE / "cron" / "output" / JOB_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
WORKDIR = Path("/mnt/d/Project2/kensho")

# 重複判定用に scripts/kanban_norm.py を import。同じ正規化ルールを
# kanban_hn_cleanup.py と共有することで、Run を跨いだ重複作成を防ぐ。
sys.path.insert(0, str(WORKDIR / "scripts"))
try:
    from kanban_norm import dedup_key as _dedup_key  # type: ignore
    from kanban_norm import extract_hn_item_id as _extract_hn_item_id  # type: ignore
    from kanban_norm import is_duplicate as _kanban_is_duplicate  # type: ignore
    from kanban_norm import is_duplicate_hn_id as _is_duplicate_hn_id  # type: ignore
except ImportError as _e:  # pragma: no cover - import 失敗は致命的
    sys.stderr.write(f"[hunter] kanban_norm import error: {_e}\n")
    raise

# 品質ゲート (t_2e20f1ef critic_proposal v58):
#   低シグナル Show HN の一括投入が loop_health を 95→70 に低下させたため、
#   (1) score ゲート (2) monetization シグナル ゲート (3) 1実行あたり投入上限
#   (4) HN item_id 主キー dedup を追加する。
MIN_HN_SCORE = 3  # score < MIN_HN_SCORE は低シグナルとしてスキップ (要件1: score<3)
MAX_KANBAN_PER_RUN = 3  # 1実行で新規作成する ready タスクの上限 (投入ペース制御)

# monetization モデルを示す語 (本文/タイトルに無ければスキップ)。
# 有料/データ販売/API化/サブスク/ストア販売/手数料/アフィリエイト 等。
MONETIZATION_PATTERNS = [
    r"\b(paid|pricing|price|premium|subscription|subscripti[onoe]d?|saas|billed|billing)\b",
    r"\b(mrr|arr|revenue|monetiz\w*|income|profit|sales|sell|selling|sold)\b",
    r"\b(api|sdk|webhook|endpoint)\b",
    r"\b(datan?set|dataset|data sale|download|dl sale|digital download)\b",
    r"\b(affiliate|sponsor|donation|tipjar|patron|crowdfund\w*)\b",
    r"\b(store|marketplace|steam|itch\.io|app store|play store|producthunt launch)\b",
    r"\b(freemium|tier|license|licensing|enterprise|seat)\b",
    r"(有料|販売|収益|マネタイズ|サブスク|課金|価格|手数料|アフィリ|データ販売|api化)",
]

# 探索ソース (RSS/JSON API で軽量に取得できるもの中心)
SOURCES = [
    {
        "name": "Hacker News (Show HN / Launch HN)",
        "url": "https://hacker-news.firebaseio.com/v0/showstories.json",
        "kind": "hn_ids",
        "limit": 30,
        "weight": "高",
        "rationale": "ローンチ直後のプロダクトが並ぶ。1-7日以内なら新規性高",
    },
    {
        "name": "Hacker News (Ask HN: 週次収益報告)",
        "url": "https://hacker-news.firebaseio.com/v0/askstories.json",
        "kind": "hn_ids",
        "limit": 30,
        "weight": "中",
        "rationale": "個人開発者の実収益が見える。自動化可能性の参考に",
    },
    {
        "name": "ProductHunt 本日ローンチ (RSS/Atom)",
        "url": "https://www.producthunt.com/feed",
        "kind": "rss",
        "limit": 20,
        "weight": "中",
        "rationale": "ローンチ翌日に需要ピーク。Kensho既存スクレイパで再現可能",
    },
    {
        "name": "Hacker News ベスト (収益関連)",
        "url": "https://hacker-news.firebaseio.com/v0/beststories.json",
        "kind": "hn_ids",
        "limit": 40,
        "weight": "中",
        "rationale": "HNで伸びてる= 既にユーザーが付いた=需要の実証",
    },
    {
        "name": "Booth (国内DL販売) 新着",
        "url": "https://booth.pm/ja/items?sort=new",
        "kind": "html",
        "limit": 1,
        "weight": "中",
        "rationale": "国内DL販売の最前線。テンプレ/素材/ツール需要",
    },
    {
        "name": "Qiita 週間新着 (技術記事/自動化の文脈)",
        "url": "https://qiita.com/api/v2/items?page=1&per_page=20",
        "kind": "json",
        "limit": 20,
        "weight": "低",
        "rationale": "国内で自動化がどう語られているか",
    },
]


# 自動収益の「種」を抽出するキーワードパターン
# 重要度判定は (Kensho既存スキルで実装可能) × (市場需要) の積
SEED_PATTERNS = [
    # カテゴリ: アプリ/ゲーム/ノート/TikTok
    {
        "category": "アプリ/ツール",
        "patterns": [
            r"\bshow hn\b",  # Show HN: 単体で「新規プロダクト公開」のシグナル
            r"\blaunch hn\b",
            r"\b(mobile|ios|android|app)\b.{0,80}\b(revenue|mrr|arr|users|downloads|sales)\b",
            r"\b(launched|shipped|released)\b.{0,80}\b(app|tool|saas)\b",
        ],
        "automation_keywords": ["scrape", "scraping", "automation", "bot", "auto", "cron", "scheduled", "ai", "agent"],
        "exclude": ["rapidapi", "apify actor", r"actor$"],
        "weight": "高",
    },
    {
        "category": "ゲーム/インタラクティブ",
        "patterns": [
            r"\b(roblox|itch\.io|gamejolt|steam)\b",
            r"\b(playable|web game|game jam)\b",
        ],
        "automation_keywords": ["asset", "template", "generation", "ai art", "procedural"],
        "exclude": ["rapidapi", "actor"],
        "weight": "中",
    },
    {
        "category": "ノート/電子書籍/情報商材",
        "patterns": [
            r"\b(note\.com|kindle|booth|gumroad|lemonsqueezy|payhip|substack)\b",
            r"\b(ebook|newsletter|paid newsletter)\b",
        ],
        "automation_keywords": ["content generation", "auto-write", "ai writer", "scraping", "automation"],
        "exclude": ["rapidapi"],
        "weight": "高",
    },
    {
        "category": "TikTok/動画物販",
        "patterns": [
            r"\b(tiktok|reels|shorts|youtube shorts)\b",
            r"\b(print[- ]on[- ]demand|printful|teepublic|redbubble|merch)\b",
            r"\b(ugc|creator fund)\b",
        ],
        "automation_keywords": ["video", "tiktok automation", "auto-post", "content pipeline", "ugc", "ai"],
        "exclude": [],
        "weight": "高",
    },
    {
        "category": "マーケットプレイス/物販自動化",
        "patterns": [
            r"\b(mercari|ebay|amazon|fba|etsy|shopee)\b.{0,80}\b(automation|bot|tool|seller|flip)\b",
        ],
        "automation_keywords": ["bot", "auto-listing", "scraping", "price monitor"],
        "exclude": ["rapidapi", r"actor$"],
        "weight": "中",
    },
    {
        "category": "自動化サービス受託/教材",
        "patterns": [
            r"\b(consulting|freelance|service|agency)\b.{0,80}\b(automation|scraping|bot)\b",
            r"\b(course|tutorial|udemy|note premium)\b",
        ],
        "automation_keywords": ["scraping", "selenium", "playwright", "bot"],
        "exclude": ["rapidapi"],
        "weight": "中",
    },
    {
        "category": "AIエージェント/自動収益関連 (広め)",
        "patterns": [
            r"\bmcp\b.{0,80}\b(server|tool|integration)\b",
            r"\b(ai agent|agents?)\b.{0,80}\b(revenue|mrr|monetize|sell|productize)\b",
            r"\b(weekly|monthly|my).{0,20}\b(revenue|mrr|arr|earnings|sales|profit)\b",
        ],
        "automation_keywords": ["automation", "cron", "scraping", "bot"],
        "exclude": ["rapidapi"],
        "weight": "中",
    },
]


def http_get(url, timeout=15, headers=None):
    """軽量HTTP GET。失敗時は None"""
    try:
        req = urllib.request.Request(
            url,
            headers=headers
            or {
                "User-Agent": "kensho-non-api-revenue-hunter/1.0 (research)",
                "Accept": "application/json, text/html, application/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers.get("content-type", "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, str(e)


def fetch_hn_story(item_id):
    """HN個別記事"""
    body, _ = http_get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def fetch_hn_list(url, limit):
    """HN IDリスト → 記事配列"""
    body, _ = http_get(url)
    if not body:
        return []
    try:
        ids = json.loads(body)[:limit]
    except json.JSONDecodeError:
        return []
    items = []
    for iid in ids:
        item = fetch_hn_story(iid)
        if item and item.get("type") == "story":
            items.append({
                "title": item.get("title", ""),
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={iid}",
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "hn_url": f"https://news.ycombinator.com/item?id={iid}",
                "text": item.get("text", ""),
            })
    return items


def fetch_reddit_json(url, limit):
    body, _ = http_get(url)
    if not body:
        return []
    try:
        d = json.loads(body)
        items = []
        for child in d.get("data", {}).get("children", [])[:limit]:
            data = child.get("data", {})
            items.append({
                "title": data.get("title", ""),
                "url": "https://reddit.com" + data.get("permalink", ""),
                "score": data.get("score", 0),
                "comments": data.get("num_comments", 0),
                "text": (data.get("selftext") or "")[:1000],
                "subreddit": data.get("subreddit", ""),
            })
        return items
    except json.JSONDecodeError:
        return []


def fetch_qiita_json(url, limit):
    body, _ = http_get(url)
    if not body:
        return []
    try:
        d = json.loads(body)
        if not isinstance(d, list):
            return []
        items = []
        for item in d[:limit]:
            items.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "score": item.get("stocks_count", 0) + item.get("likes_count", 0),
                "comments": 0,
                "text": (item.get("body") or "")[:1000],
            })
        return items
    except json.JSONDecodeError:
        return []


def fetch_html_strip(url, limit):
    """HTMLから商品タイトルらしきものを抽出 (Booth用)"""
    body, _ = http_get(url, timeout=20)
    if not body:
        return []
    try:
        text = body.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return []
    items = []
    # Booth: 商品名っぽいテキストを name 属性や link text から拾う
    # <a class="...">商品名</a> 形式
    for m in re.finditer(r'<a[^>]+href="(/ja/items/[0-9]+)"[^>]*>(.*?)</a>', text, re.DOTALL):
        href = m.group(1)
        raw = re.sub(r"<[^>]+>", " ", m.group(2))
        raw = re.sub(r"\s+", " ", raw).strip()
        if raw and len(raw) > 3 and len(raw) < 200:
            items.append({
                "title": raw,
                "url": "https://booth.pm" + href,
                "score": 0,
                "comments": 0,
                "text": "",
            })
        if len(items) >= 50:
            break
    if items:
        return items[:limit]
    # フォールバック: <title> 要素
    for m in re.finditer(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL):
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        if title and len(title) > 3 and "booth" not in title.lower():
            items.append({
                "title": title,
                "url": url,
                "score": 0,
                "comments": 0,
                "text": "",
            })
        if len(items) >= 50:
            break
    return items[:limit]


def fetch_rss(url, limit):
    """Atom/RSS両対応の簡易パーサ (依存ライブラリなし)"""
    body, _ = http_get(url, timeout=20)
    if not body:
        return []
    try:
        text = body.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return []
    items = []
    # Atom形式 (ProductHunt, GitHub Releases等)
    for entry in re.finditer(r"<entry[^>]*>(.*?)</entry>", text, re.DOTALL | re.IGNORECASE):
        block = entry.group(1)
        title_m = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
        # link は self/alternate どちらでも
        link_m = re.search(r'<link[^>]+href="([^"]+)"', block)
        content_m = re.search(r"<content[^>]*>(.*?)</content>", block, re.DOTALL)
        summary_m = re.search(r"<summary[^>]*>(.*?)</summary>", block, re.DOTALL)
        title_raw = title_m.group(1) if title_m else ""
        title = re.sub(r"<[^>]+>", " ", title_raw)
        title = re.sub(r"\s+", " ", title).strip()
        link = link_m.group(1) if link_m else url
        content = content_m.group(1) if content_m else (summary_m.group(1) if summary_m else "")
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()[:1000]
        if title:
            items.append({
                "title": title,
                "url": link,
                "score": 0,
                "comments": 0,
                "text": content,
            })
        if len(items) >= limit:
            return items
    if items:
        return items
    # RSS 2.0 fallback
    for match in re.finditer(r"<item[^>]*>(.*?)</item>", text, re.DOTALL | re.IGNORECASE):
        block = match.group(1)
        title_m = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
        link_m = re.search(r"<link[^>]*>(.*?)</link>", block, re.DOTALL)
        desc_m = re.search(r"<description[^>]*>(.*?)</description>", block, re.DOTALL)
        title = re.sub(r"<[^>]+>", " ", title_m.group(1)).strip() if title_m else ""
        title = re.sub(r"\s+", " ", title)
        link = link_m.group(1).strip() if link_m else url
        desc = re.sub(r"<[^>]+>", " ", desc_m.group(1))[:1000] if desc_m else ""
        desc = re.sub(r"\s+", " ", desc).strip()
        if title:
            items.append({"title": title, "url": link, "score": 0, "comments": 0, "text": desc})
        if len(items) >= limit:
            break
    return items


def has_monetization_signal(item):
    """本文/タイトルに monetization モデル (有料/データ販売/API化等) の語があるか。
    品質ゲート要件1 (t_2e20f1ef v58)。"""
    text = f"{item.get('title', '')} {item.get('text', '')}".lower()
    return any(re.search(pat, text, re.IGNORECASE) for pat in MONETIZATION_PATTERNS)


def quality_gate(item, created_count):
    """1件の候補に対する品質ゲート判定 (t_2e20f1ef critic_proposal v58)。
    通過なら None、そうでなければ (gate_key, status_message) を返す。
      要件1: score < MIN_HN_SCORE は低シグナルとしてスキップ
      要件1: monetization モデル語が本文/タイトルに無ければスキップ
      要件2: 1実行あたり新規投入 created_count >= MAX_KANBAN_PER_RUN でスキップ
    """
    score = item.get("score", 0) or 0
    if score < MIN_HN_SCORE:
        return ("score_low", f"(gate) score={score} < {MIN_HN_SCORE} でスキップ")
    if not has_monetization_signal(item):
        return ("no_monetization", "(gate) monetization シグナル無しでスキップ")
    if created_count >= MAX_KANBAN_PER_RUN:
        return ("cap_reached", f"(gate) 投入上限 {MAX_KANBAN_PER_RUN} 件到達のためスキップ")
    return None


def classify_seed(item):
    """記事/投稿が「自動収益の種」かどうか判定"""
    text = f"{item.get('title', '')} {item.get('text', '')}"
    text_lower = text.lower()

    matches = []
    for cat in SEED_PATTERNS:
        for pat in cat["patterns"]:
            if re.search(pat, text_lower, re.IGNORECASE):
                # exclude チェック
                excluded = False
                for ex in cat.get("exclude", []):
                    if re.search(ex, text_lower, re.IGNORECASE):
                        excluded = True
                        break
                if excluded:
                    continue
                # 自動化関連キーワードがあれば加点
                has_auto = any(kw in text_lower for kw in cat.get("automation_keywords", []))
                matches.append({
                    "category": cat["category"],
                    "weight": cat["weight"],
                    "has_automation_keyword": has_auto,
                })
                break
    return matches


def create_kanban_task(title, body, weight, url="", hn_id=""):
    """重要度中以上なら kanban に投入。
    Run 横断 dedup:
      0) HN item_id 主キー照合 (t_2e20f1ef v58 要件3)。item の hn_url / url から
         抽出した news.ycombinator.com/item?id=<digits> を tasks.body と突き合わせ、
         done/archived を含む全ステータスに一致すれば (None, "hnid-skip:<existing>")。
         タイトルの 60 字切り詰め・表記揺れに強い決定論的キー。
      1) title を scripts/kanban_norm.norm_title で正規化し、
         kanban DB の全ステータスと照合。同一キーがあれば (None, "dedup-skip:<existing>")。
      2) 重複が無ければ hermes kanban create を実行。
         失敗しても例外で timer を止めない(要件: kanban timer 生成を妨げない)。
    戻り値: (task_id_or_None, status_string)
    """
    if weight == "低":
        return None, "weight=低、見送り"
    # 0) HN item_id 主キー dedup (全ステータス照合、done/archived 含む)
    hn_id = hn_id or _extract_hn_item_id(url) or _extract_hn_item_id(body)
    if hn_id:
        try:
            is_dup, existing = _is_duplicate_hn_id(hn_id)
            if is_dup:
                return None, f"(hnid-skip) 既存 {existing} (hn_id={hn_id})"
        except Exception as e:  # DB 障害で dedup 失敗時は後段の title dedup に委ねる
            sys.stderr.write(f"[hunter] hn_id dedup check error (continue): {e}\n")
    # 1) Run 横断 dedup (全カテゴリ対象。title_like=None で全文字照合、
    #    include_all_statuses=True で done/archived を含む全ステータスと照合=
    #    「workerが実装不能判定でdone/archived済みの案件をHN掲載期間中に
    #    毎晩再作成する」ループを遮断。Stripe-style idempotency guard。2026-09-05教訓)
    try:
        is_dup, existing = _kanban_is_duplicate(
            title,
            title_like=None,
            include_all_statuses=True,
        )
        if is_dup:
            return None, f"(dedup-skip) 既存 {existing}"
    except Exception as e:  # DB 障害などで dedup が失敗しても create は試みる
        sys.stderr.write(f"[hunter] dedup check error (continue): {e}\n")
    priority = 1 if weight == "高" else 2
    # 2) title + organizer + condition から決定的な idempotency key を生成 (二重作成の最終防衛)
    import hashlib

    organizer = url or ""
    condition = body[:80] if body else ""
    idem = "hn-" + hashlib.sha1(_dedup_key(title, organizer, condition).encode("utf-8")).hexdigest()[:16]
    try:
        result = subprocess.run(
            [
                "hermes",
                "kanban",
                "create",
                title,
                "--body",
                body,
                "--assignee",
                "kensho-revenue-worker",
                "--priority",
                str(priority),
                "--created-by",
                "kensho-non-api-revenue-hunter",
                "--idempotency-key",
                idem,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # 出力から t_xxxxx を抽出
            m = re.search(r"(t_[0-9a-f]{8})", result.stdout)
            return m.group(1) if m else "(created)", "ok"
        else:
            return None, f"kanban error: {result.stderr[:200]}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        # kanban create が失敗しても timer 生成を妨げない (要件2)
        return None, f"kanban exec error: {e}"


def main():
    started = datetime.now(JST)
    print(f"== kensho-non-api-revenue-hunter: {started.isoformat()}", file=sys.stderr)

    all_seeds = []  # (source, item, matches)
    source_summaries = []

    for src in SOURCES:
        print(f"  fetching {src['name']}...", file=sys.stderr)
        if src["kind"] == "hn_ids":
            items = fetch_hn_list(src["url"], src["limit"])
        elif src["kind"] == "json":
            if "old.reddit.com" in src["url"] or "reddit.com" in src["url"]:
                items = fetch_reddit_json(src["url"], src["limit"])
            elif "qiita.com" in src["url"]:
                items = fetch_qiita_json(src["url"], src["limit"])
            else:
                items = []
        elif src["kind"] == "rss":
            items = fetch_rss(src["url"], src["limit"])
        elif src["kind"] == "html":
            items = fetch_html_strip(src["url"], src["limit"])
        else:
            items = []

        new_seeds = 0
        for item in items:
            matches = classify_seed(item)
            if matches:
                all_seeds.append((src, item, matches))
                new_seeds += 1
        source_summaries.append({
            "name": src["name"],
            "weight": src["weight"],
            "fetched": len(items),
            "seeds_found": new_seeds,
            "rationale": src["rationale"],
        })
        print(f"    → {len(items)} items, {new_seeds} seeds", file=sys.stderr)

    # 重要度順にソート
    weight_order = {"高": 0, "中": 1, "低": 2}
    all_seeds.sort(key=lambda x: (weight_order[x[2][0]["weight"]], -x[1].get("score", 0)))

    # 上位を kanban に投入 (重複防止: 同一URLは1度だけ)
    # 品質ゲート (t_2e20f1ef critic_proposal v58):
    #   要件1: score < MIN_HN_SCORE または monetization シグナル無しはスキップ
    #   要件2: 1実行の新規投入は MAX_KANBAN_PER_RUN 件で上限 (投入ペース制御)
    #   要件3: HN item_id 主キー dedup は create_kanban_task 内 (hnid-skip)
    kanban_added = []
    seen_urls = set()
    gate_stats = {"score_low": 0, "no_monetization": 0, "cap_reached": 0, "hnid_skip": 0}
    created_count = 0
    for src, item, matches in all_seeds:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        top = matches[0]
        if top["weight"] == "低":
            continue
        # --- 品質ゲート (要件1: score / monetization、要件2: 投入上限) ---
        gate = quality_gate(item, created_count)
        if gate is not None:
            gate_key, gate_msg = gate
            gate_stats[gate_key] += 1
            seen_urls.add(url)
            kanban_added.append({
                "title": item.get("title", ""),
                "url": url,
                "category": top["category"],
                "weight": top["weight"],
                "task_id": None,
                "status": gate_msg,
            })
            continue
        seen_urls.add(url)
        body = (
            f"## 発見ソース\n"
            f"- Source: {src['name']}\n"
            f"- 重要度: {top['weight']} / カテゴリ: {top['category']}\n"
            f"- スコア: {item.get('score', 0)} / コメント: {item.get('comments', 0)}\n"
            f"- URL: {url}\n"
            f"- 元記事HN: {item.get('hn_url', '-')}\n"
            f"\n## タイトル\n{item.get('title', '')}\n"
            f"\n## 要旨\n{item.get('text', '')[:500]}\n"
            f"\n## 自動化の種 (Kenshoスキルで実装可能か)\n"
            f"- 自動化キーワード含有: {'あり' if top.get('has_automation_keyword') else 'なし'}\n"
            f"- 推定実装工数: 検討要\n"
            f"\n## 申し送り\n"
            f"kensho-non-api-revenue-hunter が自動検出。"
            f"kensho-revenue-worker は本タスクを「Apify/RapidAPI以外の手法で実装できるか」観点で評価し、"
            f"実装可能なら 1) プロトタイプ 2) ローンチ手順 3) 集客の3点を 24h 以内に worker ジョブで着手すること。"
        )
        task_id, status = create_kanban_task(
            f"[非API自動収益] {top['category']}: {item.get('title', '')[:60]}",
            body,
            top["weight"],
            url=url,
            hn_id=_extract_hn_item_id(item.get("hn_url", "")) or _extract_hn_item_id(url),
        )
        if task_id:
            created_count += 1
        if "(hnid-skip)" in status:
            gate_stats["hnid_skip"] += 1
        kanban_added.append({
            "title": item.get("title", ""),
            "url": url,
            "category": top["category"],
            "weight": top["weight"],
            "task_id": task_id,
            "status": status,
        })

    # dedup-skip 件数(参考、レポート出力用)
    dedup_skip_count = sum(1 for k in kanban_added if "(dedup-skip)" in k.get("status", ""))
    hnid_skip_count = gate_stats["hnid_skip"]
    gate_skip_count = gate_stats["score_low"] + gate_stats["no_monetization"] + gate_stats["cap_reached"]
    ok_create_count = sum(1 for k in kanban_added if k["task_id"] and not k["task_id"].startswith("("))

    # レポート生成
    gate_breakdown = (
        f"score<{MIN_HN_SCORE}: {gate_stats['score_low']} / "
        f"monetization無: {gate_stats['no_monetization']} / "
        f"上限到達: {gate_stats['cap_reached']}"
    )
    report_md = f"""# 非API自動収益ハンター レポート
|**実行日時**: {started.strftime("%Y-%m-%d %H:%M JST")}
|**対象ジョブ**: {JOB_ID}
|**探索ソース数**: {len(SOURCES)}

## サマリー

| 指標 | 値 |
|---|---|
| 巡回ソース数 | {len(SOURCES)} |
| 取得アイテム合計 | {sum(s["fetched"] for s in source_summaries)} |
| 自動収益の「種」発見 | {len(all_seeds)} |
| Kanban 新規投入 | {ok_create_count} (上限 {MAX_KANBAN_PER_RUN}) |
| Kanban dedup-skip (title) | {dedup_skip_count} |
| Kanban hnid-skip (HN item_id) | {hnid_skip_count} |
| 品質ゲートスキップ | {gate_skip_count} ({gate_breakdown}) |

## ソース別取得数

| ソース | 重要度 | 取得 | 種発見 | 評価理由 |
|---|---|---|---|---|
"""
    for s in source_summaries:
        report_md += f"| {s['name']} | {s['weight']} | {s['fetched']} | {s['seeds_found']} | {s['rationale']} |\n"

    report_md += "\n## 上位の発見 (重要度順、最大20件)\n\n"
    for i, (src, item, matches) in enumerate(all_seeds[:20], 1):
        top = matches[0]
        report_md += (
            f"### {i}. [{top['category']}] {item.get('title', '')[:80]}\n"
            f"- ソース: {src['name']} / 重要度: {top['weight']} / スコア: {item.get('score', 0)}\n"
            f"- URL: {item.get('url', '')}\n"
            f"- 要旨: {(item.get('text', '') or '(なし)')[:300]}\n\n"
        )

    report_md += "\n## Kanban 投入履歴\n\n"
    if kanban_added:
        for k in kanban_added:
            # gate / hnid-skip / dedup-skip / 失敗 / ok を識別しやすくする
            if "(gate)" in k["status"]:
                marker = "(gate)"
                tid_disp = "skip"
            elif "(hnid-skip)" in k["status"]:
                marker = "(hnid-skip)"
                tid_disp = "skip"
            elif "(dedup-skip)" in k["status"]:
                marker = "(dedup-skip)"
                tid_disp = "skip"
            elif k["task_id"]:
                marker = "ok"
                tid_disp = f"`{k['task_id']}`"
            else:
                marker = "error"
                tid_disp = "—"
            report_md += f"- {tid_disp} [{marker}] [{k['weight']}/{k['category']}] {k['title'][:60]} — {k['status']}\n"
    else:
        report_md += "- (今回は投入なし — 重要度「中」以上の新規種が見つからなかった)\n"

    report_md += f"""
## 評価基準
- **重要度「高」**: Kensho 既存スキル(スクレイピング/CDP/Selenium/Cron/Gemini API) で
  1週間以内に MVP 可能、かつ市場需要が観測できる
- **重要度「中」: 1つ以上の不確実要素あり (市場規模未確認 / 法務要確認 / 技術難易度高)
- **重要度「低」**: アイデア倒れに近い / Kenshoで自動化しても旨味が薄い

## 品質ゲート (t_2e20f1ef v58)
- score < {MIN_HN_SCORE} は低シグナルとしてスキップ
- monetization モデル (有料/データ販売/API化等) の語が本文/タイトルに無ければスキップ
- 1実行あたり新規投入は {MAX_KANBAN_PER_RUN} 件まで (投入ペース制御)
- HN item_id 主キーで done/archived 含む全ステータスと照合し再生成を防止

## 申し送り
- 重要度「中」以上は kensho-revenue-worker 担当で Kanban 投入済み
- 既存 cron (kensho-research-agent / kensho-research-agent-monetize) と補完関係
- 除外: Apify/RapidAPI/スクレイパー再販系 (他ジョブ担当)
"""
    # ファイル出力
    out_path = OUT_DIR / f"{started.strftime('%Y-%m-%d_%H-%M-%S')}.md"
    out_path.write_text(report_md, encoding="utf-8")
    print(f"  → report: {out_path}", file=sys.stderr)
    # stdout にも要点 (cron ログに残る)
    print(report_md[:3000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
