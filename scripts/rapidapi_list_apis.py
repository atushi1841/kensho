#!/usr/bin/env python3
"""RapidAPI 保有全APIの列挙（id/name/slug/visibility/pricing）。

認証は goo-net-car-scraper/rapidapi_auth.json を再利用。読み取り専用。
"""

import json

import requests

AUTH = "/mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json"
GATEWAY = "https://rapidapi.com/gateway/graphql"


def load_auth():
    with open(AUTH, encoding="utf-8") as f:
        auth = json.load(f)
    cookies = {}
    for part in auth["cookies"].split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    return auth, cookies


def main():
    auth, cookies = load_auth()
    headers = {
        "content-type": "application/json",
        "csrf-token": auth["csrf_token"],
        "origin": "https://rapidapi.com",
        "rapid-client": "provider-dashboard-service",
        "referer": "https://rapidapi.com/_studio/",
        "x-entity-id": auth["entity_id"],
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    }
    q = """query GetApis($where: ApiWhereInput) {
      apis(where: $where) { nodes {
        id name slugifiedName visibility pricing
        currentVersion { id name versionStatus targetGroup { targetUrls { url } } }
      } }
    }"""
    v = {"where": {"ownerId": [auth["entity_id"]]}}
    r = requests.post(GATEWAY, headers=headers, cookies=cookies, json={"query": q, "variables": v}, timeout=30)
    body = r.json()
    if body.get("errors"):
        print("GRAPHQL ERRORS:", json.dumps(body["errors"], ensure_ascii=False))
    apis = (body.get("data") or {}).get("apis", {}).get("nodes", []) or []
    print("COUNT:", len(apis))
    for a in sorted(apis, key=lambda x: (x["name"] or "").lower()):
        cv = a.get("currentVersion") or {}
        print(
            json.dumps(
                {
                    "id": a["id"],
                    "name": a["name"],
                    "slug": a.get("slugifiedName"),
                    "vis": a.get("visibility"),
                    "pricing": a.get("pricing"),
                    "ver": cv.get("name"),
                    "baseUrl": cv.get("targetBaseUrl"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
