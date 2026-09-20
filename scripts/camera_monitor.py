#!/usr/bin/env python3
"""7-day camera margin monitor — used-camera inter-store price-difference measurement.

Builds on the existing local pipeline (yahoo-auctions-japan-scraper research
 + local suruga-scraper). LOCAL-ONLY: no Apify API, no Mercari leg, no
login-required access, no auto-bid. Gentle/low-frequency collection.

For each watchlist model it:
  1) scrapes Yahoo Auctions for sourcing candidates (fixed buy-now price),
  2) scrapes SuRUGA-ya for the retail used price of the same model,
  3) pairs SAME-model references (AND/ALL brand+model matchTokens must appear as
     exact title tokens on BOTH sides — blocks cross-model/accessory/toy hits),
  4) computes inter-store price difference per model and cross-checks the
     camerabench.net claim (median ~20% store-price gap; a third+ of models
     with >=30% spread),
  5) writes a fee/shipping-stripped sourcing candidate list + 30-model table.

Outputs:
  data/camera_monitor/sourcing_candidates_<DATE>.csv/.json
  data/camera_monitor/model_price_diff_<DATE>.csv
  data/camera_monitor/matched_pairs_<DATE>.csv
  reports/camera_monitor_<DATE>.log
Usage:
  python3 -m scripts.camera_monitor [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, "/mnt/d/Project2/yahoo-auctions-japan-scraper")

# watchlist (python module with matchTokens)
_W = _ROOT / "data" / "camera_monitor" / "watchlist.py"
if str(_W.parent) not in sys.path:
    sys.path.insert(0, str(_W.parent))
import watchlist as _wl  # noqa
WATCH = _wl.WATCHLIST

APPENDIX = {
    "グリップ": 1, "バッテリー": 1, "ストラップ": 1, "ケース": 1, "三脚": 1,
    "クリーナー": 1, "キャップ": 1, "目当て": 1, "充電": 1, "アダプタ": 1,
    "電池": 1, "フィルム": 1, "プレート": 1, "ホルダー": 1, "ブラケット": 1,
    "レンズ": 1, "カバー": 1, "レンタル": 1, "リース": 1, "貸出": 1, "部品": 1,
    "ジャンク": 1, "故障": 1, "本体のみ": 1, "マウント": 1, "シャッターユニット": 1,
    "ストロボ": 1, "変換": 1, "修理": 1, "清掃": 1,
    # カタログ/冊子/付属品/ケーブル類 — 誤ペアリング防止（同名機の別商品）
    "カタログ": 1, "パンフレット": 1, "説明書": 1, "取扱説明書": 1, "冊子": 1,
    # 撮影ガイド/操作入門/レシピ本など書籍（カメラ本体扱いしない。Z5事例: 撮影ガイド¥1700を誤ってmedian採用）
    "撮影ガイド": 1, "ガイドブック": 1, "マニュアル": 1, "撮影入門": 1, "入門書": 1, "使い方ガイド": 1,
    "レシピ本": 1, "ポートレート": 1, "作例": 1, "ミニ図鑑": 1, "ぴったりガイド": 1, "撮影術": 1,
    "キーホルダー": 1, "ケースfor": 1, "プロテクター": 1, "ケーブル": 1, "コード": 1,
    "ポーチ": 1, "タオル": 1, "ホットシューカバー": 1, "ボディキャップ": 1,
    "ネックストラップ": 1, "ストラップ本体": 1, "ブラケット型": 1,
    "スタンド": 1, "モニター保護": 1, "液晶保護": 1, "めんたま": 1, "目玉": 1,
    "シール": 1, "ステッカー": 1, "キーボード": 1, "マウス": 1, "クリアファイル": 1,
    # merchandise / non-body items that can carry a model token
    "トランスフォーマー": 1, "オプティマス": 1, "メガトロン": 1, "ネメシス": 1,
    "ディセプティコン": 1, "フィギュア": 1, "カレンダー": 1, "特別付録": 1,
    "サントラ": 1, "サウンド": 1, "トラックス": 1, "マガジン": 1, "書籍": 1,
    "タカラトミー": 1, "プライム": 1, "限定": 1, "ポスター": 1, "雑誌": 1,
    "ドラマ": 1, "cd": 1, "dvd": 1, "ソフト": 1, "ボックス": 1, "巻": 1,
}


# ---------------------------------------------------------------- helpers
def _to_int(v):
    if v is None:
        return None
    s = re.sub(r"[^\d]", "", str(v))
    return int(s) if s else None


def _today() -> str:
    # 日本時間（JST=UTC+9）基準で日付付け。夜間実行でも境界またぎ時に誤分類しない
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y%m%d")


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s).strip("_")[:40] or "kw"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    for ch in ("\u2212", "\uff0d", "\u2010", "\u2011"):
        s = s.replace(ch, "-")
    return s


def _tokens(s: str) -> set[str]:
    tok = set(re.findall(r"[a-z0-9]{2,}", _norm(s)))
    # brand aliases -> single latin brand token so matchTokens compare cleanly
    alias = {"ソニー": "sony", "キヤノン": "canon", "キャノン": "canon",
             "ニコン": "nikon", "フジフイルム": "fujifilm",
             "富士フイルム": "fujifilm", "フイルム": "fujifilm"}
    for ja, en in alias.items():
        if ja in tok:
            tok.discard(ja)
            tok.add(en)
    return tok


def _is_accessory(title: str) -> bool:
    n = _norm(title)
    return any(m in n for m in APPENDIX)


def _price_of(it) -> int | None:
    return _to_int(it.get("used_price_jpy")) or _to_int(it.get("new_price_jpy"))


# ---------------------------------------------------------------- yahoo
def _scrape_yahoo(client, keyword: str, max_pages: int, max_items: int) -> list[dict]:
    from research.research_locally import search_keyword
    return search_keyword(client, keyword, max_pages, max_items)


# ---------------------------------------------------------------- suruga
def _cache_path(keyword: str) -> Path:
    """suruga-scraper の編集済みキャッシュJSONパス（同キーワード再利用用）。"""
    return Path("/mnt/d/Project2/suruga-scraper/data") / f"_camera_mon_{_safe(keyword)}.json"


def _scrape_suruga(keyword: str, max_pages: int, use_cache: bool = False) -> dict | None:
    if use_cache:
        cp = _cache_path(keyword)
        if cp.exists():
            try:
                data = json.loads(cp.read_text(encoding="utf-8"))
                if data.get("items"):
                    print(f"    [suruga-cache] {keyword}: {len(data['items'])} items re-used", flush=True)
                    return data
            except Exception as exc:
                print(f"    [suruga-cache] {keyword} load fail: {exc}", flush=True)
    sys_path = list(sys.path)
    sys.path.insert(0, "/mnt/d/Project2/suruga-scraper/src")
    try:
        from scraper import scrape  # noqa
        out = scrape(keyword, max_pages=max_pages, in_stock_only=False,
                     output=f"_camera_mon_{_safe(keyword)}.json")
        if out is None:
            return None
        return json.loads(out.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"    [suruga] {keyword}: {exc}", flush=True)
        return None
    finally:
        sys.path[:] = sys_path


# ---------------------------------------------------------------- pairing
def compute_model_diff(yahoo_items, suruga_items, tokens: list[str]) -> dict:
    """Pair same-model Yahoo(buy-now) candidates against SuRUGA retail prices.

    A pair is valid only if EVERY matchToken (brand first, then model) appears
    as an exact title token on both sides, and neither side is an accessory.
    diff_rate = resale_price / sourcing_cost - 1 (positive => SuRUGA retails
    above the Yahoo sourcing price)."""
    tokset_need = set(tokens)

    suruga_refs = []
    for r in suruga_items:
        name = r.get("name", "")
        price = _price_of(r)
        if not price:
            continue
        if _is_accessory(name):
            continue
        if not tokset_need.issubset(_tokens(name)):
            continue
        suruga_refs.append({"title": name, "price": price, "url": r.get("url", "")})
    if not suruga_refs:
        return {"pairs": [], "matched": 0, "median_diff": None, "max_diff": None,
                "median_ge20": False, "max_ge30": False}

    pairs = []
    for it in yahoo_items:
        bn = _to_int(it.get("buyNowPrice"))
        if not bn:
            continue
        title = it.get("title", "")
        if _is_accessory(title):
            continue
        if not tokset_need.issubset(_tokens(title)):
            continue
        # median SuRUGA reference for this exact model = robust resale comp
        best = sorted(suruga_refs, key=lambda s: s["price"])[len(suruga_refs)//2]
        diff = best["price"] / bn - 1.0
        pairs.append({"yahoo_title": title, "url": it.get("detailUrl", ""),
                      "postage": it.get("postage"), "sourcing_cost": bn,
                      "resale_price": best["price"], "diff_rate": diff,
                      "suruga_title": best["title"], "source_url": best["url"]})

    if not pairs:
        return {"pairs": [], "matched": 0, "median_diff": None, "max_diff": None,
                "median_ge20": False, "max_ge30": False}
    diffs = [p["diff_rate"] for p in pairs]
    return {"pairs": pairs, "matched": len(pairs),
            "median_diff": median(diffs), "max_diff": max(diffs),
            "median_ge20": bool(median(diffs) >= 0.20),
            "max_ge30": bool(max(diffs) >= 0.30)}


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description="Camera 7-day margin monitor (local)")
    p.add_argument("--data-dir", type=Path, default=_ROOT / "data" / "camera_monitor")
    p.add_argument("--report-dir", type=Path, default=_ROOT / "reports")
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--max-items", type=int, default=25)
    p.add_argument("--suruga-pages", type=int, default=1)
    p.add_argument("--limit", type=int, default=0, help="Debug: only first N models")
    p.add_argument("--use-cache", action="store_true",
                   help="suruga募集済みJSONを再利用（同キーワードの再スクレイプを避ける）")
    args = p.parse_args()

    watch = WATCH
    if args.limit:
        watch = watch[: args.limit]

    today = _today()
    run_id = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y%m%d_%H%M%S")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    log_lines = [f"camera_margin_monitor run {run_id}",
                 f"watchlist={len(watch)} models | pages yahoo={args.max_pages} suruga={args.suruga_pages}"]

    import httpx
    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36"),
               "Accept-Language": "ja,en;q=0.9"}

    model_rows: list[dict] = []
    all_candidates: list[dict] = []
    all_pairs_debug: list[dict] = []

    async def _run():
        async with httpx.AsyncClient(headers=headers, timeout=35,
                                     follow_redirects=True) as client:
            for m in watch:
                model = m["model"]
                kw_y = m.get("keyword") or model
                kw_s = m.get("surugaKeyword") or model
                print(f"[{model}] yahoo '{kw_y}' + suruga '{kw_s}'", flush=True)
                # BOT対策: モデル間はランダム待機（個人収集・堅拗アクセス回避）
                if len(watch) > 1:
                    wait = random.uniform(4, 10)
                    print(f"    wait {wait:.1f}s (gentle interval)", flush=True)
                    await asyncio.sleep(wait)
                yahoo_items = []
                try:
                    yahoo_items = await _scrape_yahoo(client, kw_y, args.max_pages, args.max_items)
                except Exception as exc:
                    print(f"    [yahoo] {exc}", flush=True)
                print(f"    yahoo {len(yahoo_items)}", flush=True)
                suruga = _scrape_suruga(kw_s, args.suruga_pages, use_cache=args.use_cache)
                suruga_items = (suruga or {}).get("items", []) if suruga else []
                print(f"    suruga {len(suruga_items)}", flush=True)
                diff = compute_model_diff(yahoo_items, suruga_items, m["matchTokens"])
                for pa in diff["pairs"]:
                    all_pairs_debug.append({"model": model,
                                            "cost": pa["sourcing_cost"],
                                            "resale": pa["resale_price"],
                                            "diff_pct": round(pa["diff_rate"]*100, 1),
                                            "yahoo": pa["yahoo_title"][:44],
                                            "suruga": pa["suruga_title"][:34]})
                model_rows.append({
                    "model": model, "keyword": kw_y, "surugaKeyword": kw_s,
                    "yahoo_buynow": sum(1 for i in yahoo_items if _to_int(i.get("buyNowPrice"))),
                    "suruga_items": len(suruga_items),
                    "matched_pairs": diff["matched"],
                    "median_diff_pct": round(diff["median_diff"]*100, 1) if diff["median_diff"] is not None else "",
                    "max_diff_pct": round(diff["max_diff"]*100, 1) if diff["max_diff"] is not None else "",
                    "median_ge20": diff["median_ge20"], "max_ge30": diff["max_ge30"]})
                for pa in diff["pairs"]:
                    all_candidates.append({"model": model, "run_id": run_id,
                                           "yahoo_title": pa["yahoo_title"],
                                           "url": pa["url"], "postage": pa["postage"],
                                           "sourcing_cost": pa["sourcing_cost"],
                                           "resale_price": pa["resale_price"],
                                           "suruga_title": pa["suruga_title"],
                                           "source_url": pa["source_url"],
                                           "diff_pct": round(pa["diff_rate"]*100, 1)})

    asyncio.run(_run())

    tbl_path = args.data_dir / f"model_price_diff_{today}.csv"
    fields = list(model_rows[0].keys())
    with tbl_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(model_rows)

    # fee/shipping-stripped judgment (8% marketplace fee + 1000yen ship)
    FEE_RATE, SHIP = 0.08, 1000
    for c in all_candidates:
        net = c["resale_price"]*(1-FEE_RATE) - SHIP - c["sourcing_cost"]
        c["judgment_yen"] = round(net)
    cands = [c for c in all_candidates if c["judgment_yen"] > 0]
    cands.sort(key=lambda c: c["judgment_yen"], reverse=True)

    cand_csv = args.data_dir / f"sourcing_candidates_{today}.csv"
    cand_json = args.data_dir / f"sourcing_candidates_{today}.json"
    if cands:
        with cand_csv.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(cands[0].keys()))
            w.writeheader(); w.writerows(cands)
        cand_json.write_text(json.dumps({"run_id": run_id, "generatedAt":
                                         datetime.now(timezone.utc).isoformat(),
                                         "candidates": cands},
                                        ensure_ascii=False, indent=2), encoding="utf-8")

    if all_pairs_debug:
        with (args.data_dir / f"matched_pairs_{today}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(all_pairs_debug[0].keys()))
            w.writeheader(); w.writerows(all_pairs_debug)

    # ---- aggregate camerabench cross-check ----
    matched_rows = [r for r in model_rows if r["matched_pairs"] > 0]
    medians = [r["median_diff_pct"] for r in matched_rows if r["median_diff_pct"] != ""]
    overall_median = median(medians) if medians else None
    n_ge30 = sum(1 for r in matched_rows if r["max_ge30"])
    n_ge20 = sum(1 for r in matched_rows if r["median_ge20"])
    pct_ge30 = n_ge30/len(matched_rows)*100 if matched_rows else None
    pct_ge20 = n_ge20/len(matched_rows)*100 if matched_rows else None

    summary = {"run_id": run_id, "generatedAt": datetime.now(timezone.utc).isoformat(),
               "models": len(watch), "models_with_match": len(matched_rows),
               "total_sourcing_candidates_after_fees": len(cands),
               "model_median_diff_pct": overall_median,
               "pct_models_median_ge20": round(pct_ge20,1) if pct_ge20 is not None else None,
               "pct_models_max_ge30": round(pct_ge30,1) if pct_ge30 is not None else None,
               "camerabench_claim_median20": bool(overall_median is not None and overall_median >= 20),
               "camerabench_claim_third_30": bool(pct_ge30 is not None and pct_ge30 >= 30)}

    log_lines += [f"models_with_match : {len(matched_rows)}/{len(watch)}",
                  f"model_median_diff : {overall_median}% (claim ~20%)",
                  f"pct models max>=30%: {pct_ge30}% (claim ~1/3+)",
                  f"sourcing candidates after fees: {len(cands)}"]
    (args.data_dir / f"run_summary_{today}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.report_dir / f"camera_monitor_{today}.log").write_text("\n".join(log_lines)+"\n", encoding="utf-8")

    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"model table -> {tbl_path}")
    print(f"candidates  -> {cand_csv}/{cand_json} ({len(cands)} rows)")
    if cands:
        print("\n=== Top fee-stripped candidates ===")
        for c in cands[:10]:
            print(f"  +¥{c['judgment_yen']:,} [{c['model']}] {c['yahoo_title'][:34]} "
                  f"| 仕¥{c['sourcing_cost']:,}→売¥{c['resale_price']:,}")


if __name__ == "__main__":
    main()
