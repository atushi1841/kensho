"""CLI interface for Japan EC Price Monitoring Micro SaaS."""

import argparse
import json
import sys
from pathlib import Path

from .db import PriceMonitorDB
from .models import (
    AlertCondition,
    NotificationChannel,
    PriceAlertRuleCreate,
    SubscriptionTier,
)
from .service import PriceMonitorService
from .worker import PriceMonitorWorker


def main():
    parser = argparse.ArgumentParser(description="Japan EC Price Monitor Micro SaaS CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_p = subparsers.add_parser("serve", help="Start FastAPI web server")
    serve_p.add_argument("--host", default="0.0.0.0", help="Host address")
    serve_p.add_argument("--port", type=int, default=8000, help="Port")

    # Worker command
    worker_p = subparsers.add_parser("worker", help="Start background worker")
    worker_p.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")

    # Add rule command
    add_p = subparsers.add_parser("add-rule", help="Add a new monitoring rule")
    add_p.add_argument("--user-id", required=True, help="User ID")
    add_p.add_argument("--url", required=True, help="Product URL")
    add_p.add_argument("--target-price", type=int, help="Target price in JPY")
    add_p.add_argument("--channel", default="telegram", choices=["telegram", "webhook", "email", "log"])
    add_p.add_argument("--destination", required=True, help="Chat ID or Webhook URL")
    add_p.add_argument("--interval-min", type=int, default=60, help="Check interval in minutes")

    # List rules command
    list_p = subparsers.add_parser("list-rules", help="List monitoring rules")
    list_p.add_argument("--user-id", help="Filter by User ID")

    # Check rule command
    check_p = subparsers.add_parser("check", help="Check a specific rule or run due checks")
    check_p.add_argument("--rule-id", help="Specific Rule ID (omit to run due checks)")

    # Subscription command
    sub_p = subparsers.add_parser("subscribe", help="Upgrade user subscription")
    sub_p.add_argument("--user-id", required=True, help="User ID")
    sub_p.add_argument("--tier", required=True, choices=["free", "pro", "business"], help="Tier")

    args = parser.parse_args()

    service = PriceMonitorService()

    if args.command == "serve":
        import uvicorn
        from .api import app
        uvicorn.run(app, host=args.host, port=args.port)

    elif args.command == "worker":
        worker = PriceMonitorWorker(service=service, loop_interval_sec=args.interval)
        worker.start_loop()

    elif args.command == "add-rule":
        req = PriceAlertRuleCreate(
            user_id=args.user_id,
            url=args.url,
            target_price_jpy=args.target_price,
            condition=AlertCondition.LESS_THAN_OR_EQUAL if args.target_price else AlertCondition.ANY_DROP,
            notification_channel=NotificationChannel(args.channel),
            notification_destination=args.destination,
            check_interval_minutes=args.interval_min,
        )
        rule = service.create_rule(req)
        print(f"Created rule: {rule.id} ({rule.title}) - Current: ¥{rule.last_price_jpy}")

    elif args.command == "list-rules":
        rules = service.db.list_rules(user_id=args.user_id)
        for r in rules:
            print(f"[{r.id}] {r.title} | {r.platform.value} | Last: ¥{r.last_price_jpy} | Target: ¥{r.target_price_jpy} | Active: {r.is_active}")

    elif args.command == "check":
        if args.rule_id:
            res = service.check_single_rule(args.rule_id, force=True)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            res = service.run_due_checks()
            print(f"Ran due checks for {len(res)} rules.")

    elif args.command == "subscribe":
        sub = service.db.upgrade_subscription(args.user_id, SubscriptionTier(args.tier))
        print(f"User {sub.user_id} upgraded to {sub.tier.value} (Max rules: {sub.max_rules}, Min interval: {sub.min_interval_minutes}m)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
