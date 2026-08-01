"""既存 collected.json の deadline バックフィル
 - knshow詳細ページ再取得（/detail/ 系）
 - fixupx.com 経由でツイート本文から抽出（全ソース）

使い方: uv run python backfill_deadlines.py
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://knshow.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/twitter",
}

DATA_DIR = Path("data")
COLLECTED_PATH = DATA_DIR / "collected.json"


def extract_knshow_deadline(html: str) -> str:
    """knshow 詳細ページHTMLから締切日を抽出（knshow.py と同じロジック）"""
    deadline = ""
    # 1) <title>
    m_title = re.search(
        r"[【\[]\s*[締〆]切\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日",
        html.split("</title>")[0],
    )
    if m_title:
        y = m_title.group(1) or "2026"
        deadline = f"{y}-{int(m_title.group(2)):02d}-{int(m_title.group(3)):02d}"
    else:
        # 2) span data-expiredatetime
        m = re.search(r"data-expiredatetime='(\d{4}-\d{1,2}-\d{1,2})'", html)
        if m:
            deadline = m.group(1)
        else:
            # 3) 締切: X月Y日
            m = re.search(
                r"[締〆]切[：:]?\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日\s*(?:\d{1,2}:\d{2})?",
                html[:3000],
            )
            if m:
                y = m.group(1) or "2026"
                deadline = f"{y}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 4) 応募期間/締切日
    if not deadline:
        m = re.search(
            r"(?:応募期間|賞品応募締切|締切日|応募締切日)[：:]?\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日", html
        )
        if m:
            y = m.group(1) or "2026"
            deadline = f"{y}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return deadline


def extract_tweet_deadline(text: str) -> str:
    """ツイートHTML/テキストから締切日を抽出"""
    # fixupx.com はツイート本文を plain text で含む
    # 日本語日付形式
    m = re.search(r"(?:応募締切|締切|応募期限|申込期限|〆切)[^\d]*?(\d{4})[年/](\d{1,2})[月/](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(?:応募締切|締切|応募期限|申込期限|〆切)[^\d]*?(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    # 単体日付（年あり）
    m = re.search(r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 単体日付（年なし）
    m = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def backfill_knshow(collected: list[dict]) -> int:
    """knshow詳細ページ再取得によるbackfill"""
    to_fix = [
        i
        for i, c in enumerate(collected)
        if not c.get("deadline") and c.get("detail_url", "").startswith("/detail/") and "/status/" in c.get("x_url", "")
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


def backfill_via_fixupx(collected: list[dict]) -> int:
    """fixupx.com 経由でツイート本文から deadline を抽出"""
    to_fix = [i for i, c in enumerate(collected) if not c.get("deadline") and "/status/" in c.get("x_url", "")]
    if not to_fix:
        return 0
    print(f"\n[fixupx] {len(to_fix)} items → fetching tweets...")
    fixed = 0
    with httpx.Client(follow_redirects=True, timeout=15, headers=HEADERS) as cl:
        for idx, i in enumerate(to_fix):
            x_url = collected[i]["x_url"]
            fu = x_url.replace("https://x.com/", "https://fixupx.com/").replace(
                "https://twitter.com/", "https://fixupx.com/"
            )
            try:
                r = cl.get(fu, timeout=10)
                if r.status_code == 200:
                    dl = extract_tweet_deadline(r.text)
                    if dl:
                        collected[i]["deadline"] = dl
                        fixed += 1
            except Exception:
                pass
            if (idx + 1) % 50 == 0:
                print(f"  ...{idx + 1}/{len(to_fix)} ({fixed} fixed)")
            time.sleep(0.2)
    print(f"  ✅ fixupx: {fixed} fixed")
    return fixed


def main():
    if not COLLECTED_PATH.exists():
        print(f"ERROR: {COLLECTED_PATH} not found")
        sys.exit(1)

    with open(COLLECTED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    collected = data.get("collected", [])
    before = sum(1 for c in collected if not c.get("deadline"))
    print(f"Total: {len(collected)}, missing deadline: {before}")

    f1 = backfill_knshow(collected)
    f2 = backfill_via_fixupx(collected)
    total = f1 + f2

    if total > 0:
        with open(COLLECTED_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        after = sum(1 for c in collected if not c.get("deadline"))
        print(f"\n📝 Updated: {COLLECTED_PATH}")
        print(f"📊 Missing: {before} → {after} (fixed {total})")
    else:
        print("\n📝 No changes")


if __name__ == "__main__":
    main()
