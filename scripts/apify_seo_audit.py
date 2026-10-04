#!/usr/bin/env python3
"""apify_seo_audit — Apify Store 発見性（SEO）監査ツール。

revenue-critic v13-A (t_ce1f9b36) 実装。

背景（エビデンス）:
  data/revenue-daily.json の total_runs が 9/2=1125 → 9/3=1162 → 9/4=1162 と
  停滞（9/4 は増加ゼロ）。users30d も 21 で横ばい、上位5アクターの u30d=1 が
  1件も伸びていない。PPE課金適用（t_19bca94c）は完了済みだが、流入そのものが
  伸びていないため「課金単価」ではなく「発見性」がボトルネックと仮定する。

このスクリプトがやること:
  1. 自社アクター一覧（my=true）を取得し、公開中のものだけを対象にする
  2. 各アクターの title / description / seoTitle / seoDescription /
     categories / readmeSummary を実測取得
  3. Apify Store 検索（/v2/store?search=...&sortBy=popularity）で
     同カテゴリ上位競合（自社を除く）を取得
  4. 競合との差分から「具体的な」改善案を生成する
     - 説明文が競合中央値より短い
     - 競合の頻出キーワードで自社に無い語（title/desc/readme 全てに不在）
     - 競合の過半数が付けているカテゴリが自社に無い
     - seoTitle / seoDescription / readme が未設定
     - title が長すぎる／短すぎる
     - u30d=0 なのに競合は月間ユーザーを持っている（発見性ギャップ）
  5. 出力: JSON（詳細） + CSV diff（行=改善案1件）

使い方:
  python3 scripts/apify_seo_audit.py                     # 全公開アクター
  python3 scripts/apify_seo_audit.py --limit 5           # 対象を絞る
  python3 scripts/apify_seo_audit.py --top 8             # 競合を8件比較
  python3 scripts/apify_seo_audit.py --csv out.csv --json out.json
  python3 scripts/apify_seo_audit.py --fixture data.json # ネットワーク無し（テスト用）

APIキー: 環境変数 APIFY_TOKEN（無ければ kensho_revenue_collect.py と同じ既定値）
読み取り専用 — Apify 側の設定は一切変更しない。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any
# 2026-10-04 漏洩対策: トークンはURLではなく Authorization ヘッダで送る
import os as _os, sys as _sys  # noqa: E401
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _apify_auth import apify_get as _apify_get, apify_urlopen as _apify_urlopen, redact_secrets  # noqa: E402
PROJECT_DIR = "/mnt/d/Project2/kensho"
DEFAULT_OUT_DIR = os.path.join(PROJECT_DIR, "reports", "apify-seo")

APIFY_TOKEN_DEFAULT = os.environ.get("APIFY_TOKEN_DEFAULT", "")
API_BASE = "https://api.apify.com/v2"

# 1アクターあたりのStore検索試行上限（API負荷・実行時間抑制）
MAX_QUERIES_PER_ACTOR = 4

# 自社アカウント名（競合候補から除外する）
OWN_USERNAME = "fruitful_quintessence"

# Store検索で無視する汎用語（これだけで検索すると競合が無限に広がる）
QUERY_STOPWORDS = {
    "scraper",
    "scrapers",
    "api",
    "japan",
    "japanese",
    "data",
    "actor",
    "actors",
    "server",
    "mcp",
    "the",
    "and",
    "for",
    "with",
    "from",
    "price",
    "prices",
    "market",
    "cn",
    "kr",
    "usa",
    "us",
    "search",
    "used",
    "new",
}

# キーワード抽出で除外する英語stopword（小文字で比較）
KEYWORD_STOPWORDS = QUERY_STOPWORDS | {
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "or",
    "by",
    "get",
    "you",
    "your",
    "this",
    "that",
    "with",
    "extract",
    "returns",
    "return",
    "items",
    "item",
    "unofficial",
    "per",
    "no",
    "not",
    "all",
    "can",
    "will",
    "http",
    "https",
    "www",
    "com",
    "jp",
    # 競合説明文の接続・修飾語（真似しても発見性は上がらない語）
    "more",
    "other",
    "others",
    "over",
    "range",
    "type",
    "types",
    "typical",
    "via",
    "run",
    "runs",
    "charge",
    "charges",
    "counts",
    "including",
    "include",
    "details",
    "detail",
    "comprehensive",
    "contact",
    "full",
    "also",
    "just",
    "like",
    "based",
    "works",
    "well",
    "many",
    "most",
    "each",
    "every",
    "provides",
    "provide",
    "allows",
    "allow",
    "supports",
    "support",
    "features",
    "feature",
    "whether",
    "without",
    "within",
    "across",
    "any",
    "both",
    "between",
    "these",
    "those",
    "then",
    "than",
    "such",
    "into",
    "about",
    "after",
    "before",
    "here",
    "there",
    "when",
    "what",
    "which",
    "while",
    "because",
    "results",
    "result",
    "output",
    "outputs",
    "input",
    "inputs",
    "fields",
    "field",
    "values",
    "value",
    "data",
    "set",
    "sets",
    "list",
    "lists",
    "page",
    "pages",
    "site",
    "sites",
    "web",
    "online",
    "daily",
    "weekly",
    "monthly",
    "hours",
    "minutes",
    "seconds",
    "times",
    "time",
    "cost",
    "costs",
    "usd",
    "free",
    "paid",
    "month",
    "year",
    "years",
}

WORD_RE = re.compile(r"[a-z][a-z0-9+#\-]{2,}")


def _load_env_file(path: str = "/mnt/d/Project2/kensho/.env") -> dict[str, str]:
    """リポジトリの .env を絶対パスで読む（cron の cwd が /tmp でも効くように）。"""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
                if m:
                    out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def get_apify_token() -> str:
    """Apify APIトークンを取得する。

    2026-10-03 恒久修正: 以前は環境変数 APIFY_TOKEN と（環境からしか読まない）
    APIFY_TOKEN_DEFAULT を見ていたため、素の実行では両方空で 401 になった。
    実キー名は .env の APIFY_TOKEN_DEFAULT。**絶対パスの .env を読み、
    両方の名前をフォールバックで探す**。これを崩すと 401 が再発する。
    """
    env = _load_env_file()
    for name in ("APIFY_TOKEN", "APIFY_TOKEN_DEFAULT"):
        val = (os.environ.get(name) or env.get(name) or "").strip()
        if val:
            return val
    return ""


def _normalize_words(text: str) -> list[str]:
    """テキストからキーワード候補（英単語・小文字・stopword除去）を返す。"""
    words = [w.lower() for w in WORD_RE.findall(text.lower())]
    return [w for w in words if w not in KEYWORD_STOPWORDS]


def _median(values: list[float]) -> float:
    """中央値（空リストなら0.0）。"""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _candidate_words(text: str) -> list[str]:
    """テキストから検索語候補（stopword除去・ハイフン分割済み）を順序付きで返す。"""
    tokens = re.split(r"[—|–\-_:,/()\[\]\s]+", str(text).lower())
    out: list[str] = []
    for tok in tokens:
        tok = tok.strip(".?'\"")
        if not tok or tok in QUERY_STOPWORDS or len(tok) < 3:
            continue
        if tok not in out:
            out.append(tok)
    return out


def build_search_queries(actor: dict[str, Any]) -> list[str]:
    """Store検索クエリ候補を「狭い→広い」の順で返す。

    1件目で競合0件のとき次を試すことで、no_competitor_data を減らす。
    """
    queries: list[str] = []

    def add(words: list[str], size: int) -> None:
        if not words:
            return
        q = " ".join(words[:size])
        if q and q not in queries:
            queries.append(q)

    title_words = _candidate_words(actor.get("seoTitle") or "") + _candidate_words(actor.get("title") or "")
    name_words = _candidate_words(str(actor.get("name") or "").replace("_", " "))
    desc_words = _candidate_words(str(actor.get("description") or ""))[:6]

    # 1. titleの固有名詞2語（最も狭い）
    add(title_words, 2)
    # 2. titleの固有名詞3語
    add(title_words, 3)
    # 3. nameのトークン（サイト名が入っていることが多い）
    add(name_words, 3)
    add(name_words, 2)
    # 4. title先頭1語 + descriptionのキーワード
    if title_words:
        add([title_words[0]] + [w for w in desc_words if w != title_words[0]], 3)
    # 5. titleの1語のみ（最も広い・最後の砦）
    for w in title_words[:3]:
        add([w], 1)
    for w in name_words[:3]:
        add([w], 1)
    return queries


def build_search_query(actor: dict[str, Any]) -> str:
    """アクターからStore検索クエリを組み立てる（第1候補）。"""
    queries = build_search_queries(actor)
    return queries[0] if queries else ""


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    """GETしてJSONを返す。失敗時は空dict（呼び出し側でNone判定不要にする）。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "kensho-seo-audit/1.0"})
    try:
        with _apify_urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"WARN fetch failed {url.split('?')[0]}: {exc}", file=sys.stderr)
        return {}


def fetch_own_actors(token: str) -> list[dict[str, Any]]:
    """自社アクター一覧（公開分のみ、詳細付き）を返す。"""
    listing = fetch_json(f"{API_BASE}/acts?my=true&token={token}&limit=100")
    items = listing.get("data", {}).get("items", []) or []
    actors: list[dict[str, Any]] = []
    for it in items:
        aid = it.get("id")
        if not aid:
            continue
        detail = fetch_json(f"{API_BASE}/acts/{aid}?token={token}")
        data = detail.get("data") or {}
        if not data:
            continue
        if not data.get("isPublic"):
            continue
        merged = dict(data)
        merged.setdefault("name", it.get("name"))
        actors.append(merged)
        time.sleep(0.15)  # レート配慮
    return actors


def fetch_competitors(token: str, query: str, top: int, exclude_names: set[str]) -> list[dict[str, Any]]:
    """Store検索で競合アクター（自社以外）を top 件返す。

    プールは top*4 件取得する — 人気順上位が無関係アクターだと
    関連度フィルタ後に0件になるため、母数を取ってから絞る。
    """
    import urllib.parse

    if not query:
        return []
    url = f"{API_BASE}/store?search={urllib.parse.quote(query)}&token={token}&limit={max(top, 1) * 4}&sortBy=popularity"
    data = fetch_json(url)
    items = data.get("data", {}).get("items", []) or []
    comps: list[dict[str, Any]] = []
    for it in items:
        if it.get("username") == OWN_USERNAME:
            continue
        if it.get("name") in exclude_names:
            continue
        comps.append(it)
        if len(comps) >= top * 4:
            break
    return comps


def fetch_competitors_multi(
    token: str,
    actor: dict[str, Any],
    queries: list[str],
    top: int,
    exclude_names: set[str],
    sleep_seconds: float = 0.15,
) -> tuple[list[dict[str, Any]], str]:
    """クエリ候補を順に試し、関連度の高い競合を返す。戻り値: (競合, 使用クエリ)。

    関連度フィルタ後に2件以上残るクエリを優先採用する（1件しか無いと
    中央値・過半数判定が機能しないため）。全クエリで不足なら
    最も多く競合が残った結果を返す。
    """
    best: list[dict[str, Any]] = []
    best_query = queries[0] if queries else ""
    for q in queries[:MAX_QUERIES_PER_ACTOR]:
        pool = fetch_competitors(token, q, top, exclude_names)
        if sleep_seconds:
            time.sleep(sleep_seconds)
        kept = filter_competitors(actor, pool)
        if len(kept) > len(best):
            best, best_query = kept, q
        if len(kept) >= 2:
            return kept[:top], q
    return best[:top], best_query


def _relevance_score(actor: dict[str, Any], comp: dict[str, Any]) -> int:
    """自社アクターと競合の話題重複度（共有キーワード数）を返す。

    単語クエリ（例: "watch"）で無関係な人気アクターが混ざると、
    カテゴリ・キーワード提案がノイズ化する。そのため重複度で絞る。
    """
    own = set(
        _normalize_words(
            " ".join([
                str(actor.get("title") or ""),
                str(actor.get("seoTitle") or ""),
                str(actor.get("name") or "").replace("_", " "),
            ])
        )
    )
    comp_words = set(
        _normalize_words(
            " ".join([
                str(comp.get("title") or ""),
                str(comp.get("description") or ""),
            ])
        )
    )
    return len(own & comp_words)


def filter_competitors(
    actor: dict[str, Any],
    competitors: list[dict[str, Any]],
    min_overlap: int = 1,
) -> list[dict[str, Any]]:
    """話題重複 min_overlap 以上の競合だけを残す。

    重複0（無関係な人気アクター）は比較対象から落とす。
    全滅なら空を返し、呼び出し側で no_competitor_data として扱う。
    """
    return [c for c in competitors if _relevance_score(actor, c) >= min_overlap]


def analyze_actor(actor: dict[str, Any], competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """1アクター分の改善案（diff行）を返す。

    返り値の各行: {actor, issue, field, current, suggested, evidence}
    """
    findings: list[dict[str, Any]] = []
    name = str(actor.get("name") or "?")

    # 無関係な人気アクターを除外してから比較する
    competitors = filter_competitors(actor, competitors)

    desc = str(actor.get("description") or "")
    title = str(actor.get("title") or "")
    readme = str(actor.get("readmeSummary") or "")
    cats = list(actor.get("categories") or [])
    seo_title = str(actor.get("seoTitle") or "")
    seo_desc = str(actor.get("seoDescription") or "")
    mine_u30d = int((actor.get("stats") or {}).get("totalUsers30Days") or 0)

    own_blob = " ".join([title, desc, readme, seo_title, seo_desc]).lower()
    own_words = set(_normalize_words(own_blob))

    if not competitors:
        findings.append({
            "actor": name,
            "issue": "no_competitor_data",
            "field": "search_query",
            "current": build_search_query(actor),
            "suggested": "検索クエリを手動で広げる（別キーワード候補を試す）",
            "evidence": "Store検索で競合0件",
        })
        return findings

    comp_descs = [str(c.get("description") or "") for c in competitors]
    comp_titles = [str(c.get("title") or "") for c in competitors]
    comp_desc_lens = [len(d) for d in comp_descs]
    med_desc_len = _median([float(x) for x in comp_desc_lens])
    max_desc_len = max(comp_desc_lens) if comp_desc_lens else 0

    # --- 1. 説明文の長さ ---
    if len(desc) < med_desc_len:
        findings.append({
            "actor": name,
            "issue": "short_description",
            "field": "description",
            "current": f"{len(desc)}字",
            "suggested": f"競合中央値 {int(med_desc_len)}字以上に拡張（最大 {max_desc_len}字）",
            "evidence": f"競合{len(competitors)}件のdesc_len中央値={int(med_desc_len)}",
        })

    # --- 2. 競合高频キーワードで自社に無い語 ---
    doc_freq: dict[str, int] = {}
    for c in competitors:
        blob = " ".join([
            str(c.get("title") or ""),
            str(c.get("description") or ""),
        ])
        for w in set(_normalize_words(blob)):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    threshold = max(2, int(len(competitors) * 0.5))
    missing = sorted(
        ((w, n) for w, n in doc_freq.items() if n >= threshold and w not in own_words),
        key=lambda x: (-x[1], x[0]),
    )
    if missing:
        top_missing = missing[:6]
        findings.append({
            "actor": name,
            "issue": "missing_keywords",
            "field": "title+description",
            "current": "(不在) " + ", ".join(w for w, _ in top_missing),
            "suggested": "説明/タイトルに追加: " + ", ".join(f"{w}(競合{c}件)" for w, c in top_missing),
            "evidence": f"競合{len(competitors)}件中{threshold}件以上に出現し自社全文に不在",
        })

    # --- 3. 競合の過半数が使うカテゴリ ---
    cat_freq: dict[str, int] = {}
    for c in competitors:
        for cat in list(c.get("categories") or []):
            cat_freq[str(cat)] = cat_freq.get(str(cat), 0) + 1
    missing_cats = sorted(
        ((k, v) for k, v in cat_freq.items() if v >= threshold and k not in cats),
        key=lambda x: (-x[1], x[0]),
    )
    if missing_cats:
        findings.append({
            "actor": name,
            "issue": "missing_categories",
            "field": "categories",
            "current": ",".join(cats) if cats else "(なし)",
            "suggested": "追加候補: " + ", ".join(f"{k}(競合{v}件)" for k, v in missing_cats[:3]),
            "evidence": f"競合{len(competitors)}件中{threshold}件以上が設定",
        })

    # --- 4. title長さ ---
    if len(title) > 70:
        findings.append({
            "actor": name,
            "issue": "title_too_long",
            "field": "title",
            "current": f"{len(title)}字",
            "suggested": "70字以内へ短縮（Store一覧で末尾が切れる）",
            "evidence": f"title={title!r}",
        })
    elif 0 < len(title) < 20:
        findings.append({
            "actor": name,
            "issue": "title_too_short",
            "field": "title",
            "current": f"{len(title)}字",
            "suggested": "20字以上でキーワードを明記（例: 対象サイト+データ種別）",
            "evidence": f"title={title!r}",
        })

    # --- 5. seoTitle / seoDescription / readme 未設定 ---
    if not seo_title:
        findings.append({
            "actor": name,
            "issue": "seo_title_missing",
            "field": "seoTitle",
            "current": "(未設定)",
            "suggested": "検索意図を含む60字程度のタイトルを設定",
            "evidence": "detail APIのseoTitleが空",
        })
    if not seo_desc:
        findings.append({
            "actor": name,
            "issue": "seo_description_missing",
            "field": "seoDescription",
            "current": "(未設定)",
            "suggested": "価値提案+料金を含む160字程度を設定",
            "evidence": "detail APIのseoDescriptionが空",
        })
    if len(readme) < 200:
        findings.append({
            "actor": name,
            "issue": "thin_readme",
            "field": "readmeSummary",
            "current": f"{len(readme)}字",
            "suggested": "READMEを200字以上に（入力例・出力フィールド・ユースケース）",
            "evidence": f"readmeSummary長={len(readme)} / 競合中央値desc長={int(med_desc_len)}",
        })

    # --- 6. 発見性ギャップ（u30d） ---
    comp_u30d = [int((c.get("stats") or {}).get("totalUsers30Days") or 0) for c in competitors]
    med_u30d = _median([float(x) for x in comp_u30d])
    if mine_u30d == 0 and med_u30d >= 1:
        best = max(competitors, key=lambda c: int((c.get("stats") or {}).get("totalUsers30Days") or 0))
        findings.append({
            "actor": name,
            "issue": "discovery_gap",
            "field": "stats.totalUsers30Days",
            "current": "0",
            "suggested": "上位キーワード改善を優先（競合1位は月間"
            f"{int((best.get('stats') or {}).get('totalUsers30Days') or 0)}ユーザー）",
            "evidence": f"競合中央値u30d={med_u30d:g} / 自社0 / 競合1位={best.get('name')}",
        })

    # --- 7. 競合タイトルにあって自社に無い固有名詞（サイト名等） ---
    comp_site_words: dict[str, int] = {}
    for t in comp_titles:
        for w in set(_normalize_words(t)):
            comp_site_words[w] = comp_site_words.get(w, 0) + 1
    site_thr = max(2, int(len(comp_titles) * 0.6))
    missing_in_title = sorted(
        ((w, n) for w, n in comp_site_words.items() if n >= site_thr and w not in set(_normalize_words(title))),
        key=lambda x: (-x[1], x[0]),
    )
    if missing_in_title:
        findings.append({
            "actor": name,
            "issue": "title_keyword_gap",
            "field": "title",
            "current": title,
            "suggested": "タイトルへ追加: " + ", ".join(f"{w}(競合{c}件)" for w, c in missing_in_title[:4]),
            "evidence": f"競合title{len(comp_titles)}件中{site_thr}件以上に出現し自社titleに不在",
        })

    return findings


def audit(
    actors: list[dict[str, Any]],
    token: str,
    top: int,
    sleep_seconds: float = 0.15,
) -> list[dict[str, Any]]:
    """全アクターの監査を実行してdiff行のリストを返す。"""
    own_names = {str(a.get("name")) for a in actors if a.get("name")}
    rows: list[dict[str, Any]] = []
    for actor in actors:
        queries = build_search_queries(actor)
        comps, used = fetch_competitors_multi(token, actor, queries, top, own_names, sleep_seconds)
        findings = analyze_actor(actor, comps)
        for f in findings:
            f["search_query"] = used
            f["queries_tried"] = len(queries) if not comps else queries.index(used) + 1
            f["competitors"] = len(comps)
        rows.extend(findings)
    return rows


def write_csv(rows: list[dict[str, Any]], path: str) -> None:
    """CSV diffを書き出す（行=改善案1件）。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "actor",
        "issue",
        "field",
        "current",
        "suggested",
        "evidence",
        "search_query",
        "queries_tried",
        "competitors",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """issue種別ごとの件数サマリー。"""
    by_issue: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    for row in rows:
        by_issue[str(row.get("issue"))] = by_issue.get(str(row.get("issue")), 0) + 1
        by_actor[str(row.get("actor"))] = by_actor.get(str(row.get("actor")), 0) + 1
    return {
        "total_findings": len(rows),
        "actors_with_findings": len(by_actor),
        "by_issue": dict(sorted(by_issue.items(), key=lambda x: (-x[1], x[0]))),
        "worst_actors": sorted(by_actor.items(), key=lambda x: (-x[1], x[0]))[:5],
    }


def load_fixture(path: str) -> list[dict[str, Any]]:
    """テスト用: {actors:[...], competitors:{actor_name:[...]}} のJSONを読む。"""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    actors = data.get("actors") or []
    comps = data.get("competitors") or {}
    for actor in actors:
        actor["_fixture_competitors"] = comps.get(str(actor.get("name")), [])
    return actors


def audit_from_fixture(actors: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    """テスト用: fixtureの競合データで監査する（ネットワーク不使用）。"""
    rows: list[dict[str, Any]] = []
    for actor in actors:
        comps = list(actor.get("_fixture_competitors") or [])[:top]
        findings = analyze_actor(actor, comps)
        queries = build_search_queries(actor)
        for f in findings:
            f["search_query"] = queries[0] if queries else ""
            f["queries_tried"] = len(queries) if not comps else 1
            f["competitors"] = len(comps)
        rows.extend(findings)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apify Store SEO監査（読み取り専用）")
    parser.add_argument("--top", type=int, default=5, help="比較する競合件数（既定5）")
    parser.add_argument("--limit", type=int, default=0, help="対象アクター数上限（0=全件）")
    parser.add_argument("--json", dest="json_out", default="", help="JSON出力先")
    parser.add_argument("--csv", dest="csv_out", default="", help="CSV出力先")
    parser.add_argument("--fixture", default="", help="ネットワーク不使用（テスト用JSON）")
    parser.add_argument("--quiet", action="store_true", help="サマリーのみ出力")
    args = parser.parse_args(argv)

    today = datetime.now().strftime("%Y-%m-%d")
    if args.fixture:
        actors = load_fixture(args.fixture)
        rows = audit_from_fixture(actors, args.top)
    else:
        token = get_apify_token()
        actors = fetch_own_actors(token)
        if args.limit:
            actors = actors[: args.limit]
        rows = audit(actors, token, args.top)

    if not args.json_out:
        self_path = os.path.abspath(__file__)
        if "/.hermes/profiles/" in self_path:
            # profile配下のstale copy実行を防止（9/4教訓）
            print(
                f"ERROR: profile copy detected: {self_path} — use {PROJECT_DIR}/scripts/",
                file=sys.stderr,
            )
            return 2
        os.makedirs(DEFAULT_OUT_DIR, exist_ok=True)
        args.json_out = os.path.join(DEFAULT_OUT_DIR, f"apify-seo-audit-{today}.json")
        args.csv_out = os.path.join(DEFAULT_OUT_DIR, f"apify-seo-audit-{today}.csv")

    summary = summarize(rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "actors_audited": len(actors),
        "competitors_per_actor": args.top,
        "summary": summary,
        "findings": rows,
    }
    os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    if args.csv_out:
        write_csv(rows, args.csv_out)

    if not args.quiet:
        for row in rows:
            print(f"[{row['issue']}] {row['actor']} :: {row['field']} :: {row['suggested']}")
    print(f"actors={len(actors)} findings={summary['total_findings']}")
    print(f"json: {args.json_out}")
    if args.csv_out:
        print(f"csv: {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
