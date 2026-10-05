"""Data models and schemas for Japan EC Price Monitoring Micro SaaS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl


class SubscriptionTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"          # ¥1,980/month (up to 30 items, 1-hour interval, Telegram/Webhook)
    BUSINESS = "business"  # ¥4,980/month (up to 200 items, 15-min interval, Priority check)


class NotificationChannel(str, Enum):
    """Notification channels."""
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    EMAIL = "email"
    LOG = "log"


class AlertCondition(str, Enum):
    """Condition for price alert triggering."""
    LESS_THAN_OR_EQUAL = "lte"  # target_price 以下
    PERCENT_DROP = "percent_drop"  # 指定パーセント以上の値下がり
    ANY_DROP = "any_drop"        # 直前価格より値下がり
    IN_STOCK = "in_stock"        # 在庫復活


class ECPlatform(str, Enum):
    """Supported Japanese EC Platforms."""
    YAHOO_SHOPPING = "yahoo_shopping"
    RAKUTEN = "rakuten"
    MERCARI = "mercari"
    SURUGAYA = "surugaya"
    GENERIC = "generic"


class PriceItem(BaseModel):
    """Scraped item price details."""
    url: str
    title: str
    price_jpy: int
    platform: ECPlatform
    in_stock: bool = True
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    seller: str | None = None
    image_url: str | None = None


class PriceAlertRuleCreate(BaseModel):
    """Request payload to create a price monitoring rule."""
    user_id: str = Field(..., description="User or Account ID")
    url: str = Field(..., description="Target product URL")
    title_override: str | None = Field(None, description="Custom title/alias for the item")
    target_price_jpy: int | None = Field(None, description="Target price threshold in JPY")
    condition: AlertCondition = Field(AlertCondition.LESS_THAN_OR_EQUAL, description="Trigger condition")
    drop_percentage: float | None = Field(None, description="Trigger if price drops by this percent (e.g. 10.0 for 10%)")
    notification_channel: NotificationChannel = Field(NotificationChannel.TELEGRAM, description="Channel for alert")
    notification_destination: str = Field(..., description="Telegram chat ID, Webhook URL, or Email address")
    check_interval_minutes: int = Field(60, ge=15, description="Frequency of check in minutes")
    is_active: bool = True


class PriceAlertRuleUpdate(BaseModel):
    """Request payload to update a price monitoring rule."""
    title_override: str | None = None
    target_price_jpy: int | None = None
    condition: AlertCondition | None = None
    drop_percentage: float | None = None
    notification_channel: NotificationChannel | None = None
    notification_destination: str | None = None
    check_interval_minutes: int | None = None
    is_active: bool | None = None


class PriceAlertRule(BaseModel):
    """Stored Price Alert Rule entity."""
    id: str
    user_id: str
    url: str
    title: str
    platform: ECPlatform
    target_price_jpy: int | None
    condition: AlertCondition
    drop_percentage: float | None
    notification_channel: NotificationChannel
    notification_destination: str
    check_interval_minutes: int
    is_active: bool
    last_checked_at: datetime | None = None
    last_price_jpy: int | None = None
    initial_price_jpy: int | None = None
    lowest_price_seen_jpy: int | None = None
    created_at: datetime
    updated_at: datetime


class PriceLogEntry(BaseModel):
    """Historical price log record."""
    id: str
    rule_id: str
    price_jpy: int
    in_stock: bool
    recorded_at: datetime


class AlertNotificationLog(BaseModel):
    """Log record of triggered notification."""
    id: str
    rule_id: str
    user_id: str
    channel: NotificationChannel
    destination: str
    old_price_jpy: int | None
    new_price_jpy: int
    target_price_jpy: int | None
    message: str
    status: str  # "sent" or "failed"
    sent_at: datetime


class Subscription(BaseModel):
    """User subscription status."""
    user_id: str
    tier: SubscriptionTier
    monthly_fee_jpy: int
    max_rules: int
    min_interval_minutes: int
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
