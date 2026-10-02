#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')

# Try to set defaultRunBuild first
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx?token=" + tok
data = {"defaultRunBuild": "0.1.65"}
req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="PUT")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.load(resp)
        print("Set defaultRunBuild Success:", json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode())