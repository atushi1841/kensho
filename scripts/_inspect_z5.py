#!/usr/bin/env python3
import json, unicodedata, re, sys
sys.path.insert(0, "/mnt/d/Project2/kensho")
import importlib.util
spec = importlib.util.spec_from_file_location("watchlist", "/mnt/d/Project2/kensho/data/camera_monitor/watchlist.py")
wl = importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
W = wl.WATCHLIST
z5 = [m for m in W if m["model"]=="Nikon Z5"][0]
tokens = set(z5["matchTokens"])
print("tokens:", tokens)

def _norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    for ch in ("\u2212","\uff0d","\u2010","\u2011"): s = s.replace(ch,"-")
    return s
def _tokens(s):
    t = set(re.findall(r"[a-z0-9]{2,}", _norm(s)))
    alias = {"ソニー":"sony","キヤノン":"canon","キャノン":"canon","ニコン":"nikon",
             "フジフイルム":"fujifilm","富士フイルム":"fujifilm","フイルム":"fujifilm"}
    for ja,en in alias.items():
        if ja in t: t.discard(ja); t.add(en)
    return t
def pri(it):
    return _to_int(it.get("used_price_jpy")) or _to_int(it.get("new_price_jpy"))
def _to_int(v):
    if v is None: return None
    s = re.sub(r"[^\d]","",str(v)); return int(s) if s else None

d = json.load(open("/mnt/d/Project2/suruga-scraper/data/_camera_mon_Z5.json"))
items = d.get("items", [])
print("total items:", len(items))
refs=[]
for r in items:
    name=r.get("name",""); pr=pri(r)
    if not pr: continue
    if not tokens.issubset(_tokens(name)): continue
    refs.append((pr,name))
refs.sort(key=lambda x:x[0])
print("matching refs:", len(refs))
for pr,name in refs[:20]:
    print(pr, "|", name[:80])
