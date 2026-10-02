#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')

# Get full actor info
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx?token=" + tok
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
with urllib.request.urlopen(req, timeout=20) as f:
    d = json.load(f).get('data', {})
    print(json.dumps(d, indent=2))