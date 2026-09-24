"""
Kensho Actions — ツイートテキスト取得・賞品価格推定・優先順位ソート
v3.3: application/applier.py から抽出、公開関数化
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Any

_prize_cache: dict[str, int] = {}  # x_url → prize_rank


def fetch_tweet_text(url: str) -> str:
    """twscrapeでツイート本文を取得（公開関数）"""
    # twscrape import は関数内で遅延ロード（module-levelだとasyncio loopが残留する）
    from twscrape import API

    if url in _prize_cache:
        return ""
    try:
        tweet_id = url.rstrip("/").split("/")[-1]

        async def _get():
            api = API()
            tweets = await api.tweet_details(tweet_id)
            return tweets.rawContent or ""

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        text = loop.run_until_complete(_get())
        loop.close()
        return text
    except Exception:
        return ""


def extract_prize_rank(text: str) -> int:
    """
    ツイートテキストから賞品価格を推定し、ランクを返す（公開関数）。
    高額ほど大きい値。
    ランク値: 0=不明, 1=〜1000円, 2=〜5000円, 3=〜1万円, 4=〜5万円, 5=〜10万円, 10=10万円以上
    """
    if not text:
        return 0
    text_l = text.replace(",", "").replace("、", "")

    # 高額チェック（万円以上）
    m = re.search(r"(\d+)\s*万円", text_l)
    if m:
        val = int(m.group(1))
        if val >= 10:
            return 10
        elif val >= 5:
            return 5
        elif val >= 1:
            return 3

    # 金額（円）
    m = re.search(r"(\d+)\s*円", text_l)
    if m:
        val = int(m.group(1))
        if val >= 10000:
            return 3
        elif val >= 5000:
            return 2
        elif val >= 1000:
            return 1
        return 1

    # ポイント
    m = re.search(r"(\d+)\s*ポイント", text_l)
    if m:
        val = int(m.group(1))
        if val >= 5000:
            return 2
        elif val >= 1000:
            return 1

    # 賞品キーワード
    high_value = ["現金", "旅行", "海外", "金", "ギフト券", "商品券", "QUOカード"]
    for kw in high_value:
        if kw in text_l:
            return 2
    return 0


_EXPIRY_DAYS: int = 0  # 締切からこの日数以上過ぎたら除外


def sort_items(items: list[dict[str, Any]], now: datetime | None = None) -> tuple[list[dict[str, Any]], int]:
    """
    未応募アイテムを優先順にソートして返す（公開関数）。
    ソートキー: 締切日が近い（2倍） + 当選者数（最大10点）に賞品価値倍率（1.0〜3.0）を乗算
    優先度が近いアイテムはランダム順になる（アカウント間で処理する投稿が分散する）

    締切から _EXPIRY_DAYS（デフォルト0日）以上経過したアイテムは除外する。
    締切未設定のアイテムは注釈確定できないので常に含める。
    """
    if now is None:
        now = datetime.now()

    # ── 期限切れフィルター ──
    filtered: list[dict[str, Any]] = []
    _removed: int = 0
    for item in items:
        dl: str = item.get("deadline", "")
        if dl:
            try:
                dl_date: datetime = datetime.strptime(dl, "%Y-%m-%d")
                # 日付ベースで判定（時刻を無視）: 締切日を過ぎて _EXPIRY_DAYS 日以上なら除外
                if (dl_date.date() - now.date()).days < -_EXPIRY_DAYS:
                    _removed += 1
                    continue
            except Exception:
                pass  # パース不能 → 含める
        filtered.append(item)

    def _sort_key(item: dict[str, Any]) -> float:
        # ── 締切スコア ──
        dl: str = item.get("deadline", "")
        dl_score: int = 0
        if dl:
            try:
                dl_date: datetime = datetime.strptime(dl, "%Y-%m-%d")
                # ★ 日付ベースで計算（2026-08-25修正）:
                #   従来は (dl_date - now).days で、締切当日の19時時点で -1日 になり
                #   締切当日のキャンペーンが -100点（最下位）扱いになるバグがあった。
                days_left: int = (dl_date.date() - now.date()).days
                if days_left >= 0:
                    dl_score = 100 - min(days_left, 100)
                else:
                    dl_score = -100
            except Exception:
                pass

        # ── 賞品価値倍率 ──
        prize_mult: float = item.get("prize_score", {}).get("priority", 1.0)

        # ── 当選者数スコア ──
        wc: int = item.get("winner_count", 0)
        wc_score: float = min(wc / 100, 10) if wc > 0 else 0

        # ── 「その場で当たる」系ボーナス（2026-08-25追加、2026-09-24拡張）:
        #   アカウントスコア（フォロワー数・インプレッション）に左右されず抽選ツールで当選するため、
        #   フォロワーが少ないKenshoアカウントに最適。締切が同程度なら優先的に応募する。
        #   判定キーワード: その場 / 今すぐ / 即時 / その場で当たる / なくなり次第 / 先着
        #   （実測 data/collected.json 997件: その場40+今すぐ17+即時1=56件検出。先着/なくなり次第は
        #    現収集データに0件だが、今後の収集源で出る可能性があるため残す）
        _text: str = item.get("tweet_text", "") or ""
        _INSTANT_KW: tuple[str, ...] = (
            "その場",
            "今すぐ",
            "即時",
            "なくなり次第",
            "先着",
        )
        _instant_bonus: float = 20.0 if any(kw in _text for kw in _INSTANT_KW) else 0.0

        # ── 優先度スコア + ランダムジッター（±5点）──
        # 同じ優先度帯ならランダム順になり、アカウント間で処理する投稿が分散する
        score: float = (dl_score * 2 + wc_score) * prize_mult + _instant_bonus
        jitter: float = random.uniform(-5.0, 5.0)
        return -(score + jitter)

    return sorted(filtered, key=_sort_key), _removed
