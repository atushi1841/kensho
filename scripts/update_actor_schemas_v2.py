#!/usr/bin/env python3
"""Update actor version with schemas"""
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

    # Get current actor state
    actor = api_request(token, "GET", f"/acts/{ACTOR_ID}")
    data = actor.get("data", actor)
    print(f"Actor name: {data.get('name')}, isPublic: {data.get('isPublic')}")

    # First, update version 0.1 with input/output schemas
    version_update = {
        "versionNumber": "0.1",
        "input": input_schema,
        "output": output_schema,
    }
    updated_version = api_request(token, "PUT", f"/acts/{ACTOR_ID}/versions/0.1", version_update)
    print(f"Updated version: {json.dumps(updated_version, indent=2)}")

    # Now make actor public
    actor_update = {
        "isPublic": True,
        "defaultRunBuild": "0.1.72",
    }
    updated = api_request(token, "PUT", f"/acts/{ACTOR_ID}", actor_update)
    updated_data = updated.get("data", updated)
    print(f"Updated actor: isPublic={updated_data.get('isPublic')}")

    # Verify
    verified = api_request(token, "GET", f"/acts/{ACTOR_ID}")
    verified_data = verified.get("data", verified)
    print(f"Verified: isPublic={verified_data.get('isPublic')}")
    inp = verified_data.get("input")
    out = verified_data.get("output")
    print(f"Actor Input schema: {'SET' if inp else 'null'}")
    print(f"Actor Output schema: {'SET' if out else 'null'}")

    # Also verify version
    versions = verified_data.get("versions", [])
    for v in versions:
        print(f"Version {v.get('versionNumber')}: input={'SET' if v.get('input') else 'null'}, output={'SET' if v.get('output') else 'null'}")

    result = {
        "actor_id": ACTOR_ID,
        "isPublic": verified_data.get("isPublic"),
        "actor_input_schema_set": bool(inp),
        "actor_output_schema_set": bool(out),
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()