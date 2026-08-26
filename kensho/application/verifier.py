"""
Kensho Verifier — Loop Engineering検証レイヤー
- ConsecutiveFailureTracker: 連続失敗上限（Failure Ceiling）
- AccountHealthVerifier: アカウント健全性チェック（shadowban/rate-limit/suspended）
- ActionVerifier: 各アクションの成否検証（ページ確認）

実装方針:
  重検証（page.gotoによるプロフィール確認）は高コストなのでconfigでOFF可能。
  軽量検証（API戻り値の解析）はデフォルトでON。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

# ────────────────────────────────────────────
#  Result
# ────────────────────────────────────────────


@dataclass
class VerificationResult:
    """検証結果"""

    success: bool
    detail: str = ""
    failure_count: int = 0
    ceiling_hit: bool = False


# ────────────────────────────────────────────
#  ConsecutiveFailureTracker — Failure Ceiling
# ────────────────────────────────────────────


class ConsecutiveFailureTracker:
    """連続失敗を追跡し、上限到達で打ち切りを提案する。

    アカウントごとの連続失敗数を管理し、設定された閾値を超えたら
    そのサイクル内の残り処理をスキップする。
    """

    def __init__(self, max_consecutive: int = 3, cooldown_minutes: int = 30):
        self.max_consecutive = max_consecutive
        self.cooldown_minutes = cooldown_minutes
        # account_key -> {count: int, first_fail_time: float, ceiling_hit: bool}
        self._state: dict[str, dict[str, Any]] = {}

    def record_failure(self, account_key: str) -> None:
        """連続失敗を記録。上限に達したらceiling_hit=Trueになる。"""
        now = time.time()
        s = self._state.setdefault(
            account_key,
            {
                "count": 0,
                "first_fail_time": now,
                "ceiling_hit": False,
            },
        )
        s["count"] += 1
        if s["count"] == 1:
            s["first_fail_time"] = now

        if s["count"] >= self.max_consecutive:
            s["ceiling_hit"] = True

    def record_success(self, account_key: str) -> None:
        """成功でリセット。"""
        self._state.pop(account_key, None)

    def is_ceiling_hit(self, account_key: str) -> bool:
        """そのアカウントが上限到達で打ち切り状態か。"""
        s = self._state.get(account_key)
        if not s:
            return False
        # cooldown経過で自動リセット
        if s["ceiling_hit"] and time.time() - s["first_fail_time"] >= self.cooldown_minutes * 60:
            self._state.pop(account_key, None)
            return False
        return s.get("ceiling_hit", False)

    def consecutive_count(self, account_key: str) -> int:
        s = self._state.get(account_key)
        return s["count"] if s else 0

    def summary(self) -> dict[str, dict[str, Any]]:
        return dict(self._state)


# ────────────────────────────────────────────
#  AccountHealthVerifier — アカウント健全性
# ────────────────────────────────────────────


class AccountHealthVerifier:
    """ページベースのアカウント健全性チェック。

    注意: page.gotoによるナビゲーションが発生する。
    各チェック後は元のページに戻らないので、呼び出し元で再ナビゲートが必要。
    """

    @staticmethod
    def check_login_status(page: Any) -> VerificationResult:
        """Xにログインしているか簡易確認。
        複数のフォールバックセレクタとURLチェックでログイン状態を判定。
        """
        try:
            selectors = [
                '[data-testid="SideNav_AccountSwitcherButton"]',
                '[aria-label*="プロフィール"]',
                '[aria-label*="Profile"]',
                '[data-testid="AppTabBar_Profile_Link"]',
                'a[href="/settings/profile"]',
            ]
            for sel in selectors:
                if page.query_selector(sel):
                    return VerificationResult(success=True, detail="logged_in")
            # 全てのセレクタで見つからなかった -> URLがhomeページならログイン済みとみなす
            current_url = page.url
            if current_url.startswith("https://x.com/home"):
                return VerificationResult(success=True, detail="logged_in")
            return VerificationResult(success=False, detail="login_icon_missing")
        except Exception as e:
            return VerificationResult(success=False, detail=f"check_error:{e}")

    @staticmethod
    def check_rate_limit_error(page: Any) -> VerificationResult:
        """レート制限エラー発生中かページ本文をスキャン。"""
        try:
            body = page.inner_text("body").lower()
            if "rate limit exceeded" in body:
                return VerificationResult(success=False, detail="rate_limited")
            if "unusual traffic" in body:
                return VerificationResult(success=False, detail="unusual_traffic")
            return VerificationResult(success=True, detail="no_rate_limit")
        except Exception:
            return VerificationResult(success=True, detail="check_skipped")

    @staticmethod
    def check_account_suspended(page: Any) -> VerificationResult:
        """アカウント停止・制限の確認。"""
        try:
            body = page.inner_text("body").lower()
            if "account suspended" in body:
                return VerificationResult(success=False, detail="suspended")
            if "this account has been suspended" in body:
                return VerificationResult(success=False, detail="suspended")
            if "this account has been restricted" in body:
                return VerificationResult(success=False, detail="restricted")
            return VerificationResult(success=True, detail="active")
        except Exception:
            return VerificationResult(success=True, detail="check_skipped")


# ────────────────────────────────────────────
#  ActionVerifier — アクション結果確認
# ────────────────────────────────────────────


class ActionVerifier:
    """各アクションが実際にX上で反映されたか確認。

    page.gotoによるナビゲーションが必要なためコスト高。
    Configでenabled=falseなら呼ばれない想定。
    """

    @staticmethod
    def verify_follow(page: Any, screen_name: str) -> VerificationResult:
        """フォローボタンの状態確認。
        screen_nameのプロフィールに遷移し、「フォロー」ボタンが「フォロー中」表示か確認。
        """
        try:
            url = f"https://x.com/{screen_name}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.5))

            # フォローボタン状態確認
            follow_btn = page.query_selector('[data-testid$="-unfollow"]')
            if follow_btn:
                return VerificationResult(success=True, detail="following")
            # まだフォローボタンが表示されている
            not_following = page.query_selector('[data-testid$="-follow"]')
            if not_following:
                return VerificationResult(success=False, detail="not_following")
            # 判定不能
            return VerificationResult(success=False, detail="button_unresolved")
        except Exception as e:
            return VerificationResult(success=False, detail=f"verify_error:{e}")

    @staticmethod
    def verify_retweet(page: Any, tweet_id: str, fallback_url: str = "") -> VerificationResult:
        """RTボタンの状態確認。

        ツイートページに遷移し、RTボタンがアクティブ（リポスト済み）か確認。
        2026-08-26 修正: 判別不能(unresolved)は success=False に変更。
          従来 success=True(verify_unresolved) として成功扱いし、API偽装成功(RT未反映)を
          検出できていなかった。実測: VERIFY ok表示12件中、実際にRT反映されたのは1件のみ。
          確認不能は「未成立」として再試行対象にし、連続失敗はfailure_trackerで上限制御する。
        """

        def _unresolved(detail: str) -> VerificationResult:
            return VerificationResult(success=False, detail=f"verify_unresolved:{detail}")

        try:
            url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else fallback_url
            if not url:
                return _unresolved("no_url")
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.5))

            # data-testid="unretweet" が存在 → リポスト済み
            unretweet = page.query_selector('[data-testid="unretweet"]')
            if unretweet:
                return VerificationResult(success=True, detail="retweeted")
            # まだRT可能な状態 → 明確な「RT未成立」
            retweet_btn = page.query_selector('[data-testid="retweet"]')
            if retweet_btn:
                return VerificationResult(success=False, detail="not_retweeted")
            return _unresolved("button_unresolved")
        except Exception as e:
            return _unresolved(f"goto_error:{str(e)[:40]}")

    @staticmethod
    def verify_like(page: Any, tweet_id: str, fallback_url: str = "") -> VerificationResult:
        """いいねボタンの状態確認。"""
        try:
            url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else fallback_url
            if not url:
                return VerificationResult(success=False, detail="no_url")
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.5))

            # data-testid="unlike" が存在 → いいね済み
            unlike = page.query_selector('[data-testid="unlike"]')
            if unlike:
                return VerificationResult(success=True, detail="liked")
            like_btn = page.query_selector('[data-testid="like"]')
            if like_btn:
                return VerificationResult(success=False, detail="not_liked")
            return VerificationResult(success=False, detail="button_unresolved")
        except Exception as e:
            return VerificationResult(success=False, detail=f"verify_error:{e}")


__all__ = [
    "VerificationResult",
    "ConsecutiveFailureTracker",
    "AccountHealthVerifier",
    "ActionVerifier",
]
