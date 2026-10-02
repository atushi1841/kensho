#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx', headers={'Authorization': 'Bearer ' + tok})
with urllib.request.urlopen(req, timeout=20) as f:
    d = json.load(f).get('data', {})
    print('isPublic:', d.get('isPublic'))
    print('defaultBuild:', d.get('defaultBuild'))
    print('buildNumber:', d.get('buildNumber'))
    print('input:', 'present' if d.get('input') else 'missing')
    print('output:', 'present' if d.get('output') else 'missing')