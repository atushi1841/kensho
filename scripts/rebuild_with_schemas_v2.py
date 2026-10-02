#!/usr/bin/env python3
"""Rebuild actor version with input/output schemas using ApifyClient"""
import os, json

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

def main():
    token = get_token()
    print(f"Token: {'***' + token[-4:]}")

    from apify_client import ApifyClient
    client = ApifyClient(token)

    # Prepare source files - include ALL files like version 0.2
    source_files = []
    for f in os.listdir(ACTOR_DIR):
        if f == "__pycache__" or f == ".git":
            continue
        filepath = os.path.join(ACTOR_DIR, f)
        if os.path.isfile(filepath):
            try:
                content = open(filepath, "r", encoding="utf-8").read()
            except UnicodeDecodeError:
                import base64
                content = base64.b64encode(open(filepath, "rb").read()).decode("ascii")
            source_files.append({"name": f, "format": "TEXT", "content": content})

    print(f"Prepared {len(source_files)} source files")
    for f in source_files:
        print(f"  - {f['name']}")

    actor_client = client.actor(ACTOR_ID)

    # Update version 0.1 with source files (including input_schema.json and output_schema.json)
    version_client = actor_client.version("0.1")
    version_client.update(
        source_type="SOURCE_FILES",
        source_files=source_files,
        build_tag="latest",
    )
    print("Updated Actor version 0.1 with source files")

    # Build actor
    build_info = actor_client.build(version_number="0.1", wait_for_finish=120)
    print(f"Build status: {build_info.get('status')}")
    build_number = build_info.get("buildNumber")
    print(f"Build number: {build_number}")

    # Now make actor public
    import time
    time.sleep(5)
    
    actor_client.update(
        is_public=True,
        default_run_build=build_number,
    )
    updated = actor_client.get() or {}
    print(f"Actor isPublic: {updated.get('isPublic')}")

if __name__ == "__main__":
    main()