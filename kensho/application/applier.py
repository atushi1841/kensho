"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 機能を rate_limiter, reply_generator, state, actions に分割
"""

from __future__ import annotations

import datetime as dt
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from kensho.application.actions import sort_items
from kensho.application.actions_apply import do_follow, do_like, do_rt
from kensho.application.api_actions import (
    api_follow_by_screen_name,
    api_get_tweet_text,
    api_like,
    api_rt,
    extract_tweet_id_and_screen_name,
    verify_x_api_works,
)
from kensho.application.browser import (
    FINGERPRINTS,
    check_x_login,
    close_browser,
    create_account_context,
    create_browser,
)
from kensho.application.rate_limiter import (
    check_rate_limit,
    is_active_hours,
    load_daily_counts,
)
from kensho.application.state import save_collected_safe
from kensho.core.config import load as load_config
from kensho.scraping.scorer import format_prize_info, score_prize
from kensho.utils.safety import verify_ip_separation

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
COLLECTED_FILE: Path = DATA_DIR / "collected.json"

_DEFER_PREFIX: str = "DEFER:"
_DEFER_HOURS_MIN: int = 4
_DEFER_HOURS_MAX: int = 8
_DEFER_WINDOW_HOURS: int = 6


def _is_deferred(val: Any) -> bool:
    """applied値がDEFERスキップ中か判定"""
    return val is not None and isinstance(val, str) and val.startswith(_DEFER_PREFIX)


def _get_defer_time(val: str) -> dt.datetime | None:
    """DEFERの予定時刻をパース"""
    try:
        return dt.datetime.fromisoformat(val[len(_DEFER_PREFIX) :])
    except Exception:
        return None


def _should_process_item(item: dict[str, Any], account_key: str) -> bool:
    """ツイートを処理すべきか判定（DEFER解除も考慮）"""
    val = item.get("applied", {}).get(account_key)
    if val is None:
        return True  # 未処理
    if _is_deferred(val):
        defer_time = _get_defer_time(str(val))
        if defer_time and dt.datetime.now() >= defer_time:
            return True  # DEFER期限切れ → 処理可能
    return False  # 処理済み または DEFER有効中


def _save_session_cookies(ctx: Any, account_key: str, session_path: Path) -> None:
    """ブラウザコンテキストのセッションクッキーをファイルに保存する（補助機能）"""
    try:
        data = ctx.storage_state()
        session_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _wait_for_memory(cfg: dict, log: Any = None) -> bool:
    """ブラウザ起動前に空きRAMを確認。不足時は最大60秒待機。

    Returns:
            True: メモリ十分（または待機後確保）
            False: タイムアウト（警告ログを出して続行）
    """
    reserve_mb: int = cfg.get("rate_limits", {}).get("memory_reserve_mb", 2048)
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
        out(
            f"[MEM] 空きRAM {avail_mb}MB < {reserve_mb}MB → {min(10, remaining)}秒待機（残り{remaining}秒）"
        )
        time.sleep(min(10, max(1, remaining)))

    avail_mb = psutil.virtual_memory().available // (1024 * 1024)
    out(
        f"[MEM] ⚠ タイムアウト: 空きRAM {avail_mb}MB < {reserve_mb}MB → 強行（クラッシュリスク）"
    )
    return False


def _check_rss_threshold(p: Any, browser: Any, cfg: dict, log: Any = None) -> bool:
    """ブラウザ起動後・ループ中にRSSを監視、危険域ならTrueを返す。
    Returns: True=終了すべき, False=セーフ
    """

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    SAFE_RSS_MB: int = cfg.get("rate_limits", {}).get("memory_rss_limit_mb", 7000)
    try:
        self_rss_mb: int = psutil.Process().memory_info().rss // (1024 * 1024)
        children_rss_mb: int = 0
        try:
            bp = psutil.Process(p.pid) if hasattr(p, "pid") else None
        except Exception:
            bp = None
        if bp:
            children_rss_mb = sum(
                c.memory_info().rss // (1024 * 1024)
                for c in bp.children(recursive=True)
            )
        total_rss_mb: int = self_rss_mb + children_rss_mb
        pct: float = total_rss_mb / SAFE_RSS_MB * 100
        out(
            f"  [MEM] RSS: Py{self_rss_mb}MB + Brw{children_rss_mb}MB = {total_rss_mb}MB ({pct:.0f}%/7GB)"
        )
        if total_rss_mb >= SAFE_RSS_MB:
            out(f"  [MEM] ⚠ RSS {total_rss_mb}MB≧{SAFE_RSS_MB}MB → 組み切り終了")
            return True
        return False
    except Exception as e:
        out(f"  [MEM] RSS監視エラー（続行）: {e}")
        return False


def _check_tweet_result(page: Any, tweet_url: str, out: Any) -> str | None:
    """応募後にツイートの状態を確認。

    ツイートURLに再アクセスし、削除/停止/異常の有無をチェック。
    戻り値: ステータス文字列（None=正常）
    """
    import random
    import time

    # 応募直後で画面が変わっている可能性があるため、少し待ってから再訪問
    time.sleep(random.uniform(1.0, 2.5))

    # 現在のURLを確認 - すでにツイートページなら遷移不要
    current_url = page.url
    if "/status/" not in current_url:
        try:
            page.goto(tweet_url, timeout=30000, wait_until="domcontentloaded")
        except Exception:
            return "goto_failed"
        time.sleep(random.uniform(1.5, 3.0))

    # ページ本文から異常状態を検出
    try:
        body_text = page.inner_text("body")
    except Exception:
        return None  # 判定不能でも正常扱い

    body_lower = body_text.lower()

    # 削除・停止・その他の異常状態
    if "this tweet has been deleted" in body_lower:
        out("  [RESULT] ❌ ツイート削除済み")
        return "tweet_deleted"
    if "this tweet is from a suspended account" in body_lower:
        out("  [RESULT] ❌ アカウント停止")
        return "account_suspended"
    if "hmm...this page doesn't exist" in body_lower:
        out("  [RESULT] ❌ ページ不存在")
        return "page_not_found"
    if "this tweet is unavailable" in body_lower:
        out("  [RESULT] ❌ ツイート利用不可")
        return "tweet_unavailable"
    if "this tweet has been withheld" in body_lower:
        out("  [RESULT] ❌ ツイート非公開（地域制限等）")
        return "tweet_withheld"

    out("  [RESULT] ✅ ツイート正常（応募成立）")
    return "tweet_ok"


def apply_for_account(
    account_key: str,
    max_n: int,
    cfg: dict[str, Any] | None = None,
    log: Any = None,
    dry_run: bool = False,
    shared_browser: Any = None,
    shared_ipw: Any = None,
) -> tuple[int, int]:
    """
    指定されたアカウントで未応募の懸賞に応募する。

    Parameters:
        account_key: アカウントキー
        max_n: 最大処理件数
        cfg: config（Noneなら自動読込）
        log: LogWriter
        dry_run: Trueなら実際の応募はせず、処理対象の表示のみ
        shared_browser: 共有ブラウザオブジェクト（None=従来通り個別起動）
        shared_ipw: 共有ブラウザのipwインスタンス（shared_browser利用時に必要）

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

    # ★ 安全チェック: IP分離ができているか（初回のみ + 30分キャッシュ）
    safety_enabled: bool = cfg.get("safety", {}).get("ip_separation_check", True)
    if safety_enabled and not verify_ip_separation(cfg, log=log):
        msg = "[SAFETY] IP分離チェック失敗 → 全アカウントの応募を中止（プロキシ設定を確認）"
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)
        return (0, 0)

    acct: dict[str, Any] | None = None
    for a in cfg.get("accounts", []):
        if a["key"] == account_key:
            acct = a
            break
    if not acct:
        if log:
            log.write(f"[NG] アカウント '{account_key}' が見つからない")
        return (0, 0)

    display: str = acct.get("display", account_key)
    session_path: Path = Path(cfg["general"]["project_dir"]) / acct["session"]

    # レート制限設定
    limits: dict[str, Any] = cfg.get("rate_limits", {})
    ng_words: list[str] = cfg.get("ng_words", [])
    min_delay: float = limits.get("min_delay_between_actions", 12)
    max_delay: float = limits.get("max_delay_between_actions", 40)
    extra_long_pause_chance: float = limits.get("extra_long_pause_chance", 0.10)
    break_after_n: int = limits.get("break_after_n_items", 3)
    break_min: float = limits.get("break_min_seconds", 30)
    break_max: float = limits.get("break_max_seconds", 90)

    # ★ 時間あたりアクション制限（ループ内でカウント）
    _hourly_max: int = limits.get("max_actions_per_hour", 20)
    _hourly_start: float = time.time()
    _hourly_count: int = 0

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    # ★ ACCOUNT_PROFILESから行動パラメータ抽出
    fp: dict[str, Any] | None = FINGERPRINTS.get(account_key)
    profile: dict[str, Any] = fp.get("profile", {}) if fp else {}
    click_delay: int = profile.get("click_delay", 80)
    scroll_pattern: str = profile.get("scroll_pattern", "smooth")
    work_style: str = profile.get("work_style", "steady")
    typing_speed: int = profile.get("typing_speed", 150)

    out(
        f"[PROFILE] scroll={scroll_pattern} click_delay={click_delay}ms work={work_style} type={typing_speed}ms"
    )

    out(f"[Kensho] アカウント: {display} ({account_key})")

    jitter: int = random.randint(0, 60)
    out(f"[Kensho] スタート遅延: {jitter}秒（cron固定時刻対策）")
    time.sleep(jitter)

    out(f"[Kensho] {datetime.now().strftime('%H:%M:%S')} 開始")

    if not COLLECTED_FILE.exists():
        out("[Kensho] collected.json なし → スキップ")
        return (0, 0)

    with open(COLLECTED_FILE, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    items: list[dict[str, Any]] = data.get("collected", [])
    out(f"[Kensho] 全収集: {len(items)}件")

    account_applied: list[dict[str, Any]] = []
    for item in items:
        if not _should_process_item(item, account_key):
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

    total_available: int = len(account_applied)
    out(f"[Kensho] 処理可能: {total_available}件、目標: {max_n}件（不足時は補充）")

    if total_available == 0:
        out("[Kensho] 処理対象なし。")
        return (0, 0)

    # ── dry-run: 実際の応募はせず対象表示のみ ──
    if dry_run:
        out(
            f"[DRY-RUN] 処理対象 {min(max_n, len(account_applied))}件（実際には応募しません）"
        )
        for di, ditem in enumerate(account_applied[: min(3, max_n)], 1):
            dx_url: str = ditem.get("x_url", "")
            ddeadline: str = ditem.get("deadline", "") or "未設定"
            out(
                f"  [{di}/{min(max_n, len(account_applied))}] 〆{ddeadline} {dx_url[:55]}..."
            )
        if len(account_applied) > 3:
            out(f"  ...他 {len(account_applied) - 3}件")
        out("")
        return (0, 0)

    # ── メモリチェック: ブラウザ起動前に空きRAMを確認 ──
    _wait_for_memory(cfg, log)

    # ── ブラウザ起動 ──
    p: Any = None  # ★ 先に初期化（finallyでclose_browserが安全）
    local_ipw: Any = None
    local_browser: Any = None
    local_ctx: Any = None
    local_page: Any = None
    ctx: Any = None
    browser: Any = None
    page: Any = None
    using_shared: bool = False

    try:
        if shared_browser is not None:
            using_shared = True
            # 共有ブラウザでコンテキスト作成
            local_ctx, local_page = create_account_context(
                shared_browser,
                account_key,
                session_file=str(session_path) if session_path.exists() else None,
                log=log,
            )
            local_browser = shared_browser
            local_ipw = shared_ipw  # 閉じるときには使わない
        else:
            local_ipw, local_browser, local_ctx, local_page = create_browser(
                account_key=account_key,
                session_file=str(session_path) if session_path.exists() else None,
                headless=True,
                log=log,
            )

        p = local_ipw
        browser = local_browser
        ctx = local_ctx
        page = local_page
        page.set_default_timeout(30000)

        if not check_x_login(page, log):
            out("[NG] ログイン失敗 - auth_tokenが必要")
            return (0, 1)  # finally will close browser / context

        x_api_ok = False
        try:
            x_api_ok = verify_x_api_works(page)
        except Exception:
            x_api_ok = False
        out(f"[API] X内部API: {'利用可' if x_api_ok else '利用不可 → 従来方式'}")

        # ★ コンソールエラー抑制：Playwright操作の痕跡をXの検出スクリプトから隠す
        page.on(
            "console", lambda msg: None if msg.type in ("error", "warning") else None
        )
        page.on("pageerror", lambda err: None)

        # ★ セッション実行時間制限
        session_start: float = time.time()
        SESSION_TIMEOUT: int = 480  # 8分で強制打ち切り

        success: int = 0
        errors: int = 0
        idx: int = 0  # account_applied のインデックス（補充用）

        while success < max_n and idx < len(account_applied):
            # ★ セッション時間制限チェック
            if time.time() - session_start >= SESSION_TIMEOUT:
                out(
                    f"  [LIMIT] セッション時間制限（{SESSION_TIMEOUT}秒）→ 打ち切り（{success}件処理済み）"
                )
                break

            # ★ RSSメモリ監視（3件ごと）
            if success > 0 and success % 3 == 0:
                if _check_rss_threshold(p, browser, cfg, log):
                    out(f"  [MEM] RSS超過→保存して終了（{success}件処理済）")
                    save_collected_safe(data, account_key, log)
                    break

            # ★ 日次上限チェック（ループ内でも）
            if check_rate_limit(account_key, cfg):
                out(f"[LIMIT] {account_key}: 処理中に上限到達 → 残りスキップ")
                break

            # ★ 時間あたり上限チェック
            _elapsed_hourly: float = time.time() - _hourly_start
            if _elapsed_hourly >= 3600:
                # 1時間経過 → カウンタリセット
                _hourly_start = time.time()
                _hourly_count = 0
            elif _hourly_count >= _hourly_max:
                out(
                    f"[LIMIT] {account_key}: 時間あたり上限（{_hourly_max}件/時）到達 → 残りスキップ"
                )
                break

            item = account_applied[idx]
            idx += 1
            global_idx: int = success + 1  # 表示用: 何件目を処理中か

            x_url: str = item.get("x_url", "")
            if not x_url:
                out(f"  [{global_idx}/{max_n}] [SKIP] x_url 空")
                continue

            clean_url: str = x_url.split("#")[0]

            if "/status/" not in clean_url.lower():
                out(
                    f"  [{global_idx}/{max_n}] [SKIP] ツイートURLではない: {clean_url[:55]}..."
                )
                continue

            deadline_info: str = item.get("deadline", "") or "未設定"
            wc_info: str = (
                str(item.get("winner_count", ""))
                if item.get("winner_count", 0) > 0
                else "?"
            )
            elapsed_global: float = time.time() - t0

            try:
                out(
                    f"[{global_idx}/{max_n}] ⏱{elapsed_global / 60:.0f}分 "
                    f"〆{deadline_info} {wc_info}名 {clean_url[:50]}..."
                )

                # ★ 同一ツイート複数アカウント連続アクション防止
                # 他アカウントが6時間以内に処理済みなら、自垢は4-8時間後に再試行
                applied_dict: dict[str, Any] = item.get("applied", {})
                now_dt: dt.datetime = dt.datetime.now()
                window_start: dt.datetime = now_dt - dt.timedelta(
                    hours=_DEFER_WINDOW_HOURS
                )
                recent_other: str | None = None
                for other_key, other_val in applied_dict.items():
                    if other_key == account_key:
                        continue
                    if other_val is None:
                        continue
                    if _is_deferred(other_val):
                        continue
                    if isinstance(other_val, str):
                        try:
                            other_time = dt.datetime.fromisoformat(other_val)
                            if other_time >= window_start:
                                recent_other = other_key
                                break
                        except Exception:
                            continue
                if recent_other:
                    defer_hours: float = random.uniform(
                        _DEFER_HOURS_MIN, _DEFER_HOURS_MAX
                    )
                    defer_until: dt.datetime = now_dt + dt.timedelta(hours=defer_hours)
                    item.setdefault("applied", {})[account_key] = (
                        f"{_DEFER_PREFIX}{defer_until.isoformat()}"
                    )
                    save_collected_safe(data, account_key, log)
                    out(
                        f"  [DEFER] 他垢({recent_other})が{_DEFER_WINDOW_HOURS}時間以内に処理済み → "
                        f"{defer_hours:.1f}時間後({defer_until.strftime('%H:%M')})に再試行"
                    )
                    continue

                # ★ URL→tweet_id/screen_name抽出
                tweet_id, screen_name = extract_tweet_id_and_screen_name(clean_url)
                if not tweet_id:
                    out(
                        f"  [{global_idx}/{max_n}] [SKIP] URL解析失敗: {clean_url[:50]}"
                    )
                    continue

                if not x_api_ok:
                    # ★ フォールバック: 従来のpage.goto方式
                    goto_retries = 1
                    goto_ok = False
                    for _gr in range(goto_retries + 1):
                        try:
                            _resp = page.goto(
                                clean_url, timeout=60000, wait_until="domcontentloaded"
                            )
                            _status = _resp.status if _resp else "N/A"
                            out(f"  [GOTO] status={_status}")
                            goto_ok = True
                            break
                        except Exception as _ge:
                            out(
                                f"  [NG] Page.goto attempt {_gr + 1} failed: {str(_ge)[:80]}"
                            )
                            if _gr < goto_retries:
                                time.sleep(2)
                    if not goto_ok:
                        raise RuntimeError(f"Goto failed for {clean_url[:60]}")
                else:
                    out(f"  [API] page.gotoスキップ（tweet_id={tweet_id}）")

                # ★ NGワードフィルター（API経由）
                _skip_ng = False
                if ng_words:
                    try:
                        if x_api_ok:
                            body_text = api_get_tweet_text(page, tweet_id) or ""
                        else:
                            body_text = page.text_content("body") or ""
                        for w in ng_words:
                            if w in body_text:
                                out(f"  [{global_idx}/{max_n}] [SKIP] NGワード: {w}")
                                _skip_ng = True
                                break
                    except Exception:
                        pass
                if _skip_ng:
                    continue

                # ★ 賞品価値推定（scorer）
                # ツイート本文から金額・アイテムを抽出し優先度を計算
                try:
                    prize = score_prize(body_text)
                    if prize["priority"] > 0:
                        out(f"  [PRIZE] {format_prize_info(prize)}")
                        # 高優先度ツイートは保存dataにもマーク
                        item["_prize_score"] = prize
                except Exception:
                    pass

                # ★ 最小RT閾値フィルタ
                # ツイートページからエンゲージメント数を抽出し低エンゲージメントをスキップ
                rt_threshold: int = cfg.get("collection_filter", {}).get(
                    "min_retweet_threshold", 0
                )
                if rt_threshold > 0 and x_api_ok:
                    try:
                        # X APIからツイート詳細を取得してRT数を確認
                        _tweet_detail = api_get_tweet_text(page, tweet_id)  # HTTP get
                        # 簡易RT数抽出: bodyから"リポスト"や"件のリポスト"をスキャン
                        _rt_match = __import__("re").search(
                            r"([\d,]+)\s*件のリポスト", str(_tweet_detail)
                        )
                        if _rt_match:
                            _rt_count = int(_rt_match.group(1).replace(",", ""))
                            if _rt_count < rt_threshold:
                                out(
                                    f"  [{global_idx}/{max_n}] [SKIP] RT不足: {_rt_count} < {rt_threshold}"
                                )
                                continue
                    except Exception:
                        pass

                # ── 読んだふり時間（ツイート閲覧）──
                base_read = random.uniform(3, 8)
                media_delay = 0.0
                if page.query_selector(
                    '[data-testid="tweetPhoto"]'
                ) or page.query_selector("video"):
                    media_delay = random.uniform(2, 5)
                work_coef = {
                    "steady": 1.2,
                    "morning_person": 0.8,
                    "night_owl": 1.0,
                    "burst": 0.7,
                }.get(work_style, 1.0)
                read_time = (base_read + media_delay) * work_coef
                time.sleep(read_time)

                # ★ 自然なスクロール：垢別パターン＋上下混在・速度変化
                _scroll_cfg: dict[str, Any] = {
                    "smooth": {
                        "count": (4, 8),
                        "dy": (30, 120),
                        "delay": (0.3, 1.0),
                        "subdivide": True,
                        "up_chance": 0.15,
                        "mouse_move": 0.2,
                    },
                    "aggressive": {
                        "count": (2, 4),
                        "dy": (80, 350),
                        "delay": (0.1, 0.5),
                        "subdivide": False,
                        "up_chance": 0.10,
                        "mouse_move": 0.1,
                    },
                    "erratic": {
                        "count": (5, 10),
                        "dy": (-120, 200),
                        "delay": (0.2, 2.0),
                        "subdivide": True,
                        "up_chance": 0.40,
                        "mouse_move": 0.4,
                    },
                    "measured": {
                        "count": (3, 6),
                        "dy": (50, 180),
                        "delay": (0.5, 2.5),
                        "subdivide": True,
                        "up_chance": 0.20,
                        "mouse_move": 0.3,
                    },
                    "explorative": {
                        "count": (6, 12),
                        "dy": (-200, 300),
                        "delay": (0.3, 1.8),
                        "subdivide": True,
                        "up_chance": 0.35,
                        "mouse_move": 0.5,
                    },
                }.get(
                    scroll_pattern,
                    {
                        "count": (3, 6),
                        "dy": (-80, 250),
                        "delay": (0.2, 1.5),
                        "subdivide": True,
                        "up_chance": 0.15,
                        "mouse_move": 0.3,
                    },
                )
                scroll_count: int = random.randint(*_scroll_cfg["count"])
                for _ in range(scroll_count):
                    dy: int = random.randint(*_scroll_cfg["dy"])
                    delay: float = random.uniform(*_scroll_cfg["delay"])
                    if _scroll_cfg["subdivide"] and dy > 50:
                        parts: int = random.randint(2, 4)
                        for s in range(parts):
                            page.mouse.wheel(0, dy // parts + random.randint(-8, 8))
                            time.sleep(delay * 0.25)
                    else:
                        page.mouse.wheel(0, dy)
                        time.sleep(delay)
                    # ランダムマウス移動（垢別確率）
                    if random.random() < _scroll_cfg["mouse_move"]:
                        vp = page.viewport_size
                        page.mouse.move(
                            random.randint(100, vp["width"] - 100),
                            random.randint(100, vp["height"] - 100),
                        )
                time.sleep(random.uniform(0.5, 2))

                skip_follow: bool = False  # BOT対策としては他の乱数要素で十分
                skip_rt: bool = False
                skip_like: bool = False

                # ── アクション順をランダムシャッフル（BOT対策） ──

                # ── アクションキュー: skip判定に従って全アクション（強度モード廃止）──
                action_queue = []
                if not skip_follow:
                    if x_api_ok and screen_name:
                        action_queue.append(
                            lambda sn=screen_name: api_follow_by_screen_name(
                                page, sn, account_key, out
                            )
                        )
                    else:
                        action_queue.append(
                            lambda: do_follow(page, click_delay, out, account_key)
                        )
                if not skip_rt:
                    if x_api_ok and tweet_id:

                        def fallback_rt(
                            page=page,
                            click_delay=click_delay,
                            out=out,
                            account_key=account_key,
                            cfg=cfg,
                            clean_url=clean_url,
                            tweet_id=tweet_id,
                        ):
                            if not api_rt(page, tweet_id, account_key, out):
                                out("[i] RT API失敗 → UIフォールバック")
                                for _gr in range(2):
                                    try:
                                        resp = page.goto(
                                            clean_url,
                                            timeout=60000,
                                            wait_until="domcontentloaded",
                                        )
                                        _status = resp.status if resp else "N/A"
                                        out(f"  [GOTO fallback] status={_status}")
                                        break
                                    except Exception as _ge:
                                        out(
                                            f"  [NG] Page.goto fallback attempt "
                                            f"{_gr + 1} failed: {str(_ge)[:60]}"
                                        )
                                        if _gr < 1:
                                            time.sleep(2)
                                # ★ レンダリング待機: XのJS実行に時間がかかる ★
                                # 第一フェーズ: 最大15秒待機
                                _found_rt = False
                                for _w in range(15):
                                    if page.query_selector('[data-testid="retweet"]'):
                                        _found_rt = True
                                        break
                                    time.sleep(1)
                                # 第二フェーズ: 未発見ならページリロードして再試行
                                if not _found_rt:
                                    out(
                                        "  [i] RTボタン未発見、ページリロードして再試行"
                                    )
                                    try:
                                        resp2 = page.goto(
                                            page.url,
                                            timeout=45000,
                                            wait_until="domcontentloaded",
                                        )
                                        out(
                                            f"  [RELOAD] status={resp2.status if resp2 else 'N/A'}"
                                        )
                                    except Exception:
                                        out("  [i] リロード失敗、そのまま続行")
                                    for _w in range(10):
                                        if page.query_selector(
                                            '[data-testid="retweet"]'
                                        ):
                                            break
                                        time.sleep(1)
                                do_rt(page, click_delay, out, account_key, cfg)

                        action_queue.append(fallback_rt)
                    else:
                        action_queue.append(
                            lambda p=page, cd=click_delay, o=out, ak=account_key, c=cfg: (
                                do_rt(p, cd, o, ak, c)
                            )
                        )
                if not skip_like:
                    if x_api_ok and tweet_id:
                        action_queue.append(
                            lambda tid=tweet_id: api_like(page, tid, account_key, out)
                        )
                    else:
                        action_queue.append(
                            lambda: do_like(page, click_delay, out, account_key, cfg)
                        )
                random.shuffle(action_queue)
                for action_fn in action_queue:
                    action_fn()
                    time.sleep(random.uniform(1.0, 3.5))

                # リプライ: 応募はフォロー/いいね/RTのみで行うため無効化
                out("  [i] リプライ: 無効化（応募はフォロー/いいね/RTのみ）")

                # ── 応募結果チェック ──
                tweet_result = _check_tweet_result(page, clean_url, out)
                if tweet_result and tweet_result != "tweet_ok":
                    item.setdefault("results", {})[account_key] = tweet_result
                else:
                    item.setdefault("results", {})[account_key] = "ok"

                # ★ 気晴らしポーズ（稀に長め休憩｜人間らしい中断）
                if random.random() < 0.005:
                    distract_duration: float = random.uniform(20, 40)
                    out("  [DISTRACT] 気晴らし中…👀（人間らしさ）")
                    time.sleep(distract_duration)

                item["applied"][account_key] = datetime.now().isoformat()
                success += 1
                _hourly_count += 1

                if global_idx % break_after_n == 0:
                    save_collected_safe(data, account_key, log)
                    out(f"  [SAVE] 保存 ({success}/{max_n})")
                    # ★ work_style別：burstは短い活動後に長め休憩
                    if work_style == "burst":
                        rest = random.uniform(break_min * 1.5, break_max * 1.3)
                    elif work_style == "night_owl":
                        rest = random.uniform(break_min, break_max * 1.2)
                    elif work_style == "morning_person":
                        rest = random.uniform(break_min * 0.7, break_max * 0.8)
                    else:
                        rest = random.uniform(break_min, break_max)
                    out(f"  [TEA] 休憩{rest:.0f}秒（{work_style}）")
                    time.sleep(rest)
                else:
                    # ★ extra_long_pauseはwork_style別：night_owl/morning_personは非効率的
                    _extra_chance: float = extra_long_pause_chance
                    if work_style == "steady":
                        _extra_chance = extra_long_pause_chance * 1.3
                    elif work_style in ("morning_person", "burst"):
                        _extra_chance = extra_long_pause_chance * 0.6
                    if random.random() < _extra_chance:
                        extra: float = random.uniform(60, 120)
                        out(f"  [TEA] 長め休憩{extra:.0f}秒（人間らしさ）")
                        time.sleep(extra)
                    else:
                        # ★ アクション間待機もwork_style別：morning_personは短め、steadyは長め
                        if work_style == "morning_person":
                            _min_d = min_delay * 0.7
                            _max_d = max_delay * 0.8
                        elif work_style == "steady":
                            _min_d = min_delay * 1.2
                            _max_d = max_delay * 1.1
                        else:
                            _min_d = min_delay
                            _max_d = max_delay
                        time.sleep(random.uniform(_min_d, _max_d))

            except Exception as e:
                err_msg: str = str(e)[:60]
                # try to get page url
                try:
                    cur_url = page.url[:80]
                except Exception:
                    cur_url = "?"
                out(f"  [NG] {err_msg} (url={cur_url})")
                errors += 1
                time.sleep(random.uniform(10, 20))

        save_collected_safe(data, account_key, log)

        # ★ セッション状態保存（クッキー/ローカルストレージ更新）
        _save_session_cookies(ctx, account_key, session_path)
        out("  [SESSION] セッション状態更新")

        final_counts: dict[str, int] = load_daily_counts().get(account_key, {})
        out(f"\n[OK] 完了: {success}成功 / {errors}エラー")
        out(
            f"   本日累計: フォロー{final_counts.get('follow', 0)} RT{final_counts.get('rt', 0)} いいね{final_counts.get('like', 0)}"
        )
        out(f"   処理時間: 約{(time.time() - t0) / 60:.1f}分")

    finally:
        import gc

        if using_shared:
            # 共有ブラウザではコンテキストのみ閉じる
            try:
                if ctx:
                    ctx.close()
            except Exception as _e:
                if log:
                    log.write(f"[WARN] ctx.close失敗: {_e}")
        else:
            if p is not None and browser is not None:
                close_browser(p, browser, log)
        # ★ アカウント終了後: メモリ強制解放
        gc.collect()
        time.sleep(2)
        if log:
            log.write("[MEM] gc.collect + 2s wait 完了")

    return (success, errors)
