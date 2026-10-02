#!/usr/bin/env python3
import os
import json
import zipfile
from pathlib import Path
from apify_client import ApifyClient

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

client = ApifyClient(token)

# Get actor to verify it exists
actor = client.actor("DKzufUSvmuXNKHeYx")._get()
print(f"Actor: {actor['id']} - {actor['name']} - isPublic: {actor['isPublic']}")

# Create zip of actor directory (like deploy script)
REPO_ROOT = Path("/mnt/d/Project2/kensho")
ACTOR_DIR = REPO_ROOT / "apify-figure-price"
zip_path = REPO_ROOT / "japan-anime-figure-price-data.zip"

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for file in ACTOR_DIR.rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts:
            arcname = file.relative_to(ACTOR_DIR)
            zf.write(file, arcname)
print(f"Created actor zip: {zip_path} ({zip_path.stat().st_size} bytes)")

# Build source files
source_files = []
for f in ACTOR_DIR.rglob('*'):
    if f.is_file() and '__pycache__' not in f.parts:
        source_files.append({"name": str(f.relative_to(ACTOR_DIR)), "content": f.read_bytes()})

# Try exactly like the deploy script - just resource with sourceFiles, tag, waitForFinish
build = client.actor("DKzufUSvmuXNKHeYx").builds()._create({
    "resource": {
        "sourceFiles": source_files,
        "tag": "latest",
        "waitForFinish": 120
    }
})

print(f"Build status: {build.get('status')}")
print(json.dumps(build, indent=2))