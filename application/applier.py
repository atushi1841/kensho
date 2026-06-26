"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 機能を rate_limiter, reply_generator, state, actions に分割
"""
from __future__ import annotations

import json, time, random
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
from application.reply_generator import generate_reply, human_type
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


def apply_for_account(account_key: str, max_n: int,
                      cfg: dict[str, Any] | None = None,
                      log: Any = None) -> tuple[int, int]:
    """
    指定されたアカウントで未応募の懸賞に応募する。

    Parameters:
        account_key: アカウントキー
        max_n: 最大処理件数
        cfg: config（Noneなら自動読込）
        log: LogWriter

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
        out("[Kensho] 処理対象なし。")
        return (0, 0)

    p, browser, ctx, page = create_browser(
        account_key=account_key,
        session_file=str(session_path) if session_path.exists() else None,
        headless=True,
        log=log,
    )

    if not check_x_login(page, log):
        out("[NG] ログイン失敗 - auth_tokenが必要")
        close_browser(p, browser, log)
        return (0, 1)

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

            scrolls: int = random.randint(2, 5)
            for _ in range(scrolls):
                page.evaluate(f'window.scrollBy(0, {random.randint(30, 200)})')
                time.sleep(random.uniform(0.3, 1.2))
            time.sleep(random.uniform(0.5, 2))

            skip_follow: bool = random.random() < 0.05
            skip_rt: bool = random.random() < 0.08
            skip_like: bool = random.random() < 0.03

            # フォロー
            if not skip_follow:
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
                    out("  [i] フォローボタンなし")
            else:
                out("  [i] フォロー: スキップ（5%確率）")

            # RT
            if not skip_rt:
                rt_count_before: int = load_daily_counts().get(account_key, {}).get('rt', 0)
                if rt_count_before < cfg.get('rate_limits', {}).get('max_rt_per_day', 15):
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
            else:
                out("  [i] RT: スキップ（8%確率）")

            # いいね
            if not skip_like:
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
            else:
                out("  [i] いいね: スキップ（3%確率）")

            # リプライ
            if acct.get('disable_reply', False):
                out("  [i] リプライ: 設定で無効化")
            elif not (random.random() < 0.85):  # 15%で実行
                reply_count_before = load_daily_counts().get(account_key, {}).get('reply', 0)
                max_reply: int = cfg.get('rate_limits', {}).get('max_reply_per_day', 10)
                if reply_count_before < max_reply:
                    reply_btn = page.query_selector('[data-testid="reply"]')
                    if reply_btn:
                        time.sleep(random.uniform(1, 3))
                        human_like_mouse(page, reply_btn)
                        time.sleep(random.uniform(2, 4))

                        tweet_text: str = ""
                        try:
                            tweet_text = page.evaluate('''() => {
                                const article = document.querySelector('article');
                                if (!article) return "";
                                const textEls = article.querySelectorAll('[data-testid="tweetText"]');
                                return Array.from(textEls).map(e => e.textContent).join(" ").slice(0, 100);
                            }''')
                        except Exception:
                            pass

                        reply_text: str = generate_reply(tweet_text)
                        time.sleep(random.uniform(1, 2))

                        reply_box = page.query_selector('[data-testid="tweetTextarea_0"]')
                        if not reply_box:
                            reply_box = page.query_selector('[role="textbox"]')
                        if reply_box:
                            reply_box.click()
                            time.sleep(random.uniform(0.5, 1.5))
                            human_type(page, reply_box, reply_text)
                            time.sleep(random.uniform(1, 3))

                            send_btn = page.query_selector('[data-testid="tweetButton"]')
                            if send_btn:
                                time.sleep(random.uniform(0.5, 1.5))
                                human_like_mouse(page, send_btn)
                                out(f"  [OK] リプライ: {reply_text[:30]}...")
                                increment_daily_count(account_key, 'reply')
                                time.sleep(random.uniform(3, 6))
                            else:
                                out("  [i] リプライ送信ボタンなし")
                        else:
                            out("  [i] リプライ入力欄なし")
                    else:
                        out("  [i] リプライボタンなし")
                else:
                    out("  [i] リプライ: 上限到達スキップ")
            else:
                out("  [i] リプライ: スキップ（85%確率）")

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
    close_browser(p, browser, log)

    final_counts: dict[str, int] = load_daily_counts().get(account_key, {})
    out(f"\n[OK] 完了: {success}成功 / {errors}エラー")
    out(f"   本日累計: フォロー{final_counts.get('follow',0)} RT{final_counts.get('rt',0)} いいね{final_counts.get('like',0)}")
    out(f"   処理時間: 約{(time.time() - t0)/60:.1f}分")

    return (success, errors)
