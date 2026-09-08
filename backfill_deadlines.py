"""既存 collected.json の deadline バックフィル（ローカル・API不要パス中心）

critic v61（cpmeikan deadline 全欠損の恒久化）対応:
  - 保存済み tweet_text から deadline を正規表現で抽出（fast path、外部API不要）
  - 抽出不能かつ tweet 投稿日から AGE_FREEZE_DAYS 経過の項目は、投稿日を deadline 実値として
    書き込み + expired=True を付与（applier の既存「締切切れSKIP」判定が発火し、期限切れへの
    無駄アクションを防止）
  - knshow 自動化は従来どおり detail 再取得（source が knshow のみ）
  - COLLECTED_LOCK を獲得し、ディスクからの再読み込み + applied 保全マージの上で書き戻す
    （applier 実行と並行しても race で応募済み日付を消さない）

critic v68（cpmeikan deadline KPI 再定義・70%目標撤去）:
  - 現行「非空率 >= 70% → CHECK」は構造的到達不能（cp.meikan 一覧に期限表記が無く、
    毎収集で若年 deadline 空が再生成される。実測 7/33 = 21.2%）。毎日止まらない誤警報
    （alert fatigue）を生むため撤去。
  - 2層KPI: L1 ハードゲート = stale_empty（deadline 空かつ snowflake 年齢 > L1_GATE_DAYS）
    が 0 件（v67 パージの成功指標そのもの。1件でもあればパージ不全・収集停止として FAIL）。
    L2 監視ライン = cpmeikan 非空率（実測帯 20-30%）を INFO 表示のみ。FAIL 行は出さない。
  - ゲート = STALE_PURGE_DAYS(14) + STALE_GATE_GRACE_DAYS(1) = 15日: 収集（〜21時）から
    03:45 backfill までの間隔で 14日ちょうど超が正常に発生しうるため。純値14日超は INFO 併記。

使い方: uv run python backfill_deadlines.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://knshow.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/twitter",
}

DATA_DIR = Path(__file__).parent / "data"
COLLECTED_PATH = DATA_DIR / "collected.json"

# 投稿からこの日数を超えた項目は（deadline 抽出不能なら）投稿日を deadline 実値にし期限切れ扱い。
# X 懸賞の締切は実質1週間前後（proposal v61 の決定的実測: 適用済み 61.4% が投稿21日超）。
AGE_FREEZE_DAYS = 21

# deadline を抽出する際の「年」決め: 同年中の該当日が today より45日超過去なら翌年とみなす。
_YEAR_ROLLOVER = 45

# critic v68 L1 ハードゲート: collector の snowflake パージ閾値（_STALE_TWEET_DAYS）と対。
STALE_PURGE_DAYS = 14
# 収集（最終〜21時台）から 03:45 backfill までの間隔で 14日ちょうど超が正常に発生しうる
# （ゲート時刻の遅延でなくスケジュール境界）。純度14日は INFO 表示し、FAIL ゲートは +1d grace。
STALE_GATE_GRACE_DAYS = 1

# 締切キーワード
_WORDS = [
    "応募締切",
    "締切",
    "応募期限",
    "申込期限",
    "〆切",
    "締め切り",
    "応募受付",
    "募集締切",
]
_KW = "|".join(map(re.escape, _WORDS))


def snowflake_to_dt(tweet_id: str | int) -> datetime | None:
    """X tweet_id (snowflake) から投稿日時を返す。id が無効なら None。"""
    try:
        ms: int = (int(str(tweet_id)) >> 22) + 1288834974657
        return datetime.fromtimestamp(ms / 1000.0)
    except (ValueError, TypeError, OSError):
        return None


def _year_for(month: int, day: int, today: datetime | None = None) -> str:
    """M/D の年月を決める: today.year、ただし45日超過去なら翌年。"""
    t = today or datetime.now()
    for y in (t.year, t.year + 1):
        try:
            md = datetime(y, month, day)
        except ValueError:
            continue
        if (t - md).days <= _YEAR_ROLLOVER:
            return f"{y}-{md.month:02d}-{md.day:02d}"
    return f"{t.year + 1}-{month:02d}-{day:02d}"


def extract_tweet_deadline(text: str, today: datetime | None = None) -> str:
    """ツイート本文から deadline を抽出する（ローカル・API不要）。

    抽出パターン（上から優先）:
      1. 締切キーワード + YYYY年/M月D日
      2. 締切キーワード + M/D or M月D日
      3. YYYY年M月D日 or 年なし M月D日 (「…まで」)
      4. 「期間 … ~ M月D日」（期間の終了日）
    """
    if not text:
        return ""
    t = today or datetime.now()

    # 1) 締切キーワード + 完全な年月日
    m = re.search(rf"(?:{_KW})[^\d]{{0,25}}?(\d{{4}})[年/](\d{{1,2}})[月/](\d{{1,2}})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 2) 締切キーワード + M/D または M月D日
    m = re.search(rf"(?:{_KW})[^\d]{{0,25}}?(\d{{1,2}})[月/](\d{{1,2}})(?:日)?", text)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return _year_for(int(m.group(1)), int(m.group(2)), t)

    # 3a) YYYY年M月D日 …まで
    m = re.search(r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})日?[^\n]{0,30}?まで", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 3b) M月D日 …まで（曜日・時刻を挟んでも可）
    m = re.search(r"(\d{1,2})[月/](\d{1,2})日?(?:\(.{1,4}\))?[^\n]{0,25}?まで", text)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return _year_for(int(m.group(1)), int(m.group(2)), t)

    # 4) 「期間 … ~ M月D日」/「〜まで」/「…～ で終了」（終了日を採用、曜日・時刻を挟んでも可）
    m = re.search(
        r"(?:期間|締切|期限|まで)[^~〜～→]{0,15}?[~〜～→]\s*"
        r"(?:(?P<y>\d{4})[年/])?(?P<m>\d{1,2})[月/]?(?P<d>\d{1,2})日?",
        text,
    )
    if m and 1 <= int(m.group("m")) <= 12 and 1 <= int(m.group("d")) <= 31:
        if m.group("y"):
            y = m.group("y")
            try:
                md = datetime(int(y), int(m.group("m")), int(m.group("d")))
                return f"{y}-{md.month:02d}-{md.day:02d}"
            except ValueError:
                return ""
        return _year_for(int(m.group("m")), int(m.group("d")), t)
    # 4b) 裸の「〜」レンジ末尾日付（キーワードなし）: A〜B → B を採用。M月D日/年月日形式。
    m = re.search(
        r"(\d{4})?[年/]?(\d{1,2})[月/](\d{1,2})日?(?:[（(]\D{1,4}[）)]|\s|[、]){0,6}?[~〜～→]\s*"
        r"(?:(?P<y>\d{4})[年/])?(?P<m>\d{1,2})[月/](?P<d>\d{1,2})日?",
        text,
    )
    if m and 1 <= int(m.group("m")) <= 12 and 1 <= int(m.group("d")) <= 31:
        if m.group("y"):
            y = m.group("y")
            try:
                md = datetime(int(y), int(m.group("m")), int(m.group("d")))
                return f"{y}-{md.month:02d}-{md.day:02d}"
            except ValueError:
                return ""
        return _year_for(int(m.group("m")), int(m.group("d")), t)

    return ""


def extract_knshow_deadline(html: str) -> str:
    """knshow 詳細ページHTMLから締切日を抽出（knshow.py と同じロジック）"""
    deadline = ""
    _this_year = str(datetime.now().year)
    m_title = re.search(
        r"[【\[]\s*[締〆]切\s*(?:(?P<y>\d{4})[年/])?(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
        html.split("</title>")[0],
    )
    if m_title:
        y = m_title.group("y") or _this_year
        deadline = f"{y}-{int(m_title.group('m')):02d}-{int(m_title.group('d')):02d}"
    else:
        m = re.search(r"data-expiredatetime='(?P<d>\d{4}-\d{1,2}-\d{1,2})'", html)
        if m:
            deadline = m.group("d")
        else:
            m = re.search(
                r"[締〆]切[：:]?\s*(?:(?P<y>\d{4})[年/])?(?P<m>\d{1,2})月(?P<d>\d{1,2})日\s*(?:\d{1,2}:\d{2})?",
                html[:3000],
            )
            if m:
                y = m.group("y") or _this_year
                deadline = f"{y}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"
    if not deadline:
        m = re.search(
            r"(?:応募期間|賞品応募締切|締切日|応募締切日)[：:]?\s*(?:(?P<y>\d{4})[年/])?(?P<m>\d{1,2})月(?P<d>\d{1,2})日",
            html,
        )
        if m:
            y = m.group("y") or _this_year
            deadline = f"{y}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"
    return deadline


def backfill_knshow(collected: list[dict[str, Any]]) -> int:
    """knshow詳細ページ再取得によるbackfill（source=knshow のみ）"""
    to_fix = [
        i
        for i, c in enumerate(collected)
        if c.get("source") == "knshow"
        and not c.get("deadline")
        and str(c.get("detail_url", "")).startswith("/detail/")
        and "/status/" in str(c.get("x_url", ""))
    ]
    if not to_fix:
        return 0
    print(f"\n[knshow] {len(to_fix)} items → re-fetching detail pages...")
    fixed = 0
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as cl:
        for idx, i in enumerate(to_fix):
            dl_url = collected[i]["detail_url"]
            try:
                r = cl.get(f"{BASE_URL}{dl_url}", timeout=30)
                if r.status_code != 200:
                    continue
                deadline = extract_knshow_deadline(r.text)
                if deadline:
                    collected[i]["deadline"] = deadline
                    fixed += 1
            except Exception:
                pass
            if (idx + 1) % 10 == 0:
                print(f"  ...{idx + 1}/{len(to_fix)} ({fixed} fixed)")
            time.sleep(0.5)
    print(f"  ✅ knshow: {fixed} fixed")
    return fixed


def _tweet_id(x: dict[str, Any]) -> str:
    m = re.search(r"/status/(\d+)", str(x.get("x_url", "")))
    return str(x.get("tweet_id") or (m.group(1) if m else ""))


def backfill_local(collected: list[dict[str, Any]]) -> tuple[int, int, int]:
    """保存済み tweet_text から deadline を抽出（fast path）。＋年齢による期限切れ確定。

    Returns: (extracted, frozen_by_age, still_missing_young)
    """
    now = datetime.now()
    extracted = 0
    frozen = 0
    still = 0
    for c in collected:
        if c.get("deadline"):
            continue
        dl = extract_tweet_deadline(str(c.get("tweet_text") or ""), now)
        if dl:
            c["deadline"] = dl
            extracted += 1
            continue
        # 抽出不能: 投稿日が AGE_FREEZE_DAYS を過ぎていれば期限切れ確定
        post = snowflake_to_dt(_tweet_id(c))
        if post and (now - post).days >= AGE_FREEZE_DAYS:
            est = f"{post.year:04d}-{post.month:02d}-{post.day:02d}"
            c["deadline"] = est
            c["expired"] = True
            c["deadline_source"] = "age_freeze"
            frozen += 1
            continue
        still += 1
    return (extracted, frozen, still)


def _tweet_age_days(item: dict[str, Any], now: datetime) -> float | None:
    """snowflake からの tweet 経過日数。tweet_id 不正なら None。"""
    post = snowflake_to_dt(_tweet_id(item))
    if post is None:
        return None
    return (now - post).total_seconds() / 86400.0


def count_stale_empty(collected: list[dict[str, Any]], now: datetime, min_days: int) -> int:
    """deadline 空 かつ tweet 年齢が min_days 超の件数（critic v68 L1 用）。"""
    n = 0
    for c in collected:
        if c.get("deadline"):
            continue
        age = _tweet_age_days(c, now)
        if age is not None and age > min_days:
            n += 1
    return n


def main() -> None:
    dry_run: bool = "--dry-run" in sys.argv

    # COLLECTED_LOCK を獲得（applier と並行実行しても race しない）
    from kensho.application.state import acquire_lock, release_lock
    from kensho.utils.backup import safe_save_json

    if not COLLECTED_PATH.exists():
        print(f"ERROR: {COLLECTED_PATH} not found")
        sys.exit(1)

    acquired = acquire_lock(timeout=30)
    if not acquired:
        print("  [LOCK] collected.json ロック獲得失敗 → 中止（applier 実行と干渉を避けるため）")
        sys.exit(2)
    try:
        # ディスクから再読み込み（applier の最新 applied を取り込む）
        with open(COLLECTED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        collected = data.get("collected", [])
        before = sum(1 for c in collected if not c.get("deadline"))
        cp_before = sum(1 for c in collected if c.get("source") == "cpmeikan" and not c.get("deadline"))
        print(f"Total: {len(collected)}, missing deadline: {before} (cpmeikan {cp_before})")

        # critic v68 L1: エントリ時（バックフィル適用前）の生状態で測る。
        # after で測ると age_freeze（≥21日→expired 記入）がパージ不全を秘匿するため。
        now_dt = datetime.now()
        stale_strict = count_stale_empty(collected, now_dt, STALE_PURGE_DAYS)
        stale_gate = count_stale_empty(collected, now_dt, STALE_PURGE_DAYS + STALE_GATE_GRACE_DAYS)

        t0 = time.time()
        f1 = backfill_knshow(collected)
        f2, f3, still = backfill_local(collected)
        print(f"\n  knshow再取得: {f1}固定 / tweet_text抽出: {f2} / 年齢凍結: {f3} / 残(若年・抽出不能): {still}")
        print(f"  elapsed: {time.time() - t0:.1f}s")

        after = sum(1 for c in collected if not c.get("deadline"))
        cp_after = sum(1 for c in collected if c.get("source") == "cpmeikan" and not c.get("deadline"))
        total_cp = sum(1 for c in collected if c.get("source") == "cpmeikan")
        rate: float = 0.0
        if total_cp:
            rate = round(100 * (total_cp - cp_after) / total_cp, 1)

        print(f"\n📊 Missing: {before} → {after} (fixed {before - after})")
        # L2: 情報表示のみ（FAIL 行は出さない — critic v68、70%目標は構造的到達不能のため撤去）
        print(f"   [L2] cpmeikan deadline 非空率: {rate}% (INFO・実測帯20-30%)")

        if dry_run:
            gate_days = STALE_PURGE_DAYS + STALE_GATE_GRACE_DAYS
            print(f"   [L1] stale_empty: >{STALE_PURGE_DAYS}d={stale_strict} / gate>{gate_days}d={stale_gate}")
            print("\n(Dry-run: 書き込みせず終了)")
            return

        # applied/既存フィールドを保全したまま書き戻す
        data["collected"] = collected
        safe_save_json(COLLECTED_PATH, data, "collected.json")
        print("\n📝 Updated: " + str(COLLECTED_PATH))
        # L1: ハードゲート（v67 パージの成功指標）。1件でもあれば収集/purge 不全として FAIL+rc=1
        verdict = "PASS" if stale_gate == 0 else "FAIL"
        print(
            f"   [L1] stale_empty( deadline空 かつ tweet年齢>{STALE_PURGE_DAYS + STALE_GATE_GRACE_DAYS}d ): "
            f"{stale_gate} (>{STALE_PURGE_DAYS}d 純値 {stale_strict}) → {verdict}"
        )
        if stale_gate > 0:
            sys.exit(1)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
