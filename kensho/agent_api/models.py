"""Data models and schemas for AI Agent Subscription API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AgentTier(str, Enum):
    """Subscription tiers for AI agents."""

    FREE = "free"            # 3 calls/day, 60 req/min
    PRO = "pro"              # 1,980/mo, 30 calls/day, 30 req/min
    BUSINESS = "business"    # 4,980/mo, 200 calls/day, 15 req/min


class AgentStatus(str, Enum):
    """Agent registration lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class ApiKeyCreate(BaseModel):
    """Request payload to create a new API key for an agent."""

    agent_id: str | None = Field(None, description="Agent ID (optional — derived from path)")
    label: str = Field("default", description="Human-readable key label")
    expires_days: int | None = Field(None, description="Optional expiry in days")


class ApiKey(BaseModel):
    """Stored API key entity (secret shown only at creation)."""

    id: str
    agent_id: str
    label: str
    key_hash: str          # SHA-256 of the raw key — never store plaintext
    prefix: str            # first 8 chars for identification
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
    raw_key: str | None = Field(None, description="Raw key value — only returned at creation")


class AgentCreate(BaseModel):
    """Request payload to register a new AI agent."""

    name: str = Field(..., min_length=1, max_length=128, description="Agent display name")
    owner_email: str = Field(..., description="Owner contact email")
    tier: AgentTier = Field(AgentTier.FREE, description="Subscription tier")
    description: str | None = Field(None, description="Agent purpose / use case")


class Agent(BaseModel):
    """Stored AI agent entity."""

    id: str
    name: str
    owner_email: str
    tier: AgentTier
    status: AgentStatus
    description: str | None
    monthly_fee_jpy: int = 0
    daily_call_limit: int = 3
    rate_limit_per_minute: int = 60
    created_at: datetime
    updated_at: datetime


class PlanPricing(BaseModel):
    """Subscription plan pricing summary for the public plans endpoint."""

    tier: AgentTier
    name: str
    monthly_fee_jpy: int
    daily_call_limit: int
    rate_limit_per_minute: int
    features: list[str]


class UsageLogCreate(BaseModel):
    """Request payload to record a single API usage event."""

    agent_id: str
    api_key_id: str
    endpoint: str
    method: str = "GET"
    status_code: int = 200
    latency_ms: int = 0
    request_bytes: int = 0
    response_bytes: int = 0


class UsageLog(BaseModel):
    """Stored usage log record."""

    id: str
    agent_id: str
    api_key_id: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: int
    request_bytes: int
    response_bytes: int
    recorded_at: datetime


class UsageSummary(BaseModel):
    """Aggregated usage summary for an agent over a window."""

    agent_id: str
    tier: AgentTier
    window_start: datetime
    window_end: datetime
    total_calls: int
    daily_limit: int
    calls_remaining: int
    rate_limit_per_minute: int
    calls_last_minute: int
    endpoints: dict[str, int]
    status_codes: dict[str, int]
    avg_latency_ms: float
