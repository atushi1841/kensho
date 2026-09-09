import base64, hashlib, json, math, os, random, sys, time
from curl_cffi import requests as C

BASE = "/mnt/d/Project2/kensho"
OUT = os.path.join(BASE, "research/adobe_stock_20260909")

X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
_QUERY_ID_URL = "https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument/master/docs/json/API.json"
_KEYWORD = "obfiowerehiring"
_pairs = json.load(open(os.path.join(BASE, "kensho/application/transaction_pairs.json")))

def _gen_tid(method, path):
    p = random.choice(_pairs)
    key_bytes = list(base64.b64decode(p["verification"]))
    t = math.floor((time.time()*1000 - 1682924400*1000) / 1000)
    tb = [(t >> (i*8)) & 0xFF for i in range(4)]
    h = list(hashlib.sha256(f"{method}!{path}!{t}{_KEYWORD}{p['animationKey']}".encode()).digest())
    rn = random.randint(0,255)
    b = bytearray([rn, *[x ^ rn for x in [*key_bytes,*tb,*h[:16],3]]])
    return base64.b64encode(b).decode().rstrip("=")

_cached_api = None
def _api():
    global _cached_api
    if _cached_api is None:
        _cached_api = C.get(_QUERY_ID_URL, timeout=20, impersonate="chrome").json()
    return _cached_api

def _qid(name):
    return _api()["graphql"][name]["queryId"]

class XClient:
    def __init__(self, session_file):
        s = json.load(open(session_file))["cookies"]
        s = {c["name"]: c["value"] for c in s}
        self.auth_token = s.get("auth_token")
        self.ct0 = s.get("ct0")
        if not self.auth_token or not self.ct0:
            raise ValueError("missing auth_token/ct0")
    def _hdr(self):
        return {
            "authorization": f"Bearer {X_BEARER}",
            "x-csrf-token": self.ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "ja",
            "cookie": f"auth_token={self.auth_token}; ct0={self.ct0}",
            "referer": "https://x.com/",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        }
    def _req(self, op, name, method, body=None):
        q = _qid(name)
        path = f"/i/api/graphql/{q}/{op}"
        kw = {"headers": self._hdr(), "timeout": 25, "impersonate": "chrome"}
        if body is not None:
            kw["json"] = body
        r = C.request(method, f"https://x.com{path}", **kw)
        try:
            data = r.json()
        except Exception:
            data = {"_raw": r.text[:500]}
        return {"status": r.status_code, "data": data}
    def search(self, query, count=20):
        feat = _api()["graphql"]["SearchTimeline"].get("features", {})
        return self._req("SearchTimeline", "SearchTimeline", "POST",
                         {"variables": {"rawQuery": query, "count": count, "cursor": None,
                                        "querySource": "typed_query", "product": "Top"},
                          "features": feat})

QUERIES = {
    "q1_adobe_stock_shueki": "Adobe Stock 収益 lang:ja",
    "q2_adobe_stock_shinsa": "Adobe Stock 審査 lang:ja",
    "q3_adobe_stock_ai_illustration_kyoshitsu": "Adobe Stock AIイラスト 却下 lang:ja",
    "q4_stockphoto_ai_genkai": "ストックフォト AI 限界 lang:ja",
    "q5_adobe_stock_contributor": "Adobe Stockコントリビューター lang:ja",
}

SESSIONS = ["data/x_session_c.json", "data/x_session_royalkensho.json",
            "data/x_session_kudou.json", "data/x_session_TankanNotes.json",
            "data/x_session_chugakujuken.json", "data/x_session_inobase1-4.json",
            "data/x_session_toushiwatch.json"]

results = {}
status_log = []
used_client = None

for sf in SESSIONS:
    fp = os.path.join(BASE, sf)
    if not os.path.exists(fp):
        continue
    try:
        c = XClient(fp)
    except Exception as e:
        status_log.append(f"{sf}: load error {type(e).__name__}")
        continue
    # probe with a small query
    try:
        probe = c.search("Adobe Stock 収益 lang:ja", 5)
    except Exception as e:
        status_log.append(f"{sf}: probe exception {type(e).__name__}: {str(e)[:120]}")
        time.sleep(3)
        continue
    st = probe["status"]
    if st == 200:
        used_client = sf
        status_log.append(f"{sf}: VALID (probe 200)")
        results["probe_seed"] = probe["data"]
        break
    else:
        status_log.append(f"{sf}: probe HTTP {st} errors={str(probe['data'].get('errors'))[:100]}")
    time.sleep(random.uniform(3, 4))

if used_client is None:
    json.dump({"ok": False, "status_log": status_log}, open(os.path.join(OUT, "fetch_status.json"), "w"), ensure_ascii=False, indent=1)
    print("ALL SESSIONS FAILED")
    sys.exit(2)

client = XClient(os.path.join(BASE, used_client))
for key, q in QUERIES.items():
    time.sleep(random.uniform(3.2, 4.5))
    try:
        r = client.search(q, 20)
        results[key] = {"query": q, "status": r["status"], "data": r["data"]}
        status_log.append(f"{key}: HTTP {r['status']}")
    except Exception as e:
        results[key] = {"query": q, "status": -1, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        status_log.append(f"{key}: EXC {type(e).__name__}")

json.dump({"ok": True, "session": used_client, "status_log": status_log, "results": results},
          open(os.path.join(OUT, "raw_responses.json"), "w"), ensure_ascii=False)
print("DONE", used_client, len(results))
