#!/usr/bin/env python3
"""
Kensho Orchestrator — 15分おきにタスクスケジューラーから実行。
時間に応じて収集・応募を判断し、適切な処理を実行する。

v4.0: ForceBindIP廃止、サブプロセス撤廃、apply_for_account()直接呼び出し
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import random
import sys
import time
import traceback
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from kensho.core.encoding import guard_stdio

guard_stdio()

# ── CLI引数: --account <key> で垢別起動（並列ワーカー用） ──
_parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Kensho Orchestrator")
_parser.add_argument("--account", default=None, help="対象アカウントキー（指定時は垢別で起動）")
_CLI_ARGS, _ = _parser.parse_known_args()

from kensho.core.lock import acquire_pid_lock  # noqa: E402

# ── PIDロック: 多重起動防止（垢別なら垢ごとのロックで並列可） ──
_ACCOUNT: str | None = _CLI_ARGS.account
_lock_name: str = f"orchestrator-{_ACCOUNT}" if _ACCOUNT else "orchestrator"
# ※ ロック取得は main() 内で行う（import時の副作用回避: テスト可能に）

from kensho.application.applier import apply_for_account  # noqa: E402
from kensho.application.session_manager import check_sessions  # noqa: E402
from kensho.core.cleanup import clean_old_logs, kill_zombies  # noqa: E402
from kensho.core.config import load as load_config  # noqa: E402
from kensho.core.crash_guard import check_previous_crash  # noqa: E402
from kensho.core.crash_guard import start as start_crash_guard  # noqa: E402
from kensho.core.logger import LogWriter, make_path, write_daily_summary  # noqa: E402
from kensho.core.notifier import notify_error, notify_warning  # noqa: E402
from kensho.scraping.collector import collect  # noqa: E402
from kensho.utils.freeze_festival import check_and_update, get_action_scale  # noqa: E402
from kensho.utils.network import get_all_adapters  # noqa: E402
from kensho.utils.proxy_watchdog import check_proxy_health  # noqa: E402

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
    """状態ファイル保存（並列プロセス間の競合防止: ファイルロック＋マージ）

    並列実行される垢別プロセス間でstateファイルのlost updateを防ぐ。
    fcntl.flockで排他ロックし、最新のstateを読み込んでからマージして保存する。
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, "r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                current = json.load(f)
            except (json.JSONDecodeError, Exception):
                current = {}
            current.setdefault("last_processed", {})
            current["last_processed"].update(state.get("last_processed", {}))
            if "last_collect" in state:
                current["last_collect"] = state["last_collect"]
            f.seek(0)
            f.truncate()
            json.dump(current, f, ensure_ascii=False, indent=2)
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
    except FileNotFoundError:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


def should_collect(now_str: str, collect_times: list[str]) -> bool:
    """現在時刻が収集時刻の範囲内か判定（±30分）"""
    now = now_str.split(":")
    now_m = int(now[0]) * 60 + int(now[1])
    for t in collect_times:
        parts = t.split(":")
        target_m = int(parts[0]) * 60 + int(parts[1])
        if abs(now_m - target_m) <= 30:
            return True
    return False


def get_pending_batches(
    cfg: dict[str, Any],
    state: dict[str, Any],
    account_key: str | None = None,
) -> list[tuple[str, str, int]]:
    """
    スケジュール時刻を過ぎて未処理のバッチ一覧を取得。
    優先順位: round_robin（最後に処理した垢を避ける） or pending_first
    account_key 指定時はその垢のみ対象（垢別並列ワーカー用）。
    """
    now: datetime = datetime.now()
    now_m = now.hour * 60 + now.minute
    priority = cfg.get("orchestrator", {}).get("priority", "round_robin")

    # ★ 2026-08-28提案52: 凍結祭り観測時の減速（バッチサイズをscale倍に）
    #   stateファイル読取のみ（軽量）。観測中でなければ1.0 = 影響なし。
    _ff_scale: float = get_action_scale(cfg)

    # ★ 2026-08-23 BOT対策: 深夜帯は応募アクションを一切行わない（睡眠中の人間がやらない時間帯は
    #   XのBOT検出で最も強い信号）。config: orchestrator.no_action_window = ["HH:MM","HH:MM"]。
    #   スケジュール時刻を過ぎた積み残しバッチも深夜に飲み込まれて実行されるバグの対策。
    #   実測: atushi16 が00:48〜05:35にフォロー47件（スケジュールは8:00開始）
    _aw = cfg.get("orchestrator", {}).get("no_action_window") or ["00:00", "07:00"]
    if len(_aw) == 2:
        try:
            _a0 = int(_aw[0].split(":")[0]) * 60 + int(_aw[0].split(":")[1])
            _a1 = int(_aw[1].split(":")[0]) * 60 + int(_aw[1].split(":")[1])
            # 深夜を跨ぐ窓（例 23:00-07:00）
            if _a0 <= _a1:
                _in_window = _a0 <= now_m < _a1
            else:
                _in_window = now_m >= _a0 or now_m < _a1
            if _in_window:
                return []  # 深夜は全バッチスキップ
        except Exception:
            pass

    pending = []  # [(account_key, batch_time_str, batch_max)]

    for acct in cfg.get("accounts", []):
        key = acct["key"]
        # 垢別指定時は対象外をスキップ
        if account_key is not None and key != account_key:
            continue
        # ── 日別ランダムジッター（BOT対策）──
        jitter_min = cfg.get("orchestrator", {}).get("batch_jitter_minutes", 0)
        for batch in acct.get("schedule", {}).get("batches", []):
            parts = batch["time"].split(":")
            batch_m = int(parts[0]) * 60 + int(parts[1])
            orig_m = batch_m  # 状態比較用に元の時刻を保持

            # 日別決定論的ジッターを適用（同日・同垢・同バッチなら同じ値）
            if jitter_min > 0:
                seed_str = f"{now.strftime('%Y-%m-%d')}:{key}:{batch['time']}"
                r = random.Random(seed_str)
                offset = r.randint(-jitter_min, jitter_min)
                batch_m += offset

            # 時刻を過ぎているか
            if batch_m > now_m:
                continue

            # 既に処理済みか（日付＋元の時刻で比較：stateにはbt=元の時刻が保存される）
            last = state.get("last_processed", {}).get(key, "")
            if last:
                last_parts = last.split(":")
                if len(last_parts) >= 3:
                    last_date = last_parts[0]
                    last_h = int(last_parts[1])
                    last_m = int(last_parts[2])
                    today = now.strftime("%Y-%m-%d")
                    if last_date == today and last_h * 60 + last_m >= orig_m:
                        continue
                elif len(last_parts) == 2:
                    pass

            # バッチごとに処理件数をランダム化（±2のジッター）
            # 効果: max=12のとき実効10〜14件 → 5バッチで1日50〜70件に自然分散
            base_max = batch.get("max", 10)
            batch_max = max(3, base_max + random.randint(-2, 2))
            # ★ 2026-08-28提案52: 凍結祭り観測中は全垢のバッチサイズをscale倍に減速
            #   （例 0.5 → max=12のとき実効5〜7件 → 1日25〜35件）
            if _ff_scale < 1.0:
                batch_max = max(2, int(batch_max * _ff_scale))
            pending.append((key, batch["time"], batch_max))

    if not pending:
        return []

    if priority == "pending_first":
        try:
            col_path = os.path.join(os.path.dirname(__file__), "..", "data", "collected.json")
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
    shared_browser: Any = None,
    shared_ipw: Any = None,
) -> tuple[str, int, int]:
    """1アカウントの応募を直接apply_for_account()で実行"""
    log.write(f"\n  ▶ {key}（時刻{batch_time}、最大{batch_max}件）")

    # ── ランダム秒ジッター（BOT検出回避）──
    # 分レベルの日別ジッター（batch_jitter_minutes）に加え、実行開始の「秒」も
    # 毎回ランダムにする。15分おきcron発火だとそのまま実行すると常に分0秒で
    # 始まり機械的パターンになるため、0〜89秒のランダム待機を入れる。
    sec_jitter = random.randint(0, 89)
    if sec_jitter > 0:
        log.write(f"  ⏱ 秒ジッター: {sec_jitter}秒待機（人間らしい開始タイミング）")
        time.sleep(sec_jitter)

    try:
        acct = next((a for a in cfg.get("accounts", []) if a["key"] == key), None)
        if not acct:
            log.write("  [SKIP] アカウント情報なし")
            return (key, 0, 0)

        start = time.time()
        succ, err = apply_for_account(key, batch_max, cfg, log, shared_browser=shared_browser, shared_ipw=shared_ipw)

        elapsed = time.time() - start
        log.write(f"  完了: {succ}成功/{err}エラー（{elapsed:.0f}秒）")
        return (key, succ, err)

    except Exception as e:
        log.write(f"  [NG] applyエラー: {e}")
        log.write(traceback.format_exc()[-300:])
        return (key, 0, 1)


def main() -> None:
    # ── PIDロック: 多重起動防止（import時ではなく起動時に取得） ──
    if not acquire_pid_lock(_lock_name):
        sys.exit(0)

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

        # ハートビート（orchestrator_heartbeat.json）を書き込む
        try:
            hb_path = os.path.join(cfg["general"]["project_dir"], "data", "orchestrator_heartbeat.json")
            os.makedirs(os.path.dirname(hb_path), exist_ok=True)
            with open(hb_path, "w", encoding="utf-8") as _hf:
                json.dump({"ts": datetime.now().isoformat(), "pid": os.getpid()}, _hf)
        except Exception as _e:
            log.write(f"[WARN] heartbeat書き込み失敗: {_e}")

        guard.update("cleanup", "ゾンビクリーンアップ")

        # 各ステップを独立実行
        # ★ Cleanup(kill_zombies)は直列前提の「名前/親python基準のfirefox総kill」。
        #   並列垢ワーカー時は他垢の稼働中ブラウザを殺すためスキップ。
        #   孤児の掃除は firewatch.sh（PPID=1のみkill、5分おき）が安全に担う。
        if _ACCOUNT is not None:
            log.write(
                "  [SKIP] Cleanup(kill_zombies): 並列垢ワーカーでは他垢のFirefoxを守るため省略（孤児はfirewatchが掃除）"
            )  # noqa: E501
        else:
            _safe_step("Cleanup", log, lambda: kill_zombies(log))
        log_dir = os.path.join(cfg["general"]["project_dir"], "logs")
        retention = cfg["general"].get("log_retention_days", 30)
        _safe_step("Log Cleanup", log, clean_old_logs, log_dir, retention, log)

        guard.update("session_check", "セッション確認")
        session_warnings = _safe_step("Session Check", log, check_sessions, cfg, log) or []

        guard.update("network_check", "ネットワーク確認")
        _safe_step("Network Check", log, lambda: get_all_adapters())

        # ★ 2026-08-28提案52: 凍結祭り日次チェック（メインorchestratorのみ）
        #   内部で「当日チェック済み」ガードがあるため実質1日1回だけWeb検索する。
        #   観測時は get_pending_batches がバッチサイズを自動減速する。
        if _ACCOUNT is None:
            _safe_step(
                "Freeze Festival Check",
                log,
                lambda: check_and_update(cfg, log.write),
            )

        # ★ 2026-08-25: プロキシ自動復旧（メインorchestratorサイクル内で実行）
        #   垢別ワーカー(_ACCOUNT指定)は他垢のプロキシ再起動と競合するためメインのみ。
        #   proxy_watchdog が ポート死/疎通なし(出口IP取得失敗) を検出し、
        #   WiFi再接続→プロキシ再起動を自動実行する。
        if _ACCOUNT is None:
            _safe_step("Proxy Watchdog", log, lambda: check_proxy_health(cfg, log))

        now_dt = datetime.now()
        now_str = now_dt.strftime("%H:%M")
        collect_times = cfg.get("collection", {}).get("times", [])

        # 4. 収集（該当時刻のみ / 分離cron使用時はスキップ）
        guard.update("collect", "収集")
        log.write("\n--- Step 4: Collection Check ---")
        separate_cron = bool(cfg.get("collection", {}).get("separate_cron", False))
        if separate_cron:
            # 収集は専用cron(scripts/collect直接)で実行済み。応募に専念する。
            log.write("  separate_cron=true → 収集は専用cronで実行（スキップ）")
        elif should_collect(now_str, collect_times):
            last_collect = state.get("last_collect")
            do_collect = True
            if last_collect:
                # 新しい形式: YYYY-MM-DD HH:MM
                try:
                    last_dt = datetime.strptime(last_collect, "%Y-%m-%d %H:%M")
                    diff = (now_dt - last_dt).total_seconds()
                    if 0 <= diff <= 2700:  # 45分 = 2700秒
                        do_collect = False
                except ValueError:
                    # 旧形式: HH:MM のみ（日付なし）
                    parts = last_collect.split(":")
                    if len(parts) == 2:
                        try:
                            last_m = int(parts[0]) * 60 + int(parts[1])
                            now_m = now_dt.hour * 60 + now_dt.minute
                            if now_m >= last_m and (now_m - last_m) <= 45:
                                do_collect = False
                        except (ValueError, IndexError):
                            pass
            if do_collect:
                log.write(f"  収集時刻（{now_str}）→ 収集実行")
                # 秒ジッター: 毎正時発火の機械的パターンを回避
                collect_jitter = random.randint(0, 119)
                if collect_jitter > 0:
                    log.write(f"  ⏱ 収集ジッター: {collect_jitter}秒待機")
                    time.sleep(collect_jitter)
                guard.update("collect", "収集実行中")
                success, errors, total = collect(cfg, log)
                log.write(f"  収集結果: {total}件（成功{success}/エラー{errors}）")
                state["last_collect"] = now_dt.strftime("%Y-%m-%d %H:%M")
                save_state(state)
            else:
                log.write(f"  収集時刻（{now_str}）→ 前回収集から45分以内のためスキップ")
        else:
            log.write("  収集時刻外 → スキップ")

        # 5. 応募（垢別並列起動時は各垢プロセスが自分だけを処理）
        log.write("\n--- Step 5: Apply Check ---")
        if _ACCOUNT is not None:
            log.write(f"  垢別起動: {_ACCOUNT}")
        pending = get_pending_batches(cfg, state, _ACCOUNT)
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
                key_res, succ, err = _apply_account(key, bt, bm, cfg, log, shared_browser=None, shared_ipw=None)
                processed += 1
                # ★ アカウント間: メモリ強制解放 + OS回収待機
                import gc

                gc.collect()
                time.sleep(2)
                if succ > 0 or err > 0:
                    state.setdefault("last_processed", {})
                    state["last_processed"][key_res] = f"{datetime.now().strftime('%Y-%m-%d')}:{bt}"
                    save_state(state)
                else:
                    state.setdefault("last_processed", {})
                    state["last_processed"][key_res] = f"{datetime.now().strftime('%Y-%m-%d')}:{bt}"
                    save_state(state)
                    log.write(f"  [WARN] {key_res}: 結果空っぽ → スキップ済みとして記録（次回は再試行せず）")

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

    return


if __name__ == "__main__":
    main()
