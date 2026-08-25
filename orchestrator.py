#!/usr/bin/env python3
"""
Kensho Orchestrator — 15分おきにタスクスケジューラーから実行。
時間に応じて収集・応募を判断し、適切な処理を実行する。

v4.0: ForceBindIP廃止、サブプロセス撤廃、apply_for_account()直接呼び出し
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from core.encoding import guard_stdio

guard_stdio()

from core.lock import acquire_pid_lock  # noqa: E402

# ── PIDロック: 多重起動防止 ──
if not acquire_pid_lock("orchestrator"):
    sys.exit(0)

from application.applier import apply_for_account  # noqa: E402
from application.session_manager import check_sessions  # noqa: E402
from core.cleanup import clean_old_logs, kill_zombies  # noqa: E402
from core.config import load as load_config  # noqa: E402
from core.crash_guard import check_previous_crash  # noqa: E402
from core.crash_guard import start as start_crash_guard  # noqa: E402
from core.logger import LogWriter, make_path, write_daily_summary  # noqa: E402
from core.notifier import notify_error, notify_warning  # noqa: E402

from kensho.utils.network import get_all_adapters  # noqa: E402
from kensho.utils.proxy_watchdog import check_proxy_health  # noqa: E402
from scraping.collector import collect  # noqa: E402

# ── 最終処理時刻 管理ファイル ──
STATE_DIR = os.path.join(os.path.dirname(__file__), "data")
STATE_FILE = os.path.join(STATE_DIR, "orchestrator_state.json")
os.makedirs(STATE_DIR, exist_ok=True)


def load_state() -> dict[str, Any]:
    """状態ファイル読み込み（なければ空）"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            _trace: str = traceback.format_exc()[-200:]
            print(f"[WARN] 状態ファイル読み込み失敗: {_trace}", flush=True)
    return {"last_processed": {}}


def save_state(state: dict[str, Any]) -> None:
    """状態ファイル保存"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_collect(now_str: str, collect_times: list[str]) -> bool:
    """現在時刻が収集時刻の範囲内か判定（±5分）"""
    now = now_str.split(":")
    now_m = int(now[0]) * 60 + int(now[1])
    for t in collect_times:
        parts = t.split(":")
        target_m = int(parts[0]) * 60 + int(parts[1])
        if abs(now_m - target_m) <= 5:
            return True
    return False


def get_pending_batches(cfg: dict[str, Any], state: dict[str, Any]) -> list[tuple[str, str, int]]:
    """
    スケジュール時刻を過ぎて未処理のバッチ一覧を取得。
    優先順位: round_robin（最後に処理した垢を避ける） or pending_first
    """
    now: datetime = datetime.now()
    now_m = now.hour * 60 + now.minute
    priority = cfg.get("orchestrator", {}).get("priority", "round_robin")

    pending = []  # [(account_key, batch_time_str, batch_max)]

    for acct in cfg.get("accounts", []):
        key = acct["key"]
        for batch in acct.get("schedule", {}).get("batches", []):
            parts = batch["time"].split(":")
            batch_m = int(parts[0]) * 60 + int(parts[1])

            # 時刻を過ぎているか
            if batch_m > now_m:
                continue

            # 既に処理済みか（日付＋時刻で比較）
            last = state.get("last_processed", {}).get(key, "")
            if last:
                last_parts = last.split(":")
                if len(last_parts) >= 3:
                    last_date = last_parts[0]
                    last_h = int(last_parts[1])
                    last_m = int(last_parts[2])
                    today = now.strftime("%Y-%m-%d")
                    if last_date == today and last_h * 60 + last_m >= batch_m:
                        continue
                elif len(last_parts) == 2:
                    pass

            pending.append((key, batch["time"], batch.get("max", 10)))

    if not pending:
        return []

    if priority == "pending_first":
        try:
            col_path = os.path.join(os.path.dirname(__file__), "data", "collected.json")
            if os.path.exists(col_path):
                with open(col_path) as f:
                    col_data = json.load(f)
                items = col_data.get("collected", [])
                pending_counts: dict[str, int] = {}
                for item in items:
                    applied = item.get("applied", {})
                    for key, _, _ in pending:
                        if applied.get(key) is None:
                            pending_counts[key] = pending_counts.get(key, 0) + 1

                pending.sort(key=lambda x: pending_counts.get(x[0], 0), reverse=True)
        except Exception as _e:
            print(f"[WARN] pending_firstソート失敗: {_e}", flush=True)

    elif priority == "round_robin":
        last_processed = state.get("last_processed", {})

        def sort_key(x: tuple[str, str, int]) -> tuple[int, int]:
            key, time_str, _ = x
            parts = time_str.split(":")
            batch_m = int(parts[0]) * 60 + int(parts[1])
            last_rank = 1 if last_processed.get(key, "") == time_str else 0
            return (batch_m, last_rank)

        pending.sort(key=sort_key)

    return pending


def _safe_step(step_name: str, log: LogWriter, fn, *args, **kwargs) -> Any:
    """各ステップを独立したtry/exceptで実行。エラーでも後続は続行。"""
    try:
        log.write(f"--- Step: {step_name} ---")
        return fn(*args, **kwargs)
    except Exception as e:
        tb = traceback.format_exc()
        log.write(f"[SKIP] {step_name} 失敗: {e}")
        log.write(f"[TRACE] {tb[-500:]}")
        return None


def _apply_account(
    key: str,
    batch_time: str,
    batch_max: int,
    cfg: dict[str, Any],
    log: LogWriter,
) -> tuple[str, int, int]:
    """1アカウントの応募を直接apply_for_account()で実行"""
    log.write(f"\n  ▶ {key}（時刻{batch_time}、最大{batch_max}件）")
    try:
        acct = next((a for a in cfg.get("accounts", []) if a["key"] == key), None)
        if not acct:
            log.write("  [SKIP] アカウント情報なし")
            return (key, 0, 0)

        start = time.time()
        succ, err = apply_for_account(key, batch_max, cfg, log)

        elapsed = time.time() - start
        log.write(f"  完了: {succ}成功/{err}エラー（{elapsed:.0f}秒）")
        return (key, succ, err)

    except Exception as e:
        log.write(f"  [NG] applyエラー: {e}")
        log.write(traceback.format_exc()[-300:])
        return (key, 0, 1)


def main() -> None:
    log_path = make_path("orchestrator")
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    log = LogWriter(log_path, echo=is_tty)
    cfg = None

    # ── CrashGuard 開始 ──
    guard = start_crash_guard()
    guard.update("start", "起動中...")

    # ── 前回クラッシュの確認 ──
    prev_crash = check_previous_crash()
    if prev_crash:
        crash_msg = prev_crash.get("message", "")
        crash_step = prev_crash.get("step", "?")
        crash_acct = prev_crash.get("account", "")
        log.write(f"⚠️ 前回異常終了を検出: step={crash_step} msg={crash_msg} account={crash_acct}")
        log.write("   詳細: data/crash_reports/ を確認")

    try:
        # ── 起動時: 初期化 ──
        guard.update("init", "起動")

        log.write("=== Kensho Orchestrator v4 ===")
        log.write(f"起動: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        cfg = load_config()
        state = load_state()

        guard.update("cleanup", "ゾンビクリーンアップ")

        # 各ステップを独立実行
        _safe_step("Cleanup", log, lambda: kill_zombies(log))
        log_dir = os.path.join(cfg["general"]["project_dir"], "logs")
        retention = cfg["general"].get("log_retention_days", 30)
        _safe_step("Log Cleanup", log, clean_old_logs, log_dir, retention, log)

        guard.update("session_check", "セッション確認")
        session_warnings = _safe_step("Session Check", log, check_sessions, cfg, log) or []

        guard.update("network_check", "ネットワーク確認")
        _safe_step("Network Check", log, lambda: get_all_adapters())

        now_str = datetime.now().strftime("%H:%M")
        collect_times = cfg.get("collection", {}).get("times", [])

        # 4. 収集（該当時刻のみ）
        guard.update("collect", "収集")
        log.write("\n--- Step 4: Collection Check ---")
        if should_collect(now_str, collect_times):
            log.write(f"  収集時刻（{now_str}）→ 収集実行")
            guard.update("collect", "収集実行中")
            success, errors, total = collect(cfg, log)
            log.write(f"  収集結果: {total}件（成功{success}/エラー{errors}）")
        else:
            log.write("  収集時刻外 → スキップ")

        # ★ プロキシ自動復旧（死んでるプロキシを検出→アダプタ生なら再起動）
        try:
            health = check_proxy_health(cfg, log)
            if health["restored_ports"] > 0:
                log.write(f"  [WATCHDOG] ✅ 復旧: {health['restored_ports']}台 ({health['dead_ports']}台不通→再起動)")
            elif health["dead_ports"]:
                log.write(f"  [WATCHDOG] ⚠️ 不通: {health['dead_ports']}台（アダプタ切断で復旧不可）")
            else:
                log.write(f"  [WATCHDOG] ✅ 全プロキシ正常 ({health['alive_ports']})")
        except Exception as e:
            log.write(f"  [WATCHDOG] ❌ エラー: {e}")

        # 5. 応募（逐次実行: OOM防止のため1垢ずつ）
        log.write("\n--- Step 5: Apply Check ---")
        pending = get_pending_batches(cfg, state)
        max_accounts = cfg.get("orchestrator", {}).get("max_accounts_per_run", 2)

        if not pending:
            log.write("  処理待ちのバッチなし")
        else:
            # 最大max_accounts垢まで逐次実行
            batch_items = pending[:max_accounts]
            log.write(f"  処理待ち: {len(pending)}バッチ → 今回処理: {len(batch_items)}垢（逐次実行）")
            processed = 0

            for key, bt, bm in batch_items:
                guard.update("apply", f"{key} 処理中", account=key, total=bm)
                key_res, succ, err = _apply_account(key, bt, bm, cfg, log)
                processed += 1
                if succ > 0 or err > 0:
                    state.setdefault("last_processed", {})
                    state["last_processed"][key_res] = f"{datetime.now().strftime('%Y-%m-%d')}:{bt}"
                    save_state(state)
                else:
                    log.write(f"  [WARN] {key_res}: 結果空っぽ → 状態保持、次回再試行")

            log.write(f"\n  今回処理: {processed}垢")

        # 6. セッション期限警告（Discord）
        for key, display, days in session_warnings:
            if days == -1:
                notify_warning(
                    f"Sessionファイルなし: {display}",
                    "セッションファイルが見つかりません。ログインが必要です。",
                    str(log_path),
                    cfg,
                )
            elif days > 3:
                notify_warning(
                    f"Session未更新: {display}", f"{days}日間セッションが更新されていません。", str(log_path), cfg
                )

        # 7. 日次サマリー
        guard.update("summary", "日次サマリー生成")
        log.write("\n--- Step 6: Summary ---")
        summary_path = write_daily_summary()
        if summary_path:
            log.write(f"  日次サマリー: {summary_path}")

        guard.mark_done()
        log.write(f"\n=== 正常終了: {datetime.now().strftime('%H:%M:%S')} ===")

    except Exception as e:
        guard.update("error", f"致命的エラー: {e}")
        _tb = traceback.format_exc()
        try:
            with open(str(log_path), "a", encoding="utf-8") as _ef:
                _ef.write(f"\n[NG] 致命的エラー: {e}\n")
                _ef.write(_tb)
                _ef.write("\n")
        except Exception:
            pass
        try:
            log.write(f"\n[NG] 致命的エラー: {e}")
            log.write(_tb)
        except Exception:
            pass
        notify_error("Orchestrator: 致命的エラー", _tb, str(log_path), cfg)

    finally:
        log.close()

    sys.exit(0)


if __name__ == "__main__":
    main()
