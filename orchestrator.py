#!/usr/bin/env python3
"""
Kensho Orchestrator — 15分おきにタスクスケジューラーから実行。
時間に応じて収集・応募を判断し、適切な処理を実行する。
"""
from __future__ import annotations

import ctypes, sys
# 対話実行（TTYあり）では自分のターミナルが消えるのでウィンドウ非表示化をスキップ
if not sys.stdin.isatty():
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
import os, time, traceback, subprocess as sp, json
from datetime import datetime
from typing import Any
sys.path.insert(0, os.path.dirname(__file__))
from core.encoding import guard_stdio
guard_stdio()

from core.lock import acquire_pid_lock

# ── PIDロック: 多重起動防止 ──
if not acquire_pid_lock('orchestrator'):
    sys.exit(0)

from core.config import load as load_config
from core.cleanup import kill_zombies, clean_old_logs
from core.logger import make_path, LogWriter, write_daily_summary
from core.notifier import notify_error, notify_warning
from scraping.collector import collect
from application.session_manager import check_sessions
from utils.network import get_all_adapters

# ── 最終処理時刻 管理ファイル ──
STATE_DIR = os.path.join(os.path.dirname(__file__), 'data')
STATE_FILE = os.path.join(STATE_DIR, 'orchestrator_state.json')
os.makedirs(STATE_DIR, exist_ok=True)

def load_state() -> dict[str, Any]:
    """状態ファイル読み込み（なければ空）"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            _trace: str = traceback.format_exc()[-200:]
            print(f"[WARN] 状態ファイル読み込み失敗: {_trace}", flush=True)
    return {'last_processed': {}}


def save_state(state: dict[str, Any]) -> None:
    """状態ファイル保存"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def should_collect(now_str: str, collect_times: list[str]) -> bool:
    """現在時刻が収集時刻の範囲内か判定（±5分）"""
    now = now_str.split(':')
    now_m = int(now[0]) * 60 + int(now[1])
    
    for t in collect_times:
        parts = t.split(':')
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
    priority = cfg.get('orchestrator', {}).get('priority', 'round_robin')
    
    pending = []  # [(account_key, batch_time_str, batch_max)]
    
    for acct in cfg.get('accounts', []):
        key = acct['key']
        for batch in acct.get('schedule', {}).get('batches', []):
            parts = batch['time'].split(':')
            batch_m = int(parts[0]) * 60 + int(parts[1])
            
            # 時刻を過ぎているか
            if batch_m > now_m:
                continue
            
            # 既に処理済みか（日付＋時刻で比較）
            last = state.get('last_processed', {}).get(key, '')
            if last:
                last_parts = last.split(':')
                if len(last_parts) >= 3:
                    # 日付付き: "2026-06-20:19:47" → [date, hour, minute]
                    last_date = last_parts[0]
                    last_h = int(last_parts[1])
                    last_m = int(last_parts[2])
                    today = now.strftime('%Y-%m-%d')
                    if last_date == today and last_h * 60 + last_m >= batch_m:
                        continue
                elif len(last_parts) == 2:
                    # 旧形式（時刻のみ）→ 安全のためスキップしない
                    pass
            
            pending.append((key, batch['time'], batch.get('max', 10)))
    
    if not pending:
        return []
    
    if priority == 'pending_first':
        # 未応募件数が多い順
        try:
            import json
            col_path = os.path.join(os.path.dirname(__file__), 'data', 'collected.json')
            if os.path.exists(col_path):
                with open(col_path) as f:
                    col_data = json.load(f)
                items = col_data.get('collected', [])
                pending_counts: dict[str, int] = {}
                for item in items:
                    applied = item.get('applied', {})
                    for key, _, _ in pending:
                        if applied.get(key) is None:
                            pending_counts[key] = pending_counts.get(key, 0) + 1
                
                pending.sort(
                    key=lambda x: pending_counts.get(x[0], 0),
                    reverse=True
                )
        except Exception as _e:
            print(f"[WARN] pending_firstソート失敗: {_e}", flush=True)
    
    elif priority == 'round_robin':
        # 最も古いバッチ時刻順＋同一時刻なら最後に処理した垢を避ける
        last_processed = state.get('last_processed', {})
        def sort_key(x: tuple[str, str, int]) -> tuple[int, int]:
            key, time_str, _ = x
            parts = time_str.split(':')
            batch_m = int(parts[0]) * 60 + int(parts[1])
            # 最後に処理した垢は後回し
            last_rank = 1 if last_processed.get(key, '') == time_str else 0
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

def main() -> None:
    log_path = make_path('orchestrator')
    # 非TTY（Hermes terminal等がPIPEでstdoutをキャプチャ）ではechoを抑制
    # echo=True → print(flush=True) → PIPEが子プロセス終了で破損 → Windows CRT
    # がERROR_NO_DATA→EINVAL(22)にマップ → Hermesごとクラッシュ
    is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    log = LogWriter(log_path, echo=is_tty)
    cfg = None  # エラーハンドラで使うために事前定義

    try:
        log.write("=== Kensho Orchestrator ===")
        log.write(f"起動: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        cfg = load_config()
        state = load_state()
        
        # 各ステップを独立実行 — 1つ死んでも全部は止まらない
        _safe_step("Cleanup", log, lambda: kill_zombies(log))
        log_dir = os.path.join(cfg['general']['project_dir'], 'logs')
        retention = cfg['general'].get('log_retention_days', 30)
        _safe_step("Log Cleanup", log, clean_old_logs, log_dir, retention, log)
        
        session_warnings = _safe_step("Session Check", log, check_sessions, cfg, log) or []
        
        _safe_step("Network Check", log, lambda: get_all_adapters())
        
        now_str = datetime.now().strftime('%H:%M')
        collect_times = cfg.get('collection', {}).get('times', [])
        
        # 4. 収集（該当時刻のみ）
        log.write("\n--- Step 4: Collection Check ---")
        if should_collect(now_str, collect_times):
            log.write(f"  収集時刻（{now_str}）→ 収集実行")
            success, errors, total = collect(cfg, log)
            log.write(f"  収集結果: {total}件（成功{success}/エラー{errors}）")
        else:
            log.write("  収集時刻外 → スキップ")
        
        # 5. 応募（ThreadPoolExecutorで並列処理、最大2垢同時）
        log.write("\n--- Step 5: Apply Check ---")
        pending = get_pending_batches(cfg, state)
        max_accounts = cfg.get('orchestrator', {}).get('max_accounts_per_run', 2)
        apply_timeout = cfg.get('orchestrator', {}).get('apply_timeout', 1800)

        # ForceBindIPのパス
        BINDIP = os.path.join(cfg['general']['project_dir'], 'tools', 'ForceBindIP', 'ForceBindIP64.exe')
        APPLY_SCRIPT = os.path.join(cfg['general']['project_dir'], 'kensho_apply_single.py')
        PYTHON = cfg['general'].get('python', sys.executable)

        if not pending:
            log.write("  処理待ちのバッチなし")
        else:
            log.write(f"  処理待ち: {len(pending)}バッチ（最大{max_accounts}垢並列）")
            processed = 0

            def _run_one(key: str, batch_time: str, batch_max: int) -> tuple[str, int, int]:
                """1アカウントの応募を実行（並列ワーカー用）"""
                import psutil
                log.write(f"\n  ▶ {key}（時刻{batch_time}、最大{batch_max}件）")
                try:
                    acct = next((a for a in cfg.get('accounts', []) if a['key'] == key), None)
                    if not acct:
                        log.write("  [SKIP] アカウント情報なし")
                        return (key, 0, 0)

                    interface_name = acct.get('network_interface', '')
                    safe_iface = interface_name.replace("'", "''")
                    ip_result = sp.run(
                        ['powershell', '-NoProfile', '-Command',
                         f"(Get-NetIPAddress -InterfaceAlias '{safe_iface}' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress"],
                        capture_output=True, timeout=10
                    )
                    bind_ip = ip_result.stdout.decode('cp932', errors='replace').strip()

                    if not bind_ip or bind_ip == 'None' or bind_ip.startswith('169.254.'):
                        log.write(f"  [SKIP] インターフェース '{interface_name}' 未接続（IP: {bind_ip or 'なし'}）")
                        return (key, 0, 0)

                    log.write(f"  ForceBindIP: {bind_ip} ({interface_name})")

                    start = time.time()
                    si = sp.STARTUPINFO()
                    si.dwFlags = sp.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0

                    stderr_path = os.path.join(
                        cfg['general']['project_dir'], 'logs',
                        datetime.now().strftime('%Y-%m-%d'),
                        f'apply_stderr_{key}.log'
                    )
                    os.makedirs(os.path.dirname(stderr_path), exist_ok=True)

                    with open(stderr_path, 'w', encoding='utf-8') as stderr_f:
                        proc = sp.Popen(
                            [BINDIP, bind_ip, PYTHON, '-u', APPLY_SCRIPT, key, str(batch_max)],
                            stdout=sp.DEVNULL, stderr=stderr_f,
                            cwd=cfg['general']['project_dir'],
                            creationflags=0x08000000,
                            startupinfo=si
                        )

                        timed_out = False
                        try:
                            proc.wait(timeout=apply_timeout)
                        except sp.TimeoutExpired:
                            timed_out = True
                            elapsed = time.time() - start
                            log.write(f"  [TIMEOUT] {apply_timeout}秒超過（{elapsed:.0f}秒）→ ツリーごと強制終了")
                            try:
                                parent = psutil.Process(proc.pid)
                                for child in parent.children(recursive=True):
                                    try:
                                        child.kill()
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        pass
                                parent.kill()
                                proc.wait(timeout=5)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                    elapsed = time.time() - start

                    if timed_out:
                        return (key, 0, 1)

                    succ = 0
                    err = 0
                    result_file = os.path.join(
                        cfg['general']['project_dir'], 'logs',
                        datetime.now().strftime('%Y-%m-%d'),
                        f'apply_result_{key}.json'
                    )
                    try:
                        with open(result_file, 'r', encoding='utf-8') as rf:
                            res = json.load(rf)
                            succ = res.get('success', 0)
                            err = res.get('errors', 0)
                            if res.get('exception'):
                                log.write(f"  Exception: {res['exception'][:100]}")
                            if res.get('traceback'):
                                log.write(f"  Traceback: {res['traceback'][:200]}")
                    except Exception as _e:
                        log.write(f"[WARN] 結果ファイル読み込み失敗: {_e}")

                    if succ == 0 and err == 0:
                        try:
                            if os.path.exists(stderr_path):
                                sz = os.path.getsize(stderr_path)
                                if sz > 0:
                                    with open(stderr_path, 'r', encoding='utf-8', errors='replace') as sf:
                                        content = sf.read()[-500:]
                                    log.write(f"  Stderr({sz}B): {content[:300]}")
                        except Exception:
                            pass

                    log.write(f"  完了: {succ}成功/{err}エラー（{elapsed:.0f}秒{' TIMEOUT' if timed_out else ''}）")
                    return (key, succ, err)

                except Exception as e:
                    log.write(f"  [NG] applyエラー: {e}")
                    log.write(traceback.format_exc()[-300:])
                    return (key, 0, 1)

            # 並列実行（最大max_accounts垢まで同時）
            from concurrent.futures import ThreadPoolExecutor, as_completed
            batch_items = pending[:max_accounts]
            with ThreadPoolExecutor(max_workers=max_accounts) as executor:
                futures = {
                    executor.submit(_run_one, key, bt, bm): (key, bt, bm)
                    for key, bt, bm in batch_items
                }
                for future in as_completed(futures):
                    key, succ, err = future.result()
                    processed += 1
                    batch_time = futures[future][1]
                    # 状態更新（結果が取れた時のみ）
                    if succ > 0 or err > 0:
                        state.setdefault('last_processed', {})
                        state['last_processed'][key] = f"{datetime.now().strftime('%Y-%m-%d')}:{batch_time}"
                        save_state(state)
                    else:
                        log.write(f"  [WARN] {key}: 結果空っぽ（スクリプトクラッシュ？）→ 状態保持、次回再試行")

            log.write(f"\n  今回処理: {processed}垢（並列={max_accounts}）")
        
        
        # 6. セッション期限警告（Discord）
        for key, display, days in session_warnings:
            if days == -1:
                notify_warning(
                    f"Sessionファイルなし: {display}",
                    "セッションファイルが見つかりません。ログインが必要です。",
                    str(log_path),
                    cfg
                )
            elif days > 3:
                notify_warning(
                    f"Session未更新: {display}",
                    f"{days}日間セッションが更新されていません。",
                    str(log_path),
                    cfg
                )
        
        # 7. 日次サマリー（日付変わってたら生成）
        log.write("\n--- Step 6: Summary ---")
        summary_path = write_daily_summary()
        if summary_path:
            log.write(f"  日次サマリー: {summary_path}")
        
        log.write(f"\n=== 正常終了: {datetime.now().strftime('%H:%M:%S')} ===")
    
    except Exception as e:
        # まず直接ファイルにtracebackを書き込む（log.writeはprintで失敗する可能性あり）
        _tb = traceback.format_exc()
        try:
            with open(str(log_path), 'a', encoding='utf-8') as _ef:
                _ef.write(f'\n[NG] 致命的エラー: {e}\n')
                _ef.write(_tb)
                _ef.write('\n')
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

if __name__ == '__main__':
    main()
