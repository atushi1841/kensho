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
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

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

# t_cdcfc7aa: MCP常駐actor（名前に -mcp を含むサーバー型）は通常runだと必ず
# TIMED-OUT → Apifyエラーメールの再発源。自動再試行せず監視のみでskippingする。
MCP_RESIDENT_SUFFIX = "-mcp"

# t_apify_noret r41: 必須入力が無いrunは必ずFAILED → 自動再試行のたびに
# Apifyエラーメールが再送される「メール多発」源。かつself-runはexternal runに
# 計上されず収益は永久に$0のため、再試行する意味が無い。監視のみでスキップする。
#   8WBam4CPB72q9Rvsd yahoo-auctions-japan-scraper : searchKeywords 必須（無入力→FAILED）
#   wxMskoiHMPeeH2qAJ tackleberry-japan-fishing-... : keyword 必須
#   rIZ3NSg5Ul34PgpYx japan-corporate-numbers      : exampleInputが helloWorld プレースホルダ（実装未完了・exitCode91）
NO_AUTO_RETRY_ACTOR_IDS = {
    "8WBam4CPB72q9Rvsd",
    "wxMskoiHMPeeH2qAJ",
    "rIZ3NSg5Ul34PgpYx",
}

# 実行時timeout上書き（5f32176由来。常駐型の誤再試行時に備え残す）
RETRY_TIMEOUT_OVERRIDES = {
    "57SNehd4cHNFyUCj3": 7200,  # japan-market-mcp
    "RdCHlXHphoLsWnyhh": 600,  # japan-fuel-price-mcp
}


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


def check_apify_health() -> dict:
    """Apify API健康度チェック。404/token失効を検出してリカバリ提案を返す。"""
    t = APIFY_TOKEN
    if not t:
        return {"status": "down", "error": "APIFY_TOKEN未設定", "http_code": 0}
    url = f"{API_BASE}/acts?my=true&token={t}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.status
            if code == 200:
                return {"status": "ok", "http_code": 200, "error": None}
            elif code == 404:
                return {
                    "status": "degraded",
                    "http_code": 404,
                    "error": "404: token失効/endpoint変更",
                    "recovery": "token再発行またはRapidAPIへ切替",
                }
            elif code == 401:
                return {
                    "status": "degraded",
                    "http_code": 401,
                    "error": "401: トークン無効",
                    "recovery": "APIFY_TOKEN再設定",
                }
            else:
                return {"status": "degraded", "http_code": code, "error": f"HTTP {code}"}
    except urllib.error.HTTPError as e:
        code = e.code if hasattr(e, "code") else 0
        if code == 404:
            return {
                "status": "degraded",
                "http_code": 404,
                "error": "404: token失効/endpoint変更",
                "recovery": "token再発行またはRapidAPIへ切替",
            }
        return {"status": "degraded", "http_code": code, "error": f"HTTPError {code}"}
    except Exception as e:
        return {"status": "down", "http_code": 0, "error": f"{type(e).__name__}: {e}"}


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


def queue_run(actor_id: str, token: str | None = None, timeout_secs: int | None = None) -> dict[str, Any]:
    """actor を再実行（run 再生成）。

    t_cdcfc7aa ギャップ統一: 旧実装は timeout 未指定時に /builds だけを再トリガしていたため、
    「最新runがFAILED」検出に対してrunが再生成されず実効ゼロ（旧broken buildの再実行ループ）。
    /runs エンドポイントへ統一し、timeoutSecs は任意上書きとして同じ経路で渡す。
    """
    t = token or APIFY_TOKEN
    url = f"{API_BASE}/acts/{actor_id}/runs?token={t}"
    payload: dict[str, Any] = {"waitForFinish": 0}
    if timeout_secs is not None:
        payload["timeoutSecs"] = timeout_secs
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_resident_mcp(name: str, actor_id: str = "") -> bool:
    """MCP常駐（サーバー型）actorか。通常runだと必ずTIMED-OUTになりApifyエラーメールの再発源
    （t_cdcfc7aa実測: japan-market-mcp 9/12 22:13 TIMED-OUT、opts_timeout=None）。自動再試行対象外。"""
    return name.endswith(MCP_RESIDENT_SUFFIX) or actor_id in RETRY_TIMEOUT_OVERRIDES


# --- retry budget (RETRY_LIMITのwindow内実カウント) -----------------------
# 旧実装は RETRY_LIMIT を「取得run数」にしか使っておらず、失敗が継続するactorを24h窓で毎回
# 再試行し続けていた（上限3の意図と不一致）。stateファイルで実试行数を刻み上限を強制する。


def state_path() -> str:
    return os.environ.get("APIFY_MONITOR_STATE") or os.path.join(PROJECT_DIR, "data", "apify_monitor_state.json")


def load_state() -> dict[str, list[str]]:
    try:
        with open(state_path()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, list[str]]) -> None:
    p = state_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def prune_attempts(entries: list[str], hours: int = FAILURE_WINDOW_HOURS) -> list[str]:
    now = datetime.now(UTC)
    out = []
    for iso in entries or []:
        try:
            ts = datetime.fromisoformat(str(iso))
        except ValueError:
            continue
        if now - ts <= timedelta(hours=hours):
            out.append(str(iso))
    return out


def retry_allowed(state: dict[str, list[str]], actor_id: str) -> bool:
    return len(prune_attempts(state.get(actor_id, []))) < RETRY_LIMIT


def record_retry(state: dict[str, list[str]], actor_id: str) -> None:
    state[actor_id] = prune_attempts(state.get(actor_id, [])) + [datetime.now(UTC).isoformat()]


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
    resident_skipped = []
    no_input_skipped = []
    budget_exhausted = []

    print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] Apify monitor start — {total} actors")

    # 並列化: 81actor×(runs取得+sleep0.3) の逐次スキャンは6〜7分かかりcronのscript timeout（QA実測rc=124）に死ぬ。
    # ThreadPoolExecutor で判定を並列化し、全体deadline(300s)超過分は打ち切って部分結果を返す。
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if target_arg:
        todo = [a for a in actors if isinstance(a, dict) and target_arg in (a.get("id", ""), a.get("name", ""))]
    else:
        todo = [a for a in actors if isinstance(a, dict) and a.get("id")]

    deadline = time.monotonic() + SCAN_DEADLINE_SECONDS
    state = load_state()
    state_lock = threading.Lock()

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
                # MCP常駐actorは通常runだと必ずTIMED-OUT（=Apifyエラーメール再発源）。
                # 自動再試行せず観測のみでスキップ（t_cdcfc7aa）。
                if is_resident_mcp(name, actor_id):
                    resident_skipped.append(name)
                    continue
                # 必須入力の無いrunは必ずFAILED（=Apifyエラーメール再発源）。
                # self-runはexternal runに計上されず収益ゼロのため再試行しない（t_apify_noret）。
                if actor_id in NO_AUTO_RETRY_ACTOR_IDS:
                    no_input_skipped.append(name)
                    continue
                # RETRY_LIMIT実効化: 24h窓で既に上限回数再試行済みなら打ち切り
                with state_lock:
                    allowed = retry_allowed(state, actor_id)
                if not allowed:
                    budget_exhausted.append(name)
                    continue
                failed_count += 1
                if DRY_RUN:
                    print(f"  [DRY-RUN] Would retry: {name} ({actor_id})")
                    retried.append(name)
                else:
                    try:
                        result = queue_run(actor_id, timeout_secs=RETRY_TIMEOUT_OVERRIDES.get(actor_id))
                        # Apify POST /runs の応答は {"meta":..,"data":{...}} 入れ子（旧実装は最上位getで常に'?'）
                        body = result.get("data", result) if isinstance(result, dict) else {}
                        run_id = str(body.get("id") or "?")
                        # 無料クレジット枯渇(402等)でrunがqueued/prompt扱いになった場合は
                        # リトライを打ち切って【要ユーザー対応】を明示する（t_cdcfc7aa）
                        status = str(body.get("status", "")).lower()
                        if run_id == "?" and status in ("quota-exceeded", "paused"):
                            errors.append(
                                f"{name}: Apify quota state={status} 【要ユーザー対応: FREEクレジット枯渇の可能性】"
                            )
                            continue
                        retried.append(f"{name}→run:{run_id[:8]}")
                        print(f"  [RETRY] {name}: queued run {run_id[:8]}")
                        with state_lock:
                            record_retry(state, actor_id)
                            save_state(state)
                    except urllib.error.HTTPError as e:
                        if e.code == 402:
                            errors.append(
                                f"{name}: HTTP 402 quota exceeded 【要ユーザー対応: FREE枠上限、リトライ抑止】"
                            )
                        else:
                            errors.append(f"{name}: retry failed: HTTP {e.code}")
                    except Exception as e:
                        errors.append(f"{name}: retry failed: {e}")
        except TimeoutError:
            pass  # deadline超過: 以下未処理分はWARNで報告

    processed_total = len(skipped) + len(retried) + len(errors) + len(resident_skipped) + len(no_input_skipped) + len(budget_exhausted)
    if processed_total < len(todo) or time.monotonic() >= deadline:
        print(f"  [WARN] scan deadline hit: processed {processed_total}/{len(todo)}")

    # サマリー
    print("\n=== Apify Monitor Summary ===")
    print(f"Total: {total} | Retried: {len(retried)} | Skipped (ok): {len(skipped)} | Errors: {len(errors)}")
    if resident_skipped:
        print(f"Resident-MCP skipped (no auto-retry): {', '.join(resident_skipped[:20])}")
    if no_input_skipped:
        print(f"Requires-input skipped (no auto-retry): {', '.join(no_input_skipped[:20])}")
    if budget_exhausted:
        print(f"Retry-budget exhausted ({RETRY_LIMIT}/{FAILURE_WINDOW_HOURS}h): {', '.join(budget_exhausted[:20])}")
    if retried:
        print(f"Retried: {', '.join(retried[:20])}")
    if errors:
        print(f"Errors: {'; '.join(errors[:10])}")

    if DRY_RUN:
        print("\n[DRY-RUN MODE] No changes made.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
