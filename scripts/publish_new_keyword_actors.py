#!/usr/bin/env python3
"""publish_new_keyword_actors — v14-B: 需要セグメント向け 3 アクターの公開パイプライン。

背景（v13-A SEO 監査の結論）:
  - 既存 top5 アクター（camera/watch/instrument/luxury）は SEO 競合水準にあるが、
    対象キーワードセグメントの市場需要が小さく伸びが停滞している。
  - 需要の大きい JP オークション/マーケットプレイスセグメントへ新規参入する。

本スクリプトが対象とする 3 セグメントのアクター（Apify Store 上で公開運用）:

  | セグメント        | アクター名                      | Actor ID            | PPE($/件) |
  |-------------------|--------------------------------|---------------------|-----------|
  | mercari JP 転売   | mercari-japan-search-scraper   | whSePszWpMtfeLYBp   | 0.002     |
  | yahoo-auctions JP | yahoo-auctions-japan-scraper   | 8WBam4CPB72q9Rvsd   | 0.002     |
  | surugaya 中古品   | surugaya-japan-hobby-prices    | F8Hl0a8Cx9bpJBrxR   | 0.002     |

各アクターへ適用する内容:
  1. SEO: categories / seo_title / seo_description / description(300字) / title
  2. 価格: PAY_PER_EVENT の dataset-item 単価 $0.002（start $0.00005）
  3. 公開: isPublic=true（categories 必須）

使い方（デフォルト dry-run / 確認のみ）:
  python3 scripts/publish_new_keyword_actors.py                 # 全3アクターの現状確認（変更なし）
  python3 scripts/publish_new_keyword_actors.py --actor mercari # mercari のみ確認
  python3 scripts/publish_new_keyword_actors.py --apply         # 本実行（SEO+価格+公開）
  python3 scripts/publish_new_keyword_actors.py --apply --actor yahoo
  python3 scripts/publish_new_keyword_actors.py --force-price-surugaya  # 安全ガード無視で surugaya 価格設定

重要（surugaya 安全ガード）:
  surugaya は Japan-IP 限定 + Cloudflare のため、無料プランの Apify 環境では
  データが 0 件になる（実測）。有料プランの JP 国指定プロキシ前提。
  0件アクターを $0.002 の有料で公開するのは「壊れた有料アクター」を売ることになり
  Store の評価を損ねるため、デフォルトでは surugaya の価格設定をスキップする。
  機能が回復（タイムアウト期間内に実データが取れる）したら
  --force-price-surugaya を付けて $0.002 を適用する。
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.apify.com/v2"
APP_NAME = "publish_new_keyword_actors"

TARGET_PPE = 0.002  # データ1件あたりの単価 (USD)
TARGET_START = 0.00005  # Actor Start fee (USD)
MARGIN = 0.2  # Apify margin

ACTORS = {
    # key: CLI 用ショート名
    "mercari": {
        "id": "whSePszWpMtfeLYBp",
        "name": "mercari-japan-search-scraper",
        "categories": ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"],
        "title": "Mercari Japan Search Scraper — Prices & Product Data",
        "seo_title": "Mercari Japan Search Scraper — Prices & Product Data",
        "seo_description": (
            "Scrape Mercari Japan (メルカリ) listings by keyword - price, "
            "condition, brand, images, seller. For price research, reseller "
            "arbitrage and market monitoring."
        ),
        "description": (
            "Scrape Mercari Japan (メルカリ) by keyword. Get live prices, "
            "condition, brand, images and seller for reseller arbitrage, price "
            "monitoring and Japan marketplace research. Works directly from "
            "datacenter IPs (no proxy needed). Multiple keywords, price range "
            "and sort supported."
        ),
        "force_price": False,
    },
    "yahoo": {
        "id": "8WBam4CPB72q9Rvsd",
        "name": "yahoo-auctions-japan-scraper",
        "categories": ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"],
        "title": "Yahoo Auctions Japan Scraper — Multi-Keyword Resale Research",
        "seo_title": "Yahoo Auctions Japan Scraper - Used Item Price Research",
        "seo_description": (
            "Scrape Yahoo Auctions Japan by multiple keywords. Get prices, "
            "buy-now, bids for JDM used items. For reseller sourcing, "
            "arbitrage and market monitoring."
        ),
        "description": (
            "Scrape Yahoo Auctions Japan (ヤフオク!) by one or many keywords. "
            "Extract current bid price, buy-now price, bid count and seller "
            "data for JDM used items. Ideal for reseller sourcing, "
            "cross-border arbitrage and Japan used-market price research."
        ),
        "force_price": False,
    },
    "surugaya": {
        "id": "F8Hl0a8Cx9bpJBrxR",
        "name": "surugaya-japan-hobby-prices",
        "categories": ["ECOMMERCE"],
        "title": "Suruga-ya Scraper — Japan Used Hobby & Figure Prices",
        "seo_title": "Suruga-ya Scraper - Japan Used Hobby and Figure Prices",
        "seo_description": (
            "Scrape used prices from Suruga-ya (駿河屋), Japan's largest "
            "second-hand hobby store: figures, anime, games, manga, and more."
        ),
        "description": (
            "Scrape used and new prices from Suruga-ya (駿河屋), Japan's "
            "largest second-hand hobby store. Extract brand, category, "
            "condition and price for reseller arbitrage and price monitoring. "
            "Covers figures, anime, games, manga and books. Note: requires "
            "Japan-IP access (paid Apify JP residential proxies)."
        ),
        "force_price": False,
    },
}

# PUT payload のフィールド名（camelCase）に対応する文字数上限
CHAR_LIMITS = {"title": 80, "seoTitle": 60, "seoDescription": 160, "description": 300, "categories": 3}


# ----------------------------------------------------------------------------- helpers


def _token() -> str:
    tok = os.environ.get("APIFY_TOKEN")
    if not tok:
        sys.exit("APIFY_TOKEN environment variable is required")
    return tok


def _get(path: str) -> dict:
    req = urllib.request.Request(API_BASE + path, headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def _put(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"PUT {path} HTTP {e.code}: {msg[:300]}") from None


def _result_path(sub: str) -> Path:
    return Path("reports") / "apify-new-keyword-actors" / f"{APP_NAME}-{sub}-{_dt.date.today():%Y-%m-%d}.json"


def _current_seo_ok(spec: dict, d: dict) -> bool:
    """SEO フィールドが spec 通り揃っているかを返す（冪等性チェック用）。"""
    ok = True
    checks = {
        "seoTitle": spec["seo_title"],
        "seoDescription": spec["seo_description"],
    }
    for field, want in checks.items():
        cur = (d.get(field) or "").strip()
        if cur != want:
            ok = False
    if bool(d.get("isPublic")) is not True:
        ok = False
    return ok


def _effective_price(d: dict):
    """pricingInfos の最後(=有効)エントリから datasetItem 単価を返す。FREE なら None。"""
    pis = d.get("pricingInfos") or []
    if not pis:
        return None
    last = pis[-1]
    if last.get("pricingModel") != "PAY_PER_EVENT":
        return None
    ev = (last.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    return ev.get("apify-default-dataset-item", {}).get("eventPriceUsd")


def _apply_price(d: dict, target_ppe: float) -> bool:
    """既存 pricingInfos に $target_ppe の新エントリを追加して PUT。購入済みなら False。"""
    pis = d.get("pricingInfos") or []
    if not pis:
        raise RuntimeError("pricingInfos empty — cannot price (Monetization not initialized)")
    newest = [p for p in pis if p.get("pricingModel") == "PAY_PER_EVENT"]
    if not newest:
        raise RuntimeError(
            "no PAY_PER_EVENT pricing entry to template from; use --force-price-surugaya path or init via API/Web UI"
        )
    newrec = copy.deepcopy(newest[-1])
    ev = (newrec.get("pricingPerEvent") or {}).get("actorChargeEvents")
    if ev is None:
        raise RuntimeError("last PAY_PER_EVENT entry has no actorChargeEvents")
    ev["apify-default-dataset-item"]["eventPriceUsd"] = target_ppe
    ev["apify-default-dataset-item"].setdefault("eventTitle", "result")
    ev["apify-default-dataset-item"].setdefault("eventDescription", "Single result in the default dataset.")
    ev["apify-actor-start"].setdefault("eventPriceUsd", TARGET_START)
    now = _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")
    newrec["createdAt"] = now
    newrec["startedAt"] = now
    newrec["apifyMarginPercentage"] = MARGIN
    _put("/acts/" + d["id"], {"pricingInfos": pis + [newrec]})
    return True


def _surugaya_last_run_has_data(actor_id: str) -> bool:
    """surugaya: 直近実効ランが実データを出したか。0件なら有料化してはいけない。"""
    d = _get(f"/acts/{actor_id}/runs?desc=1&limit=1&status=SUCCEEDED")
    items = d.get("data", {}).get("items", [])
    for r in items:
        st = r.get("stats", {})
        if st.get("itemCount"):
            return True
    return False


# ----------------------------------------------------------------------------- apply


def process(key: str, spec: dict, apply: bool, force_price_surugaya: bool, out: dict) -> dict:
    actor_id = spec["id"]
    d = _get("/acts/" + actor_id)["data"]

    rec = {"name": spec["name"], "id": actor_id, "isPublic": d.get("isPublic"), "effective_ppe": _effective_price(d)}

    seo_ok = _current_seo_ok(spec, d)
    if not seo_ok and apply:
        payload = {
            "title": spec["title"],
            "seoTitle": spec["seo_title"],
            "seoDescription": spec["seo_description"],
            "description": spec["description"],
            "categories": spec["categories"],
            "isPublic": True,
        }
        # 文字数ガード
        for f, lim in CHAR_LIMITS.items():
            val = payload.get(f)
            if isinstance(val, list):
                if len(val) > lim:
                    payload[f] = val[:lim]
            elif isinstance(val, str) and len(val) > lim:
                payload[f] = val[:lim]
        _put("/acts/" + actor_id, payload)
        rec["seo_applied"] = True

    # 価格
    cur_ppe = _effective_price(d)
    rec["target_ppe"] = TARGET_PPE
    if cur_ppe != TARGET_PPE:
        if apply:
            guard = key == "surugaya" and not force_price_surugaya
            if guard:
                has_data = _surugaya_last_run_has_data(actor_id)
                if not has_data:
                    rec["price_skipped"] = (
                        "surugaya 0-item on Apify; refuse paid pricing without --force-price-surugaya"
                    )
                else:
                    _apply_price(d, TARGET_PPE)
                    rec["price_applied"] = True
            else:
                _apply_price(d, TARGET_PPE)
                rec["price_applied"] = True
    else:
        rec["price_matches"] = True

    # 公開（SEO 適用時に categories 込みで isPublic=true 済み。念のため明示）
    if apply and not d.get("isPublic"):
        _put("/acts/" + actor_id, {"isPublic": True, "categories": spec["categories"]})
        rec["publish"] = True

    out["actors"][key] = rec
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--actor", choices=list(ACTORS.keys()), help="対象アクター（省略時は全3件）")
    ap.add_argument("--apply", action="store_true", help="本実行（dry-run＝現状確認のみ）")
    ap.add_argument(
        "--force-price-surugaya", action="store_true", help="surugaya 安全ガードを無視して $0.002 価格を適用"
    )
    ap.add_argument("--output-directory", default="reports/apify-new-keyword-actors", help="結果出力先")
    args = ap.parse_args()

    out = {"count": 0, "actors": {}, "applied": args.apply}
    keys = [args.actor] if args.actor else list(ACTORS.keys())
    latest_ref = {}
    for k in keys:
        try:
            d = process(k, ACTORS[k], args.apply, args.force_price_surugaya, out)
            latest_ref[k] = d
        except Exception as e:  # noqa: BLE001
            out["actors"][k] = {"name": ACTORS[k]["name"], "error": str(e)}
    out["count"] = len(keys)

    outdir = Path(args.output_directory)
    outdir.mkdir(parents=True, exist_ok=True)
    pf = _result_path("result")
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"summary: {out['count']} actor(s) processed (apply={args.apply})")
    for k, rec in out["actors"].items():
        print(
            f"  {k:10s} {rec.get('name')}  public={rec.get('isPublic')} "
            f"ppe={rec.get('effective_ppe')}"
            + (
                f"  applied_seo={rec.get('seo_applied')} applied_price={rec.get('price_applied')}"
                + (f"  SKIPPED: {rec.get('price_skipped')}" if rec.get("price_skipped") else "")
                + (f"  price_matches={rec.get('price_matches')}" if rec.get("price_matches") else "")
                + (f"  published={rec.get('publish')}" if rec.get("publish") else "")
                + (f"  ERROR: {rec.get('error')}" if rec.get("error") else "")
            )
        )
    print(f"result JSON: {pf}")


if __name__ == "__main__":
    main()
