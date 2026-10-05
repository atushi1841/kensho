"""Unit tests for Japan EC Price Monitoring Micro SaaS."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from kensho.price_monitor.models import (
    AlertCondition,
    ECPlatform,
    NotificationChannel,
    PriceAlertRuleCreate,
    PriceAlertRuleUpdate,
    PriceItem,
    SubscriptionTier,
)
from kensho.price_monitor.db import PriceMonitorDB
from kensho.price_monitor.scraper import ECPriceScraper, detect_platform, clean_price
from kensho.price_monitor.notifier import PriceNotifier
from kensho.price_monitor.service import PriceMonitorService
from kensho.price_monitor.api import app
import kensho.price_monitor.api as api_module


@pytest.fixture
def temp_db(tmp_path: Path) -> PriceMonitorDB:
    db_file = tmp_path / "test_pm.db"
    return PriceMonitorDB(db_path=db_file)


@pytest.fixture
def mock_scraper() -> ECPriceScraper:
    class MockECPriceScraper(ECPriceScraper):
        def __init__(self):
            super().__init__()
            self.call_count = 0
            self.next_price = 5000
            self.next_stock = True

        def fetch_product_info(self, url: str) -> PriceItem:
            self.call_count += 1
            platform = detect_platform(url)
            return PriceItem(
                url=url,
                title="Mock Test Figure / Item",
                price_jpy=self.next_price,
                platform=platform,
                in_stock=self.next_stock,
                scraped_at=datetime.utcnow(),
            )

    return MockECPriceScraper()


class DummyNotifier(PriceNotifier):
    def __init__(self):
        self.dispatched = []

    def dispatch(self, rule, current_item, custom_message=None):
        self.dispatched.append((rule.id, current_item.price_jpy))
        return True, "sent"


def test_platform_detection():
    assert detect_platform("https://shopping.yahoo.co.jp/product/123") == ECPlatform.YAHOO_SHOPPING
    assert detect_platform("https://item.rakuten.co.jp/shop/item456/") == ECPlatform.RAKUTEN
    assert detect_platform("https://jp.mercari.com/item/m12345678") == ECPlatform.MERCARI
    assert detect_platform("https://www.suruga-ya.jp/product/detail/123") == ECPlatform.SURUGAYA
    assert detect_platform("https://example.com/item") == ECPlatform.GENERIC


def test_clean_price():
    assert clean_price(1500) == 1500
    assert clean_price("¥1,980") == 1980
    assert clean_price("3,500円（税込）") == 3500
    assert clean_price("￥ 12,000") == 12000
    assert clean_price("invalid") is None
    assert clean_price(None) is None


def test_db_subscription_and_rules_crud(temp_db: PriceMonitorDB):
    # Subscription creation
    sub = temp_db.get_or_create_subscription("user_a")
    assert sub.user_id == "user_a"
    assert sub.tier == SubscriptionTier.FREE
    assert sub.max_rules == 3

    # Create rule
    req = PriceAlertRuleCreate(
        user_id="user_a",
        url="https://shopping.yahoo.co.jp/item/123",
        target_price_jpy=4000,
        condition=AlertCondition.LESS_THAN_OR_EQUAL,
        notification_channel=NotificationChannel.TELEGRAM,
        notification_destination="12345",
        check_interval_minutes=60,
    )
    rule = temp_db.create_rule(req, ECPlatform.YAHOO_SHOPPING, "Yahoo Product")
    assert rule.id.startswith("rule_")
    assert rule.title == "Yahoo Product"
    assert rule.platform == ECPlatform.YAHOO_SHOPPING

    # List rules
    rules = temp_db.list_rules(user_id="user_a")
    assert len(rules) == 1
    assert rules[0].id == rule.id

    # Update rule
    upd = PriceAlertRuleUpdate(target_price_jpy=3500, is_active=False)
    updated = temp_db.update_rule(rule.id, upd)
    assert updated.target_price_jpy == 3500
    assert not updated.is_active

    # Plan limit enforcement
    with pytest.raises(ValueError, match="Plan limit reached"):
        for i in range(5):
            r = PriceAlertRuleCreate(
                user_id="user_a",
                url=f"https://shopping.yahoo.co.jp/item/{i}",
                notification_channel=NotificationChannel.TELEGRAM,
                notification_destination="12345",
            )
            temp_db.create_rule(r, ECPlatform.YAHOO_SHOPPING, f"Item {i}")

    # Upgrade subscription
    upgraded = temp_db.upgrade_subscription("user_a", SubscriptionTier.PRO)
    assert upgraded.tier == SubscriptionTier.PRO
    assert upgraded.max_rules == 30

    # Delete rule
    assert temp_db.delete_rule(rule.id)
    assert temp_db.get_rule(rule.id) is None


def test_service_alert_condition_evaluation(temp_db: PriceMonitorDB, mock_scraper: ECPriceScraper):
    notifier = DummyNotifier()
    service = PriceMonitorService(db=temp_db, scraper=mock_scraper, notifier=notifier)

    # 1. Target price LTE condition
    req_lte = PriceAlertRuleCreate(
        user_id="user_b",
        url="https://item.rakuten.co.jp/shop/item1/",
        target_price_jpy=4000,
        condition=AlertCondition.LESS_THAN_OR_EQUAL,
        notification_channel=NotificationChannel.TELEGRAM,
        notification_destination="chat_b",
    )
    mock_scraper.next_price = 5000
    rule = service.create_rule(req_lte)
    assert rule.last_price_jpy == 5000

    # Price stays high -> not triggered
    res1 = service.check_single_rule(rule.id)
    assert not res1["triggered"]
    assert len(notifier.dispatched) == 0

    # Price drops to 3800 -> triggered
    mock_scraper.next_price = 3800
    res2 = service.check_single_rule(rule.id)
    assert res2["triggered"]
    assert len(notifier.dispatched) == 1
    assert notifier.dispatched[0] == (rule.id, 3800)

    # 2. Percent drop condition
    req_pct = PriceAlertRuleCreate(
        user_id="user_b",
        url="https://jp.mercari.com/item/m999",
        condition=AlertCondition.PERCENT_DROP,
        drop_percentage=20.0,
        notification_channel=NotificationChannel.TELEGRAM,
        notification_destination="chat_b",
    )
    mock_scraper.next_price = 10000
    rule_pct = service.create_rule(req_pct)

    # Price drops 10% (10000 -> 9000) -> not triggered
    mock_scraper.next_price = 9000
    res3 = service.check_single_rule(rule_pct.id)
    assert not res3["triggered"]

    # Price drops 25% (9000 -> 7000 from baseline 9000, diff 22.2%) -> triggered
    mock_scraper.next_price = 7000
    res4 = service.check_single_rule(rule_pct.id)
    assert res4["triggered"]


def test_fastapi_endpoints(temp_db: PriceMonitorDB, mock_scraper: ECPriceScraper):
    # Bind test service
    notifier = DummyNotifier()
    test_service = PriceMonitorService(db=temp_db, scraper=mock_scraper, notifier=notifier)
    api_module.service = test_service

    client = TestClient(app)

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Plans
    res = client.get("/api/v1/plans")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) == 3
    assert plans[1]["name"] == "Pro Plan"
    assert plans[1]["monthly_fee_jpy"] == 1980

    # User subscription
    res = client.get("/api/v1/users/user_c/subscription")
    assert res.status_code == 200
    assert res.json()["tier"] == "free"

    # Create rule via API
    rule_payload = {
        "user_id": "user_c",
        "url": "https://item.rakuten.co.jp/test/prod123",
        "title_override": "Test Figure API",
        "target_price_jpy": 3000,
        "condition": "lte",
        "notification_channel": "telegram",
        "notification_destination": "12345678",
        "check_interval_minutes": 30,
    }
    mock_scraper.next_price = 4500
    res = client.post("/api/v1/rules", json=rule_payload)
    assert res.status_code == 201
    created = res.json()
    rule_id = created["id"]
    assert created["title"] == "Test Figure API"
    assert created["platform"] == "rakuten"

    # List rules
    res = client.get("/api/v1/rules?user_id=user_c")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Trigger rule check via API
    mock_scraper.next_price = 2800  # Below 3000 -> trigger
    res = client.post(f"/api/v1/rules/{rule_id}/check")
    assert res.status_code == 200
    data = res.json()
    assert data["triggered"] is True
    assert data["current_price_jpy"] == 2800

    # History API
    res = client.get(f"/api/v1/rules/{rule_id}/history")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Notifications API
    res = client.get("/api/v1/users/user_c/notifications")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Subscription upgrade API
    res = client.post("/api/v1/users/subscribe", json={"user_id": "user_c", "tier": "business"})
    assert res.status_code == 200
    assert res.json()["tier"] == "business"
    assert res.json()["max_rules"] == 200
