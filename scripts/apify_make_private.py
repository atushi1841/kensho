#!/usr/bin/env python3
"""apify_make_private — 重複グループの非公開化スクリプト (t_69bed5fd).

対象: 残り9重複グループ (camera-cn/kr, instrument-cn/kr, luxury-cn/kr,
      offmall-cn/kr, watch-cn/kr, goo-net-car es/pt/fr/ru,
      japan-property-market 3, japan-rent-market 3, kimono-market 3)
合計18本を make_private=true で非公開化。

成功指標: make_private=true x18
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = "/mnt/d/Project2/kensho"
API = "https://api.apify.com/v2"

# 重複グループの actual_name → 非公開化対象
TARGET_ACTORS: list[str] = [
    # camera / instrument / luxury / offmall / watch の -cn/-kr 版
    "japan-camera-market-cn-scraper",
    "japan-camera-market-kr-scraper",
    "japan-used-instrument-market-cn",
    "japan-used-instrument-market-kr",
    "japan-luxury-brand-market-cn",
    "japan-luxury-brand-market-kr",
    "japan-offmall-market-cn",
    "japan-offmall-market-kr",
    "japan-watch-market-scraper-cn",
    "japan-watch-market-scraper-kr",
    # goo-net-car-scraper の es/pt/fr/ru バリアント (5本)
    "goo-net-car-scraper-es",
    "goo-net-car-scraper-pt",
    "goo-net-car-scraper-fr",
    "goo-net-car-scraper-ru",
    # japan-property-market / japan-rent-market / kimono-market の重複3本ずつ
    "japan-property-market-cn",
    "japan-property-market-kr",
    "japan-rent-market-cn",
    "japan-rent-market-kr",
    "kimono-market-cn",
    "kimono-market-kr",
]
# 合計 20 パターン。実際の公開数は API 経由で動的確認。


def _token() -> str:
    tok = os.environ.get("APIFY_TOKEN", "").strip()
    if not tok:
        env_path = Path(PROJECT_DIR) / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith(("APIFY_TOKEN=", "APIFY_TOKEN_DEFAULT=")):
                    tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return tok


TOKEN = _token()
assert TOKEN, "no APIFY_TOKEN/APIFY_TOKEN_DEFAULT"
TOKEN_LEN = len(TOKEN)


def api_get(path: str) -> dict:
    url = f"{API}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_put(actor_id: str, payload: dict) -> tuple[int, dict]:
    url = f"{API}/acts/{actor_id}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()

    # 全アクター名 → id のマッピングを取得（user=fruitful_quintessence 限定）
    actors = api_get(f"/actors?limit=200&userId=fruitful_quintessence")["data"]["items"]
    name_to_id = {a["name"]: a["id"] for a in actors}
    print(f"total my actors: {len(name_to_id)}", file=sys.stderr)

    results = []
    for name in TARGET_ACTORS:
        aid = name_to_id.get(name)
        if not aid:
            print(f"NOT FOUND: {name}", file=sys.stderr)
            results.append({"name": name, "status": "not_found"})
            continue
        # 現在の isPublic を取得
        cur = api_get(f"/acts/{aid}")["data"]
        if not cur.get("isPublic"):
            print(f"ALREADY PRIVATE: {name}", file=sys.stderr)
            results.append({"name": name, "status": "already_private",
                            "actor_id": aid})
            continue
        if args.dry_run:
            print(f"[DRY] would private: {name} ({aid})", file=sys.stderr)
            results.append({"name": name, "status": "would_private",
                            "actor_id": aid})
            continue
        code, body = api_put(aid, {"isPublic": False})
        ok = code == 200 and body.get("data", {}).get("isPublic") is False
        results.append({
            "name": name,
            "actor_id": aid,
            "status": "privatized" if ok else "failed",
            "http_code": code,
            "isPublic_after": body.get("data", {}).get("isPublic"),
        })
        print(f"[{code}] {name}: {'OK' if ok else 'FAIL'}", file=sys.stderr)
        time.sleep(args.sleep)

    out = Path(PROJECT_DIR) / "reports" / "apify-make-private" / "apify-make-private.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    priv = sum(1 for r in results if r["status"] in ("privatized", "already_private"))
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"total={len(results)} privatized={priv} failed={failed}")
    print(f"json: {out}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
