"""Kensho Apply Actions — フォロー/RT/いいねのブラウザ操作"""

from __future__ import annotations

import random
import time as _time
from collections.abc import Callable
from typing import Any

from kensho.application.audit_ledger import audit_ledger
from kensho.application.browser import human_like_mouse
from kensho.application.policy_engine import PolicyDecision, policy_engine
from kensho.application.rate_limiter import increment_daily_count, load_daily_counts

# ── Config cache (30秒) ──
_cfg_cache: dict[str, Any] = {}
_cfg_loaded_at: float = 0.0


def _ensure_cfg() -> dict[str, Any]:
    global _cfg_cache, _cfg_loaded_at
    now = _time.time()
    if now - _cfg_loaded_at > 30:
        from kensho.core.config import load as _load_config

        _cfg_cache = _load_config()
        _cfg_loaded_at = now
    return _cfg_cache


def do_follow(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
) -> None:
    """フォローボタンをクリック"""
    _t0 = _time.time()
    _cfg_here = _ensure_cfg()
    _decision, _reason = policy_engine.evaluate(account_key, "follow", _cfg_here)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] フォロー拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", "n/a", "deny", "skipped", reason=_reason, delay_ms=_delay)
        return

    fb = page.query_selector('[data-testid*="follow"]')
    if fb:
        t: str = (fb.text_content() or "").strip()
        if "フォロー" in t or "Follow" in t:
            human_like_mouse(page, fb, click_delay=click_delay)
            out("  [OK] フォロー")
            increment_daily_count(account_key, "follow")
            policy_engine.mark_executed(account_key, "follow")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "follow", "n/a", "allow", "success", delay_ms=_delay)
            _time.sleep(random.uniform(3, 7))
        else:
            out("  [i] フォロー済み")
            # already followed – still treat as allowed+success
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "follow", "n/a", "allow", "success", reason="already_followed", delay_ms=_delay
            )
    else:
        out("  [i] フォローボタンなし（応募対象外かも）")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", "n/a", "allow", "failed", error="no_follow_button", delay_ms=_delay)


def do_rt(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
) -> None:
    """リポスト（RT）ボタンをクリック"""
    _t0 = _time.time()
    _decision, _reason = policy_engine.evaluate(account_key, "rt", cfg)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] RT拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", "n/a", "deny", "skipped", reason=_reason, delay_ms=_delay)
        return

    rt_count_before: int = load_daily_counts().get(account_key, {}).get("rt", 0)
    rt_base: int = cfg.get("rate_limits", {}).get("max_rt_per_day", 15)
    rt_jitter: int = cfg.get("rate_limits", {}).get("max_rt_jitter", 0)
    rt_limit: int = rt_base + random.randint(0, rt_jitter)
    if rt_count_before < rt_limit:
        rt = page.query_selector('[data-testid="retweet"]')
        if rt:
            _time.sleep(random.uniform(0.5, 2))
            human_like_mouse(page, rt, click_delay=click_delay)
            _time.sleep(random.uniform(1.5, 3.5))
            for mi in page.query_selector_all('[role="menuitem"]'):
                if "リポスト" in (mi.text_content() or ""):
                    human_like_mouse(page, mi, click_delay=click_delay)
                    out("  [OK] RT")
                    increment_daily_count(account_key, "rt")
                    policy_engine.mark_executed(account_key, "rt")
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(account_key, "rt", "n/a", "allow", "success", delay_ms=_delay)
                    break
            else:
                cf = page.query_selector('[data-testid="retweetConfirm"]')
                if cf:
                    human_like_mouse(page, cf, click_delay=click_delay)
                    out("  [OK] RT(confirm)")
                    increment_daily_count(account_key, "rt")
                    policy_engine.mark_executed(account_key, "rt")
                    _delay = int((_time.time() - _t0) * 1000)
                    audit_ledger.log(account_key, "rt", "n/a", "allow", "success", delay_ms=_delay)
        else:
            out("  [i] RTなし")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "rt", "n/a", "allow", "failed", error="no_rt_button", delay_ms=_delay)
    else:
        out("  [i] RT: 上限到達スキップ")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", "n/a", "deny", "skipped", reason="manual_limit_reached", delay_ms=_delay)


def do_like(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
) -> None:
    """いいねボタンをクリック"""
    _t0 = _time.time()
    _decision, _reason = policy_engine.evaluate(account_key, "like", cfg)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] いいね拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", "n/a", "deny", "skipped", reason=_reason, delay_ms=_delay)
        return

    like_count_before: int = load_daily_counts().get(account_key, {}).get("like", 0)
    if like_count_before < cfg.get("rate_limits", {}).get("max_like_per_day", 80):
        like_btn = page.query_selector('[data-testid="like"]')
        if like_btn:
            unlike_btn = page.query_selector('[data-testid="unlike"]')
            if not unlike_btn:
                _time.sleep(random.uniform(0.5, 1.5))
                human_like_mouse(page, like_btn, click_delay=click_delay)
                out("  [OK] いいね")
                increment_daily_count(account_key, "like")
                policy_engine.mark_executed(account_key, "like")
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(account_key, "like", "n/a", "allow", "success", delay_ms=_delay)
                _time.sleep(random.uniform(2, 5))
            else:
                out("  [i] いいね済み")
                _delay = int((_time.time() - _t0) * 1000)
                audit_ledger.log(
                    account_key, "like", "n/a", "allow", "success", reason="already_liked", delay_ms=_delay
                )
        else:
            out("  [i] いいねボタンなし")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "like", "n/a", "allow", "failed", error="no_like_button", delay_ms=_delay)
    else:
        out("  [i] いいね: 上限到達スキップ")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", "n/a", "deny", "skipped", reason="manual_limit_reached", delay_ms=_delay)
