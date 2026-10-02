#!/usr/bin/env python3
"""Check actor API response"""
import os, json, urllib.request, urllib.error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTOR_ID = "DKzufUSvmuXNKHeYx"

def get_token():
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if not token:
        with open(os.path.join(REPO_ROOT, ".env")) as f:
            for line in f:
                if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                    token = line.split("=", 1)[1].strip().strip('"')
                    break
    return token

def api_request(token, method, path, body=None):
    url = f"https://api.apify.com/v2{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read().decode()}")
        raise

def main():
    token = get_token()
    print(f"Token: {'***' + token[-4:]}")

    # Get current actor state
    actor = api_request(token, "GET", f"/acts/{ACTOR_ID}")
    print("Full actor response:")
    print(json.dumps(actor, indent=2))

if __name__ == "__main__":
    main()