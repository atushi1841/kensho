"""FastAPI HTTP Application for Japan EC Price Monitoring Micro SaaS."""

from __future__ import annotations

from typing import Any
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import PriceMonitorDB
from .models import (
    AlertNotificationLog,
    PriceAlertRule,
    PriceAlertRuleCreate,
    PriceAlertRuleUpdate,
    PriceLogEntry,
    Subscription,
    SubscriptionTier,
)
from .service import PriceMonitorService

app = FastAPI(
    title="Japan EC Price Monitor Micro SaaS API",
    description="リアルタイム日本EC（Yahoo!ショッピング、楽天市場、メルカリ等）価格変動監視＆即時通知サービス",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = PriceMonitorService()


class PlanPricing(BaseModel):
    tier: SubscriptionTier
    name: str
    monthly_fee_jpy: int
    max_rules: int
    min_interval_minutes: int
    features: list[str]


class UpgradeRequest(BaseModel):
    user_id: str
    tier: SubscriptionTier


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "japan-ec-price-monitor-saas", "version": "1.0.0"}


# --- Subscriptions & Pricing ---

@app.get("/api/v1/plans", response_model=list[PlanPricing], tags=["Subscription"])
def list_plans() -> list[PlanPricing]:
    """List available subscription plans."""
    return [
        PlanPricing(
            tier=SubscriptionTier.FREE,
            name="Free Plan",
            monthly_fee_jpy=0,
            max_rules=3,
            min_interval_minutes=60,
            features=["最大3商品監視", "60分間隔チェック", "Telegram通知"],
        ),
        PlanPricing(
            tier=SubscriptionTier.PRO,
            name="Pro Plan",
            monthly_fee_jpy=1980,
            max_rules=30,
            min_interval_minutes=30,
            features=["最大30商品監視", "30分間隔チェック", "Telegram & Webhook通知", "価格履歴エクスポート"],
        ),
        PlanPricing(
            tier=SubscriptionTier.BUSINESS,
            name="Business Plan",
            monthly_fee_jpy=4980,
            max_rules=200,
            min_interval_minutes=15,
            features=["最大200商品監視", "15分高頻度チェック", "無制限Webhook/Telegram", "専任サポート"],
        ),
    ]


@app.get("/api/v1/users/{user_id}/subscription", response_model=Subscription, tags=["Subscription"])
def get_user_subscription(user_id: str) -> Subscription:
    """Get user's current subscription status."""
    return service.db.get_or_create_subscription(user_id)


@app.post("/api/v1/users/subscribe", response_model=Subscription, tags=["Subscription"])
def upgrade_plan(req: UpgradeRequest) -> Subscription:
    """Upgrade or switch user's subscription tier."""
    return service.db.upgrade_subscription(req.user_id, req.tier)


# --- Monitoring Rules CRUD ---

@app.post("/api/v1/rules", response_model=PriceAlertRule, status_code=status.HTTP_201_CREATED, tags=["Rules"])
def create_rule(req: PriceAlertRuleCreate) -> PriceAlertRule:
    """Create a new price monitoring rule."""
    try:
        return service.create_rule(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/rules", response_model=list[PriceAlertRule], tags=["Rules"])
def list_rules(
    user_id: str | None = Query(None, description="Filter by user_id"),
    only_active: bool = Query(False, description="Filter only active rules")
) -> list[PriceAlertRule]:
    """List monitoring rules."""
    return service.db.list_rules(user_id=user_id, only_active=only_active)


@app.get("/api/v1/rules/{rule_id}", response_model=PriceAlertRule, tags=["Rules"])
def get_rule(rule_id: str) -> PriceAlertRule:
    """Get single monitoring rule by ID."""
    rule = service.db.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


@app.patch("/api/v1/rules/{rule_id}", response_model=PriceAlertRule, tags=["Rules"])
def update_rule(rule_id: str, req: PriceAlertRuleUpdate) -> PriceAlertRule:
    """Update rule parameters."""
    rule = service.db.update_rule(rule_id, req)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


@app.delete("/api/v1/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Rules"])
def delete_rule(rule_id: str) -> None:
    """Delete a monitoring rule."""
    ok = service.db.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


# --- Execution & Verification ---

@app.post("/api/v1/rules/{rule_id}/check", tags=["Execution"])
def trigger_rule_check(rule_id: str, force: bool = False) -> dict[str, Any]:
    """Manually trigger immediate price scrape and condition evaluation for a rule."""
    try:
        return service.check_single_rule(rule_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/v1/cron/run-due-checks", tags=["Execution"])
def run_due_checks() -> dict[str, Any]:
    """Cron-triggered batch execution of due price checks."""
    results = service.run_due_checks()
    return {"checked_count": len(results), "results": results}


# --- History & Logs ---

@app.get("/api/v1/rules/{rule_id}/history", response_model=list[PriceLogEntry], tags=["Logs"])
def get_rule_price_history(rule_id: str, limit: int = 50) -> list[PriceLogEntry]:
    """Get price history for a given rule."""
    return service.db.get_price_history(rule_id, limit=limit)


@app.get("/api/v1/users/{user_id}/notifications", response_model=list[AlertNotificationLog], tags=["Logs"])
def get_user_notifications(user_id: str, limit: int = 50) -> list[AlertNotificationLog]:
    """Get notification history for a user."""
    return service.db.get_notification_logs(user_id, limit=limit)
