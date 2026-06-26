"""knshow.com — 懸賞詳細ページ解析（knshow固有関数）"""
from __future__ import annotations

import re
import httpx

from .common import HEADERS, BASE_URL


def extract_detail_links(html: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for m in re.finditer(r'href="(/detail/[^"]+\.html)"', html):
        url: str = m.group(1)
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def extract_rd_link(html: str) -> str | None:
    m = re.search(r'href="(/rd/[^"]+)"', html)
    return m.group(1) if m else None


def resolve_redirect(rd_path: str) -> str:
    h: dict[str, str] = dict(HEADERS)
    h["Referer"] = f"{BASE_URL}/twitter"
    with httpx.Client(follow_redirects=True, timeout=15) as c:
        r = c.get(f"{BASE_URL}{rd_path}", headers=h)
        url: str = str(r.url)
        # knshow が tracking hash (#508 など) を付与するので除去
        if "#" in url:
            url = url.split("#")[0]
        return url


def is_x_url(url: str) -> bool:
    """XのツイートURLか判定（アカウントページは除外）"""
    url_lower: str = url.lower()
    if "x.com" not in url_lower and "twitter.com" not in url_lower:
        return False
    # /status/ がないものはツイートではなくアカウントページ
    if "/status/" not in url_lower:
        return False
    return True


def extract_deadline_and_winners(html: str) -> tuple[str, int]:
    """詳細ページHTMLから締切日と当選人数を抽出（v3.3: title優先 + サイドバー除外）"""
    deadline: str = ""
    winner_count: int = 0

    # 1) <title> タグから抽出（最も信頼性が高い）
    # 例: "【毎日・その場で当たる】クーリッシュバニラ1個 ... 【〆切07月01日】ロッテ"
    m_title = re.search(
        r"[【\[]\s*[締〆]切\s*(\d{1,2})月(\d{1,2})日", html.split("</title>")[0]
    )
    if m_title:
        deadline = f"2026-{int(m_title.group(1)):02d}-{int(m_title.group(2)):02d}"
    else:
        # 2) 「応募締切日」の専用spanタグ
        m = re.search(
            r"応募締切日[：:]?\s*<strong>\s*<span\s+class=\"expiredatetime-display\"\s+data-expiredatetime=\'(\d{4}-\d{1,2}-\d{1,2})\'",
            html,
        )
        if m:
            deadline = m.group(1)
        else:
            # 3) 「締切:」テキスト（サイドバーの関連案件を避けるため最初の出現のみ）
            m = re.search(
                r"[締〆]切[：:]\s*(\d{1,2})月(\d{1,2})日\s*(?:\d{1,2}:\d{2})?",
                html[:3000],
            )
            if m:
                deadline = f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # 当選人数: <strong class="tousenST"> 10,000</strong>名様
    m_w = re.search(
        r'<strong\s+class="tousenST">\s*([\d,]+)\s*</strong>\s*名様', html
    )
    if m_w:
        try:
            winner_count = int(m_w.group(1).replace(",", ""))
        except ValueError:
            winner_count = 0
    else:
        # フォールバック: titleタグから（例: "10000名様にプレゼント"）
        m_w2 = re.search(r"(\d[\d,]*)\s*名様", html.split("</title>")[0])
        if m_w2:
            try:
                winner_count = int(m_w2.group(1).replace(",", ""))
            except ValueError:
                winner_count = 0

    return deadline, winner_count
