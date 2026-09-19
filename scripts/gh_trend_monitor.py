#!/usr/bin/env python3
"""GitHub 急上昇/トレンド監視 → AIチーム候補レポート自動生成.

設計 (タスク仕様準拠):
  1. GitHub REST API /search/repositories (認証なし: 60 req/h, search 10/min)。
     二系統クエリを発行:
       a. 直近急上昇   : q='<keyword> created:>=YYYY-MM-DD' sort=stars desc
       b. trending 相当: q='<keyword> pushed:>=YYYY-MM-DD stars:>30' sort=stars desc
  2. Kensho関連キーワード一致数 + 対数スター数で重み付きスコアリング。
  3. スコア上位5件を reports/gh-trend-candidates-YYYY-MM-DD.{json,md} に日次生成。
  4. 前日分との差分 (is_new) フラグ付け → critic の取り込み判断に委譲。

出力: reports/gh-trend-candidates-YYYY-MM-DD.json + .md
"""
import json, urllib.request, urllib.parse, urllib.error, datetime, os, glob, math, time

REPO_ROOT = "/mnt/d/Project2/kensho"
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")

# Kensho/AIチーム運用に関連するキーワード (タイトル/説明/トピック/言語の部分一致でスコア加算)
KEYWORDS = [
    "scraper", "crawler", "automation", "ai-agent", "agent", "proxy",
    "playwright", "cdp", "browser-use", "browser automation", "puppeteer",
    "selenium", "n8n", "mcp", "langchain", "rag", "llm", "bot", "collect", "bulk",
]
WINDOW_DAYS = 7           # 対象窓 (直近7日)
MIN_STARS = 30            # trending 相当の下限スター数
STAR_WEIGHT = 4.0         # 対数スター1点 ≒ keyword一致4点相当 (スター1件でも関連キーワード多で上位入り)
KEYWORD_WEIGHT = 20.0     # 1 keyword一致あたりの加点


def _request(q, retries=3):
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": 50}
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "gh-trend-monitor", "Accept": "application/vnd.github+json",
    })
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r).get("items", [])
        except urllib.error.HTTPError as e:
            rate = e.headers.get("X-RateLimit-Remaining") if e.headers else None
            print(f"[WARN] GitHub API {e.code} (rate_limit_remaining={rate}) q={q!r}")
            return []
        except Exception as e:
            last_err = e
            print(f"[WARN] attempt {attempt+1}/{retries} failed: {e} — retrying")
            time.sleep(5 * (attempt + 1))
    print(f"[WARN] giving up after {retries} attempts: {last_err}")
    return []


def _keyword_groups(keywords, max_chars=60, max_terms=5):
    """キーワードを短いORグループに分割.

    GitHub検索APIは1クエリの OR/AND/NOT 演算子を5個までに制限 (7語ORは422)。
    max_terms=5 で1グループ最大5語 (演算子4個) に抑える。検索レート(10req/min)を守るため
    グループ数を絞る効果も兼ねる。
    """
    groups, cur = [], []
    cur_len = 0
    for kw in keywords:
        if cur and (len(cur) >= max_terms or cur_len + len(kw) + 4 > max_chars):
            groups.append(" OR ".join(cur))
            cur, cur_len = [], 0
        cur.append(kw)
        cur_len += len(kw) + 4
    if cur:
        groups.append(" OR ".join(cur))
    return groups


def fetch_candidates(since):
    """created:>=since (直近急上昇) と pushed:>=since stars:>MIN_STARS (trending相当) を並列的に収集.

    search API の認証なしレート (10 req/min) を守るため、キーワードをORグループへまとめ、
    1グループあたり2リクエスト (created/pushed) だけ発行する。
    """
    items, seen = [], set()
    for group in _keyword_groups(KEYWORDS):
        for q in [
            f"({group}) created:>={since}",
            f"({group}) pushed:>={since} stars:>{MIN_STARS}",
        ]:
            for it in _request(q):
                u = it.get("html_url")
                if u and u not in seen:
                    seen.add(u)
                    items.append(it)
            time.sleep(7)  # 10 req/min 上限に余裕を持たせる
    return items


def score(repo):
    text = " ".join([
        repo.get("full_name", ""), repo.get("description") or "",
        repo.get("language") or "",
        " ".join(repo.get("topics") or []),
    ]).lower()
    hits = sum(1 for k in KEYWORDS if k in text)
    stars = repo.get("stargazers_count", 0)
    return hits * KEYWORD_WEIGHT + math.log1p(stars) * STAR_WEIGHT


def load_prev_urls():
    """過去レポートとの面被りチェック用に、今日以外の累積 URL 集合を返す."""
    prev_urls = set()
    prev_files = sorted(glob.glob(os.path.join(REPORTS_DIR, "gh-trend-candidates-20*.json")), reverse=True)
    today = datetime.date.today().isoformat()
    for pf in prev_files:
        if os.path.basename(pf) == f"gh-trend-candidates-{today}.json":
            continue
        try:
            prev = json.load(open(pf))
            prev_urls |= {c["html_url"] for c in prev.get("candidates", [])}
        except Exception:
            pass
    return prev_urls


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    since = (datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    json_file = os.path.join(REPORTS_DIR, f"gh-trend-candidates-{today}.json")
    md_file = os.path.join(REPORTS_DIR, f"gh-trend-candidates-{today}.md")

    items = fetch_candidates(since)
    ranked = sorted(items, key=score, reverse=True)[:5]
    prev_urls = load_prev_urls()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()

    candidates = []
    for rank, r in enumerate(ranked, 1):
        candidates.append({
            "rank": rank,
            "score": round(score(r), 3),
            "full_name": r.get("full_name", ""),
            "html_url": r.get("html_url", ""),
            "description": r.get("description") or "",
            "language": r.get("language"),
            "stargazers_count": r.get("stargazers_count", 0),
            "forks_count": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "created_at": r.get("created_at"),
            "pushed_at": r.get("pushed_at"),
            "topics": r.get("topics") or [],
            "homepage": r.get("homepage"),
            "is_new": r.get("html_url") not in prev_urls,
        })

    report = {
        "generated_at": now,
        "date": today,
        "window_days": WINDOW_DAYS,
        "source": "https://api.github.com/search/repositories",
        "auth": "none (anonymous, 60 req/h; search 10/min)",
        "queries": [f"created:>={since}", f"pushed:>={since} stars:>{MIN_STARS}"],
        "keywords": KEYWORDS,
        "total_candidates_collected": len(items),
        "candidates": candidates,
    }
    with open(json_file, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = [
        f"# GitHub 急上昇/トレンド候補 ({today})",
        "",
        f"生成時刻: {now}  |  対象窓: 直近{WINDOW_DAYS}日  |  収集 {len(items)}件 → 上位5件",
        "",
    ]
    for c in candidates:
        tag = "🆕 NEW" if c["is_new"] else "🔁 既知"
        lines.append(f"## {c['rank']}. {c['full_name']}")
        lines.append(f"- スコア: **{c['score']:.3f}**  |  ⭐{c['stargazers_count']}  |  fork {c['forks_count']}")
        lines.append(f"- 言語: {c['language'] or '不明'}  |  created: {c['created_at'][:10] if c['created_at'] else '?'}")
        lines.append(f"- {tag} | URL: {c['html_url']}")
        lines.append(f"- 説明: {c['description'] or '(no description)'}")
        if c["topics"]:
            lines.append(f"- トピック: {', '.join(c['topics'])}")
        lines.append("")
    lines.append("## Notes")
    lines.append("- Kensho関連キーワード一致数×20 + 対数スター×4 でスコアリング。上位5件のみ表示。")
    lines.append("- is_new=🆕 の候補は critic が kanban 取り込みの判断対象。")
    lines.append("- 認証なし API 上限: 60 req/h, search 10/min。本スクリプトは1回で2×N可変リクエスト。")
    with open(md_file, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {json_file}")
    print(f"Wrote {md_file}")
    print(f"Collected {len(items)} raw candidates (window {WINDOW_DAYS}d since {since}), top {len(candidates)}:")
    for c in candidates:
        print(f"  {'🆕' if c['is_new'] else '🔁'} #{c['rank']} {c['full_name']} ⭐{c['stargazers_count']} score={c['score']}")


if __name__ == "__main__":
    main()
