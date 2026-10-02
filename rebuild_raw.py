#!/usr/bin/env python3
import os
import json
import zipfile
import requests
from pathlib import Path

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

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
        source_files.append({"name": str(f.relative_to(ACTOR_DIR)), "content": f.read_bytes().decode('utf-8')})

# Try raw HTTP POST to builds endpoint with version at top level
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
data = {
    "version": "0.1",
    "resource": {
        "sourceFiles": source_files,
        "tag": "latest",
        "waitForFinish": 120
    }
}
resp = requests.post(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))