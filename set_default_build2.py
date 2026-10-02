#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')

# Try to set default build via build endpoint
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds/0.1.65/default?token=" + tok
req = urllib.request.Request(url, method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.load(resp)
        print("Set default build Success:", json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode())