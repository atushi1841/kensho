#!/usr/bin/env python3
"""Apify PPE 価格ヘルパー — 値上げ/復帰/スナップショット/単価確認（t_c4343276 由来）。

PPE（PAY_PER_EVENT）価格の取得・変更を Apify API 直接で行う。
変更は「既存エントリ全件 + 新規1件」方式（最後のエントリが有効価格）。

使い方:
  python3 scripts/apify_ppe_price.py raw <ACTOR_ID>      # pricingInfos各エントリ表示
  python3 scripts/apify_ppe_price.py snapshot <ID>...    # 有効価格スナップショット
  python3 scripts/apify_ppe_price.py raise_price <ID> <USD>  # datasetItem単価を変更
  python3 scripts/apify_ppe_price.py runs <ID>           # 7日ウィンドウrun数（A/B判定用）
"""

import copy
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://api.apify.com/v2"
_ENV_PATH = "/mnt/d/Project2/kensho/.env"


def _resolve_token() -> str:
    """t_6f3de363: env不整合修復。APIFY_TOKEN→APIFY_TOKEN_DEFAULT→.env直接パースの順。
    全て不在なら 401 静默フォールバックではなく即失敗（原因を明示）。"""
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if tok:
        return tok.strip()
    # cronはsourceでもexportされないため.envを直接読む（2026-09-12 00:58失敗の実因）
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    sys.exit("ERROR: Apifyトークン未取得（APIFY_TOKEN/APIFY_TOKEN_DEFAULT/.env すべて不在）。401の前に終了。")


TOKEN = _resolve_token()


def _request(path: str, body: object = None, method: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # 401等のレスポンスを握りつぶさない: HTTPステータス付きで明示失敗
        sys.exit(f"ERROR: HTTP {e.code} at {path}（token失効/権限を確認）")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: network failure at {path}: {e.reason}")


def get(path: str) -> dict:
    return _request(path)


def put(path: str, body: object) -> dict:
    return _request(path, body=body, method="PUT")


def main():
    action = sys.argv[1]

    if action == "raw":
        # pricingInfos の全エントリと単価を表示（最後のエントリが有効価格）
        pis = get("/acts/" + sys.argv[2])["data"].get("pricingInfos", [])
        print("num entries:", len(pis))
        for i, pi in enumerate(pis):
            ev = pi.get("pricingPerEvent", {}).get("actorChargeEvents", {})
            price = ev.get("apify-default-dataset-item", {}).get("eventPriceUsd")
            print(f"[{i}] createdAt={pi.get('createdAt')} startedAt={pi.get('startedAt')} datasetItemUsd={price}")

    elif action == "snapshot":
        for tid in sys.argv[2:]:
            d = get("/acts/" + tid)
            a = d["data"]
            pis = a.get("pricingInfos") or []
            cur = pis[-1] if pis else None
            ev = (cur.get("pricingPerEvent") or {}).get("actorChargeEvents") if cur else None
            print(
                json.dumps(
                    {
                        "id": tid,
                        "name": a.get("name"),
                        "isPublic": a.get("isPublic"),
                        "numEntries": len(pis),
                        "pricingModel": cur.get("pricingModel") if cur else None,
                        "margin": cur.get("apifyMarginPercentage") if cur else None,
                        "datasetItemUsd": (ev or {}).get("apify-default-dataset-item", {}).get("eventPriceUsd"),
                    },
                    ensure_ascii=False,
                )
            )

    elif action == "raise_price":
        tid, new_price = sys.argv[2], float(sys.argv[3])
        d = get("/acts/" + tid)
        a = d["data"]
        pis = a.get("pricingInfos") or []
        if not pis:
            sys.exit("NO pricingInfos; abort")
        newest = pis[-1]
        newrec = copy.deepcopy(newest)
        ev = (newrec.get("pricingPerEvent") or {}).get("actorChargeEvents")
        if ev is None:
            sys.exit("no actorChargeEvents; abort")
        ev["apify-default-dataset-item"]["eventPriceUsd"] = new_price
        if "eventDescription" not in ev["apify-default-dataset-item"]:
            ev["apify-default-dataset-item"]["eventDescription"] = "Single result in the default dataset."
        now = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z")
        )
        newrec["createdAt"] = now
        newrec["startedAt"] = now
        put("/acts/" + tid, {"pricingInfos": pis + [newrec]})
        print("PUT done for", tid)
        raw = get("/acts/" + tid)["data"].get("pricingInfos", [])
        last = raw[-1]["pricingPerEvent"]["actorChargeEvents"]["apify-default-dataset-item"]["eventPriceUsd"]
        print("now datasetItemUsd =", last, "entries=", len(raw))

    elif action == "runs":
        tid = sys.argv[2]
        d = get(f"/acts/{tid}/runs?desc=1&limit=100")
        total_all = d["data"].get("all", len(d["data"].get("items", [])))
        items = d["data"].get("items", [])
        owner = get("/users/me")["data"].get("id")
        import datetime as _dd

        cutoff7 = (_dd.datetime.now(_dd.UTC) - _dd.timedelta(days=7)).replace(tzinfo=None)
        total7 = ext7 = 0
        for r in items:
            st = r.get("startedAt")
            if not st:
                continue
            try:
                dt = _dd.datetime.fromisoformat(st.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if dt >= cutoff7:
                total7 += 1
                if r.get("userId") != owner:
                    ext7 += 1
        print(f"total_runs={total_all} window7d total={total7} external={ext7}")


main()
