"""Unit tests for AI Agent Subscription API (t_52543a04)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import kensho.agent_api.api as api_module
from kensho.agent_api.api import app
from kensho.agent_api.db import AgentAPI_DB
from kensho.agent_api.models import (
    Agent,
    AgentCreate,
    AgentStatus,
    AgentTier,
    ApiKey,
    ApiKeyCreate,
    UsageLogCreate,
)
from kensho.agent_api.service import AgentAPIService


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_agent_api.db"
    return AgentAPI_DB(db_path=db_file)


@pytest.fixture
def service(temp_db):
    return AgentAPIService(db=temp_db)


@pytest.fixture
def sample_agent(service) -> Agent:
    req = AgentCreate(
        name="Test AI Agent",
        owner_email="agent@example.com",
        tier=AgentTier.FREE,
        description="Test agent for unit tests",
    )
    return service.register_agent(req)


@pytest.fixture
def sample_key(service, sample_agent) -> tuple[ApiKey, str]:
    req = ApiKeyCreate(
        agent_id=sample_agent.id,
        label="test-key",
    )
    result = service.create_api_key(req)
    return result["api_key"], result["raw_key"]


def test_health_check():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "japan-ec-price-monitor-agent-api" in data["service"]


def test_list_plans():
    client = TestClient(app)
    res = client.get("/api/v1/plans")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) == 3
    tiers = {p["tier"] for p in plans}
    assert tiers == {"free", "pro", "business"}
    assert plans[0]["monthly_fee_jpy"] == 0
    assert plans[1]["monthly_fee_jpy"] == 1980
    assert plans[2]["monthly_fee_jpy"] == 4980


def test_agent_crud(service: AgentAPIService):
    # Create
    req = AgentCreate(
        name="Agent Alpha",
        owner_email="alpha@test.com",
        tier=AgentTier.PRO,
    )
    agent = service.register_agent(req)
    assert agent.id.startswith("agent_")
    assert agent.name == "Agent Alpha"
    assert agent.tier == AgentTier.PRO
    assert agent.status == AgentStatus.ACTIVE

    # Read
    fetched = service.get_agent(agent.id)
    assert fetched is not None
    assert fetched.id == agent.id

    # List
    all_agents = service.list_agents()
    assert len(all_agents) >= 1

    # List with status filter
    active_agents = service.list_agents(status=AgentStatus.ACTIVE)
    assert len(active_agents) >= 1

    # Upgrade
    upgraded = service.upgrade_tier(agent.id, AgentTier.BUSINESS)
    assert upgraded.tier == AgentTier.BUSINESS
    assert upgraded.daily_call_limit == 200
    assert upgraded.rate_limit_per_minute == 15

    # Suspend
    suspended = service.suspend_agent(agent.id)
    assert suspended.status == AgentStatus.SUSPENDED

    # Activate
    activated = service.activate_agent(agent.id)
    assert activated.status == AgentStatus.ACTIVE

    # Get non-existent
    assert service.get_agent("agent_nonexistent") is None


def test_api_key_crud(service: AgentAPIService, sample_agent: Agent):
    # Create key
    req = ApiKeyCreate(
        agent_id=sample_agent.id,
        label="primary-key",
        expires_days=30,
    )
    result = service.create_api_key(req)
    api_key = result["api_key"]
    raw_key = result["raw_key"]
    assert api_key.id.startswith("key_")
    assert api_key.agent_id == sample_agent.id
    assert api_key.label == "primary-key"
    assert api_key.is_active is True
    assert api_key.prefix == raw_key[:8]
    assert api_key.expires_at is not None

    # List keys
    keys = service.list_api_keys(sample_agent.id)
    assert len(keys) >= 1
    assert any(k.id == api_key.id for k in keys)

    # Authenticate
    auth_result = service.authenticate(raw_key)
    assert auth_result is not None
    assert auth_result.id == api_key.id
    assert auth_result.is_active is True

    # Verify invalid key
    assert service.authenticate("invalid_key_12345") is None

    # Revoke
    assert service.revoke_api_key(api_key.id) is True
    assert service.authenticate(raw_key) is None  # Should be revoked


def test_usage_tracking(service: AgentAPIService, sample_agent: Agent, sample_key: tuple):
    api_key, raw_key = sample_key

    # Record usage
    usage_req = UsageLogCreate(
        agent_id=sample_agent.id,
        api_key_id=api_key.id,
        endpoint="/api/v1/demo/scrape",
        method="GET",
        status_code=200,
        latency_ms=150,
        request_bytes=256,
        response_bytes=1024,
    )
    log = service.record_usage(usage_req)
    assert log["id"].startswith("log_")
    assert log["agent_id"] == sample_agent.id
    assert log["endpoint"] == "/api/v1/demo/scrape"

    # Get summary
    summary = service.get_usage_summary(sample_agent.id, days=1)
    assert summary["agent_id"] == sample_agent.id
    assert summary["total_calls"] >= 1
    assert summary["daily_limit"] == 3  # FREE tier
    assert summary["calls_remaining"] >= 0
    assert summary["endpoints"] == {"/api/v1/demo/scrape": 1}
    assert summary["status_codes"] == {"200": 1}

    # Check limits
    limits = service.check_rate_limit(sample_agent.id)
    assert limits["daily_limit"] == 3
    assert limits["daily_used"] >= 1
    assert limits["rate_limit_per_minute"] == 60  # FREE tier


def test_daily_limit_enforcement(service: AgentAPIService, sample_agent: Agent):
    # FREE tier has 3 calls/day
    assert service.db.get_agent(sample_agent.id).daily_call_limit == 3

    # Create key
    key_req = ApiKeyCreate(agent_id=sample_agent.id, label="limit-test")
    res = service.create_api_key(key_req)
    key = res["api_key"]

    for i in range(3):
        service.record_usage(UsageLogCreate(
            agent_id=sample_agent.id,
            api_key_id=key.id,
            endpoint="/test",
        ))

    # Check summary - should have 3 calls now
    summary = service.get_usage_summary(sample_agent.id, days=1)
    assert summary["total_calls"] == 3
    assert summary["calls_remaining"] == 0

    # Check limits
    limits = service.check_rate_limit(sample_agent.id)
    assert limits["daily_limited"] is True


def test_api_auth_integration(temp_db: AgentAPI_DB, sample_agent: Agent):
    service = AgentAPIService(db=temp_db)
    api_module.service = service

    client = TestClient(app)

    # Create API key for sample_agent directly
    res = service.create_api_key(ApiKeyCreate(agent_id=sample_agent.id, label="auth-test"))
    api_key2 = res["api_key"]
    raw_key2 = res["raw_key"]

    # Test without key on protected endpoint
    res = client.get(f"/api/v1/limits/{sample_agent.id}")
    assert res.status_code == 401

    # Test with invalid key
    res = client.get(
        f"/api/v1/limits/{sample_agent.id}",
        headers={"X-API-Key": "invalid_key"},
    )
    assert res.status_code == 401

    # Test with valid key
    res = client.get(
        f"/api/v1/limits/{sample_agent.id}",
        headers={"X-API-Key": raw_key2},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == sample_agent.id

    # Test with revoked key
    service.revoke_api_key(api_key2.id)
    res = client.get(
        f"/api/v1/limits/{sample_agent.id}",
        headers={"X-API-Key": raw_key2},
    )
    assert res.status_code == 401


def test_fastapi_agent_endpoints(temp_db: AgentAPI_DB):
    service = AgentAPIService(db=temp_db)
    api_module.service = service

    client = TestClient(app)

    # Create agent
    res = client.post(
        "/api/v1/agents",
        json={
            "name": "Test Agent",
            "owner_email": "test@example.com",
            "tier": "free",
            "description": "Test agent via API",
        },
    )
    assert res.status_code == 201
    agent_data = res.json()
    assert agent_data["name"] == "Test Agent"
    assert agent_data["tier"] == "free"
    assert agent_data["status"] == "active"
    agent_id = agent_data["id"]

    # Get agent
    res = client.get(f"/api/v1/agents/{agent_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Test Agent"

    # List agents
    res = client.get("/api/v1/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 1

    # List with status filter
    res = client.get("/api/v1/agents?status=active")
    assert res.status_code == 200

    # Create API key
    res = client.post(
        f"/api/v1/agents/{agent_id}/keys",
        json={"label": "test-key", "expires_days": 7},
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 201
    key_data = res.json()
    assert "raw_key" in key_data  # Raw key only returned at creation
    raw_key = key_data["raw_key"]  # noqa: F841
    key_id = key_data["id"]

    # List keys
    res = client.get(f"/api/v1/agents/{agent_id}/keys")
    assert res.status_code == 200
    keys = res.json()
    assert len(keys) >= 1

    # Delete key
    res = client.delete(f"/api/v1/agents/{agent_id}/keys/{key_id}")
    assert res.status_code == 204
    # Key is now deleted; create a fresh one for authenticated tests
    res = client.post(
        f"/api/v1/agents/{agent_id}/keys",
        json={"label": "auth-test-2"},
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 201
    auth_key_data = res.json()
    auth_raw_key = auth_key_data["raw_key"]

    # Try to delete non-existent key
    res = client.delete(f"/api/v1/agents/{agent_id}/keys/nonexistent")
    assert res.status_code == 404

    # Usage summary (authenticated)
    res = client.get(
        f"/api/v1/usage/{agent_id}",
        headers={"X-API-Key": auth_raw_key},
    )
    assert res.status_code == 200
    usage = res.json()
    assert usage["agent_id"] == agent_id

    # Limits check (authenticated)
    res = client.get(
        f"/api/v1/limits/{agent_id}",
        headers={"X-API-Key": auth_raw_key},
    )
    assert res.status_code == 200
    limits = res.json()
    assert limits["daily_limit"] == 3  # Free tier

    # Upgrade tier
    res = client.post(
        f"/api/v1/agents/{agent_id}/upgrade",
        json={"tier": "pro"},
    )
    assert res.status_code == 200
    upgraded = res.json()
    assert upgraded["tier"] == "pro"
    assert upgraded["daily_call_limit"] == 30

    # Suspend agent
    res = client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert res.status_code == 200
    assert res.json()["status"] == "suspended"

    # Activate agent
    res = client.post(f"/api/v1/agents/{agent_id}/activate")
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # Invalid upgrade tier
    res = client.post(
        f"/api/v1/agents/{agent_id}/upgrade",
        json={"tier": "invalid_tier"},
    )
    assert res.status_code == 400
