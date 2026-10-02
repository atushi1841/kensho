#!/usr/bin/env python3
import subprocess
import os

# Get GH_TOKEN from gh CLI
result = subprocess.run(['cmd.exe', '/c', 'gh auth token'], capture_output=True, text=True)
token = result.stdout.strip()
os.environ['GH_TOKEN'] = token

import urllib.request
import json

def gh(verb, url):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    req = urllib.request.Request(url, headers=headers, method=verb)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.getcode(), json.loads(r.read().decode())

# Check japan-prize-giveaway-scraper on GitHub
code, d = gh("GET", "https://api.github.com/repos/atushi1841/japan-prize-giveaway-scraper/contents/README.md")
if code == 200:
    import base64
    content = base64.b64decode(d["content"]).decode(errors="replace")
    print(f"japan-prize-giveaway-scraper README: {len(content)} chars")
    print(content[:300])
else:
    print(f"japan-prize-giveaway-scraper: NO README on GitHub (code={code})")

# Check japan-anime-figure-price-data on GitHub
code, d = gh("GET", "https://api.github.com/repos/atushi1841/japan-anime-figure-price-data/contents/README.md")
if code == 200:
    import base64
    content = base64.b64decode(d["content"]).decode(errors="replace")
    print(f"\njapan-anime-figure-price-data README: {len(content)} chars")
    print(content[:300])
else:
    print(f"\njapan-anime-figure-price-data: NO README on GitHub (code={code})")