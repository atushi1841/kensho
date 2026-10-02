#!/usr/bin/env python3
"""Deploy Japan Anime Figure Price Data actor to Apify."""
import os
import sys
import json
import zipfile
from pathlib import Path

REPO_ROOT = Path("/mnt/d/Project2/kensho")
ACTOR_DIR = REPO_ROOT / "apify-figure-price"

def check_token() -> str:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("APIFY_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"')
                        break
    if not token:
        raise RuntimeError("APIFY_TOKEN not set. Export it or add to .env")
    return token

def deploy_actor(token: str, actor_name: str = "japan-anime-figure-price-data") -> dict:
    # Create zip of actor directory
    zip_path = REPO_ROOT / f"{actor_name}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in ACTOR_DIR.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                arcname = file.relative_to(ACTOR_DIR)
                zf.write(file, arcname)
    print(f"Created actor zip: {zip_path} ({zip_path.stat().st_size} bytes)")

    # Build the create payload with ONLY accepted fields
    create_payload = {
        "name": actor_name,
        "description": "Japan Anime Figure Price Data — secondary market prices for 650+ figures (MyFigureList). Pay-per-event via Apify PPE.",
    }

    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)

        # Try to get existing actor by name
        existing = client.actor(actor_name)._get()
        if existing:
            actor_id = existing["id"]
            print(f"Actor exists: {actor_id}")
        else:
            print("Actor does not exist, creating...")
            actor = client.actors()._create(resource=create_payload)
            actor_id = actor["id"]
            print(f"Created new actor: {actor_id}")

        # Build and deploy - send source files
        source_files = []
        for f in ACTOR_DIR.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts:
                source_files.append({"name": str(f.relative_to(ACTOR_DIR)), "content": f.read_bytes()})

        build = client.actor(actor_id).builds()._create({
            "resource": {
                "sourceFiles": source_files,
                "tag": "latest",
                "waitForFinish": 120,
            }
        })

        print(f"Build status: {build.get('status')}")
        return {"actor_id": actor_id, "build": build}

    except Exception as e:
        print(f"Deploy error: {e}")
        raise

def main():
    token = check_token()
    result = deploy_actor(token)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()