"""CLI interface for AI Agent Subscription API."""

import argparse
import json

from .models import AgentCreate, AgentTier
from .service import AgentAPIService


def main():
    parser = argparse.ArgumentParser(description="AI Agent Subscription API CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_p = subparsers.add_parser("serve", help="Start FastAPI web server")
    serve_p.add_argument("--host", default="0.0.0.0", help="Host address")
    serve_p.add_argument("--port", type=int, default=8001, help="Port (default: 8001)")

    # Register agent command
    register_p = subparsers.add_parser("register", help="Register a new AI agent")
    register_p.add_argument("--name", required=True, help="Agent name")
    register_p.add_argument("--email", required=True, help="Owner email")
    register_p.add_argument("--tier", default="free", choices=["free", "pro", "business"])
    register_p.add_argument("--description", default=None, help="Agent description")

    # List agents command
    list_p = subparsers.add_parser("list", help="List registered agents")
    list_p.add_argument("--status", default=None, choices=["active", "suspended", "expired"])

    # Create API key command
    key_p = subparsers.add_parser("create-key", help="Create a new API key")
    key_p.add_argument("--agent-id", required=True, help="Agent ID")
    key_p.add_argument("--label", default="default", help="Key label")
    key_p.add_argument("--expires-days", type=int, default=None, help="Expiry in days")

    # List API keys command
    keys_p = subparsers.add_parser("list-keys", help="List API keys for an agent")
    keys_p.add_argument("--agent-id", required=True, help="Agent ID")

    # Usage summary command
    usage_p = subparsers.add_parser("usage", help="Get usage summary for an agent")
    usage_p.add_argument("--agent-id", required=True, help="Agent ID")
    usage_p.add_argument("--days", type=int, default=1, help="Days to look back")

    # Check limits command
    limits_p = subparsers.add_parser("limits", help="Check rate limits for an agent")
    limits_p.add_argument("--agent-id", required=True, help="Agent ID")

    args = parser.parse_args()

    service = AgentAPIService()

    if args.command == "serve":
        import uvicorn

        from .api import app
        uvicorn.run(app, host=args.host, port=args.port)

    elif args.command == "register":
        req = AgentCreate(
            name=args.name,
            owner_email=args.email,
            tier=AgentTier(args.tier),
            description=args.description,
        )
        agent = service.register_agent(req)
        print(json.dumps({
            "id": agent.id,
            "name": agent.name,
            "tier": agent.tier.value,
            "status": agent.status.value,
            "created_at": agent.created_at.isoformat(),
        }, ensure_ascii=False, indent=2))

    elif args.command == "list":
        from .models import AgentStatus
        status_filter = AgentStatus(args.status) if args.status else None
        agents = service.list_agents(status=status_filter)
        for a in agents:
            print(f"[{a.id}] {a.name} ({a.tier.value}) - {a.status.value}")

    elif args.command == "create-key":
        from .models import ApiKeyCreate
        req = ApiKeyCreate(
            agent_id=args.agent_id,
            label=args.label,
            expires_days=args.expires_days,
        )
        api_key, raw_key = service.create_api_key(req)
        print("⚠️  Store this key securely - it will not be shown again:")
        print(f"API Key: {raw_key}")
        print(json.dumps({
            "key_id": api_key.id,
            "prefix": api_key.prefix,
            "created_at": api_key.created_at.isoformat(),
        }, ensure_ascii=False, indent=2))

    elif args.command == "list-keys":
        keys = service.list_api_keys(args.agent_id)
        for k in keys:
            status = "active" if k.is_active else "revoked"
            expires = k.expires_at.isoformat() if k.expires_at else "never"
            print(f"[{k.id}] {k.label} ({k.prefix}...) - {status} (expires: {expires})")

    elif args.command == "usage":
        summary = service.get_usage_summary(args.agent_id, days=args.days)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    elif args.command == "limits":
        limits = service.check_rate_limit(args.agent_id)
        print(json.dumps(limits, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
