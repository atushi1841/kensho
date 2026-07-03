"""Kensho Apply Actions — フォロー/RT/いいねのブラウザ操作"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

from kensho.application.browser import human_like_mouse
from kensho.application.rate_limiter import increment_daily_count, load_daily_counts


def do_follow(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
) -> None:
    """フォローボタンをクリック"""
    fb = page.query_selector('[data-testid*="follow"]')
    if fb:
        t: str = (fb.text_content() or "").strip()
        if "フォロー" in t or "Follow" in t:
            human_like_mouse(page, fb, click_delay=click_delay)
            out("  [OK] フォロー")
            increment_daily_count(account_key, "follow")
            time.sleep(random.uniform(3, 7))
        else:
            out("  [i] フォロー済み")
    else:
        out("  [i] フォローボタンなし（応募対象外かも）")


def do_rt(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
) -> None:
    """リポスト（RT）ボタンをクリック"""
    rt_count_before: int = load_daily_counts().get(account_key, {}).get("rt", 0)
    rt_base: int = cfg.get("rate_limits", {}).get("max_rt_per_day", 15)
    rt_jitter: int = cfg.get("rate_limits", {}).get("max_rt_jitter", 0)
    rt_limit: int = rt_base + random.randint(0, rt_jitter)
    if rt_count_before < rt_limit:
        rt = page.query_selector('[data-testid="retweet"]')
        if rt:
            time.sleep(random.uniform(0.5, 2))
            human_like_mouse(page, rt, click_delay=click_delay)
            time.sleep(random.uniform(1.5, 3.5))
            for mi in page.query_selector_all('[role="menuitem"]'):
                if "リポスト" in (mi.text_content() or ""):
                    human_like_mouse(page, mi, click_delay=click_delay)
                    out("  [OK] RT")
                    increment_daily_count(account_key, "rt")
                    break
            else:
                cf = page.query_selector('[data-testid="retweetConfirm"]')
                if cf:
                    human_like_mouse(page, cf, click_delay=click_delay)
                    out("  [OK] RT(confirm)")
                    increment_daily_count(account_key, "rt")
        else:
            out("  [i] RTなし")
    else:
        out("  [i] RT: 上限到達スキップ")


def do_like(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
) -> None:
    """いいねボタンをクリック"""
    like_count_before: int = load_daily_counts().get(account_key, {}).get("like", 0)
    if like_count_before < cfg.get("rate_limits", {}).get("max_like_per_day", 80):
        like_btn = page.query_selector('[data-testid="like"]')
        if like_btn:
            unlike_btn = page.query_selector('[data-testid="unlike"]')
            if not unlike_btn:
                time.sleep(random.uniform(0.5, 1.5))
                human_like_mouse(page, like_btn, click_delay=click_delay)
                out("  [OK] いいね")
                increment_daily_count(account_key, "like")
                time.sleep(random.uniform(2, 5))
            else:
                out("  [i] いいね済み")
        else:
            out("  [i] いいねボタンなし")
    else:
        out("  [i] いいね: 上限到達スキップ")
