#!/usr/bin/env python3
"""
seo_rank_watch.py v2 — 実Google順位計測型SEO Rank Watch
=================================================================
設計 (2026-09-11 実測調査に基づく):

1. 計測: Apify公式「Google Search Results Scraper」(actId nFJndFXA5zjCTuudP)
   - 実Google SERPのorganicResultsを取得し、target_urlの実順位を測る
   - 1キーワード/回・maxResults=20 で $0.02-0.04程度。月間コスト <$1.5
   - 予算ガード: 当日 Apify usage が DAILY_USD_CAP 超えたら計測スキップ
2. 選定: watchwords.json から
   - status=active で next_review_day 到達 → 観察フェーズ (改善効果判定)
   - それ以外は計測回数が最少のactive候補を1件
3. 改善 (close-keyword優先):
   - rank 4-10 → タイトル微調整 (Apify actor title PATCH)
   - rank 11-20 → 記事bodyにキーワードH2追加 (dev.to article PATCH)
   - rank 21+ or 圏外 → 新規dev.to記事で被リンク獲得 (週次cron任せ)
   - 改善は1回/日まで。実APIを叩いて「loopを閉じる」
4. 記録: rank-history.json / improvement-log.json は append-only
5. ステートマシン: initial → active → observing → (7日後判定) achieved/retry

使い方: python3 scripts/seo_rank_watch.py [--dry-run]
"""

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "seo"
HIST = DATA / "rank-history.json"
IMPROVE = DATA / "improvement-log.json"
WATCH = DATA / "watchwords.json"
ENV = ROOT / ".env"

DAILY_USD_CAP = 0.50  # Apify SERP計測の日次上限
GS_ACT = "nFJndFXA5zjCTuudP"  # Apify公式 Google Search Results Scraper


def env_val(key: str) -> str:
    """project .env から値取得 (プロセス環境を優先)"""
    if key in os.environ:
        return os.environ[key]
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_json(path: Path, list_key: str, entry: dict) -> None:
    """append-only 追記 (既存エントリは絶対に書き換えない)"""
    d = load_json(path, {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault(list_key, []).append(entry)
    # 不要キー掃除 (v1の残骸)
    for k in ("notes", "created_at", "source"):
        d.setdefault(k, d.get(k, ""))
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- SERP 計測
def apify_headers() -> dict:
    tok = env_val("APIFY_TOKEN_DEFAULT")
    if not tok:
        raise RuntimeError("APIFY_TOKEN_DEFAULT が未設定")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def apify_today_usage_usd() -> float:
    """当日のApifyプラットフォーム使用料 (USD)"""
    try:
        import requests

        r = requests.get(
            "https://api.apify.com/v2/runs",
            headers=apify_headers(),
            params={"limit": 200, "startedAfter": today() + "T00:00:00Z"},
            timeout=60,
        )
        runs = r.json().get("data", {}).get("items", [])
        total = sum(float(x.get("usageTotalUsd") or 0) for x in runs)
        return round(total, 4)
    except Exception as e:
        print(f"[warn] usage取得失敗: {e}")
        return 0.0


def google_rank(keyword: str, target_url: str, max_results: int = 20):
    """実Google SERPでtarget_urlの順位を取得。見つからなければ None"""
    import requests

    run = (
        requests
        .post(
            f"https://api.apify.com/v2/acts/{GS_ACT}/runs?waitForFinish=150",
            headers=apify_headers(),
            json={
                "queries": keyword,
                "countryCode": "jp",
                "searchLanguage": "ja",
                "maxResults": max_results,
            },
            timeout=170,
        )
        .json()
        .get("data", {})
    )
    if run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"SERP run 失敗: status={run.get('status')}")
    usd = float(run.get("usageTotalUsd") or 0)

    items = requests.get(
        f"https://api.apify.com/v2/datasets/{run['defaultDatasetId']}/items",
        headers=apify_headers(),
        params={"limit": 10},
        timeout=60,
    ).json()
    rank = None
    total_organic = 0
    for it in items:
        organic = it.get("organicResults") or []
        total_organic = max(total_organic, len(organic))
        for i, o in enumerate(organic, 1):
            if target_url in (o.get("u") or o.get("url") or o.get("link") or ""):
                rank = i
                break
        if rank:
            break
    return rank, total_organic, usd


# ---------------------------------------------------------------- 選定
def select_keyword(keywords: list, history: dict) -> dict | None:
    """計測対象を1件選ぶ: 観察到期を最優先、次に計測回数最少のactive。

    ⚠ 到期判定は ``<=``（2026-09-26 修正）。旧実装は ``next_review_day == today()``
    の完全一致で、期限日を1日でも逃すと永久に選ばれなかった。加えて全語が
    observing（active=0）だったため actives が空になり、9/19〜9/26 の15日間
    毎日「対象キーワードなし」で no-op = 計測ループが完全停止していた
    （cron は last_status=ok なので一見正常。silent-pipeline 型の停滞）。
    """
    logs = history.get("log", [])
    counts: dict[str, int] = {}
    for e in logs:
        if e.get("keyword"):
            counts[e["keyword"]] = counts.get(e["keyword"], 0) + 1

    # 1) observing 到期チェック（期限超過分も拾う。超過=観察判定が遅れている）
    overdue = [
        kw for kw in keywords
        if kw.get("status") == "observing"
        and kw.get("next_review_day")
        and kw["next_review_day"] <= today()
    ]
    if overdue:
        # 最も期限が古い語から
        return sorted(overdue, key=lambda k: k.get("next_review_day") or "")[0]

    # 2) active のうち最少計測
    actives = [kw for kw in keywords if kw.get("status") == "active"]
    if actives:
        return min(actives, key=lambda k: (counts.get(k["key"], 0), k["key"]))

    # 3) フォールバック: 未到期の observing を最少計測で選ぶ。
    #    「対象ゼロで永久停止」を構造的に防ぐ（語が1つでもループは回り続ける）。
    observing = [kw for kw in keywords if kw.get("status") == "observing"]
    if observing:
        return min(observing, key=lambda k: (counts.get(k["key"], 0), k["key"]))

    # 4) どれも無いときだけ None（＝seed 未登録のみ）
    return keywords[0] if keywords else None


# ---------------------------------------------------------------- 改善
def improve_apify_title(actor_path: str, keyword: str) -> bool:
    """actor title にキーワードを自然に含める (PATCH相当はPUT)"""
    import requests

    H = apify_headers()  # noqa: N806 (ruff pre-commit互換: 大文字ヘッダdictはローカル完結)
    api = f"https://api.apify.com/v2/acts/{actor_path}"
    a = requests.get(api, headers=H, timeout=30).json()["data"]
    cur = a.get("title") or ""
    if keyword.lower() in cur.lower():
        print(f"  [skip] title already contains keyword: {cur!r}")
        return False
    # 現タイトル + 区切り + keyword (30-60字目安)
    sep = " | " if "|" not in cur else " — "
    new_title = f"{cur}{sep}{keyword.title()}"[:80]
    r = requests.put(api, headers=H, json={"title": new_title}, timeout=30)
    ok = r.status_code == 200
    print(f"  title: {cur!r} -> {new_title!r} ({r.status_code})")
    return ok


def improve_devto_article(article_id: int, keyword: str, api_key: str) -> bool:
    """記事body末尾にキーワードH2節を追記 (被リンク用)"""
    import requests

    H = {"api-key": api_key, "Content-Type": "application/json"}  # noqa: N806
    r = requests.get(f"https://dev.to/api/articles/{article_id}", headers=H, timeout=30).json()
    body = r.get("body_markdown") or ""
    if keyword.lower() in body.lower():
        print("  [skip] article already mentions keyword")
        return False
    slug = keyword.lower().replace(" ", "-")
    section = (
        f"\n\n## More on {keyword.title()}\n\n"
        f"If you are looking for a {slug}, the Apify actors below cover it:\n\n"
        f"- [Mercari Japan scraper](https://apify.com/fruitful_quintessence/mercari-japan-search-scraper)\n"
        f"- [Yahoo Auctions / Suruga-ya price data](https://apify.com/fruitful_quintessence/japan-offmall-market-scraper)\n"
    )
    r2 = requests.put(
        "https://dev.to/api/articles/me",
        headers=H,
        json={"article": {"body_markdown": body + section}},
        timeout=30,
    )
    ok = r2.status_code in (200, 201)
    print(f"  dev.to article {article_id}: append section ({r2.status_code})")
    return ok


def decide_action(rank, keyword: str) -> str:
    """close-keyword戦略: rank帯ごとに最小コストの一手"""
    if rank is None:
        return "new_devto_backlink"
    if rank <= 3:
        return "hold"  # 上位安定 — 触らない
    if rank <= 10:
        return "tune_title"
    if rank <= 20:
        return "append_body_section"
    return "new_devto_backlink"


# ---------------------------------------------------------------- main
def main() -> int:
    dry = "--dry-run" in sys.argv

    watch = load_json(WATCH, {"keywords": []})
    keywords = [k for k in watch.get("keywords", []) if k.get("status") != "retired"]
    hist = load_json(HIST, {"log": []})

    # ステートマシン initial→active 昇格 (9/11修正: これが無くseed語が永久不選出だった)
    promoted = False
    for k in keywords:
        if k.get("status") == "initial":
            k["status"] = "active"
            promoted = True
            print(f"initial→active 昇格: {k['key']}")
    if promoted:
        WATCH.write_text(json.dumps(watch, ensure_ascii=False, indent=2), encoding="utf-8")

    # v1ログの掃除: keywordなしの skip エントリは選定カウントから除外済み
    kw = select_keyword(keywords, hist)
    if not kw:
        print("対象キーワードなし — 終了")
        return 0

    key = kw["key"]
    target = kw.get("target_url") or ""
    print(f"[{today()}] 計測対象: {key} -> {target}")

    if dry:
        print("[dry-run] 計測せず終了")
        return 0

    # 予算ガード
    used = apify_today_usage_usd()
    print(f"Apify当日使用: ${used:.4f} / cap ${DAILY_USD_CAP:.2f}")
    if used >= DAILY_USD_CAP:
        print("日次予算上限到達 — 計測スキップ")
        append_json(HIST, "log", {"date": today(), "note": f"budget_cap_skip: ${used:.2f}"})
        return 0

    # 実順位計測
    rank, organic_count, usd = google_rank(key, target)
    print(f"Google順位: {rank if rank else '圏外'} / organic {organic_count}件 / cost ${usd:.4f}")

    entry = {
        "date": today(),
        "keyword": key,
        "rank": rank,
        "rank_source": "google_jp_serp_apify",
        "imp": organic_count,
        "cost_usd": round(usd, 4),
        "action_taken": "none",
    }
    append_json(HIST, "log", entry)

    # 改善判定 (1回/日まで)
    action = decide_action(rank, key)
    print(f"改善アクション: {action}")
    improved = False
    detail = ""

    if action == "tune_title":
        actor = re.sub(r"^https://apify\.com/", "", target)
        improved = improve_apify_title(actor, key)
        detail = f"title tuned -> contains {key!r}"
    elif action == "append_body_section":
        art_id = kw.get("devto_article_id")
        if art_id:
            improved = improve_devto_article(int(art_id), key, env_val("DEVTO_API_KEY"))
            detail = f"dev.to {art_id} append section"
        else:
            action = "new_devto_backlink"
            detail = "no article_id — fallback to backlink"
    elif action == "new_devto_backlink":
        # 即席で新規記事は回さない (週次devto-weekly-seo-post cronに任せる)
        detail = "queued for weekly devto post cron"
        improved = False
    elif action == "hold":
        detail = "rank<=3 stable — no action"

    if action not in ("none", "hold"):
        entry2 = {
            "date": today(),
            "keyword": key,
            "rank_before": rank,
            "status": "active",
            "action": action,
            "detail": detail,
            "improved": improved,
            "next_review_day": (date.today() + timedelta(days=7)).isoformat(),
        }
        append_json(IMPROVE, "log", entry2)
        # 観察フェーズへ
        if improved or action == "new_devto_backlink":
            kw["status"] = "observing"
            kw["next_review_day"] = (date.today() + timedelta(days=7)).isoformat()
            # watchwords.json 更新 (status列のみ — これはseed自身の寿命管理)
            watch["keywords"] = [kw if k2["key"] == kw["key"] else k2 for k2 in watch["keywords"]]
            WATCH.write_text(json.dumps(watch, ensure_ascii=False, indent=2), encoding="utf-8")

    # observing 到期 → achieved判定
    for k2 in watch["keywords"]:
        if k2.get("status") == "observing" and k2.get("next_review_day") == today():
            recs = [e for e in hist["log"] if e.get("keyword") == k2["key"]]
            if recs:
                first, last = recs[0], recs[-1]
                improved_rank = (last.get("rank") or 99) < (first.get("rank") or 99)
                k2["status"] = "achieved" if improved_rank else "active"
                note = "achieved" if improved_rank else "retry"
                print(f"観察判定: {k2['key']} -> {note}")
                append_json(
                    IMPROVE,
                    "log",
                    {
                        "date": today(),
                        "keyword": k2["key"],
                        "status": k2["status"],
                        "rank_first": first.get("rank"),
                        "rank_last": last.get("rank"),
                    },
                )
    WATCH.write_text(json.dumps(watch, ensure_ascii=False, indent=2), encoding="utf-8")

    print("完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
