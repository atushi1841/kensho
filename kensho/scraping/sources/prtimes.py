"""PR TIMES — プレスリリースの記念プレゼント・抽選キャンペーン収集（収集源第5ソース）

PR TIMES（https://prtimes.jp）のキーワードトピックスページ（プレゼント/キャンペーン/抽選/新商品）
からプレスリリースを走査し、本文に埋め込まれた X 公式キャンペーンツイート `/status/<id>` URL を
抽出して collected.json 互換アイテムとして返す。

実測（2026-09-19 検証）:
  - PR TIMES は企業アカウント プロフィール(x.com/company) へのリンクは多いが、
    特定のキャンペーンツイート /status/<id> を直接埋め込むのは一部のリリースのみ。
    （例: 映画Gift1Get1キャンペーン、カワサキ Ninja 1100SXプレゼント等が見付かる）
  - /status/ URL を含むものだけを収集に追加する（応募可能なツイートのみ）。プロフィール
    リンクは RT 対象でないため除外。これにより既存4ソースが拾い切れない新規X懸賞を補完する。

TOS: 読み取り専用・応募分のみ取得・再販しない。レート制限回避のため fetch 間にランダム遅延。
検知不能なリリースは deadline を空文字で返し、collector の snowflake 年齢パージで自然に処理。
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
from typing import Any

from .common import _fetch_with_retry, has_skip_keyword

# ── 第5収集源: PR TIMES キーワードトピックス ──
_PRTIMES_BASE: str = "https://prtimes.jp"

# 記念プレゼント/抽選/新商品キャンペーンが集まるキーワードトピックス
_KEYWORDS: tuple[str, ...] = ("プレゼント", "キャンペーン", "抽選", "新商品")

# 全キーワード合計で走査するリリース上限（レート制限・時間抑制）
_MAX_RELEASES: int = 40

_X_STATUS_RE: re.Pattern[str] = re.compile(r"https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+")

# 締切日抜き出し（締切/応募期間/…まで の直後120文字に日付を要求。見付からなければ空）
_DATE_FULL_RE: re.Pattern[str] = re.compile(r"(202[0-9])[年/.\-](\d{1,2})[月/.\-](\d{1,2})")
_DATE_SHORT_RE: re.Pattern[str] = re.compile(r"(\d{1,2})月(\d{1,2})日")
_DEADLINE_ANCHOR_RE: re.Pattern[str] = re.compile(r"(締切|締め切り|応募期間|キャンペーン期間|受付期間|\sまで)")
_WINNER_RE: re.Pattern[str] = re.compile(r"(\d[\d,]*)\s*名")


def _kw_page_url(keyword: str) -> str:
    """キーワードトピックスURL（パーセントエンコード済み）。"""
    return f"{_PRTIMES_BASE}/topics/keywords/{urllib.parse.quote(keyword)}"


def _extract_release_links(html: str) -> list[tuple[str, str]]:
    """トピックスページから プレスリリースURL + タイトルのペアを抽出（順序維持・一意化）。"""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for u, t in re.findall(r'href="(/main/html/rd/p/[^"]+)"[^>]*title="([^"]+)"', html):
        path = u.split("#")[0].rstrip("/")
        if path in seen:
            continue
        seen.add(path)
        pairs.append((_PRTIMES_BASE + path, t))
    return pairs


def _extract_deadline(html: str) -> str:
    """プレスリリース本文から応募締切日を抽出。締切/応募期間 キーワードの直後のみ採用。

    誤検知防止: リリース公開日（og:release）のような日付は「締切/…まで」アンカーが無いため
    採用しない。見付からない場合は空文字 → collector の tweet_id snowflake 年齢パージが処理。
    """
    for m in _DEADLINE_ANCHOR_RE.finditer(html):
        seg: str = html[m.start() : m.start() + 120]
        fm = _DATE_FULL_RE.search(seg)
        if fm:
            return f"{fm.group(1)}-{int(fm.group(2)):02d}-{int(fm.group(3)):02d}"
        sm = _DATE_SHORT_RE.search(seg)
        if sm:
            return f"2026-{int(sm.group(1)):02d}-{int(sm.group(2)):02d}"
    return ""


def _extract_winner_count(html: str) -> int:
    """当選者人数（◯名）を抽出。見付からない場合は 0。"""
    seg: str = html
    # プレゼント/抽選軸で近い「◯名」を優先、それ以外は先頭の「◯名」
    for m in re.finditer(r"(抽選|プレゼント|当選|応募)", seg):
        sub = seg[m.start() : m.start() + 120]
        wm = _WINNER_RE.search(sub)
        if wm:
            try:
                return int(wm.group(1).replace(",", ""))
            except ValueError:
                pass
    wm = _WINNER_RE.search(seg)
    if wm:
        try:
            return int(wm.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


def scrape_prtimes(out: Any, processed_set: set[str], account_keys: list[str]) -> list[dict[str, Any]]:
    """PR TIMES キーワードトピックスから X キャンペーンツイートを収集。

    戻り値: collected.json 互換アイテム（x_url = `/status/<id>` のもののみ）。
    """
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    # ── Step 1: キーワードトピックスからリリースURLを収集 ──
    release_pairs: list[tuple[str, str]] = []
    for kw in _KEYWORDS:
        url: str = _kw_page_url(kw)
        try:
            time.sleep(random.uniform(0.5, 1.2))
            code, html, _ = _fetch_with_retry(url, timeout=25, source="prtimes")
            if code != 200:
                out(f"  [PRT] {kw}: HTTP {code} - スキップ")
                continue
            found: list[tuple[str, str]] = _extract_release_links(html)
            release_pairs.extend(found)
            out(f"  [PRT] {kw}: リリース走査{len(found)}件 (累計{len(release_pairs)}件)")
        except Exception as e:  # noqa: BLE001 — fail-open
            out(f"  [PRT] {kw}: ERROR {type(e).__name__}: {e}")

    release_pairs = release_pairs[:_MAX_RELEASES]
    out(f"  [PRT] リリース走査計{len(release_pairs)}件（走査数であり収集件数ではない）")

    # ── Step 2: 各リリースから X /status/ URL を抽出 ──
    for path, title in release_pairs:
        if path in processed_set:
            continue
        try:
            time.sleep(random.uniform(0.8, 1.6))
            code, release_html, _ = _fetch_with_retry(path, timeout=25, source="prtimes")
            if code != 200:
                continue

            x_urls: list[str] = list(dict.fromkeys(_X_STATUS_RE.findall(release_html)))
            for xu in x_urls:
                if xu in seen_x_urls or xu in processed_set:
                    continue
                seen_x_urls.add(xu)

                pos: int = release_html.find(xu)
                context: str = release_html[max(0, pos - 1500) : pos + 400] if pos > 0 else release_html[:1500]

                deadline: str = _extract_deadline(context)
                winner_count: int = _extract_winner_count(context)
                tid_m = re.search(r"/status/(\d+)", xu)
                detail_url: str = f"{path}#{tid_m.group(1) if tid_m else str(len(items))}"

                applied: dict[str, None] = {k: None for k in account_keys}
                items.append({
                    "detail_url": detail_url,
                    "x_url": xu,
                    "tweet_id": tid_m.group(1) if tid_m else "",
                    "source": "prtimes",
                    "time": 0.0,
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": "",
                    "applied": applied,
                    "keyword_flag": has_skip_keyword(context),
                    "title": title,
                })
                out(f"    ✅ {xu[:70]}...")
        except Exception as e:  # noqa: BLE001 — fail-open
            out(f"  [PRT] ERROR {path}: {type(e).__name__}: {e}")

    out(f"  [PRT] 計{len(items)}件（Xキャンペーンツイート埋込リリースのみ）")
    return items
