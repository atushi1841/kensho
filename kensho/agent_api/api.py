"""FastAPI Application for AI Agent Subscription API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Agent,
    AgentCreate,
    AgentStatus,
    AgentTier,
    ApiKey,
    ApiKeyCreate,
    PlanPricing,
)
from .service import AgentAPIService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Japan EC Price Monitor — AI Agent API",
    description=(
        "AIエージェント向けの日本EC価格監視APIサブスクリプションサービス。"
        "Kenshoスクレイパー資産をREST APIで提供し、"
        "APIキー認証・レートリミット・使用量追跡を管理します。"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = AgentAPIService()


# ── Auth helper ──────────────────────────────────────────────

def _authenticate(request: Any) -> tuple[str, str]:
    """Extract and verify API key from request headers.

    Returns:
        (agent_id, raw_key_if_present)

    Raises:
        HTTPException on invalid/missing key.
    """
    raw_key = request.headers.get("X-API-Key", "")
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    auth = service.authenticate_and_check_limits(raw_key)
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    if auth["daily_limits"]["daily_limited"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily call limit reached "
                f"({auth['daily_limits']['daily_used']}/"
                f"{auth['daily_limits']['daily_limit']})"
            ),
        )
    if auth["daily_limits"]["rate_limited"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    return auth["agent_id"], raw_key


# ── Health & Plans ───────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "japan-ec-price-monitor-agent-api",
        "version": "1.0.0",
    }


@app.get("/api/v1/plans", response_model=list[PlanPricing], tags=["Subscription"])
def list_plans() -> list[PlanPricing]:
    plans = service.get_plans()
    result = []
    for p in plans:
        result.append(
            PlanPricing(
                tier=AgentTier(p["tier"]),
                name=p["name"],
                monthly_fee_jpy=p["monthly_fee_jpy"],
                daily_call_limit=p["daily_call_limit"],
                rate_limit_per_minute=p["rate_limit_per_minute"],
                features=p["features"],
            )
        )
    return result


# ── Agent CRUD ───────────────────────────────────────────────

@app.post(
    "/api/v1/agents",
    response_model=Agent,
    status_code=status.HTTP_201_CREATED,
    tags=["Agents"],
)
def create_agent(req: AgentCreate) -> Agent:
    try:
        return service.register_agent(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/agents/{agent_id}", response_model=Agent, tags=["Agents"])
def get_agent(agent_id: str) -> Agent:
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.get("/api/v1/agents", response_model=list[Agent], tags=["Agents"])
def list_agents(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
) -> list[Agent]:
    sf = AgentStatus(status_filter) if status_filter else None
    return service.list_agents(status=sf)


@app.post("/api/v1/agents/{agent_id}/suspend", response_model=Agent, tags=["Agents"])
def suspend_agent(agent_id: str) -> Agent:
    agent = service.suspend_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/api/v1/agents/{agent_id}/activate", response_model=Agent, tags=["Agents"])
def activate_agent(agent_id: str) -> Agent:
    agent = service.activate_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/api/v1/agents/{agent_id}/upgrade", response_model=Agent, tags=["Agents"])
def upgrade_agent(agent_id: str, req: dict[str, str]) -> Agent:
    try:
        tier = AgentTier(req["tier"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tier. Use: free, pro, business")
    agent = service.upgrade_tier(agent_id, tier)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── API Key Management ───────────────────────────────────────

@app.post(
    "/api/v1/agents/{agent_id}/keys",
    status_code=status.HTTP_201_CREATED,
    tags=["API Keys"],
)
def create_api_key(agent_id: str, req: ApiKeyCreate) -> dict[str, Any]:
    try:
        # Override agent_id from path parameter if not in request
        req.agent_id = agent_id
        result = service.create_api_key(req)
        api_key = result["api_key"]
        raw_key = result["raw_key"]
        # Return the key with raw value only at creation time
        resp = api_key.model_dump()
        resp["raw_key"] = raw_key
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/agents/{agent_id}/keys", response_model=list[ApiKey], tags=["API Keys"])
def list_api_keys(agent_id: str) -> list[ApiKey]:
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return service.list_api_keys(agent_id)


@app.delete("/api/v1/agents/{agent_id}/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["API Keys"])
def revoke_api_key(agent_id: str, key_id: str) -> None:
    api_key = service.list_api_keys(agent_id)
    if not any(k.id == key_id for k in api_key):
        raise HTTPException(status_code=404, detail="Key not found")
    ok = service.revoke_api_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")


# ── Usage & Analytics ────────────────────────────────

@app.get("/api/v1/usage/{agent_id}", tags=["Usage"])
def get_usage_summary(request: Request, agent_id: str, days: int = Query(1, ge=1, le=365)) -> dict[str, Any]:
    _authenticate(request)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return service.get_usage_summary(agent_id, days=days)


@app.get("/api/v1/limits/{agent_id}", tags=["Usage"])
def check_limits(request: Request, agent_id: str) -> dict[str, Any]:
    _authenticate(request)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return service.check_rate_limit(agent_id)


# ── Demo Endpoint (authenticated) ───────────────────────────

@app.get("/api/v1/demo/scrape", tags=["Demo"])
def demo_scrape(request: Request, x_url: str = Query(..., description="Product URL to scrape")) -> dict[str, Any]:
    """Demo endpoint that scrapes a product URL and returns price info.

    Requires valid X-API-Key header.
    """
    _authenticate(request)
    return {
        "url": x_url,
        "status": "demo",
        "note": "Connect to kensho.price_monitor.scraper for real scraping",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }
