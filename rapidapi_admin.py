#!/usr/bin/env python3
"""RapidAPI Studio GraphQL Admin CLI — fully automated, no GUI needed.

Usage:
  python3 rapidapi_admin.py status <api_id>
  python3 rapidapi_admin.py publish <api_id>
  python3 rapidapi_admin.py unpublish <api_id>
  python3 rapidapi_admin.py plans <api_id>
  python3 rapidapi_admin.py create-plan <api_id> <type> [perusage_price]
  python3 rapidapi_admin.py set-secret <api_id> <name> <value> <placement>
  python3 rapidapi_admin.py subscribe <api_id> <tier>   # FREE_BASIC|PRO
  python3 rapidapi_admin.py gateway-test <slug>
"""

import argparse
import json
import os
import sys

from hermes_tools import terminal

AUTH_FILE = os.path.expanduser("~/.hermes/profiles/kensho-sweeps/rapidapi_auth.json")
GRAPHQL_URL = "https://rapidapi.com/gateway/graphql"


def load_auth():
    with open(AUTH_FILE) as f:
        return json.load(f)


def run_graphql(auth, query, variables=None, operation_name=None):
    """Execute a GraphQL mutation/query against RapidAPI gateway."""
    headers = {
        "content-type": "application/json",
        "x-entity-id": str(auth["entity_id"]),
        "csrf-token": auth["csrf_token"],
        "rapid-client": "provider-dashboard-service",
        "origin": "https://rapidapi.com",
        "referer": "https://rapidapi.com/_studio/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        ),
        "x-api-key": auth.get("x_api_key", ""),
    }
    cookie = auth.get("cookies", "")
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    if operation_name:
        payload["operationName"] = operation_name

    # Use curl for reliability
    curl_cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        GRAPHQL_URL,
        "-H",
        "content-type: application/json",
        "-H",
        f"x-entity-id: {auth['entity_id']}",
        "-H",
        f"csrf-token: {auth['csrf_token']}",
        "-H",
        "rapid-client: provider-dashboard-service",
        "-H",
        "origin: https://rapidapi.com",
        "-H",
        "referer: https://rapidapi.com/_studio/",
        "-H",
        f"user-agent: {headers['user-agent']}",
        "-b",
        cookie,
        "-d",
        json.dumps(payload),
    ]
    result = terminal(" ".join(curl_cmd), timeout=30)
    return json.loads(result["output"]) if result["exit_code"] == 0 else None


def cmd_status(api_id, auth):
    query = """query GetApi($where: ApiWhereInput!) {
        apis(where: $where) { nodes { id name visibility slugifiedName
            currentVersion { id name versionStatus }
            pricing { currency pricePerRequest planType }
        }}
    }"""
    result = run_graphql(auth, query, {"where": {"id": [api_id], "ownerId": [auth["entity_id"]]}})
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_unpublish(api_id, auth):
    mutation = """mutation UpdateApi($api: ApiUpdateInput!) {
        updateApi(api: $api) { id name visibility }
    }"""
    result = run_graphql(auth, mutation, {"api": {"id": api_id, "visibility": "PRIVATE"}})
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_publish(api_id, auth):
    mutation = """mutation UpdateApi($api: ApiUpdateInput!) {
        updateApi(api: $api) { id name visibility }
    }"""
    result = run_graphql(auth, mutation, {"api": {"id": api_id, "visibility": "PUBLIC"}})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_plans(api_id, auth):
    query = """query GetBillingPlans($where: BillingPlanVersionWhereInput!) {
        billingPlanVersions(where: $where) { nodes { id name type status
            limits { amount period } pricing { perusagePrice currency } } }
    }"""
    result = run_graphql(auth, query, {"where": {"apiId": api_id}})
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_create_plan(api_id, plan_type, perusage_price, auth):
    mutation = """mutation CreateBillingPlan($input: CreateBillingPlanInput!) {
        createBillingPlan(input: $input) { billingPlan { id name } }
    }"""
    # Get api slug first（将来のStudio URL生成用、現状はapiIdのみで送信可）
    status = run_graphql(
        auth,
        """query GetApi($where: ApiWhereInput!) {
        apis(where: $where) { nodes { id name slugifiedName } }}""",
        {"where": {"id": [api_id], "ownerId": [auth["entity_id"]]}},
    )
    if not (status and status.get("data")):
        print("WARN: API照会失敗、plan作成は続行", file=sys.stderr)

    perusage = float(perusage_price)
    variables = {
        "input": {
            "apiId": api_id,
            "name": "PRO",
            "type": plan_type,
            "billingLimits": [
                {
                    "amount": 100000,
                    "item": "billingitem_requests",
                    "limitType": "soft",
                    "overagePrice": 0.01,
                    "period": "MONTHLY",
                    "perusagePrice": perusage,
                    "unlimited": False,
                }
            ],
            "isStudent": False,
            "isPrivatePlan": False,
            "legalAccountId": "",
            "legalDocumentId": "",
            "targetGroup": "",
            "enableBillingFeatures": [],
            "currency": None,
            "rateLimit": None,
        }
    }
    result = run_graphql(auth, mutation, variables)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_set_secret(api_id, secret_name, secret_value, placement, auth):
    mutation = """mutation UpdateApiVersions($input: UpdateApiVersionsInput!) {
        updateApiVersions(input: $input) { apiVersion { id name } }
    }"""
    variables = {
        "input": {
            "apiId": api_id,
            "apiVersionId": "",  # will be filled from current version
            "accessControl": {
                "secretParameters": [{"name": secret_name, "value": secret_value, "placement": placement}]
            },
        }
    }
    result = run_graphql(auth, mutation, variables)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_subscribe(api_id, tier, auth):
    """Subscribe to an API tier (FREE_BASIC or PRO) using the RapidAPI subscribe flow."""
    print(f"Subscribing to {api_id} tier={tier}...")
    # This requires the CDP flow for the FREE_BASIC subscription
    # For now, we'll use the GraphQL approach
    mutation = """mutation SubscribeApi($input: SubscribeInput!) {
        subscribe(input: $input) { subscription { id status } }
    }"""
    variables = {"input": {"apiId": api_id, "billingPlanId": tier}}
    result = run_graphql(auth, mutation, variables)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_gateway_test(slug, auth):
    """Test the gateway endpoint with X-RapidAPI-Key."""
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    if not api_key:
        print("ERROR: Set RAPIDAPI_KEY env var")
        return

    host = f"{slug}.p.rapidapi.com"
    urls = [f"https://{host}/", f"https://{slug}1.p.rapidapi.com/"]
    for url in urls:
        curl_cmd = (
            f'curl -s -o /dev/null -w "%{{http_code}}" -H "X-RapidAPI-Key: ***" -H "X-RapidAPI-Host: {host}" "{url}"'
        )
        result = terminal(curl_cmd, timeout=15)
        print(f"{url} -> {result['output'].strip()}")


def main():
    parser = argparse.ArgumentParser(description="RapidAPI Studio GraphQL Admin")
    parser.add_argument(
        "command",
        choices=["status", "publish", "unpublish", "plans", "create-plan", "set-secret", "subscribe", "gateway-test"],
    )
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()

    auth = load_auth()

    if args.command == "status":
        cmd_status(args.args[0], auth)
    elif args.command == "publish":
        cmd_publish(args.args[0], auth)
    elif args.command == "unpublish":
        cmd_unpublish(args.args[0], auth)
    elif args.command == "plans":
        cmd_plans(args.args[0], auth)
    elif args.command == "create-plan":
        cmd_create_plan(args.args[0], args.args[1], args.args[2] if len(args.args) > 2 else "0.02", auth)
    elif args.command == "set-secret":
        cmd_set_secret(args.args[0], args.args[1], args.args[2], args.args[3], auth)
    elif args.command == "subscribe":
        cmd_subscribe(args.args[0], args.args[1], auth)
    elif args.command == "gateway-test":
        cmd_gateway_test(args.args[0], auth)


if __name__ == "__main__":
    main()
