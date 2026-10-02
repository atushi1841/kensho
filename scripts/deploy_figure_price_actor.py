#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTOR_DIR = REPO_ROOT / "apify-figure-price"

def check_token() -> str:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        token = os.environ.get("APIFY_TOKEN_DEFAULT")
    if not token:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                        token = line.split("=", 1)[1].strip().strip('"')
                        break
    if not token:
        raise RuntimeError("APIFY_TOKEN not set. Export it or add to .env")
    return token

def deploy_actor(token: str, actor_name: str = "japan-anime-figure-price-data") -> dict:
    from apify_client import ApifyClient
    import json
    client = ApifyClient(token)

    # Prepare source files
    # Apify's build embeds input/output schemas into actorDefinition ONLY when
    # the source files include .actor/actor.json (with inputSchema/outputSchema)
    # and .actor/input_schema.json / .actor/output_schema.json.
    # Root actor.json conflicts and causes "no output schema" — MUST EXCLUDE.
    # .actor/actor.json IS REQUIRED for schema embedding — MUST INCLUDE.
    # Only include essential source files to avoid size limits
    ESSENTIAL_FILES = {
        ".actor/actor.json",
        ".actor/input_schema.json",
        ".actor/output_schema.json",
        "main.py",
        "Dockerfile",
        "requirements.txt",
        "README.md",
    }
    # Data files (must include for actor to run)
    DATA_FILES = {
        "data/anime_figure_prices_normalized.jsonl",
        "data/anime_figure_prices_normalized.csv",
    }
    source_files = []
    for f in ACTOR_DIR.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts and '.git' not in f.parts:
            rel_path = str(f.relative_to(ACTOR_DIR))
            # Only include essential files and data files
            if rel_path not in ESSENTIAL_FILES and rel_path not in DATA_FILES:
                continue
            # Must include: .actor/actor.json (REQUIRED for schema embedding), 
            # .actor/input_schema.json, .actor/output_schema.json
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                import base64
                content = base64.b64encode(f.read_bytes()).decode("ascii")
            source_files.append({"name": rel_path, "format": "TEXT", "content": content})

    print(f"Prepared {len(source_files)} source files for Actor deploy")

    # Load input/output schemas from .actor directory (root files are wrong format)
    with open(ACTOR_DIR / ".actor" / "input_schema.json", "r", encoding="utf-8") as f:
        input_schema = json.load(f)
    with open(ACTOR_DIR / ".actor" / "output_schema.json", "r", encoding="utf-8") as f:
        output_schema = json.load(f)

    # Get or create actor
    actor_id = None
    actors_page = client.actors().list(my=True, limit=100)
    for a in actors_page.items:
        if a.get("name") == actor_name:
            actor_id = a["id"]
            print(f"Found existing actor: {actor_id}")
            break
    if not actor_id:
        print(f"Creating new actor: {actor_name}")
        created = client.actors().create(
            name=actor_name,
            title="Japan Anime Figure Price Intelligence API",
            input=input_schema,
            output=output_schema,
        )
        actor_id = created["id"]
        print(f"Created new actor: {actor_id}")
    actor_client = client.actor(actor_id)

    # Build actor with new source files (update existing version 0.1)
    print("Updating Actor version 0.1 with source files")
    version_client = actor_client.version("0.1")
    version_client.update(
        source_type="SOURCE_FILES",
        source_files=source_files,
        build_tag="latest",
    )
    print("Updated Actor version 0.1 with source files")

    build_info = actor_client.build(version_number="0.1", wait_for_finish=120)
    print(f"Build status: {build_info.get('status')}")

    # Get the new build number
    build_number = build_info.get("buildNumber")
    print(f"Build number: {build_number}")

    # Make actor public. The Apify API rejects `versions`/`defaultRunBuild` on actor update
    # (schema-validation: not allowed by the schema). Publishability is decided from the
    # default build's actorDefinition (input/output schema embedded in actor.json at build
    # time), so the only requirement is that the rebuild above used an actor.json that
    # contains both `input` and `output`. isPublic alone is accepted once schemas exist.
    import time
    time.sleep(5)
    # First set default build to the newly built version so isPublic sees the schemas
    actor_client.update(default_run_build=build_number, is_public=True)
    updated = actor_client.get() or {}
    is_public = updated.get("isPublic")
    print(f"Actor isPublic: {is_public}")

    # Verify the default build actually captured both schemas (root cause of prior 403)
    try:
        builds = client.actors(actor_id).builds().list(limit=5, desc=True)
        default_build = builds.items[0] if builds.items else {}
        ad = default_build.get("actorDefinition") or {}
        print(f"Default build {default_build.get('buildNumber')}: input={ad.get('input') is not None} output={ad.get('output') is not None}")
    except Exception as e:
        print(f"Build schema verification skipped: {e}")

    return {"actor_id": actor_id, "build": build_info, "isPublic": is_public}

def main():
    token = check_token()
    result = deploy_actor(token)
    # Serialize datetime to ISO format for JSON
    import datetime
    def default_serializer(obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
    print(json.dumps(result, indent=2, default=default_serializer))

if __name__ == "__main__":
    main()