"""Service layer: Rule evaluation, pricing checks, alert orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .db import PriceMonitorDB
from .models import (
    AlertCondition,
    ECPlatform,
    PriceAlertRule,
    PriceAlertRuleCreate,
    PriceAlertRuleUpdate,
    PriceItem,
    SubscriptionTier,
)
from .notifier import PriceNotifier
from .scraper import ECPriceScraper, detect_platform

logger = logging.getLogger(__name__)


class PriceMonitorService:
    """Core domain logic for price monitoring and alerting."""

    def __init__(self, db: PriceMonitorDB | None = None, scraper: ECPriceScraper | None = None, notifier: PriceNotifier | None = None):
        self.db = db or PriceMonitorDB()
        self.scraper = scraper or ECPriceScraper()
        self.notifier = notifier or PriceNotifier()

    # --- Rule Management ---
    def create_rule(self, req: PriceAlertRuleCreate) -> PriceAlertRule:
        platform = detect_platform(req.url)
        # Verify product reachable and get initial title if needed
        initial_title = "Monitored Item"
        initial_price: int | None = None
        in_stock: bool = True

        try:
            item = self.scraper.fetch_product_info(req.url)
            initial_title = item.title
            initial_price = item.price_jpy
            in_stock = item.in_stock
        except Exception as e:
            logger.warning(f"Could not immediately fetch product info for {req.url}: {e}")

        rule = self.db.create_rule(req, platform=platform, initial_title=initial_title)

        if initial_price is not None:
            self.db.update_price_check_result(rule.id, initial_price, in_stock)
            updated_rule = self.db.get_rule(rule.id)
            if updated_rule:
                rule = updated_rule

        return rule

    def evaluate_condition(self, rule: PriceAlertRule, current_price_jpy: int, in_stock: bool) -> bool:
        """Determine whether the alert condition is satisfied."""
        if not in_stock and rule.condition != AlertCondition.IN_STOCK:
            return False

        if rule.condition == AlertCondition.LESS_THAN_OR_EQUAL:
            if rule.target_price_jpy is not None:
                return current_price_jpy <= rule.target_price_jpy
            return False

        elif rule.condition == AlertCondition.ANY_DROP:
            baseline = rule.last_price_jpy or rule.initial_price_jpy
            if baseline is not None:
                return current_price_jpy < baseline
            return False

        elif rule.condition == AlertCondition.PERCENT_DROP:
            baseline = rule.last_price_jpy or rule.initial_price_jpy
            if baseline is not None and baseline > 0 and rule.drop_percentage:
                pct = ((baseline - current_price_jpy) / baseline) * 100.0
                return pct >= rule.drop_percentage
            return False

        elif rule.condition == AlertCondition.IN_STOCK:
            return in_stock

        return False

    def check_single_rule(self, rule_id: str, force: bool = False) -> dict[str, Any]:
        """Check a single rule now, evaluate condition, record price, send notification if triggered."""
        rule = self.db.get_rule(rule_id)
        if not rule:
            raise ValueError(f"Rule {rule_id} not found")

        if not rule.is_active and not force:
            return {"rule_id": rule_id, "skipped": "inactive"}

        # Scrape current price
        item = self.scraper.fetch_product_info(rule.url)

        old_price = rule.last_price_jpy
        triggered = self.evaluate_condition(rule, item.price_jpy, item.in_stock)

        # Update DB state
        self.db.update_price_check_result(rule.id, item.price_jpy, item.in_stock)

        notification_result = None
        if triggered:
            # Dispatch alert
            ok, status = self.notifier.dispatch(rule, item)
            msg = self.notifier.build_alert_message(rule, item)
            log_entry = self.db.add_notification_log(
                rule_id=rule.id,
                user_id=rule.user_id,
                channel=rule.notification_channel,
                destination=rule.notification_destination,
                old_price=old_price,
                new_price=item.price_jpy,
                target_price=rule.target_price_jpy,
                message=msg,
                status=status,
            )
            notification_result = {"status": status, "sent": ok, "log_id": log_entry.id}

        return {
            "rule_id": rule_id,
            "url": rule.url,
            "title": rule.title,
            "current_price_jpy": item.price_jpy,
            "previous_price_jpy": old_price,
            "in_stock": item.in_stock,
            "triggered": triggered,
            "notification": notification_result,
            "checked_at": datetime.utcnow().isoformat(),
        }

    def run_due_checks(self) -> list[dict[str, Any]]:
        """Run checks for all active rules whose interval has elapsed."""
        active_rules = self.db.list_rules(only_active=True)
        now = datetime.utcnow()
        results: list[dict[str, Any]] = []

        for rule in active_rules:
            is_due = False
            if rule.last_checked_at is None:
                is_due = True
            else:
                elapsed = (now - rule.last_checked_at).total_seconds() / 60.0
                if elapsed >= rule.check_interval_minutes:
                    is_due = True

            if is_due:
                try:
                    res = self.check_single_rule(rule.id)
                    results.append(res)
                except Exception as e:
                    logger.error(f"Error checking rule {rule.id}: {e}")
                    results.append({"rule_id": rule.id, "error": str(e)})

        return results
