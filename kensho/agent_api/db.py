"""SQLite Database Layer for AI Agent Subscription API."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import (
    Agent,
    AgentCreate,
    AgentStatus,
    AgentTier,
    ApiKey,
    ApiKeyCreate,
    UsageLog,
    UsageLogCreate,
    UsageSummary,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "agent_api.db"

TIER_LIMITS: dict[AgentTier, dict[str, Any]] = {
    AgentTier.FREE: {
        "monthly_fee_jpy": 0,
        "daily_call_limit": 3,
        "rate_limit_per_minute": 60,
        "features": [
            "3 calls/day",
            "60 req/min rate limit",
            "Basic scraping endpoints",
            "Community support",
        ],
    },
    AgentTier.PRO: {
        "monthly_fee_jpy": 1980,
        "daily_call_limit": 30,
        "rate_limit_per_minute": 30,
        "features": [
            "30 calls/day",
            "30 req/min rate limit",
            "All scraping endpoints",
            "Price history access",
            "Email support",
        ],
    },
    AgentTier.BUSINESS: {
        "monthly_fee_jpy": 4980,
        "daily_call_limit": 200,
        "rate_limit_per_minute": 15,
        "features": [
            "200 calls/day",
            "15 req/min rate limit (priority)",
            "All endpoints + webhooks",
            "Unlimited history",
            "Priority support",
            "Custom integrations",
        ],
    },
}


def _generate_api_key(prefix: str = "kensho") -> tuple[str, str]:
    """Generate a secure API key and return (raw_key, hash)."""
    raw_key = f"{prefix}_{uuid.uuid4().hex}_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


class AgentAPI_DB:
    """Database manager for AI agent subscriptions and usage tracking."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_email TEXT NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'free',
                    status TEXT NOT NULL DEFAULT 'active',
                    description TEXT,
                    monthly_fee_jpy INTEGER NOT NULL DEFAULT 0,
                    daily_call_limit INTEGER NOT NULL DEFAULT 3,
                    rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT 'default',
                    key_hash TEXT NOT NULL,
                    prefix TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS usage_logs (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    api_key_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'GET',
                    status_code INTEGER NOT NULL DEFAULT 200,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    request_bytes INTEGER NOT NULL DEFAULT 0,
                    response_bytes INTEGER NOT NULL DEFAULT 0,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE,
                    FOREIGN KEY (api_key_id) REFERENCES api_keys (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_agents_tier ON agents(tier);
                CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
                CREATE INDEX IF NOT EXISTS idx_api_keys_agent ON api_keys(agent_id);
                CREATE INDEX IF NOT EXISTS idx_usage_agent ON usage_logs(agent_id);
                CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_logs(recorded_at);
                CREATE INDEX IF NOT EXISTS idx_usage_key ON usage_logs(api_key_id);
            """)

    # --- Agent CRUD ---
    def create_agent(self, req: AgentCreate) -> Agent:
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        tier = req.tier
        limits = TIER_LIMITS[tier]

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO agents (
                    id, name, owner_email, tier, status, description,
                    monthly_fee_jpy, daily_call_limit, rate_limit_per_minute,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_id, req.name, req.owner_email, tier.value,
                    AgentStatus.ACTIVE.value, req.description,
                    limits["monthly_fee_jpy"], limits["daily_call_limit"],
                    limits["rate_limit_per_minute"], now.isoformat(), now.isoformat(),
                ),
            )

        return Agent(
            id=agent_id,
            name=req.name,
            owner_email=req.owner_email,
            tier=tier,
            status=AgentStatus.ACTIVE,
            description=req.description,
            created_at=now,
            updated_at=now,
        )

    def get_agent(self, agent_id: str) -> Agent | None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cur.fetchone()
            return self._row_to_agent(row) if row else None

    def list_agents(self, status: AgentStatus | None = None, limit: int = 50) -> list[Agent]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM agents WHERE 1=1"
            params: list[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status.value)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            cur.execute(query, params)
            return [self._row_to_agent(r) for r in cur.fetchall()]

    def update_agent(self, agent_id: str, **kwargs: Any) -> Agent | None:
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        allowed = {
            "name", "description", "tier", "status",
            "monthly_fee_jpy", "daily_call_limit", "rate_limit_per_minute",
        }
        fields: list[str] = []
        params: list[Any] = []

        for key, val in kwargs.items():
            if key in allowed:
                fields.append(f"{key} = ?")
                if key == "tier":
                    val = val.value if isinstance(val, AgentTier) else val
                params.append(val)

        if not fields:
            return agent

        fields.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(agent_id)

        with self._get_conn() as conn:
            conn.execute(f"UPDATE agents SET {', '.join(fields)} WHERE id = ?", params)

        return self.get_agent(agent_id)

    # --- API Key Management ---
    def create_api_key(self, req: ApiKeyCreate) -> tuple[ApiKey, str]:
        agent = self.get_agent(req.agent_id)
        if not agent:
            raise ValueError(f"Agent {req.agent_id} not found")
        if agent.status != AgentStatus.ACTIVE:
            raise ValueError(f"Agent {req.agent_id} is not active ({agent.status.value})")

        now = datetime.utcnow()
        key_id = f"key_{uuid.uuid4().hex[:12]}"
        expires_at = None
        if req.expires_days:
            expires_at = (now + timedelta(days=req.expires_days)).isoformat()

        raw_key, key_hash = _generate_api_key()
        prefix = raw_key[:8]

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO api_keys (
                    id, agent_id, label, key_hash, prefix,
                    is_active, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key_id, req.agent_id, req.label, key_hash, prefix,
                    1, expires_at, now.isoformat(),
                ),
            )

        api_key = ApiKey(
            id=key_id,
            agent_id=req.agent_id,
            label=req.label,
            key_hash=key_hash,
            prefix=prefix,
            is_active=True,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
            created_at=now,
        )

        return api_key, raw_key

    def list_api_keys(self, agent_id: str) -> list[ApiKey]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM api_keys WHERE agent_id = ? ORDER BY created_at DESC",
                (agent_id,),
            )
            return [self._row_to_api_key(r) for r in cur.fetchall()]

    def get_api_key(self, key_id: str) -> ApiKey | None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
            row = cur.fetchone()
            return self._row_to_api_key(row) if row else None

    def verify_api_key(self, raw_key: str) -> ApiKey | None:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM api_keys
                   WHERE key_hash = ? AND is_active = 1
                   AND (expires_at IS NULL OR expires_at > ?)
                   LIMIT 1""",
                (key_hash, now),
            )
            row = cur.fetchone()
            return self._row_to_api_key(row) if row else None

    def revoke_api_key(self, key_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
            return cur.rowcount > 0

    # --- Usage Tracking ---
    def record_usage(self, req: UsageLogCreate) -> UsageLog:
        now = datetime.utcnow()
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO usage_logs (
                    id, agent_id, api_key_id, endpoint, method,
                    status_code, latency_ms, request_bytes, response_bytes, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id, req.agent_id, req.api_key_id, req.endpoint,
                    req.method, req.status_code, req.latency_ms,
                    req.request_bytes, req.response_bytes, now.isoformat(),
                ),
            )

        return UsageLog(
            id=log_id,
            agent_id=req.agent_id,
            api_key_id=req.api_key_id,
            endpoint=req.endpoint,
            method=req.method,
            status_code=req.status_code,
            latency_ms=req.latency_ms,
            request_bytes=req.request_bytes,
            response_bytes=req.response_bytes,
            recorded_at=now,
        )

    def get_usage_summary(
        self,
        agent_id: str,
        days: int = 1,
        include_last_minute: bool = False,
    ) -> UsageSummary:
        now = datetime.utcnow()
        window_start = now - timedelta(days=days)

        with self._get_conn() as conn:
            cur = conn.cursor()

            # Get agent info
            cur.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            agent_row = cur.fetchone()
            if not agent_row:
                raise ValueError(f"Agent {agent_id} not found")

            # Count calls in window
            cur.execute(
                """SELECT COUNT(*) as cnt
                   FROM usage_logs
                   WHERE agent_id = ? AND recorded_at >= ?""",
                (agent_id, window_start.isoformat()),
            )
            total_calls = cur.fetchone()["cnt"] or 0

            # Calls in last minute
            last_minute_start = (now - timedelta(minutes=1)).isoformat()
            cur.execute(
                """SELECT COUNT(*) as cnt
                   FROM usage_logs
                   WHERE agent_id = ? AND recorded_at >= ?""",
                (agent_id, last_minute_start),
            )
            calls_last_minute = cur.fetchone()["cnt"] or 0

            # Endpoint breakdown
            cur.execute(
                """SELECT endpoint, COUNT(*) as cnt
                   FROM usage_logs
                   WHERE agent_id = ? AND recorded_at >= ?
                   GROUP BY endpoint""",
                (agent_id, window_start.isoformat()),
            )
            endpoints = {row["endpoint"]: row["cnt"] for row in cur.fetchall()}

            # Status code breakdown
            cur.execute(
                """SELECT status_code, COUNT(*) as cnt
                   FROM usage_logs
                   WHERE agent_id = ? AND recorded_at >= ?
                   GROUP BY status_code""",
                (agent_id, window_start.isoformat()),
            )
            status_codes = {str(row["status_code"]): row["cnt"] for row in cur.fetchall()}

            # Avg latency
            cur.execute(
                """SELECT AVG(latency_ms) as avg_lat
                   FROM usage_logs
                   WHERE agent_id = ? AND recorded_at >= ?""",
                (agent_id, window_start.isoformat()),
            )
            avg_lat = cur.fetchone()["avg_lat"] or 0.0

        tier = AgentTier(agent_row["tier"])
        limits = TIER_LIMITS[tier]

        return UsageSummary(
            agent_id=agent_id,
            tier=tier,
            window_start=window_start,
            window_end=now,
            total_calls=total_calls,
            daily_limit=limits["daily_call_limit"],
            calls_remaining=max(0, limits["daily_call_limit"] - total_calls),
            rate_limit_per_minute=limits["rate_limit_per_minute"],
            calls_last_minute=calls_last_minute,
            endpoints=endpoints,
            status_codes=status_codes,
            avg_latency_ms=round(avg_lat, 2),
        )

    def count_daily_calls(self, agent_id: str) -> int:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) as cnt FROM usage_logs WHERE agent_id = ? AND recorded_at >= ?",
                (agent_id, today_start),
            )
            return cur.fetchone()["cnt"] or 0

    # --- Plan Info ---
    def get_plans(self) -> list[dict[str, Any]]:
        plans = []
        for tier in [AgentTier.FREE, AgentTier.PRO, AgentTier.BUSINESS]:
            limits = TIER_LIMITS[tier]
            plans.append({
                "tier": tier.value,
                "name": f"{tier.value.title()} Plan",
                "monthly_fee_jpy": limits["monthly_fee_jpy"],
                "daily_call_limit": limits["daily_call_limit"],
                "rate_limit_per_minute": limits["rate_limit_per_minute"],
                "features": limits["features"],
            })
        return plans

    # --- Helpers ---
    @staticmethod
    def _row_to_agent(row: sqlite3.Row) -> Agent:
        return Agent(
            id=row["id"],
            name=row["name"],
            owner_email=row["owner_email"],
            tier=AgentTier(row["tier"]),
            status=AgentStatus(row["status"]),
            description=row["description"],
            monthly_fee_jpy=row["monthly_fee_jpy"],
            daily_call_limit=row["daily_call_limit"],
            rate_limit_per_minute=row["rate_limit_per_minute"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_api_key(row: sqlite3.Row) -> ApiKey:
        return ApiKey(
            id=row["id"],
            agent_id=row["agent_id"],
            label=row["label"],
            key_hash=row["key_hash"],
            prefix=row["prefix"],
            is_active=bool(row["is_active"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
