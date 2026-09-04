#!/usr/bin/env python3
"""apify_ppe_store_seo — v26-3: Apify Store description SEO最適化 + README充実（PPE課金5アクター）。

対応アクター（PPE=$0.005 で課金設定済、u30d=1 で3日以上停滞）:
  | key        | アクター名                          | Actor ID            |
  |------------|-------------------------------------|---------------------|
  | camera     | japan-used-camera-market-scraper    | mQaZFo6up4YZKepC3   |
  | watch      | japan-watch-market-scraper          | gMqdrS2evpcybSZc2   |
  | luxury     | japan-luxury-brand-market-scraper   | b0vuqa3ESvy2mOwFB   |
  | instrument | japan-used-instrument-market-scraper| yN1R26HrV6C2MBKas   |
  | offmall    | japan-offmall-market-scraper        | Zh4kqcS4dYPWpFzBd   |

背景（v18-B SEO 監査 / v14-C〜v15-A 一括テンプレーティングの後遺症）:
  1. luxury の description に "Updated for better discoverability." が2回付加
     され、300字で中途半端に切れて読める説明になっていない。
  2. instrument の title/seoTitle が63字制限で "…Comparison digi" のように
     切り詰められている（SEOターム "digimart" が欠落）。
  3. camera/watch/luxury/offmall は categories が ['ECOMMERCE'] のみ。
     Store 検索（AUTOMATION / DEVELOPER_TOOLS）で拾われない。
  4. 全5アクターの readme が空（readme_len=0）。

本スクリプトの仕事:
  - 各アクターに「Japanese二手中古価格データ」系のSEOキーワード
    （used / second-hand / pre-owned / resale arbitrage / 中古カメラ / 中古時計 /
    中古ブランド / 中古楽器 等）を含む title/seoTitle/seoDescription/description
    を適用。
  - categories を ['ECOMMERCE','AUTOMATION','DEVELOPER_TOOLS'] に統一。
  - readme を docs/apify-actors/README-<key>.md から読み込んで設定。
  - 上述の後遺症（luxuryの重複文案 / instrumentの切り詰め）を同時に修復。

★ README の重要制約（実測 2026-09-05）:
  公開 API の PUT /acts/{id}（UpdateActorRequest）には `readme` フィールドが
  無く、schema-validation で 400 になる。README はアクターのソース README.md
  からビルド時に生成される（read-only）。
  よって本スクリプトは README をライブ適用せず、docs/apify-actors/ に
  commitment 済みの「ソース再ビルド用の正式 README」として管理する。
  description/seoTitle/seoDescription/title/categories は API でライブ適用する。

使い方（デフォルト dry-run / 変更なし）:
  python3 scripts/apify_ppe_store_seo.py                # 全5アクターのdiff確認
  python3 scripts/apify_ppe_store_seo.py --actor camera # cameraのみ確認
  python3 scripts/apify_ppe_store_seo.py --apply        # 本実行（SEO+categories）
  python3 scripts/apify_ppe_store_seo.py --apply --actor watch

制約:
  - title ≤63 / seoTitle ≤60 / seoDescription ≤160 / description ≤300 / ≥3 categories
  - isPublic=true を維持（公開状態を落とさない）
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.apify.com/v2"
APP_NAME = "apify_ppe_store_seo"

# --- Apify schema 実制限（v14-C/v15-A で実測確認済） ---
CHAR_LIMITS = {"title": 63, "seoTitle": 60, "seoDescription": 160, "description": 300, "categories": 3}

# 全アクターに統一する discovery 用カテゴリ
CATEGORIES = ["ECOMMERCE", "AUTOMATION", "DEVELOPER_TOOLS"]

BASE_README = Path(__file__).resolve().parent.parent / "docs" / "apify-actors"


def _spec(key: str, actor_id: str, ppe: float) -> dict[str, Any]:
    """アクター別に title/seoTitle/seoDescription/description/readme_path を返す。"""
    s: dict[str, Any] = {"id": actor_id, "ppe": ppe, "categories": list(CATEGORIES)}
    if key == "camera":
        s.update(
            name="japan-used-camera-market-scraper",
            title="Japan Used Camera Prices — Kitamura, Fujiya, Map Camera",
            seoTitle="Japan Used Camera Price Data — Kitamura Fujiya Map Camera",
            seoDescription=(
                "Second-hand camera prices from Kitamura, Fujiya & Map Camera "
                "(キタムラ, フジヤカメラ, マップカメラ). Used 中古 prices, condition, model."
            ),
            description=(
                "Scrape Japan used camera market prices (中古カメラ) from Kitamura, Fujiya "
                "Camera and Map Camera. Get live second-hand prices, body & lens condition, "
                "brand/model data for resale arbitrage, cross-border sourcing and price "
                "research. Clean JSON, pay-per-event ($0.005/item), no proxy needed."
            ),
        )
    elif key == "watch":
        s.update(
            name="japan-watch-market-scraper",
            title="Japan Used Watch Prices — Jackroad, Kitamura, Komehyo",
            seoTitle="Japan Used Watch Price Data — Jackroad Kitamura Komehyo",
            seoDescription=(
                "Second-hand luxury watch prices from Jackroad, Kitamura & Komehyo "
                "(ジャックロード, キタムラ, コメ兵). Rolex, Omega, Grand Seiko used 中古時計."
            ),
            description=(
                "Second-hand luxury watch market data (中古時計) from Japan's trusted dealers "
                "Jackroad, Kitamura and Komehyo. Used Rolex, Omega, Grand Seiko prices with "
                "condition, model and reference for resale arbitrage and cross-shop price "
                "comparison. Clean JSON, pay-per-event ($0.005/item)."
            ),
        )
    elif key == "luxury":
        s.update(
            name="japan-luxury-brand-market-scraper",
            title="Japan Used Luxury Prices — Komehyo, Jackroad, Brand Off",
            seoTitle="Japan Luxury Resale Prices — Komehyo Jackroad Brand Off",
            seoDescription=(
                "Pre-owned luxury brand prices from Komehyo, Jackroad & Brand Off "
                "(コメ兵, ブランドオフ). Hermès, Chanel, Louis Vuitton used 中古ブランド bags."
            ),
            description=(
                "Japan pre-owned luxury brand price data (中古ブランド品) from Komehyo, "
                "Jackroad and Brand Off. Used Hermès, Chanel, Louis Vuitton, Goyard bags, "
                "wallets & watches with condition, year and authentication status for resale "
                "analysis and price monitoring. Pay-per-event ($0.005/item)."
            ),
        )
    elif key == "instrument":
        s.update(
            name="japan-used-instrument-market-scraper",
            title="Japan Used Instrument Prices — Digimart, Ishibashi",
            seoTitle="Japan Used Musical Instrument Prices — Digimart Ishibashi",
            seoDescription=(
                "Second-hand musical instrument prices from Digimart & Ishibashi U-BOX "
                "(島村楽器, 石橋楽器). Used guitars, basses, synths 中古楽器 for resale."
            ),
            description=(
                "Japan's used musical instrument market (中古楽器) from Digimart and Ishibashi "
                "Music. Second-hand guitar, bass, synthesizer and pro-audio prices with model & "
                "condition for resale arbitrage and price monitoring. Clean JSON output, "
                "pay-per-event ($0.005/item)."
            ),
        )
    elif key == "offmall":
        s.update(
            name="japan-offmall-market-scraper",
            title="Japan Used Goods Prices — Hard Off OffMall Store",
            seoTitle="Japan Used Goods Price Data — Hard Off OffMall",
            seoDescription=(
                "Used goods prices from Hard Off OffMall (ハードオフ, オフモール) official "
                "store — cameras, watches, instruments, luxury, electronics across 800+ stores."
            ),
            description=(
                "Used goods price data from Hard Off OffMall (ハードオフ/オフモール), Japan's "
                "second-hand chain official online store. Used cameras, watches, instruments, "
                "luxury brands, smartphones & game consoles with condition and price. "
                "Pay-per-event ($0.005/item), daily snapshots."
            ),
        )
    else:
        raise ValueError(f"unknown key: {key}")
    s["readme_path"] = BASE_README / f"README-{key}.md"
    return s


SPECS: dict[str, dict[str, Any]] = {
    key: _spec(
        key,
        {
            "camera": "mQaZFo6up4YZKepC3",
            "watch": "gMqdrS2evpcybSZc2",
            "luxury": "b0vuqa3ESvy2mOwFB",
            "instrument": "yN1R26HrV6C2MBKas",
            "offmall": "Zh4kqcS4dYPWpFzBd",
        }[key],
        0.005,
    )
    for key in ("camera", "watch", "luxury", "instrument", "offmall")
}


# ----------------------------------------------------------------------------- validate


def validate_spec(spec: dict[str, Any]) -> list[str]:
    """文字数/カテゴリ/README存在 の違反を列挙（pure、テスト対象）。超過は問答無用に返す。"""
    problems: list[str] = []
    key = spec["name"]
    for field, lim in CHAR_LIMITS.items():
        if field == "categories":
            cats = spec.get("categories")
            if len(cats or []) > lim:
                problems.append(f"{key}: categories={len(cats or [])} > {lim}")
            continue
        val = spec.get(field)
        if isinstance(val, str) and len(val) > lim:
            problems.append(f"{key}: {field}={len(val)} > {lim}")
    # 破損マーカー（後遺症）を許さない
    desc = spec.get("description", "")
    if "Updated for better discoverability" in desc:
        problems.append(f"{key}: description contains junk suffix")
    if "…Comparison d" in spec.get("title", "") or "digi" in spec.get("title", ""):
        problems.append(f"{key}: title contains truncated keyword remnant")
    readme = spec.get("readme_path")
    if not (isinstance(readme, Path) and readme.exists() and readme.read_text(encoding="utf-8").strip()):
        problems.append(f"{key}: readme missing or empty ({readme})")
    return problems


def validate_all() -> list[str]:
    out: list[str] = []
    for key, spec in SPECS.items():
        for p in validate_spec(spec):
            out.append(p)
    return out


# ----------------------------------------------------------------------------- api


def _token() -> str:
    tok = os.environ.get("APIFY_TOKEN")
    if not tok:
        sys.exit("APIFY_TOKEN environment variable is required")
    return tok


def _get(path: str) -> dict:
    req = urllib.request.Request(API_BASE + path, headers={"Authorization": f"Bearer {_token()}"}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _put(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"PUT {path} HTTP {e.code}: {msg[:300]}") from None


# ----------------------------------------------------------------------------- diff / apply


def meta_diff(spec: dict[str, Any], current: dict) -> dict[str, tuple[Any, Any]]:
    """spec が current と異なるフィールドを {name: (current, proposed)} で返す。"""
    diffs: dict[str, tuple[Any, Any]] = {}
    mapping = {
        "title": "title",
        "seoTitle": "seoTitle",
        "seoDescription": "seoDescription",
        "description": "description",
        "categories": "categories",
    }
    for spec_field, api_field in mapping.items():
        cur = current.get(api_field)
        want = spec[spec_field]
        if cur != want:
            diffs[api_field] = (cur, want)
    return diffs


def apply_meta(spec: dict[str, Any], current: dict, diffs: dict[str, tuple[Any, Any]]) -> None:
    payload = {k: v[1] for k, v in diffs.items()}
    payload["isPublic"] = current.get("isPublic", True)
    _put("/acts/" + spec["id"], payload)


def readme_artifact(spec: dict[str, Any]) -> dict[str, Any]:
    """README は API 適用不可のため「ソース再ビルド用リポジトリ成果物」として報告する。"""
    path = spec["readme_path"]
    return {
        "path": str(path),
        "exists": bool(path.exists()),
        "chars": len(path.read_text(encoding="utf-8")) if path.exists() else 0,
        "live_readme": "read-only via API — requires actor source rebuild",
    }


def process(key: str, apply: bool, out: dict) -> None:
    spec = SPECS[key]
    d = _get("/acts/" + spec["id"])["data"]
    rec: dict[str, Any] = {"name": spec["name"], "id": spec["id"], "isPublic": d.get("isPublic")}
    mdiff = meta_diff(spec, d)
    rec["meta_diffs"] = list(mdiff.keys())
    rec["readme"] = readme_artifact(spec)
    if apply and mdiff:
        apply_meta(spec, d, mdiff)
        rec["meta_applied"] = list(mdiff.keys())
    out["actors"][key] = rec


def _result_path() -> Path:
    return Path("reports") / "apify-ppe-store-seo" / f"{APP_NAME}-{_dt.date.today():%Y-%m-%d}.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--actor", choices=list(SPECS.keys()), help="対象アクター（省略時は全5件）")
    ap.add_argument("--apply", action="store_true", help="本実行（dry-run＝diff確認のみ）")
    args = ap.parse_args()

    problems = validate_all()
    if problems:
        print("VALIDATION FAILED — refusing to run:")
        for p in problems:
            print(f"  ! {p}")
        sys.exit(2)

    keys = [args.actor] if args.actor else list(SPECS.keys())
    out = {"count": 0, "applied": args.apply, "actors": {}}
    for k in keys:
        try:
            process(k, args.apply, out)
        except Exception as e:  # noqa: BLE001
            out["actors"][k] = {"name": SPECS[k]["name"], "error": str(e)}
    out["count"] = len(keys)

    pf = _result_path()
    pf.parent.mkdir(parents=True, exist_ok=True)
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"summary: {out['count']} actor(s) processed (apply={args.apply}); result JSON: {pf}")
    for k, rec in out["actors"].items():
        if "error" in rec:
            print(f"  {k:12s} ERROR: {rec['error']}")
            continue
        diffs = rec.get("meta_diffs") or []
        rd = rec.get("readme") or {}
        status = f"readme_artifact_exists={rd.get('exists')} chars={rd.get('chars')} ({rd.get('live_readme')})"
        print(
            f"  {k:12s} {rec['name']}  public={rec['isPublic']} meta_diff={diffs} {status}"
            + (f"  APPLIED_meta={rec.get('meta_applied')}" if args.apply else "")
        )


if __name__ == "__main__":
    main()
