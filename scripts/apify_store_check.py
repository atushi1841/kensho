import requests

ENV = "/mnt/d/Project2/kensho/.env"


def env_val(key):
    for line in open(ENV, encoding="utf-8"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")


TOK = env_val("APIFY_TOKEN_DEFAULT")
# 自actor（fruitful_quintessence）の store search を逆引き: どのキーワードで 1位 にいるか
# 既知のpopular なキーワードを試す
for q in ["mercari", "mercari japan", "used goods japan", "dlsite", "kakaku"]:
    r = requests.get("https://api.apify.com/v2/store", params={"token": TOK, "query": q, "limit": 200}, timeout=25)
    d = r.json()
    if not d.get("ok"):
        print(f"FAIL q={q} resp={d}")
        continue
    items = d.get("data", {}).get("items", [])
    my = [i for i in items if i.get("username") == "fruitful_quintessence"]
    print(f"q={q} total={d.get('data', {}).get('count')} mine={len(my)} names={[i.get('name') for i in my[:3]]}")
