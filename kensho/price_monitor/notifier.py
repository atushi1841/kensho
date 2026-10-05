"""Notification dispatcher for Japan EC Price Monitoring Micro SaaS."""

from __future__ import annotations

import json
import logging
from typing import Any
import httpx

from .models import NotificationChannel, PriceAlertRule, PriceItem
from ..utils.notify import send_telegram

logger = logging.getLogger(__name__)


class PriceNotifier:
    """Dispatches price drop alerts to user destinations."""

    @staticmethod
    def build_alert_message(rule: PriceAlertRule, current_item: PriceItem) -> str:
        """Format human-readable alert message in Japanese."""
        old_price = rule.last_price_jpy or rule.initial_price_jpy
        diff_yen = (old_price - current_item.price_jpy) if old_price else 0
        diff_pct = (diff_yen / old_price * 100) if (old_price and old_price > 0) else 0

        lines = [
            f"🔔 <b>【価格監視アラート】値下がりを検知しました！</b>",
            f"📦 <b>商品名:</b> {rule.title}",
            f"🏷️ <b>プラットフォーム:</b> {rule.platform.value.upper()}",
            f"💰 <b>現在価格:</b> ¥{current_item.price_jpy:,}",
        ]
        if old_price and diff_yen > 0:
            lines.append(f"📉 <b>変動:</b> -¥{diff_yen:,} ({diff_pct:.1f}% OFF)")
        if rule.target_price_jpy:
            lines.append(f"🎯 <b>目標価格:</b> ¥{rule.target_price_jpy:,} 以下達成")

        lines.extend([
            f"🔗 <b>商品リンク:</b> {rule.url}",
            f"⏰ <b>検知日時:</b> {current_item.scraped_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ])
        return "\n".join(lines)

    def dispatch(
        self,
        rule: PriceAlertRule,
        current_item: PriceItem,
        custom_message: str | None = None
    ) -> tuple[bool, str]:
        """Dispatch notification to specified channel. Returns (success, status_or_error)."""
        msg = custom_message or self.build_alert_message(rule, current_item)
        channel = rule.notification_channel
        destination = rule.notification_destination

        try:
            if channel == NotificationChannel.TELEGRAM:
                # Use destination as chat_id
                ok = send_telegram(msg, chat_id=destination)
                return ok, "sent" if ok else "failed_telegram_api"

            elif channel == NotificationChannel.WEBHOOK:
                payload = {
                    "event": "price_drop_alert",
                    "rule_id": rule.id,
                    "user_id": rule.user_id,
                    "url": rule.url,
                    "title": rule.title,
                    "platform": rule.platform.value,
                    "current_price_jpy": current_item.price_jpy,
                    "previous_price_jpy": rule.last_price_jpy,
                    "target_price_jpy": rule.target_price_jpy,
                    "in_stock": current_item.in_stock,
                    "timestamp": current_item.scraped_at.isoformat(),
                }
                resp = httpx.post(destination, json=payload, timeout=10.0)
                if resp.status_code < 400:
                    return True, "sent"
                return False, f"webhook_status_{resp.status_code}"

            elif channel == NotificationChannel.EMAIL:
                # Simulated SMTP / log email delivery
                logger.info(f"[EMAIL ALERT] To: {destination}\nSubject: [Price Alert] {rule.title}\n{msg}")
                return True, "sent"

            elif channel == NotificationChannel.LOG:
                logger.info(f"[LOG ALERT] {rule.id}: {msg}")
                return True, "sent"

        except Exception as e:
            logger.error(f"Error dispatching notification for rule {rule.id}: {e}")
            return False, str(e)

        return False, "unknown_channel"
