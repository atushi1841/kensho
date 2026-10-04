#!/usr/bin/env python3
"""apify_seo_desc_repair — Apify アクターの説明文の「壊れた末尾」を検出して直す。

なぜ必要か（2026-10-03 実測）:
  過去のキーワード注入（apify_seo_full_apply）が説明文の末尾に意味の通らない断片を
  残していた。実例（mercari-japan-search-scraper）:
    "...JSON/CSV output via Apify dataset. Pay-per-event per item scraped largest."
  "largest." は文になっていない。機械生成の痕跡として見え、購入判断を損なう。

APIの罠（2つ目）:
  **一覧API(/acts)の description は詳細API(/acts/{user}~{name})の値と違う。**
  一覧で壊れ文を探すと 0 件になる（mercari は一覧では検出できず、詳細では検出できた）。
  アクターのフィールド判定は必ず詳細APIで行う。isPublic でも同じ罠を踏んでいる。

使い方:
  python3 scripts/apify_seo_desc_repair.py            # 検出のみ（書き込みなし）
  python3 scripts/apify_seo_desc_repair.py --apply    # 実際に PUT して直す
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "/mnt/d/Project2/kensho"
API = "https://api.apify.com/v2"
OWN_USER = "fruitful_quintessence"

DESC_MAX = 300
SEODESC_MAX = 160
TARGET_MIN = 250

# 文末として成立しない語尾（機械生成の断片）。正当な語尾(JSON./CSV./dataset.)は含めない。
GARBLED_TAIL = re.compile(
    r"(?:^|[.\s])(largest|scraped|per|and|with|for|the|to|of|in|a|an|s|item|items|result|results)\.\s*$",
    re.IGNORECASE,
)

CLOSING = "Output is JSON or CSV via the Apify dataset; billing is pay-per-result."


def get_token() -> str:
    env = {}
    try:
        with open(os.path.join(REPO, ".env"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
                if m:
                    env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    for name in ("APIFY_TOKEN", "APIFY_TOKEN_DEFAULT"):
        val = (os.environ.get(name) or env.get(name) or "").strip()
        if val:
            return val
    return ""


def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        API + path, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {}


def actor_detail(token: str, name: str) -> dict | None:
    st, body = api("GET", f"/acts/{OWN_USER}~{name}", token)
    return body.get("data") if st == 200 else None


def _truncate_safe(t: str, limit: int) -> str:
    """上限内で文末で切る。function word で終わらせない（壊れ文を作らない）。"""
    if len(t) <= limit:
        return t
    head = t[:limit]
    cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    if cut > limit * 0.5:
        return head[: cut + 1].strip()
    # 文末が無い場合は語境界で切り、助詞・前置詞で終わらないよう語を1つ落とす
    words = head.split()
    while words and words[-1].strip(".,;:").lower() in {
        "a", "an", "and", "as", "at", "billing", "by", "for", "from", "in",
        "is", "of", "on", "or", "per", "the", "to", "with", "your",
    }:
        words.pop()
    return " ".join(words).rstrip(",;:") + "."


def repair_text(text: str, limit: int) -> tuple[str, bool]:
    """壊れた末尾を落とし、必要なら結びの一文を足して上限内に収める。"""
    t = (text or "").strip()
    if not t:
        return t, False
    changed = False
    while GARBLED_TAIL.search(t):
        # 壊れた末尾の断片（最後のピリオド以降）を削って、その前の文で終わらせる
        cut = t.rstrip().rfind(".", 0, len(t.rstrip()) - 1)
        if cut <= 0:
            break
        t = t[: cut + 1].strip()
        changed = True
    if changed:
        # 結びを戻して長さを確保。既に JSON/CSV や dataset に触れている場合は
        # 定型文を丸ごと足すと重複するので、課金の一文だけにする。
        body_l = t.lower()
        closing = ("Billing is pay-per-result." if ("json" in body_l or "dataset" in body_l)
                   else CLOSING)
        if len(t) < TARGET_MIN and len(t) + 1 + len(closing) <= limit:
            if closing.split()[0].lower() not in body_l:
                t = f"{t.rstrip()} {closing}"
                if len(t) > limit:
                    t = t[: limit - 1].rstrip() + "."
    return t, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--out", default=os.path.join(REPO, "reports", "apify-seo", "desc-repair.json"))
    args = ap.parse_args()

    token = get_token()
    if not token:
        print("ERROR: token 不在", flush=True)
        return 2

    names = [a["name"] for a in api("GET", f"/acts?limit={args.limit}", token)[1]["data"]["items"]]
    details: list[dict] = []
    with cf.ThreadPoolExecutor(8) as ex:
        for d in ex.map(lambda n: actor_detail(token, n), names):
            if d:
                details.append(d)

    rows = []
    for d in details:
        desc = d.get("description") or ""
        sdesc = d.get("seoDescription") or ""
        new_desc, ch1 = repair_text(desc, DESC_MAX)
        new_sdesc, ch2 = repair_text(sdesc, SEODESC_MAX)
        if not (ch1 or ch2):
            continue
        row = {
            "actor": d["name"], "id": d["id"],
            "desc_before": desc, "desc_after": new_desc,
            "seodesc_before": sdesc, "seodesc_after": new_sdesc,
        }
        rows.append(row)
        print(f"{d['name']:<46} desc {len(desc)}->{len(new_desc)}  seoDesc {len(sdesc)}->{len(new_sdesc)}")

    print(f"\n対象: {len(rows)}本 / 走査 {len(details)}本")
    for r in rows[:5]:
        print(f"\n[{r['actor']}]\n  before: ...{r['desc_before'][-80:]}\n  after : ...{r['desc_after'][-80:]}")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "applied": bool(args.apply),
           "scanned": len(details), "targets": rows}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    if args.apply:
        ok = 0
        for r in rows:
            st, _ = api("PUT", f"/acts/{r['id']}", token,
                        {"description": r["desc_after"], "seoDescription": r["seodesc_after"]})
            st2, body = api("GET", f"/acts/{r['id']}", token)
            live = body.get("data", {}) if st2 == 200 else {}
            match = (live.get("description") == r["desc_after"])
            r["put_status"] = st
            r["readback_match"] = bool(match)
            ok += 1 if (st == 200 and match) else 0
            print(f"PUT {r['actor']:<46} {st} readback={'一致' if match else '不一致'}")
        out["applied_ok"] = ok
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print(f"\n適用: {ok}/{len(rows)} 本（read-back 一致）")

    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
