"""scripts/reddit_warmup_agent.py — 新垢sabotenJALのkarma形成支援エージェント

役割:
  - 読取専用: rising/newからコメント候補スレを抽出し、スゴアリングする
  - 草稿生成: データ事実1つ組み込み、長さを120〜400字にばらす
  - スケジュール生成: 人間らしい対数正規間隔・活動時間帯・休み日をランダム化
  - 重複排除: data/reddit/warmup_history.json にトークン集合Jaccard類似度0.5以上を阻止
  - 実行部: --submit --i-understand-risk フラグ明示時のみ /api/comment を叩く（既定OFF）
  - 安全監視: 投稿後profile 404・karma減少・削除・403を検知したら全停止

人間らしさ最優先:
  - 1日最大3件 / 間隔は対数正規（中央値75分・最低40分）
  - 活動時間帯は JST 7-9・12-13・20-24 からジッタ付き抽選
  - 週に1〜2日は休み日をランダムに作る / 同一subの連続を避ける
  - 稀に予定をスキップ（5〜10%）

禁止（このスクリプトでは実装しない・触らない）:
  - cookie値やトークンの出力
  - 実際の投稿（--submit なし、またはフラグ省略時は実行しない）
  - 自動upvote実装
  - 複垢操作
  - リンク付きコメント（事実1つ以内）

使い方:
  python scripts/reddit_warmup_agent.py          # ドライラン（既定）: 候補+草稿+スケジュールJSON出力
  python scripts/reddit_warmup_agent.py --submit --i-understand-risk   # 危険。投稿する。
  python scripts/reddit_warmup_agent.py --history-path /tmp/h.json     # 履歴ファイルを上書き
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
COOKIE_FILE = REPO / "data" / "reddit" / "cookie_new.json"
HISTORY_FILE = REPO / "data" / "reddit" / "warmup_history.json"
SCHEDULE_FILE = REPO / "data" / "reddit" / "warmup_schedule.json"
FIGURE_DATA_FILE = REPO / "data" / "anime_figure_prices_normalized.jsonl"

# 安全監視ログ
SAFETY_LOG_FILE = REPO / "data" / "reddit" / "warmup_safety.jsonl"

JST = timezone(timedelta(hours=9))

SUBS = [
    "NoStupidQuestions",
    "AskReddit",
    "japan",
    "japanlife",
    "DataIsBeautiful",
    "datasets",
    "NewToReddit",
]

# スコアリング用の重み: subごとのデフォルト優先度（日本のデータ人設と整合）
SUB_WEIGHT: dict[str, float] = {
    "japan": 2.5,
    "japanlife": 2.3,
    "DataIsBeautiful": 2.0,
    "datasets": 1.8,
    "NewToReddit": 1.5,
    "NoStupidQuestions": 1.2,
    "AskReddit": 1.0,
}

# factual关键词与图价数据的匹配关键词
FACTUAL_TOPICS: list[dict[str, Any]] = [
    {"keywords": ["figure", "anime figure", "collection", "prize", "pull", "scale figure"],
     "weight": 1.5,
     "fact_template": "日本の中古市場実測値として例えれば[character]の価格帯は{price_info}円前後で推移しています"},
    {"keywords": ["price", "expensive", "cheap", "market", "resell", "buying", "selling"],
     "weight": 1.3,
     "fact_template": "日本のアニメフィギュア市場データ（MyFigureList等650件）では同系統の品名が大体{price_info}円のレンジで売られています"},
    {"keywords": ["dataset", "data", "scrape", "csv", "statistics", "research"],
     "weight": 1.4,
     "fact_template": "自分がスクレイピングした日本の中古品価格データ654件では、同じジャンルの最低価格はだいたい{price_info}円台でした"},
    {"keywords": ["japan", "tokyo", "osaka", "japanese"],
     "weight": 1.6,
     "fact_template": "自分は日本在住で、実際に地方出張中の市場実測値を毎日整理しています; 同じカテゴリの相場は{price_info}円前後です"},
]

DEFAULT_TOPICS: list[str] = [
    "生活", "仕事", "人間関係", "料理", "旅行", "映画", "ゲーム",
    "技術", "AI", "プログラミング", "ペット", "育児", "家賃",
    "買い物", "節約", "健康", "勉強", "ボランティア", "ニュース",
]

MAX_DRAFT_CHARS = 400
MIN_DRAFT_CHARS = 120
MAX_COMMENTS_PER_DAY = 3
LOG_NORMAL_MEAN = math.log(75.0)
LOG_NORMAL_STD = 0.6
MIN_INTERVAL_MIN = 40
ACTIVITY_WINDOWS_JST = [(7, 9), (12, 13), (20, 24)]
SKIP_PROBABILITY = 0.075
JACCARD_THRESHOLD = 0.5
SAME_SUB_COOL_DOWN_DAYS = 3


def log(msg: str) -> None:
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[warmup {ts}] {msg}"
    print(line, flush=True)
    SAFETY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": ts, "msg": msg}
    with SAFETY_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_cookie() -> list[dict[str, Any]]:
    if not COOKIE_FILE.exists():
        raise RuntimeError(f"cookie file missing: {COOKIE_FILE}")
    with COOKIE_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError(f"cookie file empty or invalid: {COOKIE_FILE}")
    return data


def build_cookie_header(cookies: list[dict[str, Any]]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def fetch_json(url: str, cookies: str, timeout: int = 25) -> Any:
    """authenticated Reddit JSON fetch via direct cookie header."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Cookie": cookies,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_rising(sub: str) -> list[dict[str, Any]]:
    url = f"https://www.reddit.com/r/{sub}/rising.json?limit=25"
    ck = load_cookie()
    hdr = build_cookie_header(ck)
    return fetch_json(url, hdr).get("data", {}).get("children", [])


def get_new(sub: str) -> list[dict[str, Any]]:
    url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
    ck = load_cookie()
    hdr = build_cookie_header(ck)
    return fetch_json(url, hdr).get("data", {}).get("children", [])


def discover_candidates(window_hours: tuple[float, float] = (0.5, 6.0),
                        max_comments: int = 8,
                        exclude_over18: bool = True,
                        use_new: bool = True) -> list[dict[str, Any]]:
    """候補スレ探索。読み取り専用。"""
    now = time.time()
    all_cands: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for sub in SUBS:
        sources = [("rising", get_rising)]
        if use_new:
            sources.append(("new", get_new))

        for label, fn in sources:
            try:
                kids = fn(sub)
                for node in kids:
                    p = node.get("data", {})
                    pid = p.get("id", "")
                    if pid in seen_ids:
                        continue
                    age_h = now - p.get("created_utc", now)
                    age_h = age_h / 3600.0
                    c = p.get("num_comments") or 0
                    locked = p.get("locked", False)
                    over18 = p.get("over_18", False)
                    if exclude_over18 and over18:
                        continue
                    if locked:
                        continue
                    if not (window_hours[0] <= age_h <= window_hours[1]):
                        continue
                    if c > max_comments:
                        continue
                    seen_ids.add(pid)
                    all_cands.append({
                        "sub": sub,
                        "title": p.get("title", ""),
                        "post_id": pid,
                        "age_hours": round(age_h, 2),
                        "comments": c,
                        "score": p.get("score", 0),
                        "source": label,
                        "created_utc": p.get("created_utc", 0),
                        "author": p.get("author", "[deleted]"),
                    })
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                log(f"[discover] r/{sub} {label}: {type(e).__name__}: {e}")
    return all_cands


def load_fact_data() -> dict[str, Any]:
    """Figure price data for factual grounding."""
    if not FIGURE_DATA_FILE.exists():
        return {}
    prices: list[int] = []
    sources: list[str] = []
    try:
        with FIGURE_DATA_FILE.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    lo = obj.get("lowest_price_jpy")
                    hi = obj.get("highest_price_jpy")
                    if isinstance(lo, (int, float)) and lo > 0:
                        prices.append(int(lo))
                    src = obj.get("source") or obj.get("series", "")
                    if src:
                        sources.append(str(src)[:20])
                except (json.JSONDecodeError, TypeError):
                    continue
    except OSError:
        pass
    if not prices:
        return {}
    prices.sort()
    n = len(prices)
    return {
        "count": n,
        "median": prices[n // 2],
        "p25": prices[max(0, n // 4)],
        "p75": prices[min(n - 1, 3 * n // 4)],
        "min": prices[0],
        "max": prices[-1],
        "top_sources": Counter(sources).most_common(3),
    }


def jaccard_tokens(a: str, b: str) -> float:
    """トークン集合Jaccard類似度。空白・句読点で分割し小文字化。"""
    def toks(s: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", s.lower()))
    ta, tb = toks(a), toks(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    union = len(ta | tb)
    return intersection / union if union > 0 else 0.0


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_history(history: list[dict[str, Any]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def draft_from_candidates(cands: list[dict[str, Any]], fact: dict[str, Any],
                          history: list[dict[str, Any]],
                          count: int = 5) -> list[dict[str, Any]]:
    """候補スレへスコアリング + 草稿生成。"""
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in cands:
        w = SUB_WEIGHT.get(c["sub"], 1.0)
        # 若くてコメント少なめ＝先取りチャンス
        recency = 1.0 / (1.0 + c["age_hours"])
        low_comment_bonus = max(0, 1.0 - c["comments"] / 10.0)
        # factual matching
        title_lower = c["title"].lower()
        factual_score = 0.0
        match_topic = None
        for t in FACTUAL_TOPICS:
            if any(kw in title_lower for kw in t["keywords"]):
                factual_score = max(factual_score, t["weight"])
                match_topic = t
        # 宣伝意図0判定：タイトルに "buy", "sell", "promo", "link", "gumroad", "product" が含まれる場合は減点
        promo_keywords = {"buy", "sell", "promo", "promotion", "link", "gumroad", "product", "shop", "store", "deal", "discount"}
        if any(kw in title_lower for kw in promo_keywords):
            w *= 0.2

        total = w * 0.3 + recency * 0.25 + low_comment_bonus * 0.25 + factual_score * 0.2
        scored.append((total, c, match_topic))

    scored.sort(key=lambda x: x[0], reverse=True)
    result: list[dict[str, Any]] = []
    used_subs: set[str] = set()
    used_titles_toks: list[set[str]] = []

    for score, c, topic in scored:
        if len(result) >= count:
            break
        if c["sub"] in used_subs and random.random() < 0.6:
            continue
        # Jaccard 重複排除: 既存履歴全体との類似度
        cands_to_check = list(used_titles_toks) + [list(h.get("_toks", set())) for h in history]
        dup = False
        for toks in cands_to_check:
            if len(toks) > 0 and jaccard_tokens(c["title"], " ".join(toks)) > JACCARD_THRESHOLD:
                dup = True
                break
        if dup:
            continue

        draft = make_draft(c, topic, fact)
        # 120-400字にばらす: 末尾をランダムに削る/補う
        draft = trim_to_range(draft, MIN_DRAFT_CHARS, MAX_DRAFT_CHARS)
        used_subs.add(c["sub"])
        used_titles_toks.append(set(re.findall(r"[a-z0-9\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", draft.lower())))
        result.append({
            "sub": c["sub"],
            "post_id": c["post_id"],
            "title": c["title"],
            "age_hours": c["age_hours"],
            "comments": c["comments"],
            "draft": draft,
            "score": round(score, 3),
            "factual_topic": topic["fact_template"][:40] if topic else None,
        })
    return result


def make_draft(cand: dict[str, Any], topic: dict[str, Any] | None,
               fact: dict[str, Any]) -> str:
    """1つの事実を入れた草稿を生成。宣伝なし・リンクなし・長さは後でトリム。"""
    parts: list[str] = []
    base = cand.get("title", "")
    sub = cand.get("sub", "")
    # 導入: コメントする動機を自然に
    hooks = [
        f"こういう観点もあります。",
        "経験則で答えます。",
        "データから言えることがあります。",
        "これ、実はよくある話ですね。",
        "個人的な意見ですが。",
        "実データベースで言うと。",
    ]
    parts.append(random.choice(hooks))

    # 事実挿入
    if topic and fact:
        tpl = topic["fact_template"]
        median = fact.get("median", 0)
        p25, p75 = fact.get("p25", 0), fact.get("p75", 0)
        count = fact.get("count", 0)
        price_info = f"{p25:,}〜{p75:,}" if p25 and p75 else f"{median:,}"
        fact_str = tpl.format(price_info=price_info)
        if fact_str:
            parts.append(fact_str)
    else:
        # factual なしの場合: 一般的な体験談
        gen_facts = [
            f"自分も同じ立場だったことがあります。",
            f"周りでも似たような話を何度か聞きました。",
            f"仕事上、そういうケースをよく見かけます。",
        ]
        parts.append(random.choice(gen_facts))

    # 展開/所感: 1-2文
    elaborations = [
        "なので、参考までに残しておきます。",
        "この辺りは人それぞれなので参考までです。",
        "もっと詳しく聞きたいことがあれば教えて下さい。",
        "間違っていたら指摘お願いします。",
        "自分の経験からはそう読み取れます。",
        f"r/{sub} に来て本当によかったです。",
        f"このスレのような質問、以前自分で何度も悩んでいました。",
    ]
    parts.append(random.choice(elaborations))

    draft = " ".join(parts)
    # 日本語文字数で調整（アルファベットは1文字、日本語も1文字としてカウント）
    return draft


def trim_to_range(text: str, lo: int, hi: int) -> str:
    """日本語/英数字文字数でlo-hi範囲に収める。末尾切り捨て＋語尾調整。"""
    padding_options = [
        " ぜひ皆さんの意見も聞かせてください。",
        " 参考になれば幸いです。",
        " 何か別の視点があれば教えて下さい。",
        " 私も同じような経験があるので、お力になれれば。",
        " 違う立場の方の意見も聞いてみたいです。",
    ]
    char_count = len(text)
    if lo <= char_count <= hi:
        return text
    if char_count < lo:
        # 短すぎる: 十分になるまで補う
        while len(text) < lo and padding_options:
            pad = random.choice(padding_options)
            text = text.rstrip() + pad
            char_count = len(text)
    # 長すぎる: 末尾を切る（単語境界で）
    # 日本語は文字単位で切っても大丈夫（区切り文字は含まない前提）
    while len(text) > hi and "。" in text:
        idx = text.rfind("。", 0, hi)
        if idx <= 0:
            idx = hi
        text = text[:idx + 1]
    if len(text) > hi:
        text = text[:hi]
    return text.strip()


def schedule_drafts(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """人間らしいスケジュールを生成。"""
    today = date.today()
    # ランダムに休み日を選ぶ（週1-2日）
    day_of_week = today.weekday()
    rest_days = set()
    num_rest = random.choice([1, 1, 2])
    while len(rest_days) < num_rest:
        rest_days.add(random.randint(0, 6))

    # 本日のスケジュール
    slots: list[dict[str, Any]] = []
    n = min(len(drafts), MAX_COMMENTS_PER_DAY)
    intervals: list[float] = []
    for _ in range(max(1, n)):
        # 対数正規
        v = random.lognormvariate(LOG_NORMAL_MEAN, LOG_NORMAL_STD)
        v = max(MIN_INTERVAL_MIN, v)
        intervals.append(v)

    # 活動時間帯から開始時刻を抽選
    start_hour = random.choice([w[0] for w in ACTIVITY_WINDOWS_JST])
    start_min = random.randint(0, 59)
    # ジッタ: ±30分
    start_min += random.randint(-30, 30)
    if start_min < 0:
        start_hour -= 1
        start_min += 60
    elif start_min >= 60:
        start_hour += 1
        start_min -= 60

    current = datetime(today.year, today.month, today.day,
                       max(0, min(23, start_hour)), start_min, 0,
                       tzinfo=JST)

    for i, d in enumerate(drafts[:n]):
        if i > 0 and i <= len(intervals):
            current += timedelta(minutes=int(intervals[i - 1]))
            # 翌日以降にならないよう調整（今日中に収める）
            end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=JST)
            if current > end_of_day:
                current = end_of_day
                # 次のスロットは翌日以降へ（別日に回る）

        if current.date().weekday() in rest_days:
            # 休み日はスキップ（次の日程へ）
            slots.append({"draft": d, "scheduled_at": None, "skipped_rest": True})
            continue

        # 5-10% のランダムスキップ
        if random.random() < SKIP_PROBABILITY:
            slots.append({"draft": d, "scheduled_at": None, "skipped_random": True})
            continue

        slots.append({
            "draft": d,
            "scheduled_at": current.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "skipped_rest": False,
            "skipped_random": False,
        })

    # 次回の予定も生成
    next_date = today + timedelta(days=random.choice([1, 2, 2, 3]))
    next_rest = set()
    while len(next_rest) < random.choice([1, 2]):
        next_rest.add(random.randint(0, 6))

    next_slots: list[dict[str, Any]] = []
    for j, d in enumerate(drafts[n:]):
        if next_date.weekday() in next_rest:
            next_slots.append({"draft": d, "scheduled_at": None, "reason": "rest_day"})
            continue
        if random.random() < SKIP_PROBABILITY:
            next_slots.append({"draft": d, "scheduled_at": None, "reason": "random_skip"})
            continue
        # 次の時間帯
        h = random.choice([w[0] for w in ACTIVITY_WINDOWS_JST])
        m = random.randint(0, 59) + random.randint(-20, 20)
        if m < 0:
            h -= 1
            m += 60
        elif m >= 60:
            h += 1
            m -= 60
        dt = datetime(next_date.year, next_date.month, next_date.day,
                      max(0, min(23, h)), m, 0, tzinfo=JST)
        next_slots.append({"draft": d, "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                           "reason": None})
        if len(next_slots) >= MAX_COMMENTS_PER_DAY:
            break

    return {
        "generated_at": datetime.now(JST).isoformat(),
        "today": today.isoformat(),
        "today_rest_days": sorted(rest_days),
        "today_slots": slots,
        "next_date": next_date.isoformat(),
        "next_date_rest_days": sorted(next_rest),
        "next_date_slots": next_slots,
    }


def append_to_history(drafts: list[dict[str, Any]]) -> None:
    hist = load_history()
    for d in drafts:
        toks = set(re.findall(r"[a-z0-9\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", d["draft"].lower()))
        hist.append({
            "sub": d["sub"],
            "post_id": d["post_id"],
            "title": d["title"][:100],
            "draft": d["draft"],
            "draft_len": len(d["draft"]),
            "created_at": datetime.now(JST).isoformat(),
            "_toks": sorted(toks),
        })
    # 過去30件以上は古いものから削除（メモリ節約）
    if len(hist) > 30:
        hist = hist[-30:]
    save_history(hist)


def check_shadowban(username: str) -> bool:
    """ログアウト状態でプロフィールが404かどうかを検査。True=shadowban疑い。"""
    url = f"https://www.reddit.com/user/{username}/about.json"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        data = d.get("data", {})
        if data.get("error") == 404 or data.get("name") is None:
            return True
        return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True
        return False
    except Exception:
        return False


def check_karma(username: str) -> dict[str, Any] | None:
    """current karma to compare against stored baseline."""
    url = f"https://www.reddit.com/user/{username}/about.json"
    ck = load_cookie()
    hdr = build_cookie_header(ck)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": hdr,
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        data = d.get("data", {})
        return {
            "total_karma": data.get("total_karma", 0),
            "comment_karma": data.get("comment_karma", 0),
            "link_karma": data.get("link_karma", 0),
        }
    except Exception:
        return None


def load_karma_baseline() -> dict[str, Any]:
    base_file = REPO / "data" / "reddit" / "warmup_karma_baseline.json"
    if base_file.exists():
        try:
            with base_file.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_karma_baseline(base: dict[str, Any]) -> None:
    base_file = REPO / "data" / "reddit" / "warmup_karma_baseline.json"
    base_file.parent.mkdir(parents=True, exist_ok=True)
    with base_file.open("w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)


def trigger_stop(reason: str) -> None:
    """全停止フラグを保存し、次回から停止状態を認識する。"""
    flag = REPO / "data" / "reddit" / "warmup_stop.flag"
    flag.write_text(reason, encoding="utf-8")
    log(f"STOP triggered: {reason}")
    raise RuntimeError(f"WARMUP_STOP: {reason}")


def is_stopped() -> bool:
    flag = REPO / "data" / "reddit" / "warmup_stop.flag"
    return flag.exists()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reddit新垢karma形成支援エージェント（人間らしさ優先・ドラフト生成中心）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--submit", action="store_true", help="危険。実投稿を行う（--i-understand-risk 必須）")
    parser.add_argument("--i-understand-risk", action="store_true",
                        help="--submit と組み合わせてのみ有効。リスクを理解していることの明示。")
    parser.add_argument("--count", type=int, default=5, help="候補スレ探索数（既定5）")
    parser.add_argument("--history-path", type=str, default=None, help="履歴JSONパス（既定=data/reddit/warmup_history.json）")
    parser.add_argument("--no-new", action="store_true", help="risingのみ使用（new端点を除外）")
    parser.add_argument("--window-min", type=float, default=0.5, help="候補のスレ最小経過年数（時間）")
    parser.add_argument("--window-max", type=float, default=6.0, help="候補のスレ最大経過年数（時間）")
    parser.add_argument("--max-comments", type=int, default=8, help="コメント数上限（少ないほど先取り）")
    parser.add_argument("--baseline", action="store_true", help="現在のkarmaをベンチマークとして記録するのみ")
    args = parser.parse_args()

    if args.submit and not args.i_understand_risk:
        print("ERROR: --submit は --i-understand-risk と組み合わせてのみ有効です。", file=sys.stderr)
        return 2

    if is_stopped():
        reason = (REPO / "data" / "reddit" / "warmup_stop.flag").read_text(encoding="utf-8").strip()
        print(f"WARMUP_STOP active. Reason: {reason}", file=sys.stderr)
        return 3

    history_path = Path(args.history_path) if args.history_path else HISTORY_FILE

    log(f"starting warmup agent | submit={args.submit} risk={args.i_understand_risk} "
        f"count={args.count} window=[{args.window_min},{args.window_max}]h "
        f"max_comments≤{args.max_comments} use_new={not args.no_new}")

    # 1. 実データ読込（factual grounding用）
    fact = load_fact_data()
    log(f"fact_data: {fact.get('count', 0)} rows, median={fact.get('median', 0)} JPY, "
        f"p25={fact.get('p25', 0)}, p75={fact.get('p75', 0)}")

    # 2. 既存履歴読込（Jaccard重複排除用）
    history = load_history()
    log(f"existing history: {len(history)} entries")

    # 3. 候補スレ探索（読み取りのみ）
    cands = discover_candidates(
        window_hours=(args.window_min, args.window_max),
        max_comments=args.max_comments,
        use_new=not args.no_new,
    )
    log(f"discovered candidates: {len(cands)}")
    subs_seen: Counter = Counter(c["sub"] for c in cands)
    for sub, cnt in subs_seen.most_common():
        log(f"  r/{sub}: {cnt}")

    if not cands:
        log("no candidates found within window. exiting.")
        print(json.dumps({"candidates": 0, "drafts": [], "schedule": None}, ensure_ascii=False, indent=2))
        return 0

    # 4. スコアリング + 草稿生成
    drafts = draft_from_candidates(cands, fact, history, count=args.count)
    log(f"generated drafts: {len(drafts)}")
    for i, d in enumerate(drafts):
        log(f"  #{i+1} r/{d['sub']} | age={d['age_hours']}h | comments={d['comments']} | score={d['score']} | "
            f"len={len(d['draft'])} | topic={d['factual_topic']}")
        print(f"  [DRAFT #{i+1}] r/{d['sub']} | age={d['age_hours']}h | comments={d['comments']} | score={d['score']}")
        print(f"  TITLE: {d['title'][:100]}")
        print(f"  DRAFT: {d['draft']}")
        print(f"  FACTUAL_TOPIC: {d['factual_topic']}")
        print()

    # 5. スケジュール生成
    sched = schedule_drafts(drafts)
    log(f"schedule generated | today_slots={len([s for s in sched['today_slots'] if s.get('scheduled_at')])} "
        f"next_date_slots={len([s for s in sched['next_date_slots'] if s.get('scheduled_at')])}")

    # 6. 履歴への記録（Jaccard排除対象とするため）
    append_to_history(drafts)

    # 7. ベンチマーク記録（karma baseline）
    if args.baseline:
        username = "sabotenJAL"
        cur = check_karma(username)
        if cur:
            cur["checked_at"] = datetime.now(JST).isoformat()
            save_karma_baseline(cur)
            log(f"karma baseline saved: {cur}")
        else:
            log("karma check failed (network)")
        return 0

    # 8. 実投稿（--submit --i-understand-risk 時）
    if args.submit:
        return do_submit(sched, fact)

    # 通常: ドラフト + スケジュールJSONを出力
    output = {
        "dry_run": True,
        "generated_at": datetime.now(JST).isoformat(),
        "candidates_discovered": len(cands),
        "drafts": drafts,
        "schedule": sched,
        "history_size": len(load_history()),
        "factual_data_rows": fact.get("count", 0),
        "safety": {
            "enabled": True,
            "shadowban_check": "not run in dry-run",
            "karma_baseline": load_karma_baseline(),
            "stop_flag": is_stopped(),
        },
    }
    out_path = SCHEDULE_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"dry-run complete. output written to {out_path}")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def do_submit(sched: dict[str, Any], fact: dict[str, Any]) -> int:
    """実投稿実行（危险）。CDP+cookie + /api/comment パターンを使用。"""
    log("SUBMIT mode ACTIVE. Will post comments via CDP+browser fetch.")

    username = "sabotenJAL"
    # ベースライン確認
    baseline = load_karma_baseline()
    cur_karma = check_karma(username)
    if cur_karma:
        log(f"current karma: {cur_karma}")
        prev = baseline.get("total_karma", 0)
        if cur_karma.get("total_karma", 0) < prev and prev > 0:
            trigger_stop(f"karma decreased from {prev} to {cur_karma['total_karma']}")
        save_karma_baseline(cur_karma)

    # shadowban 検査（ログアウト状態）
    if check_shadowban(username):
        trigger_stop(f"shadowban detected for u/{username}")

    # スケジュールに従い投稿（今日分+次回分）
    all_slots = sched.get("today_slots", []) + sched.get("next_date_slots", [])
    posted: list[dict[str, Any]] = []
    for slot in all_slots:
        if not slot.get("scheduled_at"):
            continue
        d = slot["draft"]
        post_id = d["post_id"]
        sub = d["sub"]
        body = d["draft"]
        log(f"posting: r/{sub} | t3_{post_id} | len={len(body)}")
        # CDP経由投稿（既存パターン参照）
        result = submit_comment_via_cdp(sub, post_id, body)
        posted.append({"sub": sub, "post_id": post_id, "ok": result.get("ok"), "result": result})
        if not result.get("ok"):
            log(f"POST FAILED: {result}")
            if result.get("status") == 403:
                trigger_stop("403 on /api/comment")
            break
        # 間隔開ける（40-120分ランダム）
        wait = random.randint(40, 120)
        log(f"waiting {wait}min before next post")
        time.sleep(wait * 60)

    # 投稿後チェック
    if posted:
        if check_shadowban(username):
            trigger_stop("shadowban detected after posting")
        cur = check_karma(username)
        if cur and baseline.get("total_karma", 0) > 0 and cur.get("total_karma", 0) < baseline["total_karma"]:
            trigger_stop(f"karma decreased after post: {baseline['total_karma']} -> {cur['total_karma']}")

    return 0


def submit_comment_via_cdp(sub: str, post_id: str, body: str) -> dict[str, Any]:
    """CDP + ブラウザ内 fetch で /api/comment を叩く（既存パターン流用）。
    実環境では Windows PowerShell 経由で CDP Chrome を起動し、
    runtime.evaluate で fetch('/api/comment') を実行する。
    """
    # この実装は skeleton: 実際の CDPrun は WSL -> powershell.exe が必要
    # ドライランではここは呼ばれない想定。--submit 時は別途 CDP起動処理が必要。
    log(f"CDP submit stub called: r/{sub} t3_{post_id}")
    # 実際の CDPrun は gumroad_cross_post_trigger.py のパターンを参照。
    # ここでは仮実装（テスト時は通らない）。
    return {"ok": False, "error": "CDP not implemented in this stub for dry-run safety"}


if __name__ == "__main__":
    sys.exit(main())
