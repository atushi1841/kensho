"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 機能を rate_limiter, reply_generator, state, actions に分割
"""
from __future__ import annotations

import json
import time
import random
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import load as load_config
from application.browser import (
    create_browser, check_x_login, close_browser,
    human_like_mouse,
)

from application.rate_limiter import (
    check_rate_limit,
    increment_daily_count,
    is_active_hours,
    load_daily_counts,
)
from application.state import save_collected_safe
from application.actions import sort_items

DATA_DIR: Path = Path(__file__).parent.parent / 'data'
COLLECTED_FILE: Path = DATA_DIR / 'collected.json'


def _save_session_cookies(ctx: Any, account_key: str, session_path: Path) -> None:
    """ブラウザコンテキストのセッションクッキーをファイルに保存する（補助機能）"""
    try:
        data = ctx.storage_state()
        session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _wait_for_memory(cfg: dict, log: Any = None) -> bool:
    """ブラウザ起動前に空きRAMを確認。不足時は最大60秒待機。

Returns:
        True: メモリ十分（または待機後確保）
        False: タイムアウト（警告ログを出して続行）
    """
    reserve_mb: int = cfg.get('rate_limits', {}).get('memory_reserve_mb', 2048)
    deadline: float = time.time() + 60  # 最大60秒待機

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    while time.time() < deadline:
        avail_mb: int = psutil.virtual_memory().available // (1024 * 1024)
        if avail_mb >= reserve_mb:
            return True
        remaining: int = int(deadline - time.time())
        out(f"[MEM] 空きRAM {avail_mb}MB < {reserve_mb}MB → {min(10, remaining)}秒待機（残り{remaining}秒）")
        time.sleep(min(10, max(1, remaining)))

    avail_mb = psutil.virtual_memory().available // (1024 * 1024)
    out(f"[MEM] ⚠ タイムアウト: 空きRAM {avail_mb}MB < {reserve_mb}MB → 強行（クラッシュリスク）")
    return False


def apply_for_account(account_key: str, max_n: int,
                      cfg: dict[str, Any] | None = None,
                      log: Any = None,
                      dry_run: bool = False) -> tuple[int, int]:
    """
    指定されたアカウントで未応募の懸賞に応募する。

    Parameters:
        account_key: アカウントキー
        max_n: 最大処理件数
        cfg: config（Noneなら自動読込）
        log: LogWriter
        dry_run: Trueなら実際の応募はせず、処理対象の表示のみ

    Returns: (success_count, error_count)
    """
    t0: float = time.time()
    if cfg is None:
        cfg = load_config()

    # 時間帯チェック
    if not is_active_hours(cfg):
        msg: str = "[SKIP] 動作時間外（深夜）→ スキップ"
        if log:
            log.write(msg)
        else:
            print(msg)
        return (0, 0)

    # 日次上限チェック
    if check_rate_limit(account_key, cfg):
        msg = f"[SKIP] {account_key}: 日次上限到達 → スキップ"
        if log:
            log.write(msg)
        else:
            print(msg)
        return (0, 0)

    acct: dict[str, Any] | None = None
    for a in cfg.get('accounts', []):
        if a['key'] == account_key:
            acct = a
            break
    if not acct:
        if log:
            log.write(f"[NG] アカウント '{account_key}' が見つからない")
        return (0, 0)

    display: str = acct.get('display', account_key)
    session_path: Path = Path(cfg['general']['project_dir']) / acct['session']

    # レート制限設定
    limits: dict[str, Any] = cfg.get('rate_limits', {})
    min_delay: float = limits.get('min_delay_between_actions', 12)
    max_delay: float = limits.get('max_delay_between_actions', 40)
    extra_long_pause_chance: float = limits.get('extra_long_pause_chance', 0.10)
    break_after_n: int = limits.get('break_after_n_items', 3)
    break_min: float = limits.get('break_min_seconds', 30)
    break_max: float = limits.get('break_max_seconds', 90)

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    out(f"[Kensho] アカウント: {display} ({account_key})")

    jitter: int = random.randint(0, 60)
    out(f"[Kensho] スタート遅延: {jitter}秒（cron固定時刻対策）")
    time.sleep(jitter)

    out(f"[Kensho] {datetime.now().strftime('%H:%M:%S')} 開始")

    if not COLLECTED_FILE.exists():
        out("[Kensho] collected.json なし → スキップ")
        return (0, 0)

    with open(COLLECTED_FILE, 'r', encoding='utf-8') as f:
        data: dict[str, Any] = json.load(f)

    items: list[dict[str, Any]] = data.get('collected', [])
    out(f"[Kensho] 全収集: {len(items)}件")

    account_applied: list[dict[str, Any]] = []
    for item in items:
        if item.get('applied', {}).get(account_key) is not None:
            continue
        if check_rate_limit(account_key, cfg):
            out(f"[LIMIT] {account_key}: 処理中に上限到達 → 残りスキップ")
            break
        account_applied.append(item)

    out(f"[Kensho] この垢の未応募: {len(account_applied)}件")

    # 優先順にソート
    account_applied = sort_items(account_applied)

    if not account_applied:
        out("[Kensho] この垢の未応募なし。スキップ。")
        return (0, 0)

    to_process: list[dict[str, Any]] = account_applied[:max_n]
    out(f"[Kensho] 処理: {len(to_process)}件（max={max_n}）")

    if not to_process:
        out('[Kensho] 処理対象なし。')
        return (0, 0)

    # ── dry-run: 実際の応募はせず対象表示のみ ──
    if dry_run:
        out(f'[DRY-RUN] 処理対象 {len(to_process)}件（実際には応募しません）')
        for di, ditem in enumerate(to_process[:3], 1):
            dx_url: str = ditem.get('x_url', '')
            ddeadline: str = ditem.get('deadline', '') or '未設定'
            out(f'  [{di}/{len(to_process)}] 〆{ddeadline} {dx_url[:55]}...')
        if len(to_process) > 3:
            out(f'  ...他 {len(to_process) - 3}件')
        out('')
        return (0, 0)

    # ── メモリチェック: ブラウザ起動前に空きRAMを確認 ──
    _wait_for_memory(cfg, log)

    # ── ブラウザ起動（例外捕捉でstderr出力を確実に）──
    try:
        p, browser, ctx, page = create_browser(
            account_key=account_key,
            session_file=str(session_path) if session_path.exists() else None,
            headless=True,
            log=log,
        )
    except Exception as e:
        out(f"[NG] ブラウザ起動失敗: {e}")
        import traceback
        out(f"  {traceback.format_exc()[-300:]}")
        return (0, 1)

    if not check_x_login(page, log):
        out("[NG] ログイン失敗 - auth_tokenが必要")
        close_browser(p, browser, log)
        return (0, 1)

    # ★ コンソールエラー抑制：Playwright操作の痕跡をXの検出スクリプトから隠す
    page.on('console', lambda msg: None if msg.type in ('error','warning') else None)
    page.on('pageerror', lambda err: None)

    success: int = 0
    errors: int = 0
    total: int = len(to_process)

    for i, item in enumerate(to_process):
        global_idx: int = i + 1
        x_url: str = item.get('x_url', '')
        if not x_url:
            out(f"  [{global_idx}/{total}] [SKIP] x_url 空")
            continue

        clean_url: str = x_url.split('#')[0]

        if '/status/' not in clean_url.lower():
            out(f"  [{global_idx}/{total}] [SKIP] ツイートURLではない: {clean_url[:55]}...")
            continue

        deadline_info: str = item.get('deadline', '') or '未設定'
        wc_info: str = str(item.get('winner_count', '')) if item.get('winner_count', 0) > 0 else '?'
        elapsed_global: float = time.time() - t0

        try:
            out(f"[{global_idx}/{total}] ⏱{elapsed_global/60:.0f}分 "
                f"〆{deadline_info} {wc_info}名 {clean_url[:50]}...")

            page.goto(clean_url, timeout=120000)
            time.sleep(random.uniform(2, 5))

            # ★ 自然なスクロール：上下混在・速度変化
            scrolls: int = random.randint(3, 6)
            for _ in range(scrolls):
                dy: int = random.randint(-80, 250)
                delay: float = random.uniform(0.2, 1.5)
                if dy > 0:
                    # 下スクロールは自然（徐々に）
                    for s in range(random.randint(1, 3)):
                        page.mouse.wheel(0, dy // 3 + random.randint(-10, 10))
                        time.sleep(delay * 0.3)
                else:
                    # 上スクロール（たまに）
                    page.mouse.wheel(0, dy)
                    time.sleep(delay)
                # たまにマウスをランダム位置に動かす
                if random.random() < 0.3:
                    vp = page.viewport_size
                    page.mouse.move(random.randint(100, vp['width']-100),
                                    random.randint(100, vp['height']-100))
            time.sleep(random.uniform(0.5, 2))

            skip_follow: bool = random.random() < random.uniform(0.02, 0.04)
            skip_rt: bool = random.random() < random.uniform(0.01, 0.03)
            skip_like: bool = random.random() < random.uniform(0.03, 0.05)

            # ── アクション順をランダムシャッフル（BOT対策） ──
            def _do_follow() -> None:
                fb = page.query_selector('[data-testid*="follow"]')
                if fb:
                    t: str = (fb.text_content() or '').strip()
                    if 'フォロー' in t or 'Follow' in t:
                        human_like_mouse(page, fb)
                        out("  [OK] フォロー")
                        increment_daily_count(account_key, 'follow')
                        time.sleep(random.uniform(3, 7))
                    else:
                        out("  [i] フォロー済み")
                else:
                    out("  [i] フォローボタンなし（応募対象外かも）")

            def _do_rt() -> None:
                rt_count_before: int = load_daily_counts().get(account_key, {}).get('rt', 0)
                rt_base: int = cfg.get('rate_limits', {}).get('max_rt_per_day', 15)
                rt_jitter: int = cfg.get('rate_limits', {}).get('max_rt_jitter', 0)
                rt_limit: int = rt_base + random.randint(0, rt_jitter)
                if rt_count_before < rt_limit:
                    rt = page.query_selector('[data-testid="retweet"]')
                    if rt:
                        time.sleep(random.uniform(0.5, 2))
                        human_like_mouse(page, rt)
                        time.sleep(random.uniform(1.5, 3.5))
                        for mi in page.query_selector_all('[role="menuitem"]'):
                            if 'リポスト' in (mi.text_content() or ''):
                                human_like_mouse(page, mi)
                                out("  [OK] RT")
                                increment_daily_count(account_key, 'rt')
                                break
                        else:
                            cf = page.query_selector('[data-testid="retweetConfirm"]')
                            if cf:
                                human_like_mouse(page, cf)
                                out("  [OK] RT(confirm)")
                                increment_daily_count(account_key, 'rt')
                    else:
                        out("  [i] RTなし")
                else:
                    out("  [i] RT: 上限到達スキップ")

            def _do_like() -> None:
                like_count_before: int = load_daily_counts().get(account_key, {}).get('like', 0)
                if like_count_before < cfg.get('rate_limits', {}).get('max_like_per_day', 80):
                    like_btn = page.query_selector('[data-testid="like"]')
                    if like_btn:
                        unlike_btn = page.query_selector('[data-testid="unlike"]')
                        if not unlike_btn:
                            time.sleep(random.uniform(0.5, 1.5))
                            human_like_mouse(page, like_btn)
                            out("  [OK] いいね")
                            increment_daily_count(account_key, 'like')
                            time.sleep(random.uniform(2, 5))
                        else:
                            out("  [i] いいね済み")
                    else:
                        out("  [i] いいねボタンなし")
                else:
                    out("  [i] いいね: 上限到達スキップ")

            action_queue = []
            if not skip_follow:
                action_queue.append(_do_follow)
            if not skip_rt:
                action_queue.append(_do_rt)
            if not skip_like:
                action_queue.append(_do_like)
            random.shuffle(action_queue)
            for action_fn in action_queue:
                action_fn()

            # リプライ: 応募はフォロー/いいね/RTのみで行うため無効化
            out("  [i] リプライ: 無効化（応募はフォロー/いいね/RTのみ）")

            item['applied'][account_key] = datetime.now().isoformat()
            success += 1

            if global_idx % break_after_n == 0:
                save_collected_safe(data, account_key, log)
                out(f"  [SAVE] 保存 ({global_idx}/{len(to_process)})")
                rest: float = random.uniform(break_min, break_max)
                out(f"  [TEA] 休憩{rest:.0f}秒（レート制限対策）")
                time.sleep(rest)
            else:
                if random.random() < extra_long_pause_chance:
                    extra: float = random.uniform(60, 120)
                    out(f"  [TEA] 長め休憩{extra:.0f}秒（人間らしさ）")
                    time.sleep(extra)
                else:
                    time.sleep(random.uniform(min_delay, max_delay))

        except Exception as e:
            err_msg: str = str(e)[:60]
            out(f"  [NG] {err_msg}")
            errors += 1
            time.sleep(random.uniform(10, 20))

    save_collected_safe(data, account_key, log)

    # ★ セッション状態保存（クッキー/ローカルストレージ更新）
    try:
        new_storage = ctx.storage_state()
        if session_path:
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(new_storage, f, ensure_ascii=False)
            out("  [SESSION] セッション状態更新")
    except Exception as e:
        out(f"  [WARN] セッション保存失敗: {e}")

    close_browser(p, browser, log)

    final_counts: dict[str, int] = load_daily_counts().get(account_key, {})
    out(f"\n[OK] 完了: {success}成功 / {errors}エラー")
    out(f"   本日累計: フォロー{final_counts.get('follow',0)} RT{final_counts.get('rt',0)} いいね{final_counts.get('like',0)}")
    out(f"   処理時間: 約{(time.time() - t0)/60:.1f}分")

    return (success, errors)
