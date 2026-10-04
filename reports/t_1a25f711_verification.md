# t_1a25f711 verification report
## verification_evidence
$ git show --oneline -s HEAD
e084148
$ grep -n "MAX_TAGS = 4" /mnt/d/Project2/kensho/devto_weekly_pipeline.py
37:MAX_TAGS = 4
$ grep -n "tags = tags[:MAX_TAGS]" /mnt/d/Project2/kensho/devto_weekly_pipeline.py
263:tags = tags[:MAX_TAGS] if tags else ["development","automation"]
$ python3 - <<'PY'
import json,urllib.request,urllib.error
k=open('/mnt/d/Project2/kensho/.env').read()
k=[l for l in k.splitlines() if l.startswith('DEVTO_API_KEY=')][0].split('=',1)[1].strip()
data=json.dumps({'article':{'title':'devto tag test uniq','body_markdown':'test','published':False,'tags':['a','b','c','d','e']}}).encode()
req=urllib.request.Request('https://dev.to/api/articles', data=data, headers={'api-key':k,'Content-Type':'application/json','User-Agent':'kensho-test'})
try:
    r=urllib.request.urlopen(req,timeout=20)
    print('unexpected success')
except urllib.error.HTTPError as e:
    print('code',e.code)
PY
