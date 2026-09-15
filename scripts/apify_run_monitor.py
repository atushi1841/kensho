#!/usr/bin/env python3
"""Apify actor 実行失敗を監視し、失敗していたら自動再実行する。

使い方:
    python3 scripts/apify_run_monitor.py              # 全actor監視
    python3 scripts/apify_run_monitor.py --actor MASK  # 指定actorのみ
    python3 scripts/apify_run_monitor.py --dry-run     # テストモード

結果:
    - 失敗runを検出 → 自動再実行（queue）
    - サマリーをstdoutに出力（cronからTelegramへ転送）
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

# === Path setup ===
# realpath: cron実行時はプロファイルscripts直下（実体またはsymlink）から起動されるため、
# __file__のabspathではリポジトリ.envに辿り着けない。symlink解決後に親でrepo rootを特定する。
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# === Config ===
APIFY_TOKEN = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT", "")
if not APIFY_TOKEN:
    # .env 探索: cron実行時はcwd非保証・profile実体コピー配置もあり得るため、
    # プロジェクト直下に加えてリポジトリ絶対パスも候補に持つ（QA run492推奨①）。
    for env_path in [
        os.path.join(PROJECT_DIR, ".env"),
        "/mnt/d/Project2/kensho/.env",
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                        APIFY_TOKEN = line.split("=", 1)[1].strip().strip("'\"").lstrip("\ufeff")
                        break
        if APIFY_TOKEN:
            break

API_BASE = "https://api.apify.com/v2"
FAILURE_WINDOW_HOURS = 24  # この時間内の失敗を監視
RETRY_LIMIT = 3  # 同actorの再试行上限
SCAN_DEADLINE_SECONDS = 240  # フルスキャンの実時間上限（cron script timeout内へ収める）
DRY_RUN = "--dry-run" in sys.argv


def get(path: str, token: str | None = None) -> dict | list:
    """Apify API GET リクエスト。pathにクエリが付いている場合は & で連結（401再発防止）。"""
    t = token or APIFY_TOKEN
    sep = "&" if "?" in path else "?"
    url = f"{API_BASE}{path}{sep}token={t}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    last_err: Exception | None = None
    for attempt in range(2):  # 一過性timeoutは1回だけ再試行（QA実測: urlopen error timed out）
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.URLError as e:
            if isinstance(e, urllib.error.HTTPError):
                raise
            last_err = e
            time.sleep(1.0)
    raise last_err  # type: ignore[misc]


def get_last_runs(actor_id: str, token: str | None = None, limit: int = 5) -> list[dict]:
    """actor の最新実行一覧を取得。data={total,count,items:[...]} 入れ子にも生listにも対応。"""
    try:
        data = get(f"/acts/{actor_id}/runs?desc=1&limit={limit}", token)
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                items = inner.get("items", [])
                return items if isinstance(items, list) else []
            return inner if isinstance(inner, list) else []
        return data if isinstance(data, list) else []
    except urllib.error.HTTPError as e:
        print(f"  [WARN] {actor_id}: runs fetch HTTP {e.code}", file=sys.stderr)
        return []


def is_failed(run: dict) -> bool:
    """実行が失敗/タイムアウトか判定。"""
    status = run.get("status", "").upper()
    return status in ("FAILED", "TIME_OUT", "ABORTED", "CRASHED")


def needs_retry(actor_id: str, token: str | None = None) -> tuple[bool, dict | None]:
    """このactorに再実行が必要か判定。重複防止込み。"""
    runs = get_last_runs(actor_id, token, limit=RETRY_LIMIT)
    if not runs:
        return False, None
    # 最新が成功していれば不要
    latest = runs[0]
    if latest.get("status", "").upper() == "SUCCEEDED":
        return False, None
    # 最新が失敗で、window内なら再実行
    started = latest.get("startedAt", "")
    if started:
        try:
            ts = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if datetime.now(UTC) - ts > timedelta(hours=FAILURE_WINDOW_HOURS):
                return False, None  # 古い失敗は放置
        except ValueError:
            pass
    return is_failed(latest), latest


def queue_run(actor_id: str, token: str | None = None, timeout_secs: int | None = None) -> dict:
    """actor をキューに追加して実行。timeout_secs を指定すると runs エンドポイントを使用し実行時にtimeoutを上書き。"""
    t = token or APIFY_TOKEN
    if timeout_secs is not None:
        url = f"{API_BASE}/acts/{actor_id}/runs?token={t}"
        data = json.dumps({"timeoutSecs": timeout_secs, "waitForFinish": 0}).encode("utf-8")
    else:
        url = f"{API_BASE}/acts/{actor_id}/builds?token={t}"
        data = json.dumps({"waitForFinish": 0}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # Actor一覧取得（公開アクター）
    target_arg = None
    for a in sys.argv[1:]:
        if a.startswith("--actor="):
            target_arg = a.split("=", 1)[1]

    if target_arg:
        actors = [{"id": target_arg, "name": target_arg}]
        # IDでなく名前の可能性を調査
        if not target_arg.startswith("act_"):
            try:
                data = get(f"/acts/{target_arg}")
                actors = [data.get("data", data) if isinstance(data, dict) else data]
            except urllib.error.HTTPError:
                pass
    else:
        data = get("/acts?limit=200")
        # Apify一覧は data={total,count,items:[...]} のページネング辞書（タスク一覧の生listと形が違う）
        inner = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(inner, dict):
            actors = inner.get("items", [])
        else:
            actors = inner if isinstance(inner, list) else []

    total = len(actors)
    failed_count = 0
    retried = []
    skipped = []
    errors = []

    print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] Apify monitor start — {total} actors")

    # 並列化: 81actor×(runs取得+sleep0.3) の逐次スキャンは6〜7分かかりcronのscript timeout（QA実測rc=124）に死ぬ。
    # ThreadPoolExecutor で判定を並列化し、全体deadline(300s)超過分は打ち切って部分結果を返す。
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if target_arg:
        todo = [a for a in actors if isinstance(a, dict) and target_arg in (a.get("id", ""), a.get("name", ""))]
    else:
        todo = [a for a in actors if isinstance(a, dict) and a.get("id")]

    deadline = time.monotonic() + SCAN_DEADLINE_SECONDS

    def check(actor: dict):
        actor_id = actor.get("id", "")
        name = actor.get("name", actor_id)
        try:
            need, _ = needs_retry(actor_id)
            return actor_id, name, need, None
        except urllib.error.HTTPError as e:
            return actor_id, name, False, f"{name}: HTTP {e.code}"
        except Exception as e:
            return actor_id, name, False, f"{name}: {e}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(check, a): a for a in todo}
        try:
            pending = as_completed(futures, timeout=SCAN_DEADLINE_SECONDS)
            while True:
                try:
                    fut = next(pending)
                except StopIteration:
                    break
                actor_id, name, need, err = fut.result()
                if err:
                    errors.append(err)
                    continue
                if not need:
                    skipped.append(name)
                    continue
                failed_count += 1
                if DRY_RUN:
                    print(f"  [DRY-RUN] Would retry: {name} ({actor_id})")
                    retried.append(name)
                else:
                    try:
                        # Determine timeout for MCP actors to avoid TIMED-OUT
                        timeout_secs = None
                        if actor_id == "57SNehd4cHNFyUCj3":  # japan-market-mcp
                            timeout_secs = 7200
                        elif actor_id == "RdCHlXHphoLsWnyhh":  # japan-fuel-price-mcp
                            timeout_secs = 600
                        result = queue_run(actor_id, timeout_secs=timeout_secs)
                        run_id = result.get("id", "?")
                        retried.append(f"{name}→run:{run_id[:8]}")
                        print(f"  [RETRY] {name}: queued run {run_id[:8]}")
                    except Exception as e:
                        errors.append(f"{name}: retry failed: {e}")
        except TimeoutError:
            pass  # deadline超過: 以下未処理分はWARNで報告

    if len(skipped) + len(retried) + len(errors) < len(todo) or time.monotonic() >= deadline:
        print(f"  [WARN] scan deadline hit: processed {len(skipped) + len(retried) + len(errors)}/{len(todo)}")

    # サマリー
    print("\n=== Apify Monitor Summary ===")
    print(f"Total: {total} | Retried: {len(retried)} | Skipped (ok): {len(skipped)} | Errors: {len(errors)}")
    if retried:
        print(f"Retried: {', '.join(retried[:20])}")
    if errors:
        print(f"Errors: {'; '.join(errors[:10])}")

    if DRY_RUN:
        print("\n[DRY-RUN MODE] No changes made.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
