#!/usr/bin/env python3
"""scripts/actor_weekly_run.py — Apify Actor週次自動実行結果をX/dev.toで公開。

設計:
  - 上位PPEアクターを週1回自動実行し、run結果(runId, status, datasetId)を取得
  - 結果をX(@atushi16)へ投稿: tweet_devto.py 同様 x_post_driver.js + CDP 経路
  - 結果をdev.to記事としても週1投稿（既存 pipeline 経路）
  - dedup: data/actor_weekly_run_state.json に ISO 週キー保存

使い方:
  python3 scripts/actor_weekly_run.py                  # 週次実行（同週済みならスキップ）
  python3 scripts/actor_weekly_run.py --dry-run        # 投稿せず実行内容を表示
  python3 scripts/actor_weekly_run.py --force          # 週次dedupを無視
  python3 scripts/actor_weekly_run.py --slot a         # スロット指定（a=月曜/b=金曜）
  python3 scripts/actor_weekly_run.py --max 1          # 最大1アクター（既定2）

退出コード:
  0=実行/スキップ(正常)  2=dry-run  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, UTC
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "scripts"
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "actor_weekly_run_state.json"
WIN_TEMP = Path("/mnt/c/temp")
X_DRIVER_JS = SCRIPTS_DIR / "x_post_driver.js"

# Apify API
APIFY_API = "https://api.apify.com/v2"
ACCOUNT_NAME = "fruitful_quintessence"

# 週次投稿スロット（BOT検知回避のため月曜↔金曜で4日間隔）
SLOTS: tuple[str, ...] = ("a", "b")

# 実行対象アクター（優先度順、価格/人気で選定）
PRIORITY_ACTORS: list[dict[str, Any]] = [
    {"name": "mandarake-auction-scraper", "id": "q2E37PVTg5JcGOTEn", "priority": 1},
    {"name": "japan-offmall-market-scraper", "id": "Zh4kqcS4dYPWpFzBd", "priority": 1},
    {"name": "mercari-japan-search-scraper", "id": "whSePszWpMtfeLYBp", "priority": 1},
    {"name": "japan-used-camera-market-scraper", "id": "mQaZFo6up4YZKepC3", "priority": 2},
    {"name": "yahoo-auctions-japan-scraper", "id": "8WBam4CPB72q9Rvsd", "priority": 2},
]

# X 投稿テンプレート（自然な日本語）
TWEET_TEMPLATES: list[dict[str, str]] = [
    {
        "success": (
            "「{actor_name}」を走らせてみました！\n"
            "{run_count}件のデータを取得（runId: {run_id}）\n"
            "→ https://apify.com/{account}/{actor_name}\n\n"
            "#Apify #スクレイピング #データ収集"
        ),
        "queued": (
            "「{actor_name}」の実行を起動しました（runId: {run_id}）\n"
            "完了までしばらくお待ちを → https://apify.com/{account}/{actor_name}\n\n"
            "#Apify #automation #scraping"
        ),
        "failed": (
            "「{actor_name}」の実行が失敗しました（runId: {run_id}）\n"
            "原因: {error}\n"
            "→ https://apify.com/{account}/{actor_name}\n\n"
            "#Apify #debug"
        ),
    },
    {
        "success": (
            "Japan market data update:\n"
            "{actor_name} → {run_count} items\n"
            "Run ID: {run_id}\n"
            "https://apify.com/{account}/{actor_name}\n\n"
            "#apify #japan #data"
        ),
        "queued": (
            "Running {actor_name} on Apify...\n"
            "Run ID: {run_id}\n"
            "Status: QUEUED\n"
            "https://apify.com/{account}/{actor_name}\n\n"
            "#apify #automation"
        ),
        "failed": (
            "{actor_name} failed on Apify\n"
            "Run ID: {run_id}\n"
            "Error: {error}\n"
            "https://apify.com/{account}/{actor_name}\n\n"
            "#apify #error"
        ),
    },
]


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W42）。"""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _load_token() -> str:
    """Apifyトークンを.env/環境変数から取得。"""
    tok = os.environ.get("APIFY_TOKEN", "").strip() or os.environ.get(
        "APIFY_TOKEN_DEFAULT", ""
    ).strip()
    if not tok:
        env_path = REPO / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line.startswith(("APIFY_TOKEN=", "APIFY_TOKEN_DEFAULT=")):
                    tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if tok:
                        break
    return tok


def api_get(path: str, token: str) -> dict:
    """Apify API GET（Authorizationヘッダ使用）。"""
    url = f"{APIFY_API}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(path: str, payload: dict, token: str) -> dict:
    """Apify API POST（Authorizationヘッダ使用）。"""
    url = f"{APIFY_API}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_actor_id(token: str, name: str, fallback_id: str) -> str:
    """API名からactor_idを取得（失敗時はfallback）。"""
    try:
        resp = api_get(f"/acts?my=true&limit=200", token)
        for it in resp.get("data", {}).get("items", []):
            if it.get("name") == name:
                return it.get("id") or fallback_id
    except Exception:
        pass
    return fallback_id


def run_actor(actor_id: str, token: str, dry_run: bool = False) -> dict[str, Any]:
    """1アクターのrunをトリガー。結果を返す。"""
    result = {"actor_id": actor_id, "triggered": False, "run_id": None, "status": None, "error": None, "dataset_id": None}
    if dry_run:
        result["triggered"] = True
        result["run_id"] = "DRY-RUN"
        result["status"] = "DRY_RUN"
        return result
    try:
        resp = api_post(f"/acts/{actor_id}/runs", {"waitForFinish": 0}, token)
        body = resp.get("data", resp) if isinstance(resp, dict) else {}
        run_id = str(body.get("id") or "")
        status = str(body.get("status", "")).lower()
        dataset_id = body.get("defaultDatasetId") or body.get("data", {}).get("defaultDatasetId")
        result["triggered"] = bool(run_id and run_id != "?")
        result["run_id"] = run_id
        result["status"] = status or "QUEUED"
        result["dataset_id"] = dataset_id
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def pick_actors(actors: list[dict], state: dict, max_pick: int = 2) -> list[dict]:
    """未投稿アクターを max_pick 件ランダム選択。"""
    posted_keys: set[str] = set()
    for wk, slots in state.get("posted_weeks", {}).items():
        for sl, info in slots.items():
            for rid in info.get("run_ids", []):
                posted_keys.add(rid)

    available = []
    for act in actors:
        aid = act.get("id") or act.get("actor_id")
        if aid in posted_keys:
            continue
        available.append(act)

    random.shuffle(available)
    return available[:max_pick]


def generate_tweet(result: dict, actor_name: str) -> str:
    """run結果からtweet本文を生成。"""
    account = ACCOUNT_NAME
    run_id = result.get("run_id") or "?"
    status = result.get("status") or "unknown"
    error = result.get("error") or ""

    if status == "DRY_RUN":
        cat = "queued"
    elif result.get("error"):
        cat = "failed"
    else:
        cat = "success"

    template_pool = TWEET_TEMPLATES[random.randint(0, len(TWEET_TEMPLATES) - 1)]
    tmpl = template_pool.get(cat, template_pool["success"])
    text = tmpl.format(
        actor_name=actor_name, run_id=run_id[:8] if run_id else "?",
        account=account, run_count=result.get("dataset_id", ""), error=error[:50],
    )
    if len(text) > 280:
        text = text[:277] + "…"
    return text


def post_via_cdp(text: str, log_fn: Any) -> str:
    """Windows Chrome + CDP で X へ投稿。"""
    if not X_DRIVER_JS.exists():
        raise RuntimeError(f"driver が見つからない: {X_DRIVER_JS}")
    WIN_TEMP.mkdir(parents=True, exist_ok=True)
    (WIN_TEMP / "x_body.txt").write_text(text, encoding="utf-8")
    shutil.copyfile(X_DRIVER_JS, WIN_TEMP / "x_post_driver.js")
    out_json = WIN_TEMP / "x_post_out.json"
    if out_json.exists():
        out_json.unlink()

    log_fn("Windows Chrome + CDP 経路で投稿します")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "cd C:\\\\temp; node x_post_driver.js x_body.txt C:\\\\temp\\\\x_post_out.json"],
            capture_output=True, text=True, timeout=420,
        )
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-5:]
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"CDP タイムアウト: {e}") from e

    if not out_json.exists():
        raise RuntimeError(f"driver が結果を書かなかった: {tail}")
    res = json.loads(out_json.read_text(encoding="utf-8"))
    tweet_id = str(res.get("tweet_id") or "")
    if not tweet_id.isdigit():
        status = res.get("status", "unknown")
        raise RuntimeError(f"実IDが取れなかった (status={status}, log={tail})")
    log_fn(f"投稿成功: tweet_id={tweet_id} permalink={res.get('permalink', '')}")
    return tweet_id


def post_to_devto(title: str, body_markdown: str, token: str, log_fn: Any) -> str:
    """dev.to へ記事を投稿。結果として URL を返す。"""
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
    payload = json.dumps({
        "article": {"title": title, "body_markdown": body_markdown,
                    "tags": ["apify", "scraping", "data"], "published": True},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://dev.to/api/articles", data=payload, method="POST",
        headers={"Api-Key": token, "Content-Type": "application/json",
                 "User-Agent": ua, "Accept": "application/vnd.forem.api-v1+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        art = data.get("article", data)
        url = art.get("url") or ""
        log_fn(f"dev.to 投稿成功: {url}")
        return url
    except Exception as e:
        raise RuntimeError(f"dev.to 投稿失敗: {e}") from e


def build_devto_article(actor_name: str, result: dict) -> tuple[str, str]:
    """dev.to 用記事タイトル+本文を生成。"""
    run_id = result.get("run_id") or "?"
    status = result.get("status") or "unknown"
    dataset_id = result.get("dataset_id") or ""
    error = result.get("error") or ""

    title = f"Apify Actor Weekly Run: {actor_name} — {status.upper()}"
    body = f"""## Run Summary

- **Actor**: [{actor_name}](https://apify.com/{ACCOUNT_NAME}/{actor_name})
- **Run ID**: `{run_id}`
- **Status**: {status}
"""
    if dataset_id:
        body += f"- **Dataset ID**: `{dataset_id}`\n"
    if error:
        body += f"- **Error**: {error}\n"

    body += f"""
## What's Next

This is an automated weekly run to keep our Apify actors active and visible.
Run results are posted to [X (@atushi16)](https://x.com/atushi16) as well.

---
*Auto-generated by kensho project — Apify actor weekly visibility pipeline*
"""
    return title, body


def main() -> None:
    ap = argparse.ArgumentParser(description="Apify Actor週次自動実行結果をX/dev.toで公開")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--slot", default="a", choices=["a", "b"], help="投稿スロット（a=月曜/b=金曜）")
    ap.add_argument("--max", type=int, default=2, help="1回あたりの最大実行アクター数")
    args = ap.parse_args()

    def log(msg: str) -> None:
        line = f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        log_dir = REPO / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "actor_weekly_run.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # 1. API キー取得
    token = _load_token()
    if not token and not args.dry_run:
        log("ERROR: APIFY_TOKEN が見つかりません（.env または環境変数）。")
        sys.exit(1)
    masked = token[:4] + "...[REDACTED]" + token[-4:] if len(token) > 8 else "[REDACTED]"
    log(f"Apify API token: {masked}")

    # 2. アクター解決
    resolved = []
    for act in PRIORITY_ACTORS:
        aid = resolve_actor_id(token, act["name"], act["id"])
        resolved.append({"name": act["name"], "id": aid, "priority": act["priority"]})
    resolved.sort(key=lambda x: x["priority"])
    log(f"対象アクター: {len(resolved)}件")

    # 3. state 読み込み・未投稿アクター絞り込み
    state = _load_json(STATE_FILE)
    today = date.today()
    key = week_key(today)

    picked = pick_actors(resolved, state, max_pick=args.max)
    if not picked:
        log("未投稿アクターなし（全アクター既に投稿済み）。スキップ。")
        sys.exit(0)
    log(f"対象アクター: {len(picked)}件 / 週={key} / slot={args.slot}")
    for i, act in enumerate(picked):
        log(f"  [{i+1}] {act['name']} → {act['id']}")

    if args.dry_run:
        for i, act in enumerate(picked):
            result = run_actor(act["id"], token, dry_run=True)
            txt = generate_tweet(result, act["name"])
            log(f"DRY-RUN actor[{i+1}]: {act['name']} → run={result['run_id']} tweet[{len(txt)}chars]: {txt!r}")
        log("DRY-RUN: 投稿は実行していません。")
        sys.exit(2)

    # 4. 実行・投稿（ランダム遅延付き）
    state.setdefault("posted_weeks", {})
    week_slot = state["posted_weeks"].setdefault(key, {})
    if args.force or args.slot not in week_slot:
        for i, act in enumerate(picked):
            log(f"実行[{i+1}/{len(picked)}]: {act['name']}...")
            result = run_actor(act["id"], token, dry_run=False)
            log(f"  status={result.get('status')} run_id={result.get('run_id')} error={result.get('error')}")

            # X 投稿
            txt = generate_tweet(result, act["name"])
            log(f"Xtweet({len(txt)}chars): {txt[:100]}...")
            try:
                tweet_id = post_via_cdp(txt, log)
            except Exception as e:
                log(f"ERROR: X投稿失敗: {e}")
                sys.exit(1)

            # dev.to 投稿
            devto_title, devto_body = build_devto_article(act["name"], result)
            devto_token = os.environ.get("DEVTO_API_KEY", "")
            if not devto_token:
                env_path = REPO / ".env"
                if env_path.is_file():
                    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                        line = line.strip()
                        if line.startswith("DEVTO_API_KEY="):
                            devto_token = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            devto_url = ""
            if devto_token and len(devto_token) >= 8:
                try:
                    devto_url = post_to_devto(devto_title, devto_body, devto_token, log)
                except Exception as e:
                    log(f"WARN: dev.to投稿失敗: {e}")
            else:
                log("WARN: DEVTO_API_KEY 未設定 → dev.to投稿スキップ")

            # state更新
            if args.slot not in week_slot:
                week_slot[args.slot] = {}
            week_slot[args.slot][act["id"]] = {
                "run_id": result.get("run_id"),
                "status": result.get("status"),
                "dataset_id": result.get("dataset_id"),
                "error": result.get("error"),
                "tweet_id": tweet_id,
                "devto_url": devto_url,
                "posted_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "date": today.isoformat(),
                "slot": args.slot,
            }
            # BOT検知回避遅延（3〜8秒）
            if i < len(picked) - 1:
                delay = random.uniform(3.0, 8.0)
                log(f"  BOT検知回避: {delay:.1f}s 待機")
                time.sleep(delay)
    else:
        log(f"WARN: slot={args.slot} は既に今週投稿済み（forceなし）。スキップ。")
        sys.exit(0)

    # 5. state保存
    _save_json(STATE_FILE, state)
    log(f"状態記録: {STATE_FILE}")
    log(f"完了: {key}/{args.slot} に {len(picked)} 件実行・投稿")


if __name__ == "__main__":
    main()
