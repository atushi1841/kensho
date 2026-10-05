"""SQLite Database Layer for Japan EC Price Monitoring Micro SaaS."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    AlertCondition,
    AlertNotificationLog,
    ECPlatform,
    NotificationChannel,
    PriceAlertRule,
    PriceAlertRuleCreate,
    PriceAlertRuleUpdate,
    PriceLogEntry,
    Subscription,
    SubscriptionTier,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "price_monitor.db"


class PriceMonitorDB:
    """Synchronous & Async-compatible SQLite DB manager."""

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
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL DEFAULT 'free',
                    monthly_fee_jpy INTEGER NOT NULL DEFAULT 0,
                    max_rules INTEGER NOT NULL DEFAULT 3,
                    min_interval_minutes INTEGER NOT NULL DEFAULT 60,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    expires_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    target_price_jpy INTEGER,
                    condition TEXT NOT NULL,
                    drop_percentage REAL,
                    notification_channel TEXT NOT NULL,
                    notification_destination TEXT NOT NULL,
                    check_interval_minutes INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT,
                    last_price_jpy INTEGER,
                    initial_price_jpy INTEGER,
                    lowest_price_seen_jpy INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES subscriptions (user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS price_logs (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    price_jpy INTEGER NOT NULL,
                    in_stock INTEGER NOT NULL DEFAULT 1,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (rule_id) REFERENCES rules (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notification_logs (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    old_price_jpy INTEGER,
                    new_price_jpy INTEGER NOT NULL,
                    target_price_jpy INTEGER,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    FOREIGN KEY (rule_id) REFERENCES rules (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rules_user ON rules(user_id);
                CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
                CREATE INDEX IF NOT EXISTS idx_price_logs_rule ON price_logs(rule_id);
            """)

    # --- Subscription Management ---
    def get_or_create_subscription(self, user_id: str, tier: SubscriptionTier = SubscriptionTier.FREE) -> Subscription:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_sub(row)

            fee_map = {SubscriptionTier.FREE: 0, SubscriptionTier.PRO: 1980, SubscriptionTier.BUSINESS: 4980}
            limit_map = {SubscriptionTier.FREE: 3, SubscriptionTier.PRO: 30, SubscriptionTier.BUSINESS: 200}
            interval_map = {SubscriptionTier.FREE: 60, SubscriptionTier.PRO: 30, SubscriptionTier.BUSINESS: 15}

            now_str = datetime.utcnow().isoformat()
            sub = Subscription(
                user_id=user_id,
                tier=tier,
                monthly_fee_jpy=fee_map[tier],
                max_rules=limit_map[tier],
                min_interval_minutes=interval_map[tier],
                is_active=True,
                created_at=datetime.fromisoformat(now_str),
            )
            cur.execute(
                """INSERT INTO subscriptions (user_id, tier, monthly_fee_jpy, max_rules, min_interval_minutes, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sub.user_id, sub.tier.value, sub.monthly_fee_jpy, sub.max_rules, sub.min_interval_minutes, 1 if sub.is_active else 0, now_str)
            )
            return sub

    def upgrade_subscription(self, user_id: str, tier: SubscriptionTier) -> Subscription:
        fee_map = {SubscriptionTier.FREE: 0, SubscriptionTier.PRO: 1980, SubscriptionTier.BUSINESS: 4980}
        limit_map = {SubscriptionTier.FREE: 3, SubscriptionTier.PRO: 30, SubscriptionTier.BUSINESS: 200}
        interval_map = {SubscriptionTier.FREE: 60, SubscriptionTier.PRO: 30, SubscriptionTier.BUSINESS: 15}

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE subscriptions
                   SET tier = ?, monthly_fee_jpy = ?, max_rules = ?, min_interval_minutes = ?, is_active = 1
                   WHERE user_id = ?""",
                (tier.value, fee_map[tier], limit_map[tier], interval_map[tier], user_id)
            )
            if cur.rowcount == 0:
                self.get_or_create_subscription(user_id, tier)
        return self.get_or_create_subscription(user_id)

    # --- Rule CRUD ---
    def create_rule(self, req: PriceAlertRuleCreate, platform: ECPlatform, initial_title: str) -> PriceAlertRule:
        sub = self.get_or_create_subscription(req.user_id)
        current_rules = self.list_rules(req.user_id)
        if len(current_rules) >= sub.max_rules:
            raise ValueError(f"Plan limit reached: {sub.tier.value} tier allows max {sub.max_rules} rules. Please upgrade.")

        rule_id = f"rule_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        title = req.title_override or initial_title
        interval = max(req.check_interval_minutes, sub.min_interval_minutes)

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO rules (
                    id, user_id, url, title, platform, target_price_jpy, condition,
                    drop_percentage, notification_channel, notification_destination,
                    check_interval_minutes, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rule_id, req.user_id, req.url, title, platform.value,
                    req.target_price_jpy, req.condition.value, req.drop_percentage,
                    req.notification_channel.value, req.notification_destination,
                    interval, 1 if req.is_active else 0, now.isoformat(), now.isoformat()
                )
            )
        rule = self.get_rule(rule_id)
        assert rule is not None
        return rule

    def get_rule(self, rule_id: str) -> PriceAlertRule | None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cur.fetchone()
            return self._row_to_rule(row) if row else None

    def list_rules(self, user_id: str | None = None, only_active: bool = False) -> list[PriceAlertRule]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM rules WHERE 1=1"
            params: list[Any] = []
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if only_active:
                query += " AND is_active = 1"
            query += " ORDER BY created_at DESC"
            cur.execute(query, params)
            return [self._row_to_rule(r) for r in cur.fetchall()]

    def update_rule(self, rule_id: str, req: PriceAlertRuleUpdate) -> PriceAlertRule | None:
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        fields: list[str] = []
        params: list[Any] = []
        if req.title_override is not None:
            fields.append("title = ?")
            params.append(req.title_override)
        if req.target_price_jpy is not None:
            fields.append("target_price_jpy = ?")
            params.append(req.target_price_jpy)
        if req.condition is not None:
            fields.append("condition = ?")
            params.append(req.condition.value)
        if req.drop_percentage is not None:
            fields.append("drop_percentage = ?")
            params.append(req.drop_percentage)
        if req.notification_channel is not None:
            fields.append("notification_channel = ?")
            params.append(req.notification_channel.value)
        if req.notification_destination is not None:
            fields.append("notification_destination = ?")
            params.append(req.notification_destination)
        if req.check_interval_minutes is not None:
            fields.append("check_interval_minutes = ?")
            params.append(req.check_interval_minutes)
        if req.is_active is not None:
            fields.append("is_active = ?")
            params.append(1 if req.is_active else 0)

        if not fields:
            return rule

        fields.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(rule_id)

        with self._get_conn() as conn:
            conn.execute(f"UPDATE rules SET {', '.join(fields)} WHERE id = ?", params)

        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            return cur.rowcount > 0

    def update_price_check_result(self, rule_id: str, current_price_jpy: int, in_stock: bool) -> None:
        rule = self.get_rule(rule_id)
        if not rule:
            return

        now = datetime.utcnow()
        now_str = now.isoformat()
        initial_price = rule.initial_price_jpy if rule.initial_price_jpy is not None else current_price_jpy
        lowest = min(rule.lowest_price_seen_jpy or current_price_jpy, current_price_jpy)

        with self._get_conn() as conn:
            conn.execute(
                """UPDATE rules
                   SET last_price_jpy = ?, initial_price_jpy = ?, lowest_price_seen_jpy = ?, last_checked_at = ?, updated_at = ?
                   WHERE id = ?""",
                (current_price_jpy, initial_price, lowest, now_str, now_str, rule_id)
            )
            # Record price log
            log_id = f"plog_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO price_logs (id, rule_id, price_jpy, in_stock, recorded_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (log_id, rule_id, current_price_jpy, 1 if in_stock else 0, now_str)
            )

    def add_notification_log(
        self,
        rule_id: str,
        user_id: str,
        channel: NotificationChannel,
        destination: str,
        old_price: int | None,
        new_price: int,
        target_price: int | None,
        message: str,
        status: str = "sent"
    ) -> AlertNotificationLog:
        now = datetime.utcnow()
        log_id = f"nlog_{uuid.uuid4().hex[:12]}"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO notification_logs (
                    id, rule_id, user_id, channel, destination, old_price_jpy,
                    new_price_jpy, target_price_jpy, message, status, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id, rule_id, user_id, channel.value, destination,
                    old_price, new_price, target_price, message, status, now.isoformat()
                )
            )
        return AlertNotificationLog(
            id=log_id,
            rule_id=rule_id,
            user_id=user_id,
            channel=channel,
            destination=destination,
            old_price_jpy=old_price,
            new_price_jpy=new_price,
            target_price_jpy=target_price,
            message=message,
            status=status,
            sent_at=now,
        )

    def get_price_history(self, rule_id: str, limit: int = 50) -> list[PriceLogEntry]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM price_logs WHERE rule_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (rule_id, limit)
            )
            return [
                PriceLogEntry(
                    id=r["id"],
                    rule_id=r["rule_id"],
                    price_jpy=r["price_jpy"],
                    in_stock=bool(r["in_stock"]),
                    recorded_at=datetime.fromisoformat(r["recorded_at"])
                )
                for r in cur.fetchall()
            ]

    def get_notification_logs(self, user_id: str, limit: int = 50) -> list[AlertNotificationLog]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM notification_logs WHERE user_id = ? ORDER BY sent_at DESC LIMIT ?",
                (user_id, limit)
            )
            return [
                AlertNotificationLog(
                    id=r["id"],
                    rule_id=r["rule_id"],
                    user_id=r["user_id"],
                    channel=NotificationChannel(r["channel"]),
                    destination=r["destination"],
                    old_price_jpy=r["old_price_jpy"],
                    new_price_jpy=r["new_price_jpy"],
                    target_price_jpy=r["target_price_jpy"],
                    message=r["message"],
                    status=r["status"],
                    sent_at=datetime.fromisoformat(r["sent_at"])
                )
                for r in cur.fetchall()
            ]

    # --- Helpers ---
    @staticmethod
    def _row_to_sub(row: sqlite3.Row) -> Subscription:
        return Subscription(
            user_id=row["user_id"],
            tier=SubscriptionTier(row["tier"]),
            monthly_fee_jpy=row["monthly_fee_jpy"],
            max_rules=row["max_rules"],
            min_interval_minutes=row["min_interval_minutes"],
            is_active=bool(row["is_active"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"])
        )

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> PriceAlertRule:
        return PriceAlertRule(
            id=row["id"],
            user_id=row["user_id"],
            url=row["url"],
            title=row["title"],
            platform=ECPlatform(row["platform"]),
            target_price_jpy=row["target_price_jpy"],
            condition=AlertCondition(row["condition"]),
            drop_percentage=row["drop_percentage"],
            notification_channel=NotificationChannel(row["notification_channel"]),
            notification_destination=row["notification_destination"],
            check_interval_minutes=row["check_interval_minutes"],
            is_active=bool(row["is_active"]),
            last_checked_at=datetime.fromisoformat(row["last_checked_at"]) if row["last_checked_at"] else None,
            last_price_jpy=row["last_price_jpy"],
            initial_price_jpy=row["initial_price_jpy"],
            lowest_price_seen_jpy=row["lowest_price_seen_jpy"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
