#!/usr/bin/env python3
"""github_release_weekly.py — Weekly dataset release to GitHub Releases.

Creates a GitHub Release tagged weekly/<YEAR>-W<ISO_WEEK> and uploads the
normalized anime figure price CSV (compressed) as an asset.

Usage:
  python3 scripts/github_release_weekly.py            # dry-run
  python3 scripts/github_release_weekly.py --publish  # create release
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

REPO = "atushi1841/kensho"
CSV_PATH = Path("data/anime_figure_prices_normalized.csv")
API = f"https://api.github.com/repos/{REPO}/releases"


def iso_week_tag(today: date | None = None) -> str:
    """Return GitHub Release tag in weekly/<YEAR>-W<ISO_WEEK> format."""
    d = today or date.today()
    iso = d.isocalendar()
    return f"weekly/{iso[0]}-W{iso[1]:02d}"


def release_name(tag: str) -> str:
    """Human-readable release name from ISO week tag."""
    parts = tag.split("/")
    return f"Weekly Dataset {parts[1]}"


def read_csv_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    return path.read_bytes()


def gzip_bytes(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(data)
    return buf.getvalue()


def gh_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kensho-weekly-release/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"[ERR] GitHub API {method} {url} → HTTP {e.code}: {body}", file=sys.stderr)
        raise SystemExit(4) from e


def find_existing_release(token: str, tag: str) -> dict | None:
    try:
        data = gh_request("GET", f"{API}/tags/{tag}", token)
        return data if data.get("id") else None
    except SystemExit:
        return None


def create_release(token: str, tag: str, csv_gz: bytes) -> dict:
    body = f"Normalized anime figure price dataset — {len(csv_gz)} bytes gzipped."
    release = gh_request(
        "POST",
        API,
        token,
        {
            "tag_name": tag,
            "name": release_name(tag),
            "body": body,
            "prerelease": False,
            "draft": False,
        },
    )
    return release


def upload_asset(token: str, upload_url: str, filename: str, data: bytes) -> dict:
    url = f"{upload_url}?name={filename}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/gzip",
        "User-Agent": "kensho-weekly-release/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"[ERR] asset upload HTTP {e.code}: {body}", file=sys.stderr)
        raise SystemExit(5) from e


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    csv_path = repo_root / CSV_PATH

    ap = argparse.ArgumentParser(description="Weekly GitHub Release for anime figure dataset")
    ap.add_argument("--publish", action="store_true", help="Create the release (default: dry-run)")
    args = ap.parse_args()

    tag = iso_week_tag()
    filename = f"anime_figure_prices_{tag.replace('/', '_')}.csv.gz"

    print(f"[INFO] tag={tag} filename={filename}")
    print(f"[INFO] csv_path={csv_path} exists={csv_path.is_file()}")

    if not csv_path.is_file():
        print(f"[ERR] CSV not found at {csv_path}", file=sys.stderr)
        return 2

    raw = read_csv_bytes(csv_path)
    gz = gzip_bytes(raw)
    print(f"[INFO] raw={len(raw)}B gzipped={len(gz)}B")

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[WARN] GITHUB_TOKEN not set — cannot publish", file=sys.stderr)
        if args.publish:
            return 3
        print("[DRY-RUN] --publish 未指定のためリリースを作成しません")
        return 0

    if not args.publish:
        print("[DRY-RUN] --publish 未指定のためリリースを作成しません")
        return 0

    existing = find_existing_release(token, tag)
    if existing:
        print(f"[INFO] Release already exists: {existing.get('html_url')}")
        return 0

    release = create_release(token, tag, gz)
    print(f"[OK] Release created: {release.get('html_url')} (id={release.get('id')})")

    upload_url = release.get("upload_url", "").split("{")[0]
    asset = upload_asset(token, upload_url, filename, gz)
    print(f"[OK] Asset uploaded: {asset.get('name')} ({asset.get('size')}B) → {asset.get('browser_download_url')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())