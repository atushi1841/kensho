"""Policy Engine — 各アクション前にポリシー評価（日次上限・時間あたり上限・最低間隔・確率スキップ・アクティブ時間）"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from enum import Enum
from typing import Any

from kensho.application.rate_limiter import load_daily_counts


class RiskClass(Enum):
    LOW = "LOW"  # いいね
    MEDIUM = "MEDIUM"  # フォロー
    HIGH = "HIGH"  # RT


class PolicyDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"


_RISK_FOR_ACTION: dict[str, RiskClass] = {
    "like": RiskClass.LOW,
    "follow": RiskClass.MEDIUM,
    "rt": RiskClass.HIGH,
}

_DAILY_BASE_LIMITS: dict[str, int] = {
    "like": 80,
    "rt": 15,
    "follow": 100,
}

_RISK_WEIGHTS = {
    RiskClass.LOW: 1.0,
    RiskClass.MEDIUM: 0.8,
    RiskClass.HIGH: 0.9,
}

_RISK_HOURLY_LIMITS = {
    RiskClass.LOW: 20,
    RiskClass.MEDIUM: 8,
    RiskClass.HIGH: 12,
}

_MIN_INTERVAL = {
    RiskClass.LOW: 1.0,
    RiskClass.MEDIUM: 3.0,
    RiskClass.HIGH: 2.0,
}

_SKIP_PROBABILITY = {
    RiskClass.LOW: 0.05,
    RiskClass.MEDIUM: 0.10,
    RiskClass.HIGH: 0.08,
}

# default active hours (UTC) – 0〜23 を許容
_DEFAULT_ACTIVE_HOURS = list(range(0, 24))


class PolicyEngine:
    def __init__(self) -> None:
        self._account_timestamps: dict[str, list[float]] = defaultdict(list)
        # dict[account_key] -> list[timestamp_of_last_action_of_any_type]  (for min interval)
        self._min_interval_history: dict[str, float] = {}
        # hourly sliding window: dict[account_key][action_type] -> list[timestamp]
        self._hourly_history: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    def evaluate(
        self,
        account_key: str,
        action_type: str,
        cfg: dict[str, Any] | None = None,
    ) -> tuple[PolicyDecision, str]:
        risk = _RISK_FOR_ACTION.get(action_type)
        if risk is None:
            return PolicyDecision.DENY, f"unknown_action:{action_type}"

        # 1. daily limit
        daily_counts = load_daily_counts()
        current_daily = daily_counts.get(account_key, {}).get(action_type, 0)
        base_max = (
            cfg.get("rate_limits", {}).get(f"max_{action_type}_per_day", 0)
            if cfg
            else _DAILY_BASE_LIMITS.get(action_type, 0)
        )
        risk_weights_config = cfg.get("policy_engine", {}).get("risk_weights", {}) if cfg else {}
        weight = risk_weights_config.get(action_type, _RISK_WEIGHTS[risk])
        effective_max = max(1, int(base_max * weight))
        if current_daily >= effective_max:
            return PolicyDecision.DENY, (f"daily_limit:{action_type}({current_daily}/{effective_max})")

        # 2. hourly limit
        now = time.time()
        hour_ago = now - 3600
        hourly = self._hourly_history[account_key][action_type]
        # remove old entries
        while hourly and hourly[0] < hour_ago:
            hourly.pop(0)
        current_hourly = len(hourly)
        hourly_limits_config = cfg.get("policy_engine", {}).get("hourly_limits", {}) if cfg else {}
        hourly_limit = hourly_limits_config.get(action_type, _RISK_HOURLY_LIMITS[risk])
        if current_hourly >= hourly_limit:
            return PolicyDecision.DENY, (f"hourly_limit:{action_type}({current_hourly}/{hourly_limit})")

        # 3. minimum interval
        last_time = self._min_interval_history.get(account_key)
        if last_time is not None:
            elapsed = now - last_time
            min_int = _MIN_INTERVAL[risk]
            if elapsed < min_int:
                return PolicyDecision.DENY, (f"min_interval:{action_type}({elapsed:.1f}s/{min_int}s)")

        # 4. probability skip
        skip_config = cfg.get("policy_engine", {}).get("skip_probability", {}) if cfg else {}
        skip_prob = skip_config.get(action_type, _SKIP_PROBABILITY[risk])
        if random.random() < skip_prob:
            return PolicyDecision.DENY, (f"prob_skip:{action_type}({skip_prob:.2f})")

        # 5. active hours (configurable)
        active_hours = cfg.get("active_hours", _DEFAULT_ACTIVE_HOURS) if cfg else _DEFAULT_ACTIVE_HOURS
        current_hour = time.gmtime().tm_hour
        if current_hour not in active_hours:
            return PolicyDecision.DENY, (f"inactive_hour:{action_type}(hour={current_hour})")

        return PolicyDecision.ALLOW, ""

    def mark_executed(self, account_key: str, action_type: str) -> None:
        """アクション実行後に呼び出し、最低間隔／時間上限のタイムスタンプを更新"""
        now = time.time()
        self._min_interval_history[account_key] = now
        self._hourly_history[account_key][action_type].append(now)


policy_engine = PolicyEngine()
