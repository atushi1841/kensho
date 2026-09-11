#!/usr/bin/env python3
"""
SEO Rank Watch — dev.to / Apify Store keyword rank observation loop.
Ported from 'SEO Rank Watch' tweet prompt (AI site 放置 SEO 改善プロンプト)。
Phase 1: 計測→候補選定 → Phase 2: 1キーワード改善 → Phase 3: 7日観察 → 完了

[WORKFLOW]
1. watchwords.json から 1 keyword を選定（優先度 high → medium → low、未観察優先）
2. rank-history.json から該当 keyword の latest rank / imp を取得
   - dev.to: /api/articles + 独自 analytics（または search ページ PV）で近似
   - Apify store: store API search count / 自actor 順位※
3. rank-history.json にその日分の {date, keyword, rank, rank_source, imp, action_taken} を追記
4. improvement-log.json から該当 keyword の status が 'observing' かつ 7日経過なら：
   - status を 'achieved' に変更。次の cycle 候補からは除く。
5. まだ 'active' あるいは 'observing' 状態の keyword が 1 つだけに絞る：
   - rank_est < 900（概算で上位圏） かつ imp > 0 であること
6. 候補が 1 つ見つかったら、「改善アクション定義」を 1〜2文で作成
   - 例: "meta description に target keyword を先頭配置 + H1 に含載"
7. improvement-log.json に {date, keyword, status: active, action_definition, next_review_day: +7} を追記
8. 7日目以降は status を 'observing' に変更、改善は実施しない（観察のみ）
9. それ以上（候補なし、または 7日観察中）は何もしない — 次回 run で再試行

[CONVENTIONS]
- rank_source: "devto_approx" | "apify_store" | "manual"
- status: "active" | "observing" | "achieved"
- next_review_day: ISO date string YYYY-MM-DD
- 周期: 毎日 1 回 cron 実行。1 run で 1 keyword に絞る。
- GSC が使えない環境（Kensho）では dev.to analytics（記事 PV）を代理指標にする。
- 「7日待つ」のは構造的に最も重要 — 一括改善の弊害（何が効いたか不明）を回避。

[USAGE]
python3 scripts/seo_rank_watch.py

[SIDE EFFECTS]
- data/seo/watchwords.json 読み込み（初回 seed は手動登録）
- data/seo/rank-history.json 追記
- data/seo/improvement-log.json 追記
"""

import json
import os
import re
from datetime import date, datetime, timedelta

ENV = "/mnt/d/Project2/kensho/.env"
SEED_DIR = "/mnt/d/Project2/kensho/data/seo"


def env_val(key):
    for line in open(ENV, encoding="utf-8"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_json(path, entry):
    """append-only: read existing, append entry, write back (overwrite entire file)"""
    data = load_json(path) or {}
    if isinstance(data, dict):
        data.setdefault("log", []).append(entry)
    elif isinstance(data, list):
        data.append(entry)
    save_json(path, data)


def pick_keyword(watchwords):
    """Select one keyword from watchwords.json.
    Priority: high → medium → low.
    Preference: status 未観察 or observing 7日経過分は復活させる。
    Returns: (keyword_dict, index) or (None, None)
    """
    keywords = watchwords.get("keywords", [])
    if not keywords:
        return None, None

    today = date.today().isoformat()

    # まず 'observing' かつ next_review_day 過去のものを復活
    for i, kw in enumerate(keywords):
        rev = kw.get("next_review_day", "")
        if rev and rev <= today and kw.get("status") == "observing":
            return kw, i

    # 優先度順ソート（high=3, medium=2, low=1）
    prio_map = {"high": 3, "medium": 2, "low": 1}
    sorted_kw = sorted(keywords, key=lambda k: prio_map.get(k.get("priority", "low"), 1), reverse=True)

    # status が 'achieved' ではないものから first_candidate
    for i, kw in enumerate(sorted_kw):
        if kw.get("status") not in ("achieved",):
            next_rev = kw.get("next_review_day", "")
            if not next_rev or next_rev <= today:
                return kw, sorted_kw.index(kw)

    # 見つからなければ最初の initial/active
    for kw in sorted_kw:
        if kw.get("status") not in ("achieved",):
            return kw, sorted_kw.index(kw)

    return None, None


def check_rank_devto(slug):
    """dev.to rank approx via article search or API."""
    tok = env_val("DEVTO_API_KEY")
    if not tok:
        return None, None, "no_token"
    try:
        import requests

        r = requests.get(
            "https://dev.to/api/articles",
            params={"per_page": 5, "tag": "japan"},
            timeout=15,
            headers={"Api-Key": tok},
        )
        if r.status_code != 200:
            return None, None, f"api_err:{r.status_code}"
        articles = r.json()
        # article タイトルから検索順位を推定
        for i, a in enumerate(articles):
            if slug.lower() in a.get("title", "").lower():
                imp = len(a.get("description", "") or "")
                return i + 1, imp, "devto_approx"
        # ヒットしなかった→ rank > 5 とする
        if articles:
            imp_vals = []
            for a in articles:
                d = a.get("description", "") or ""
                m = re.search(r"(\d[\d,]*\s*views?)", d.replace(",", ""))
                if m:
                    imp_vals.append(int(m.group(1).split()[0].replace(",", "")))
            if imp_vals:
                median_imp = sorted(imp_vals)[len(imp_vals) // 2]
            else:
                median_imp = len(articles[0].get("description", "")) if articles else 0
        else:
            median_imp = 0
        return 99, median_imp, "devto_approx_no_hit"
    except Exception as e:
        return None, None, f"devto_err:{e}"


def check_rank_apify(keyword):
    """Apify store search での自 actor 順位を確認."""
    tok = env_val("APIFY_TOKEN_DEFAULT")
    if not tok:
        return None, None, "no_token"
    try:
        import requests

        r = requests.get(
            "https://api.apify.com/v2/store",
            params={"token": tok, "query": keyword, "limit": 50},
            timeout=25,
        )
        if r.status_code != 200:
            return None, None, f"api_err:{r.status_code}"
        d = r.json().get("data", {})
        items = d.get("items", [])
        my = [it for it in items if it.get("username") == "fruitful_quintessence"]
        if not my:
            return 999, 0, "apify_store_no_me"
        rank = items.index(my[0]) + 1
        info = my[0].get("stats", {})
        imp = info.get("totalUsers7Days", info.get("bookmarkCount", 0))
        return rank, imp, "apify_store"
    except Exception as e:
        return None, None, f"apify_err:{e}"


def main():
    today = date.today().isoformat()
    watchwords_path = os.path.join(SEED_DIR, "watchwords.json")
    rank_path = os.path.join(SEED_DIR, "rank-history.json")
    log_path = os.path.join(SEED_DIR, "improvement-log.json")

    watchwords = load_json(watchwords_path) or {"keywords": []}
    rank_history = load_json(rank_path) or {"log": []}
    improvement_log = load_json(log_path) or {"log": []}

    # 1. keyword 選定
    kw, kw_idx = pick_keyword(watchwords)
    if kw is None:
        print("[RANK_WATCH] No actionable keyword today. All under achieved or pending review.")
        append_json(rank_path, {"date": today, "note": "no_candidate_all_achieved_or_pending"})
        return

    keyword_key = kw.get("key", "")
    target_url = kw.get("target_url", "")
    priority = kw.get("priority", "low")

    print(f"[RANK_WATCH] Selected keyword: {keyword_key} (priority={priority}, status={kw.get('status', 'initial')})")

    # 2. rank 計測
    # まず Apify store でチェック（キーワードが apify/mercari/dlsite に該当する場合）
    apify_keywords = ["mercari", "dlsite", "apify", "kakaku", "suruga-ya"]
    rank_est, imp_est, rank_source = None, None, "none"

    if any(kw_key in keyword_key.lower() for kw_key in apify_keywords):
        rank_est, imp_est, rank_source = check_rank_apify(keyword_key)
        print(
            f"[RANK_WATCH] Apify store check for '{keyword_key}': rank={rank_est}, imp={imp_est}, source={rank_source}"
        )

    # dev.to fallback（Apify でヒットしなかった、またはランクが取れなかった場合）
    if rank_est is None or rank_est >= 900:
        slug = None
        if target_url:
            m = re.search(r"[^/]+$", target_url)
            if m:
                slug = m.group(0)
        if not slug:
            slug = keyword_key
        rank_est, imp_est, rank_source = check_rank_devto(slug)
        print(f"[RANK_WATCH] dev.to fallback for '{keyword_key}': rank={rank_est}, imp={imp_est}, source={rank_source}")

    # 3. rank-history に追記
    history_entry = {
        "date": today,
        "keyword": keyword_key,
        "rank": rank_est if rank_est else 999,
        "rank_source": rank_source,
        "imp": imp_est if imp_est else 0,
        "action_taken": "none_yet",
    }
    # 既に同じkeyword+date がある場合は追記せずスキップ
    same_day = [e for e in rank_history.get("log", []) if e.get("date") == today and e.get("keyword") == keyword_key]
    if not same_day:
        rank_history.setdefault("log", []).append(history_entry)
        save_json(rank_path, rank_history)
        print(f"[RANK_WATCH] Appended to rank-history.json (total entries: {len(rank_history['log'])})")
    else:
        print(f"[RANK_WATCH] Duplicate date entry skipped for {keyword_key}")

    # 4. improvement-log の処理: status が 'observing' で 7日経過なら 'achieved' へ
    existing_imp_entries = [e for e in improvement_log.get("log", []) if e.get("keyword") == keyword_key]

    latest_status = "active"
    if existing_imp_entries:
        dates_sorted = sorted(existing_imp_entries, key=lambda e: e.get("date", ""))
        latest = dates_sorted[-1]
        latest_status = latest.get("status", "active")
        latest_review = latest.get("next_review_day", "")
    else:
        latest_review = ""

    # observing 状態で 7日経過チェック
    if latest_status == "observing" and latest_review:
        review_date = datetime.strptime(latest_review, "%Y-%m-%d").date()
        if review_date <= date.today():
            latest["status"] = "achieved"
            latest["achieved_at"] = today
            print(f"[RANK_WATCH] Status changed from 'observing' to 'achieved' for {keyword_key} (reviewed {today})")

    # 5. candidate selection: 今日の rank_est / imp_est が条件を満たす keyword が 1 つだけか確認
    # 候補となる条件: rank_est < 900 かつ imp_est > 0 （および status が achieved でないこと）
    candidates = []
    for i, k in enumerate(watchwords.get("keywords", [])):
        s = k.get("status", "initial")
        if s == "achieved":
            continue
        # observing だけど review day が未来なら候補から除く
        if s == "observing":
            rev = k.get("next_review_day", "")
            if rev and rev > today:
                print(f"[RANK_WATCH] '{k.get('key')}' is in observing period (until {rev}) — not a candidate this run")
                continue
        # 今日の rank_est / imp_est がこの keyword に該当し、条件を満たす場合
        # 条件: rank_est < 900 かつ imp_est > 0
        # そしてこの keyword が today の選定対象（keyword_key と一致）であること
        if keyword_key and k.get("key") == keyword_key:
            if rank_est is not None and rank_est < 900 and imp_est is not None and imp_est > 0:
                candidates.append((k, i))
                print(f"[RANK_WATCH] '{k.get('key')}' is a candidate today: rank={rank_est}, imp={imp_est}")
            else:
                reason = []
                if rank_est is None or rank_est >= 900:
                    reason.append(f"rank_est={rank_est} not < 900")
                if imp_est is None or imp_est <= 0:
                    reason.append(f"imp_est={imp_est} not > 0")
                print(f"[RANK_WATCH] '{k.get('key')}' skipped: {', '.join(reason)}")
        # keyword_key と一致しない他 keyword はスキップ

    print(
        f"[RANK_WATCH] Candidate count for '{keyword_key}': {len(candidates)} "
        f"(total keywords: {len(watchwords.get('keywords', []))})"
    )

    if len(candidates) == 1:
        # 候補が 1 つだけ → 改善アクションを定義して active → observing へ
        chosen_kw, chosen_idx = candidates[0]
        chosen_key = chosen_kw.get("key", "")

        # 既存の improvement log から同じ keyword の last action_definition を取得
        last_action = ""
        if existing_imp_entries:
            for e in reversed(existing_imp_entries):
                if e.get("action_definition"):
                    last_action = e.get("action_definition")
                    break

        # 新しい action_definition を生成
        action_def = ""
        if 2 <= rank_est <= 10:
            action_def = (
                f"[{chosen_key}] 順位 {rank_est} 圏内キーワードへの対応: "
                "meta description に target keyword を先頭配置し、H1 に含載する。インラインリンクも補完する。"
            )
        elif rank_est > 10 and rank_est < 900:
            action_def = (
                f"[{chosen_key}] 順位圏外キーワードへの対応: "
                "ページ構造を見直し、関連キーワードを H2/H3 に自然に組み込む。"
            )
        else:
            action_def = (
                f"[{chosen_key}] コンテンツ改善: "
                "現在の記事構造を見直し、ユーザー意図に即した見出し構成と本文量を拡張する。"
            )

        # last_action と被らない範囲で調整
        if last_action and last_action in action_def:
            action_def = action_def.replace(last_action, f"[見直し済み]{action_def}")

        # new improvement log entry
        new_entry = {
            "date": today,
            "keyword": chosen_key,
            "status": "active",
            "action_definition": action_def,
            "next_review_day": (date.today() + timedelta(days=7)).isoformat(),
        }
        improvement_log.setdefault("log", []).append(new_entry)
        save_json(log_path, improvement_log)

        # watchwords の status を 'active' に更新
        watchwords["keywords"][kw_idx]["status"] = "active"
        watchwords["keywords"][kw_idx]["next_review_day"] = (date.today() + timedelta(days=7)).isoformat()
        save_json(watchwords_path, watchwords)

        print("[RANK_WATCH] 🎯 1 candidate found! action_definition set.")
        print(f"    keyword: {chosen_key}")
        print(f"    rank: {rank_est} (source: {rank_source})")
        print(f"    imp: {imp_est}")
        print(f"    action: {action_def[:80]}...")
        print(f"    next review: {new_entry['next_review_day']}")

    elif len(candidates) == 0:
        print(
            f"[RANK_WATCH] No candidates today for '{keyword_key}' — "
            "all keywords either achieved, in observing period, or rank/imp not met."
        )
        # 7日経過分の observing を 'achieved' に一括昇格させる機会
        for k in watchwords.get("keywords", []):
            if k.get("status") == "observing":
                rev = k.get("next_review_day", "")
                if rev and rev <= today:
                    k["status"] = "achieved"
                    print(f"[RANK_WATCH] Auto-upgraded '{k.get('key')}' from observing to achieved (7 days elapsed)")
        save_json(watchwords_path, watchwords)

        # rank-history にノーアクションログ
        append_json(rank_path, {"date": today, "note": "no_candidates_rank_imp_not_met"})

    else:
        # 候補が 2 つ以上ある場合は何もしない — 次回 run で再試行
        append_json(
            rank_path,
            {"date": today, "note": f"multiple_candidates:{len(candidates)} — skip this run for {keyword_key}"},
        )
        print(f"[RANK_WATCH] {len(candidates)} candidates found — skipping this run, will retry next cycle.")

    print("[RANK_WATCH] Done.")


if __name__ == "__main__":
    main()
