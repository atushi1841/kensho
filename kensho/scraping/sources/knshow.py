"""knshow.com — 懸賞詳細ページ解析（knshow固有関数）"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import httpx

from .browser_fetch import fetch_via_browser
from .common import BASE_URL, HEADERS

# critic t_18ecf0a5: knshow 502部分劣化対策 — kenkaku v144ページ単位リトライを移植。
#   knshow 一覧ページ/リダイレクト解決が単発fetch(timeout=15)で 502 を通し、knshow=0 の
#   セッションを生んでいた。指数バックオフリトライ3アテンプト（base 3s → 3,6 → 10sキャップ）
#   を適用し、knshow=0 セッションを7日間で半減させる。
_KNSHOW_MAX_TRIES: int = 3  # 合計3アテンプト（初期試行 + リトライ2回）
_KNSHOW_RETRY_BACKOFF: float = 3.0  # 指数バックオフ base 3.0s
_KNSHOW_RETRY_BACKOFF_MAX: float = 10.0  # バックオフ上限（3,6 → 10sキャップ）
_KNSHOW_TIMEOUT: int = 15

# ── Cloudflare 失敗分類（critic t_c0e0563d / 2026-09-24 実測）──
# 実測: knshow.com は 2026-09-23 13:00 JST 以降 Cloudflare から 502 を返し続けている。
#   応答は body "error code: 502" / 実ブラウザでは title "knshow.com | 502: Bad gateway"。
#   同一IPの実ブラウザ（patchright chromium headless）でも 502、robots.txt は
#   cf-cache-status: STALE（= origin 再検証失敗によるキャッシュ配信）、動的パスは全て 502。
#   → これは Cloudflare ボットチャレンジではなく **origin 障害**であり、ブラウザ化では通らない。
# 一方 403/503 + "Just a moment..." は CF ボットチャレンジで、実ブラウザなら通過しうる。
#   両者を混同すると「無条件にブラウザ起動」= 高コストかつ無効な対策に進むため分類して分岐する。
CF_ORIGIN_OUTAGE: str = "origin_outage"
CF_BOT_CHALLENGE: str = "bot_challenge"
CF_UNKNOWN: str = "unknown"
KNSHOW_OK: str = "ok"
BROWSER_OK: str = "browser_ok"

_CF_ORIGIN_MARKERS: tuple[str, ...] = (
    "error code: 502",
    "502: bad gateway",
    "error code: 520",
    "521: web server is down",
    "522: connection timed out",
    "523: origin is unreachable",
    "524: a timeout occurred",
)
_CF_CHALLENGE_MARKERS: tuple[str, ...] = (
    "just a moment",
    "cf-mitigated",
    "challenge-platform",
    "__cf_chl",
    "attention required! | cloudflare",
    "enable javascript and cookies to continue",
)


def classify_knshow_failure(code: int, html: str | None) -> str:
    """knshow の非200応答を Cloudflare 失敗種別へ分類する（fail-open: 判定不能は unknown）。

    origin_outage = CF の origin 障害ページ（ブラウザでも解決不能）/ bot_challenge = 実ブラウザで
    通過しうるチャレンジ / unknown = 判別不能。呼出側は source_health の last_error へ記録し、
    アラート本文で「origin 障害」か「ボットチャレンジ」かを切り分ける。
    """
    low: str = (html or "").lower()
    for marker in _CF_ORIGIN_MARKERS:
        if marker in low:
            return CF_ORIGIN_OUTAGE
    for marker in _CF_CHALLENGE_MARKERS:
        if marker in low:
            return CF_BOT_CHALLENGE
    if code in (403, 429, 503):
        return CF_BOT_CHALLENGE
    return CF_UNKNOWN


def fetch_knshow_listing(
    fetcher: Callable[..., tuple[int, str, str]],
    url: str,
    *,
    out: Callable[[str], None] | None = None,
    browser_fetcher: Callable[[str], tuple[int, str] | None] | None = None,
    referer: str | None = None,
) -> tuple[int, str, str, str]:
    """一覧取得（リトライ付き）+ ボットチャレンジ時のみ実ブラウザフォールバック（t_c0e0563d）。

    戻り値 (code, html, final_url, kind)。kind は ok / origin_outage / bot_challenge /
    unknown / browser_ok。ブラウザ経路の失敗（patchright 不在・起動不能・タイムアウト）は
    fail-open: 従来 httpx 経路の失敗結果をそのまま返し、収集全体は止めない。

    ★ t_686afe68: referer を BASE_URL/twitter に固定して渡す（従来は scrapling デフォルトの
      https://www.google.com/ が使われていた）。knshow.com は referer チェックで 502 を返す
      型の Protection があり、同一 run 内で 502→リトライ→502 の死ループが起きていた。
      referer=BASE_URL/twitter に設定することで 200 が返る cases へ移行する（実測 9/25 12run）。
    """
    code, html, final_url = fetch_listing_with_retry(fetcher, url, out=out, referer=referer)
    if code == 200:
        return code, html, final_url, KNSHOW_OK
    kind: str = classify_knshow_failure(code, html)
    if kind != CF_BOT_CHALLENGE:
        return code, html, final_url, kind
    if out:
        out(f"  [KNSHOW] 一覧: ボットチャレンジ検出（HTTP {code}）→ 実ブラウザで再取得")
    bf: Callable[[str], tuple[int, str] | None] = browser_fetcher if browser_fetcher is not None else fetch_via_browser
    got: tuple[int, str] | None = None
    try:
        got = bf(url)
    except Exception as e:  # noqa: BLE001 — fail-open（収集全体を止めない）
        if out:
            out(f"  [KNSHOW] ブラウザフォールバック例外（fail-open）: {e}")
    if got is not None and got[0] == 200 and got[1]:
        if out:
            out(f"  [KNSHOW] 一覧: ブラウザフォールバック成功（チャレンジ通過 {len(got[1])}bytes）")
        return 200, got[1], url, BROWSER_OK
    if out:
        out("  [KNSHOW] ブラウザフォールバック不成立 → 従来経路の失敗を維持（fail-open）")
    return code, html, final_url, kind


def fetch_listing_with_retry(
    fetcher: Callable[..., tuple[int, str, str]],
    url: str,
    *,
    out: Callable[[str], None] | None = None,
    referer: str | None = None,
) -> tuple[int, str, str]:
    """knshow 一覧ページ単位の指数バックオフリトライ（kenkaku v144移植 / critic t_18ecf0a5）。

    scrapeモード別fetcher（scrapling/proxy/fetch等）を包む。HTTP 5xx(502含む)/ネットワーク例外
    のみ 3アテンプトまでリトライ（バックオフ 3,6 → 10sキャップ）。非5xx(404等)は即スキップ。
    最終失敗コードを返し、成功/失敗の判定とヘルス記録は呼出側（collector Step1）が担う。

    ★ t_686afe68: referer を fetcher に渡す（scrapling_fetch は referer ヘッダーを設定する）。
      従来は scrapling デフォルトの https://www.google.com/ が使われていたが、knshow.com は
      referer チェックで 502 を返す Protection を持つため、BASE_URL/twitter への固定が必要。
    """
    code, html, final_url = 0, "", ""
    for attempt in range(_KNSHOW_MAX_TRIES):
        try:
            code, html, final_url = fetcher(url, referer=referer) if referer is not None else fetcher(url)
        except Exception:  # noqa: BLE001 — ConnectTimeout/ReadTimeout等はリトライ対象
            code, html, final_url = 0, "", ""
        if code != 0 and code < 500:
            return code, html, final_url
        if attempt < _KNSHOW_MAX_TRIES - 1:
            delay: float = min(_KNSHOW_RETRY_BACKOFF * (2**attempt), _KNSHOW_RETRY_BACKOFF_MAX)
            if out:
                _label: str = f"HTTP {code}" if code else "ネットワーク例外"
                out(f"  [KNSHOW] 一覧: {_label} → リトライ{attempt + 1}/{_KNSHOW_MAX_TRIES - 1}（{delay:.0f}s待ち）")
            time.sleep(delay)
    return code, html, final_url


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
    # critic t_18ecf0a5: ネットワーク例外で指数バックオフリトライ（kenkaku v144移植・3アテンプト）
    for attempt in range(_KNSHOW_MAX_TRIES):
        try:
            with httpx.Client(follow_redirects=True, timeout=_KNSHOW_TIMEOUT) as c:
                r = c.get(f"{BASE_URL}{rd_path}", headers=h)
            url: str = str(r.url)
            # knshow が tracking hash (#508 など) を付与するので除去
            if "#" in url:
                url = url.split("#")[0]
            return url
        except Exception:
            if attempt == _KNSHOW_MAX_TRIES - 1:
                raise
            delay: float = min(_KNSHOW_RETRY_BACKOFF * (2**attempt), _KNSHOW_RETRY_BACKOFF_MAX)
            time.sleep(delay)
    return ""  # 到達しない（ループ内で return or raise）


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
    # 例: "【〆切07月01日】" または "【〆切2026年06月25日】"
    m_title = re.search(r"[【\[]\s*[締〆]切\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日", html.split("</title>")[0])
    if m_title:
        year = m_title.group(1) if m_title.group(1) else "2026"
        deadline = f"{year}-{int(m_title.group(2)):02d}-{int(m_title.group(3)):02d}"
    else:
        # 2) 「応募締切日」の専用spanタグ
        m = re.search(
            r"応募締切日[：:]?\s*<strong>\s*<span\s+class=\"expiredatetime-display\"\s+data-expiredatetime=\'(\d{4}-\d{1,2}-\d{1,2})\'",
            html,
        )
        if m:
            deadline = m.group(1)
        else:
            # 3) 「締切:」テキスト（サイドバーの関連案件を避けるため出現位置を限定）
            m = re.search(
                r"[締〆]切[：:]?\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日\s*(?:\d{1,2}:\d{2})?",
                html[:3000],
            )
            if m:
                year = m.group(1) if m.group(1) else "2026"
                deadline = f"{year}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # 4) 本文中の「応募期間」「賞品応募締切」「締切日」の後にある日付（<title> / サイドバー以外）
        if not deadline:
            m = re.search(
                r"[応募期間|賞品応募締切|締切日|応募締切日][：:]?\s*(?:(\d{4})[年/])?(\d{1,2})月(\d{1,2})日",
                html,
            )
            if m:
                year = m.group(1) if m.group(1) else "2026"
                deadline = f"{year}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 当選人数: <strong class="tousenST"> 10,000</strong>名様
    m_w = re.search(r'<strong\s+class="tousenST">\s*([\d,]+)\s*</strong>\s*名様', html)
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
