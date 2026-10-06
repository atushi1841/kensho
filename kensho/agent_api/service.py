"""Service layer for AI Agent Subscription API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .db import AgentAPI_DB
from .models import (
    Agent,
    AgentCreate,
    AgentStatus,
    AgentTier,
    ApiKey,
    ApiKeyCreate,
    UsageLogCreate,
)

logger = logging.getLogger(__name__)


class AgentAPIService:
    """Core business logic for AI agent subscriptions and API key management."""

    def __init__(self, db: AgentAPI_DB | None = None):
        self.db = db or AgentAPI_DB()

    # --- Agent Management ---
    def register_agent(self, req: AgentCreate) -> Agent:
        """Register a new AI agent with subscription tier."""
        return self.db.create_agent(req)

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get agent details by ID."""
        return self.db.get_agent(agent_id)

    def list_agents(self, status: AgentStatus | None = None) -> list[Agent]:
        """List agents with optional status filter."""
        return self.db.list_agents(status=status)

    def suspend_agent(self, agent_id: str) -> Agent | None:
        """Suspend an agent (disable API access)."""
        return self.db.update_agent(agent_id, status=AgentStatus.SUSPENDED)

    def activate_agent(self, agent_id: str) -> Agent | None:
        """Reactivate a suspended agent."""
        return self.db.update_agent(agent_id, status=AgentStatus.ACTIVE)

    # --- API Key Management ---
    def create_api_key(
        self, req: ApiKeyCreate
    ) -> dict[str, Any]:
        """Create a new API key for an agent. Returns dict with api_key and raw_key."""
        api_key, raw_key = self.db.create_api_key(req)
        return {"api_key": api_key, "raw_key": raw_key}

    def list_api_keys(self, agent_id: str) -> list[ApiKey]:
        """List all API keys for an agent."""
        return self.db.list_api_keys(agent_id)

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke (deactivate) an API key."""
        return self.db.revoke_api_key(key_id)

    def authenticate(self, raw_key: str) -> ApiKey | None:
        """Validate an API key and return key info if valid."""
        return self.db.verify_api_key(raw_key)

    # --- Usage Tracking ---
    def record_usage(self, req: UsageLogCreate) -> Any:
        """Record an API usage event."""
        log = self.db.record_usage(req)
        return {
            "id": log.id,
            "agent_id": log.agent_id,
            "endpoint": log.endpoint,
            "status_code": log.status_code,
            "recorded_at": log.recorded_at.isoformat(),
        }

    def get_usage_summary(self, agent_id: str, days: int = 1) -> dict[str, Any]:
        """Get usage summary for an agent."""
        summary = self.db.get_usage_summary(agent_id, days=days)
        return summary.model_dump()

    def check_rate_limit(self, agent_id: str) -> dict[str, Any]:
        """Check if an agent has hit their rate limits."""
        summary = self.db.get_usage_summary(agent_id, days=1)

        daily_limit = summary.daily_limit
        daily_used = summary.total_calls
        calls_last_min = summary.calls_last_minute
        rate_limit = summary.rate_limit_per_minute

        return {
            "agent_id": agent_id,
            "daily_limit": daily_limit,
            "daily_used": daily_used,
            "daily_remaining": summary.calls_remaining,
            "daily_usage_pct": round(daily_used / daily_limit * 100, 1) if daily_limit > 0 else 0,
            "rate_limit_per_minute": rate_limit,
            "calls_last_minute": calls_last_min,
            "rate_limited": calls_last_min >= rate_limit,
            "daily_limited": daily_used >= daily_limit,
        }

    def authenticate_and_check_limits(
        self, raw_key: str
    ) -> dict[str, Any] | None:
        """Authenticate key and check all limits. Returns auth info or None if invalid."""
        api_key = self.authenticate(raw_key)
        if not api_key:
            return None

        agent = self.get_agent(api_key.agent_id)
        if not agent:
            return None

        limits = self.check_rate_limit(agent.id)
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "tier": agent.tier.value,
            "key_prefix": api_key.prefix,
            "daily_limits": limits,
            "authenticated_at": datetime.utcnow().isoformat(),
        }

    # --- Plan Info ---
    def get_plans(self) -> list[dict[str, Any]]:
        """Get all subscription plan details."""
        return self.db.get_plans()

    def upgrade_tier(self, agent_id: str, new_tier: AgentTier) -> Agent | None:
        """Upgrade an agent's subscription tier."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        if agent.status != AgentStatus.ACTIVE:
            raise ValueError(f"Agent {agent_id} is not active")

        limits = {
            AgentTier.FREE: {"daily": 3, "rpm": 60, "fee": 0},
            AgentTier.PRO: {"daily": 30, "rpm": 30, "fee": 1980},
            AgentTier.BUSINESS: {"daily": 200, "rpm": 15, "fee": 4980},
        }

        new_limits = limits[new_tier]
        return self.db.update_agent(
            agent_id,
            tier=new_tier,
            monthly_fee_jpy=new_limits["fee"],
            daily_call_limit=new_limits["daily"],
            rate_limit_per_minute=new_limits["rpm"],
        )
