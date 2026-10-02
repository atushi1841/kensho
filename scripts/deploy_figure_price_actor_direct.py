#!/usr/bin/env python3
"""Deploy japan-anime-figure-price-data actor to Apify with input/output schemas."""
import os, json, urllib.request, urllib.error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTOR_DIR = os.path.join(REPO_ROOT, "apify-figure-price")
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

    # Load actor spec
    with open(os.path.join(ACTOR_DIR, "actor.json")) as f:
        spec = json.load(f)
    input_schema = spec.get("input")
    output_schema = spec.get("output")

    # 1. Get current actor state
    actor = api_request(token, "GET", f"/acts/{ACTOR_ID}")
    print(f"Actor name: {actor.get('name')}, isPublic: {actor.get('isPublic')}")

    # 2. Update actor with input/output schemas and make public
    update_body = {
        "isPublic": True,
        "defaultRunBuild": actor.get("defaultRunBuild"),
        "input": input_schema,
        "output": output_schema,
    }
    updated = api_request(token, "PUT", f"/acts/{ACTOR_ID}", update_body)
    print(f"Updated actor: isPublic={updated.get('isPublic')}, input={'set' if updated.get('input') else 'null'}")

    # 3. Verify
    verified = api_request(token, "GET", f"/acts/{ACTOR_ID}")
    print(f"Verified: isPublic={verified.get('isPublic')}")
    inp = verified.get("input")
    out = verified.get("output")
    print(f"Input schema: {'SET' if inp else 'null'}")
    print(f"Output schema: {'SET' if out else 'null'}")

    result = {
        "actor_id": ACTOR_ID,
        "isPublic": verified.get("isPublic"),
        "input_schema_set": bool(inp),
        "output_schema_set": bool(out),
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()