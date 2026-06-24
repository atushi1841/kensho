"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 型ヒント追加 + 日次上限 + 人間らしいランダム間隔強化
"""
from __future__ import annotations

import sys, os, json, time, random, psutil
from datetime import datetime, date
from pathlib import Path
from typing import Any

from core.config import load as load_config
from application.browser import (
    create_browser, check_x_login, close_browser,
    human_like_mouse,
)
from utils.backup import safe_save_json

DATA_DIR: Path = Path(__file__).parent.parent / 'data'
COLLECTED_FILE: Path = DATA_DIR / 'collected.json'
DAILY_COUNTS_FILE: Path = DATA_DIR / 'daily_counts.json'

# ── collected.json 排他制御（race condition対策）──
COLLECTED_LOCK: Path = DATA_DIR / 'collected.lock'


def _acquire_lock(timeout: int = 30) -> bool:
    """排他ロックを取得する（最大timeout秒待つ）"""
    import os as _os
    deadline: float = time.time() + timeout
    while time.time() < deadline:
        try:
            fd: int = _os.open(str(COLLECTED_LOCK), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
            _os.write(fd, str(os.getpid()).encode())
            _os.close(fd)
            return True
        except (FileExistsError, OSError):
            try:
                with open(COLLECTED_LOCK) as f:
                    old_pid: int = int(f.read().strip())
                if not psutil.pid_exists(old_pid):
                    _os.remove(str(COLLECTED_LOCK))
                    continue
            except Exception as _e:
                print(f"[LOCK] 古いロック読み込み失敗: {_e}", flush=True)
            time.sleep(random.uniform(0.5, 1.5))
            continue
    return False


def _release_lock() -> None:
    """排他ロックを解放"""
    try:
        if COLLECTED_LOCK.exists():
            COLLECTED_LOCK.unlink()
    except Exception as _e:
        print(f"[LOCK] 解放失敗: {_e}", flush=True)


def _save_collected_safe(data: dict[str, Any], account_key: str, log: Any = None) -> None:
    """
    collected.json を安全に保存（race condition対策）。
    保存直前にディスクから再読み込みし、他プロセスの変更をマージしてから書き込む。
    """
    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    locked: bool = _acquire_lock(timeout=30)
    if not locked:
        out("  [LOCK] collected.json ロック取得失敗 → 強制保存")

    try:
        try:
            with open(COLLECTED_FILE, 'r', encoding='utf-8') as f:
                current: dict[str, Any] = json.load(f)
            current_items: list[dict[str, Any]] = current.get('collected', [])
            current_map: dict[str, dict[str, Any]] = {item['detail_url']: item for item in current_items}

            my_items: list[dict[str, Any]] = data.get('collected', [])
            merged_items: list[dict[str, Any]] = list(current_items)
            merged_urls: set[str] = set(current_map.keys())

            for item in my_items:
                detail_url: str = item.get('detail_url', '')
                if detail_url in merged_urls:
                    idx: int = next(i for i, it in enumerate(merged_items) if it.get('detail_url') == detail_url)
                    merged_items[idx]['applied'] = item.get('applied', merged_items[idx].get('applied', {}))
                else:
                    merged_items.append(item)

            data['collected'] = merged_items
        except Exception as _e:
            print(f"[SAVE] マージ読み込み失敗: {_e}", flush=True)

        safe_save_json(COLLECTED_FILE, data, 'collected.json')
    finally:
        if locked:
            _release_lock()


# ── 日次カウンター管理 ──
def _load_daily_counts() -> dict[str, Any]:
    """本日のカウンター読み込み"""
    today: str = date.today().isoformat()
    if DAILY_COUNTS_FILE.exists():
        try:
            with open(DAILY_COUNTS_FILE, 'r', encoding='utf-8') as f:
                data: dict[str, Any] = json.load(f)
            if data.get('date') == today:
                return data.get('counts', {})  # type: ignore[no-any-return]
        except Exception as _e:
            print(f"[LIMIT] 日次カウンター読み込み失敗: {_e}", flush=True)
    return {}


def _save_daily_counts(counts: dict[str, Any]) -> None:
    """本日のカウンター保存（バックアップ付き）"""
    today: str = date.today().isoformat()
    DAILY_COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    safe_save_json(DAILY_COUNTS_FILE, {'date': today, 'counts': counts}, 'daily_counts.json')


def _check_rate_limit(account_key: str, cfg: dict[str, Any]) -> bool:
    """
    日次上限 + 時間あたり上限に達してないかチェック。
    達してれば True（これ以上処理しない）、達してなければ False。
    """
    limits: dict[str, Any] = cfg.get('rate_limits', {})
    max_follow: int = limits.get('max_follow_per_day', 50)
    max_rt: int = limits.get('max_rt_per_day', 15)
    max_like: int = limits.get('max_like_per_day', 80)
    max_reply: int = limits.get('max_reply_per_day', 10)
    max_per_hour: int = limits.get('max_actions_per_hour', 15)

    counts: dict[str, Any] = _load_daily_counts()
    acct: dict[str, Any] = counts.get(account_key, {'follow': 0, 'rt': 0, 'like': 0, 'reply': 0})
    f: int = acct.get('follow', 0)
    r: int = acct.get('rt', 0)
    l: int = acct.get('like', 0)
    rep: int = acct.get('reply', 0)

    if f >= max_follow:
        print(f"[LIMIT] {account_key}: フォロー上限到達 ({f}/{max_follow})")
        return True
    if r >= max_rt:
        print(f"[LIMIT] {account_key}: RT上限到達 ({r}/{max_rt})")
        return True
    if l >= max_like:
        print(f"[LIMIT] {account_key}: いいね上限到達 ({l}/{max_like})")
        return True
    if rep >= max_reply:
        print(f"[LIMIT] {account_key}: リプライ上限到達 ({rep}/{max_reply})")
        return True

    # ── 時間あたり上限チェック ──
    hourly: dict[str, int] = acct.get('hourly', {})
    current_hour: str = datetime.now().strftime('%H')
    hour_total: int = hourly.get(current_hour, 0)
    if hour_total >= max_per_hour:
        print(f"[LIMIT] {account_key}: 時間あたり上限到達 ({hour_total}/{max_per_hour}/時)")
        return True

    return False


def _increment_daily_count(account_key: str, action_type: str, n: int = 1) -> None:
    """日次カウンターと時間別カウンターを増やす"""
    counts: dict[str, Any] = _load_daily_counts()
    if account_key not in counts:
        counts[account_key] = {'follow': 0, 'rt': 0, 'like': 0, 'reply': 0, 'hourly': {}}
    counts[account_key][action_type] = counts[account_key].get(action_type, 0) + n
    # 時間別カウント
    current_hour: str = datetime.now().strftime('%H')
    if 'hourly' not in counts[account_key]:
        counts[account_key]['hourly'] = {}
    counts[account_key]['hourly'][current_hour] = counts[account_key]['hourly'].get(current_hour, 0) + n
    _save_daily_counts(counts)


def _is_active_hours(cfg: dict[str, Any]) -> bool:
    """現在時刻が動作許可時間帯かチェック"""
    limits: dict[str, Any] = cfg.get('rate_limits', {})
    start_s: str = limits.get('active_hours_start', '09:00')
    end_s: str = limits.get('active_hours_end', '23:59')
    now: datetime = datetime.now()
    now_m: int = now.hour * 60 + now.minute
    start_m: int = int(start_s.split(':')[0]) * 60 + int(start_s.split(':')[1])
    end_m: int = int(end_s.split(':')[0]) * 60 + int(end_s.split(':')[1])
    return start_m <= now_m <= end_m


# ── リプライ生成 ──
_REPLY_TEMPLATES: list[str] = [
    "参加します！",
    "応募しました😊",
    "当たりますように🙏",
    "楽しみです！",
    "ぜひ欲しいです✨",
    "いいですね👍",
    "これ気になってました！",
    "絶対欲しいです🔥",
    "応募させていただきます🙌",
    "当選楽しみにしてます！",
]


def _generate_reply(tweet_text: str) -> str:
    """ツイート内容に応じた自然なリプライを生成"""
    text: str = tweet_text.lower()

    if any(w in text for w in ['プレゼント', 'キャンペーン', '懸賞', '抽選']):
        templates: list[str] = [
            "参加します！当たりますように🙏",
            "キャンペーン参加しました✨",
            "ぜひ当たってほしいです😊",
        ]
    elif any(w in text for w in ['感想', '教えて', 'コメント', 'リプライ']):
        templates = [
            "素敵な企画ですね！",
            "面白そうです👍",
            "気になってました✨",
        ]
    elif any(w in text for w in ['春', '夏', '秋', '冬', '季節']):
        season: str = '春' if '春' in text else '夏' if '夏' in text else '秋' if '秋' in text else '冬'
        templates = [
            f"{season}らしい素敵な企画ですね！",
            f"{season}を感じます😊",
        ]
    else:
        templates = _REPLY_TEMPLATES

    return random.choice(templates)


def _human_type(page: Any, element: Any, text: str) -> None:
    """人間らしいタイピング（1文字ずつランダム間隔）"""
    element.focus()
    for char in text:
        page.keyboard.type(char, delay=random.randint(30, 150))
        if random.random() < 0.05:
            time.sleep(random.uniform(0.5, 2))
    time.sleep(random.uniform(0.3, 1.0))


def apply_for_account(account_key: str, max_n: int,
                      cfg: dict[str, Any] | None = None,
                      log: Any = None) -> tuple[int, int]:
    """
    指定されたアカウントで未応募の懸賞に応募する。

    Parameters:
        account_key: アカウントキー（config.yamlのaccounts[].key）
        max_n: 最大処理件数
        cfg: config（Noneなら自動読込）
        log: LogWriter

    Returns: (success_count, error_count)
    """
    t0: float = time.time()
    if cfg is None:
        cfg = load_config()

    # ── 時間帯チェック ──
    if not _is_active_hours(cfg):
        msg: str = "[SKIP] 動作時間外（深夜）→ スキップ"
        if log:
            log.write(msg)
        else:
            print(msg)
        return (0, 0)

    # ── 日次上限チェック ──
    if _check_rate_limit(account_key, cfg):
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
        if _check_rate_limit(account_key, cfg):
            out(f"[LIMIT] {account_key}: 処理中に上限到達 → 残りスキップ")
            break
        account_applied.append(item)

    out(f"[Kensho] この垢の未応募: {len(account_applied)}件")

    import random as _random
    _now: datetime = datetime.now()

    # 賞品価格キャッシュ（x_url → prize_rank）
    _prize_cache: dict[str, int] = {}

    def _fetch_tweet_text(url: str) -> str:
        """twscrapeでツイート本文を取得"""
        if url in _prize_cache:
            return ''  # キャッシュ済み
        try:
            import asyncio
            from twscrape import API
            tweet_id = url.rstrip('/').split('/')[-1]
            async def _get():
                api = API()
                # ゲストセッションで取得
                tweets = await api.tweet_details(tweet_id)
                return tweets.rawContent or ''
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            text = loop.run_until_complete(_get())
            loop.close()
            return text
        except Exception:
            return ''

    def _extract_prize_rank(text: str) -> int:
        """
        ツイートテキストから賞品価格を推定し、ランクを返す。
        高額ほど大きい値。
        ランク値: 0=不明, 1=〜1000円, 2=〜5000円, 3=〜1万円, 4=〜5万円, 5=〜10万円, 10=10万円以上
        """
        if not text:
            return 0
        text_l = text.replace(',', '').replace('、', '')

        # 高額チェック（万円以上）
        m = re.search(r'(\d+)\s*万円', text_l)
        if m:
            val = int(m.group(1))
            if val >= 10:
                return 10  # 10万円以上
            elif val >= 5:
                return 5   # 5万円以上
            elif val >= 1:
                return 3   # 1万円以上

        # 金額（円）
        m = re.search(r'(\d+)\s*円', text_l)
        if m:
            val = int(m.group(1))
            if val >= 10000:
                return 3
            elif val >= 5000:
                return 2
            elif val >= 1000:
                return 1
            return 1

        # ポイント
        m = re.search(r'(\d+)\s*ポイント', text_l)
        if m:
            val = int(m.group(1))
            if val >= 5000:
                return 2
            elif val >= 1000:
                return 1

        # 賞品キーワード
        high_value = ['現金', '旅行', '海外', '金', 'ギフト券', '商品券', 'QUOカード']
        for kw in high_value:
            if kw in text_l:
                return 2

        return 0


    def _sort_key(item: dict[str, Any], now: datetime | None = None) -> float:
        if now is None:
            now = datetime.now()
        dl: str = item.get('deadline', '')
        wc: int = item.get('winner_count', 0)
        x_url: str = item.get('x_url', '')
        dl_score: int = 0
        if dl:
            try:
                dl_date: datetime = datetime.strptime(dl, '%Y-%m-%d')
                days_left: int = (dl_date - now).days
                if days_left >= 0:
                    dl_score = 100 - min(days_left, 100)
                else:
                    dl_score = -100
            except Exception:
                pass
        wc_score: float = min(wc / 100, 100) if wc > 0 else 0
        # 賞品価格ランク（キャッシュ→なければツイート取得）
        if x_url not in _prize_cache:
            tweet_text: str = _fetch_tweet_text(x_url)
            _prize_cache[x_url] = _extract_prize_rank(tweet_text)
        prize_rank: int = _prize_cache[x_url]
        return -(dl_score * 2 + wc_score + prize_rank * 10)

    account_applied.sort(key=_sort_key)

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

        # /status/ がないURL（アカウントページ）はスキップ
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

            # ── フォロー ──
            if not skip_follow:
                fb = page.query_selector('[data-testid*="follow"]')
                if fb:
                    t: str = (fb.text_content() or '').strip()
                    if 'フォロー' in t or 'Follow' in t:
                        human_like_mouse(page, fb)
                        out("  [OK] フォロー")
                        _increment_daily_count(account_key, 'follow')
                        time.sleep(random.uniform(3, 7))
                    else:
                        out("  [i] フォロー済み")
                else:
                    out("  [i] フォローボタンなし")
            else:
                out("  [i] フォロー: スキップ（5%確率）")

            # ── RT ──
            if not skip_rt:
                rt_count_before: int = _load_daily_counts().get(account_key, {}).get('rt', 0)
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
                                _increment_daily_count(account_key, 'rt')
                                break
                        else:
                            cf = page.query_selector('[data-testid="retweetConfirm"]')
                            if cf:
                                human_like_mouse(page, cf)
                                out("  [OK] RT(confirm)")
                                _increment_daily_count(account_key, 'rt')
                    else:
                        out("  [i] RTなし")
                else:
                    out("  [i] RT: 上限到達スキップ")
            else:
                out("  [i] RT: スキップ（8%確率）")

            # ── いいね ──
            if not skip_like:
                like_count_before: int = _load_daily_counts().get(account_key, {}).get('like', 0)
                if like_count_before < cfg.get('rate_limits', {}).get('max_like_per_day', 80):
                    like_btn = page.query_selector('[data-testid="like"]')
                    if like_btn:
                        unlike_btn = page.query_selector('[data-testid="unlike"]')
                        if not unlike_btn:
                            time.sleep(random.uniform(0.5, 1.5))
                            human_like_mouse(page, like_btn)
                            out("  [OK] いいね")
                            _increment_daily_count(account_key, 'like')
                            time.sleep(random.uniform(2, 5))
                        else:
                            out("  [i] いいね済み")
                    else:
                        out("  [i] いいねボタンなし")
                else:
                    out("  [i] いいね: 上限到達スキップ")
            else:
                out("  [i] いいね: スキップ（3%確率）")

            # ── リプライ ──
            if acct.get('disable_reply', False):
                out("  [i] リプライ: 設定で無効化")
            elif not (random.random() < 0.85):  # 15%で実行
                reply_count_before = _load_daily_counts().get(account_key, {}).get('reply', 0)
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

                        reply_text: str = _generate_reply(tweet_text)
                        time.sleep(random.uniform(1, 2))

                        reply_box = page.query_selector('[data-testid="tweetTextarea_0"]')
                        if not reply_box:
                            reply_box = page.query_selector('[role="textbox"]')
                        if reply_box:
                            reply_box.click()
                            time.sleep(random.uniform(0.5, 1.5))
                            _human_type(page, reply_box, reply_text)
                            time.sleep(random.uniform(1, 3))

                            send_btn = page.query_selector('[data-testid="tweetButton"]')
                            if send_btn:
                                time.sleep(random.uniform(0.5, 1.5))
                                human_like_mouse(page, send_btn)
                                out(f"  [OK] リプライ: {reply_text[:30]}...")
                                _increment_daily_count(account_key, 'reply')
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
                _save_collected_safe(data, account_key, log)
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

    _save_collected_safe(data, account_key, log)
    close_browser(p, browser, log)

    final_counts: dict[str, int] = _load_daily_counts().get(account_key, {})
    out(f"\n[OK] 完了: {success}成功 / {errors}エラー")
    out(f"   本日累計: フォロー{final_counts.get('follow',0)} RT{final_counts.get('rt',0)} いいね{final_counts.get('like',0)}")
    out(f"   処理時間: 約{(time.time() - t0)/60:.1f}分")

    return (success, errors)
