#!/usr/bin/env python3
"""Deploy the Japan Anime Figure Demand Feature Vectors actor to Apify.

Implements the Apify Store PPE sales channel for the AI Agent Demand
Forecasting data product (see reports product spec t_f601390c).

Steps (all idempotent, safe to re-run):
  1. find-or-create the actor `japan-anime-figure-demand-features`
  2. upload version ``0.1`` as SOURCE_FILES (data included — same shape as the
     proven sibling deploy of `japan-anime-figure-price-data`)
  3. trigger a build and wait for SUCCEEDED
  4. set Pay-Per-Event pricing: $0.002 per default-dataset item
  5. publish (``isPublic: true``) so the actor is listed on the Apify Store
  6. read everything back and print a verification block

Usage:
    python3 scripts/deploy_feature_vector_actor.py [--no-publish] [--price 0.002]
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.apify.com/v2"
REPO_ROOT = Path("/mnt/d/Project2/kensho")
ACTOR_DIR = REPO_ROOT / "apify-figure-feature-vectors"
ACTOR_NAME = "japan-anime-figure-demand-features"
VERSION_NUMBER = "0.1"

#: Files pushed into the actor version. ``data/`` is included on purpose: the
#: container is self-contained and performs no network fetch at run time.
SKIP_PARTS = {"__pycache__", "tests", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc"}


def resolve_token() -> str:
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
    if token:
        return token.strip()
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(("APIFY_TOKEN_DEFAULT=", "APIFY_TOKEN=")):
                return line.split("=", 1)[1].strip().strip('"')
    sys.exit("ERROR: no Apify token (APIFY_TOKEN / APIFY_TOKEN_DEFAULT / .env all missing)")


TOKEN = resolve_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def request(path: str, body: object | None = None, method: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:1500]
        sys.exit(f"ERROR: HTTP {exc.code} {method or 'GET'} {path}\n{detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"ERROR: network failure at {path}: {exc.reason}")


def collect_source_files() -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(ACTOR_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ACTOR_DIR)
        if SKIP_PARTS.intersection(rel.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        files.append(
            {
                "name": str(rel),
                "content": base64.b64encode(path.read_bytes()).decode(),
                "format": "BASE64",
            }
        )
    return files


def find_actor() -> str | None:
    page = 1
    while page <= 20:
        listing = request(f"/acts?limit=1000&page={page}")["data"]
        for item in listing.get("items", []):
            if item.get("name") == ACTOR_NAME:
                return item["id"]
        if page * 1000 >= listing.get("total", 0):
            break
        page += 1
    return None


def ensure_actor() -> tuple[str, bool]:
    actor_id = find_actor()
    if actor_id:
        print(f"[1/6] found existing actor {actor_id}")
        return actor_id, True
    created = request("/acts", body={"name": ACTOR_NAME}, method="POST")["data"]
    print(f"[1/6] created actor {created['id']}")
    return created["id"], False


def upload_version(actor_id: str) -> dict:
    files = collect_source_files()
    total = sum(len(f["content"]) for f in files)
    print(f"[2/6] uploading {len(files)} source files ({total / 1e6:.2f} MB base64)")
    for f in files:
        print(f"        {f['name']} ({len(f['content'])} b64 chars)")
    payload = {
        "versionNumber": VERSION_NUMBER,
        "sourceType": "SOURCE_FILES",
        "sourceFiles": files,
        "buildTag": "latest",
    }
    version = request(f"/acts/{actor_id}/versions", body=payload, method="POST")["data"]
    print(f"        version {version.get('versionNumber')} created")
    return version


def build_and_wait(actor_id: str) -> dict:
    build = request(f"/acts/{actor_id}/builds", body={"versionNumber": VERSION_NUMBER, "tag": "latest", "useCache": False}, method="POST")["data"]
    build_id = build["id"]
    print(f"[3/6] build {build_id} started (version {build.get('versionNumber')})")
    deadline = time.time() + 1800
    status = build.get("status")
    while time.time() < deadline and status in ("READY", "RUNNING"):
        time.sleep(10)
        status = request(f"/actor-builds/{build_id}")["data"].get("status")
        print(f"        build status = {status}")
    final = request(f"/actor-builds/{build_id}")["data"]
    if final.get("status") != "SUCCEEDED":
        sys.exit(f"ERROR: build {build_id} ended with status={final.get('status')}")
    print(f"        build SUCCEEDED (buildNumber {final.get('buildNumber')})")
    return final


def build_pricing(price_usd: float) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        {
            "pricingModel": "PAY_PER_EVENT",
            "pricingPerEvent": {
                "actorChargeEvents": {
                    "apify-actor-start": {
                        "eventTitle": "Actor Start",
                        "eventDescription": (
                            "Charged when the Actor starts running. Number of events charged "
                            "depends on Actor memory (one event per GB, minimum one event)."
                        ),
                        "isOneTimeEvent": True,
                        "eventPriceUsd": 0.00005,
                    },
                    "apify-default-dataset-item": {
                        "eventTitle": "result",
                        "eventDescription": "Single result in the default dataset.",
                        "isOneTimeEvent": False,
                        "eventPriceUsd": price_usd,
                        "isPrimaryEvent": True,
                    },
                }
            },
            "apifyMarginPercentage": 0.2,
            "createdAt": now,
            "startedAt": now,
        }
    ]


def set_pricing_and_publish(actor_id: str, price_usd: float, publish: bool) -> dict:
    current = request(f"/acts/{actor_id}")["data"]
    existing = current.get("pricingInfos") or []
    pricing = build_pricing(price_usd)
    body: dict = {"pricingInfos": (existing + pricing) if existing else pricing}
    if publish:
        body["isPublic"] = True
    request(f"/acts/{actor_id}", body=body, method="PUT")
    print(f"[4/6] pricing appended (${price_usd}/item); [5/6] isPublic={'True' if publish else 'unchanged'}")
    return request(f"/acts/{actor_id}")["data"]


def read_back(actor_id: str, build: dict) -> dict:
    data = request(f"/acts/{actor_id}")["data"]
    pis = data.get("pricingInfos") or []
    latest = pis[-1] if pis else {}
    events = ((latest.get("pricingPerEvent") or {}).get("actorChargeEvents")) or {}
    record = {
        "actorId": actor_id,
        "name": data.get("name"),
        "isPublic": data.get("isPublic"),
        "defaultBuild": (data.get("defaultRunOptions") or {}).get("build"),
        "buildNumber": build.get("buildNumber"),
        "buildStatus": build.get("status"),
        "pricingModel": latest.get("pricingModel"),
        "datasetItemUsd": (events.get("apify-default-dataset-item") or {}).get("eventPriceUsd"),
        "startEventUsd": (events.get("apify-actor-start") or {}).get("eventPriceUsd"),
        "margin": latest.get("apifyMarginPercentage"),
    }
    print("[6/6] read-back verification")
    for key, value in record.items():
        print(f"        {key} = {value}")
    return record


def sync_dataset() -> None:
    """The 2 MB snapshot lives in the repo at data/ and is gitignored inside the
    actor dir. Copy it in before packing so the container stays self-contained."""
    target = ACTOR_DIR / "data" / "anime_figure_prices_normalized.jsonl"
    if target.exists():
        return
    source = REPO_ROOT / "data" / "anime_figure_prices_normalized.jsonl"
    if not source.exists():
        sys.exit(f"ERROR: dataset missing at both {target} and {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    print(f"        copied dataset {source.name} ({target.stat().st_size} bytes) into the actor package")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--price", type=float, default=0.002, help="USD per dataset item (default 0.002)")
    parser.add_argument("--no-publish", action="store_true", help="skip isPublic=true")
    parser.add_argument("--json-out", type=Path, default=None, help="write the verification record as JSON")
    args = parser.parse_args()

    if not ACTOR_DIR.exists():
        sys.exit(f"ERROR: actor dir not found: {ACTOR_DIR}")

    sync_dataset()
    actor_id, _existed = ensure_actor()
    upload_version(actor_id)
    build = build_and_wait(actor_id)
    read_back(actor_id, build)
    set_pricing_and_publish(actor_id, args.price, publish=not args.no_publish)
    record = read_back(actor_id, build)

    if args.json_out:
        args.json_out.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
