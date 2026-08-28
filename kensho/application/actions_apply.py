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
    target: str = "n/a",
) -> tuple[bool, str | None]:
    """フォローボタンをクリック。成功(or既フォロー)ならTrue。

    Returns:
        (success, error_code) — error_code は失敗時の短い識別子。
        呼び出し側がエラー種別を見て applied 付与の判断に使う（提案68）。
    """
    _t0 = _time.time()
    _cfg_here = _ensure_cfg()
    _decision, _reason = policy_engine.evaluate(account_key, "follow", _cfg_here)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] フォロー拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", target, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return (False, "policy_denied")

    fb = page.query_selector('[data-testid*="follow"]')
    if fb:
        t: str = (fb.text_content() or "").strip()
        if "フォロー" in t or "Follow" in t:
            human_like_mouse(page, fb, click_delay=click_delay)
            # ★ 2026-08-25 反映確認を追加（フォロー空振り対策）
            #   従来: クリック後に無条件で成功を返し、実フォローが増えていなくても
            #   カウントだけ積み上がる（8/24実測: allow 186件のうちフォロー59件、
            #   実フォロワー増加は約10件）。クリック後に「フォロー中(unfollow化)」へ
            #   変わったことを確認してから success にする。
            for _w in range(6):  # 最大~6秒ポーリング
                try:
                    if page.query_selector('[data-testid="unfollow"]'):
                        out("  [OK] フォロー")
                        increment_daily_count(account_key, "follow")
                        policy_engine.mark_executed(account_key, "follow")
                        _delay = int((_time.time() - _t0) * 1000)
                        audit_ledger.log(account_key, "follow", target, "allow", "success", delay_ms=_delay)
                        _time.sleep(random.uniform(3, 7))
                        return (True, None)
                except Exception:
                    pass
                _time.sleep(1)
            # 反映なし → 空振り。成功と誤計上しない
            out("  [!] フォロー反映なし → 失敗扱い")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key,
                "follow",
                target,
                "allow",
                "failed",
                error="follow_confirm_missing",
                delay_ms=_delay,
            )
            return (False, "follow_confirm_missing")
        else:
            out("  [i] フォロー済み")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(
                account_key, "follow", target, "allow", "success", reason="already_followed", delay_ms=_delay
            )
            return (True, "already_followed")
    else:
        out("  [i] フォローボタンなし（応募対象外かも）")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "follow", target, "allow", "failed", error="no_follow_button", delay_ms=_delay)
        return (False, "no_follow_button")


def do_rt(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
    target: str = "n/a",
) -> bool:
    """リポスト（RT）ボタンをクリック。成功(or既RT)ならTrue。"""
    _t0 = _time.time()
    _decision, _reason = policy_engine.evaluate(account_key, "rt", cfg)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] RT拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", target, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return False

    rt_count_before: int = load_daily_counts().get(account_key, {}).get("rt", 0)
    rt_base: int = cfg.get("rate_limits", {}).get("max_rt_per_day", 15)
    rt_jitter: int = cfg.get("rate_limits", {}).get("max_rt_jitter", 0)
    rt_limit: int = rt_base + random.randint(0, rt_jitter)
    if rt_count_before >= rt_limit:
        out("  [i] RT: 上限到達スキップ")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", target, "deny", "skipped", reason="manual_limit_reached", delay_ms=_delay)
        return False

    # ★ 既にリポスト済みなら成功扱い（unlikeの逆。RT済み==応募充足）★
    try:
        if page.query_selector('[data-testid="unretweet"]') or page.query_selector(
            'button[aria-label="リポストを取り消す"], button[aria-label="Undo repost"]'
        ):
            out("  [i] RT済み（unretweet検出）")
            # ★ 2026-08-25: already_retweeted は新規行動でないので日次カウント/実行に加算しない（API側と整合）。
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "rt", target, "allow", "success", reason="already_retweeted", delay_ms=_delay)
            return True
    except Exception:
        pass

    rt = page.query_selector('[data-testid="retweet"]')
    if not rt:
        # フォールバック: aria-labelの"リポスト"/"Repost"ラベル（XのDOM構成変更対策）
        rt = page.query_selector(
            'button[aria-label="リポスト"], button[aria-label="Repost"], button[aria-label*="Repost"]'
        )
    if not rt:
        out("  [i] RTなし")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", target, "allow", "failed", error="no_rt_button", delay_ms=_delay)
        return False

    _time.sleep(random.uniform(0.5, 2))
    human_like_mouse(page, rt, click_delay=click_delay)

    def _rt_done(via: str, reason: str = "") -> bool:
        increment_daily_count(account_key, "rt")
        policy_engine.mark_executed(account_key, "rt")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "rt", target, "allow", "success", reason=reason, delay_ms=_delay)
        out(f"  [OK] RT({via})")
        return True

    # ★ 2026-08-23微調整: 確定要素をポーリングで掴む（メニュー/確認モーダル/即時反映の最先勝ち）
    #   メニュー/モーダルの描画が遅い場合に単発チェックだと掴み損ねる「確定要素なし」を解消。
    for _w in range(6):  # 最大~6秒ポーリング
        # 即時反映済み？
        try:
            if page.query_selector('[data-testid="unretweet"]'):
                return _rt_done("反映", "retweeted")
        except Exception:
            pass
        # メニュー項目（Repost/リポスト。Quote/引用は除外）を探してクリック
        _clicked_menu = False
        try:
            for mi in page.query_selector_all('[role="menuitem"]'):
                _t = (mi.text_content() or "").lower()
                if ("リポスト" in _t or "repost" in _t) and not ("引用" in _t or "quote" in _t):
                    human_like_mouse(page, mi, click_delay=click_delay)
                    _clicked_menu = True
                    break
        except Exception:
            pass
        if _clicked_menu:
            return _rt_done("メニュー", "menu_clicked")
        # 確認モーダル
        try:
            _cf = page.query_selector('[data-testid="retweetConfirm"]')
            if _cf:
                human_like_mouse(page, _cf, click_delay=click_delay)
                return _rt_done("confirm", "confirm_clicked")
        except Exception:
            pass
        _time.sleep(1)

    # ポーリング後もunretweet化を少し待つ（クリック反映が遅い場合）
    for _w in range(4):
        try:
            if page.query_selector('[data-testid="unretweet"]'):
                return _rt_done("反映確認", "retweeted")
        except Exception:
            pass
        _time.sleep(1)

    out("  [i] RTボタン押下後の確定要素なし → 失敗扱い")
    _delay = int((_time.time() - _t0) * 1000)
    audit_ledger.log(account_key, "rt", target, "allow", "failed", error="rt_confirm_missing", delay_ms=_delay)
    return False


def do_like(
    page: Any,
    click_delay: int,
    out: Callable[[str], None],
    account_key: str,
    cfg: dict[str, Any],
    target: str = "n/a",
) -> bool:
    """いいねボタンをクリック。成功(or既いいね)ならTrue。"""
    _t0 = _time.time()
    _decision, _reason = policy_engine.evaluate(account_key, "like", cfg)
    if _decision == PolicyDecision.DENY:
        out(f"  [POLICY] いいね拒否: {_reason}")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", target, "deny", "skipped", reason=_reason, delay_ms=_delay)
        return False

    like_count_before: int = load_daily_counts().get(account_key, {}).get("like", 0)
    if like_count_before >= cfg.get("rate_limits", {}).get("max_like_per_day", 80):
        out("  [i] いいね: 上限到達スキップ")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", target, "deny", "skipped", reason="manual_limit_reached", delay_ms=_delay)
        return False

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
            audit_ledger.log(account_key, "like", target, "allow", "success", delay_ms=_delay)
            _time.sleep(random.uniform(2, 5))
            return True
        else:
            out("  [i] いいね済み")
            _delay = int((_time.time() - _t0) * 1000)
            audit_ledger.log(account_key, "like", target, "allow", "success", reason="already_liked", delay_ms=_delay)
            return True
    else:
        out("  [i] いいねボタンなし")
        _delay = int((_time.time() - _t0) * 1000)
        audit_ledger.log(account_key, "like", target, "allow", "failed", error="no_like_button", delay_ms=_delay)
        return False
