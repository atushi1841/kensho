"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 機能を rate_limiter, reply_generator, state, actions に分割
"""

from __future__ import annotations

import datetime as dt
import json
import random
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psutil

# ★ 複数アカウントフォロー案件検出パターン（「@A と @B をフォロー」）
_MULTI_ACCOUNT_FOLLOW_PATTERN: re.Pattern = re.compile(r"@\w+\s+(と|&|＆|and)\s+@\w+", re.IGNORECASE)

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
from kensho.application.verifier import AccountHealthVerifier, ConsecutiveFailureTracker
from kensho.core.config import load as load_config
from kensho.scraping.scorer import format_prize_info, score_prize
from kensho.utils.safety import verify_ip_separation

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
COLLECTED_FILE: Path = DATA_DIR / "collected.json"

_DEFER_PREFIX: str = "DEFER:"


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
        session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
        out(f"[MEM] 空きRAM {avail_mb}MB < {reserve_mb}MB → {min(10, remaining)}秒待機（残り{remaining}秒）")
        time.sleep(min(10, max(1, remaining)))

    avail_mb = psutil.virtual_memory().available // (1024 * 1024)
    out(f"[MEM] ⚠ タイムアウト: 空きRAM {avail_mb}MB < {reserve_mb}MB → 強行（クラッシュリスク）")
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
            children_rss_mb = sum(c.memory_info().rss // (1024 * 1024) for c in bp.children(recursive=True))
        total_rss_mb: int = self_rss_mb + children_rss_mb
        pct: float = total_rss_mb / SAFE_RSS_MB * 100
        out(f"  [MEM] RSS: Py{self_rss_mb}MB + Brw{children_rss_mb}MB = {total_rss_mb}MB ({pct:.0f}%/7GB)")
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
    if safety_enabled:
        safe, blocked_accounts = verify_ip_separation(cfg, log=log)
        if not safe:
            msg = "[SAFETY] IP分離チェック異常 → 全アカウントの応募を中止（全プロキシ不通）"
            if log:
                log.write(msg)
            else:
                print(msg, flush=True)
            return (0, 0)
        if account_key in blocked_accounts:
            msg = f"[SAFETY] {account_key}: IP重複によりブロック → この垢だけスキップ"
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
    required_words: dict = cfg.get("required_words", {})
    skip_url_posts: bool = cfg.get("skip_url_posts", False)
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

    # ★ Failure Ceiling設定読み込み（Loop Engineering）
    fc_cfg: dict = cfg.get("failure_ceiling", {})
    fc_enabled: bool = fc_cfg.get("enabled", True)
    fc_max: int = fc_cfg.get("max_consecutive_failures", 3)
    fc_cooldown: int = fc_cfg.get("cooldown_minutes", 30)

    # ★ 検証設定読み込み
    verif_cfg: dict = cfg.get("verification", {})
    verif_account_health: bool = verif_cfg.get("verify_account_health", True)

    # ★ ConsecutiveFailureTracker（このサイクル用）
    failure_tracker = ConsecutiveFailureTracker(max_consecutive=fc_max, cooldown_minutes=fc_cooldown)

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

    out(f"[PROFILE] scroll={scroll_pattern} click_delay={click_delay}ms work={work_style} type={typing_speed}ms")

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
    account_applied, _removed = sort_items(account_applied)
    if _removed > 0:
        out(f"[索] 期限切れ除外: {_removed}件")

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
        out(f"[DRY-RUN] 処理対象 {min(max_n, len(account_applied))}件（実際には応募しません）")
        for di, ditem in enumerate(account_applied[: min(3, max_n)], 1):
            dx_url: str = ditem.get("x_url", "")
            ddeadline: str = ditem.get("deadline", "") or "未設定"
            out(f"  [{di}/{min(max_n, len(account_applied))}] 〆{ddeadline} {dx_url[:55]}...")
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
        page.set_default_timeout(60000)

        login_success = check_x_login(page, log, screen_name=account_key)
        if not login_success:
            out("[NG] ログイン失敗 - auth_tokenが必要")
            return (0, 1)  # finally will close browser / context

        if verif_account_health and not dry_run:
            try:
                health_check = AccountHealthVerifier()
                # check_x_login が成功している場合はログイン状態チェックをスキップ (UI変更対策)
                if not login_success:
                    login_ok = health_check.check_login_status(page)
                    if not login_ok.success:
                        out(f"  [HEALTH] ⚠ ログイン状態: {login_ok.detail} → この垢スキップ")
                        return (0, 0)
                else:
                    out("  [HEALTH] check_x_login成功によりログイン状態チェックをスキップ")
                rate_ok = health_check.check_rate_limit_error(page)
                if not rate_ok.success:
                    out(f"  [HEALTH] ⚠ レート制限: {rate_ok.detail}")
                susp_ok = health_check.check_account_suspended(page)
                if not susp_ok.success:
                    out(f"  [HEALTH] ⚠ アカウント異常: {susp_ok.detail} → この垢スキップ")
                    return (0, 0)
                out("  [HEALTH] ✅ 健全性OK")
            except Exception as he:
                out(f"  [HEALTH] チェック失敗（続行）: {he}")

        x_api_ok = False
        try:
            x_api_ok = verify_x_api_works(page)
        except Exception:
            x_api_ok = False
        out(f"[API] X内部API: {'利用可' if x_api_ok else '利用不可 → 従来方式'}")

        # ★ コンソールエラー抑制：Playwright操作の痕跡をXの検出スクリプトから隠す
        page.on("console", lambda msg: None if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda err: None)

        # ★ セッション実行時間制限
        # 1800秒(30分)に延長（2026-08-20）: 900秒では1バッチ4〜9件しか処理できず、
        #   max 12-14件の目標に達する前に打ち切られ、日次136枠を損失していた。
        #   50件/日達成のため、バッチ1回で目標件数まで到達できるようにする。
        session_start: float = time.time()
        # 1800秒(30分)→2400秒(40分)に延長（2026-08-23）: RTフォールバック短縮後も、
        # 低速回線垢(kudou/chugakujuken/zin/Tankan)はgoto180s・選択待ち等で1アイテム2〜3分消費し、
        # 30分だとmax 12-14件に達せず6〜8件で打ち切られる。40分に延ばし目標件数まで到達させる。
        SESSION_TIMEOUT: int = 2400  # 30分→40分

        success: int = 0
        errors: int = 0
        idx: int = 0  # account_applied のインデックス（補充用）

        while success < max_n and idx < len(account_applied):
            # ★ セッション時間制限チェック
            if time.time() - session_start >= SESSION_TIMEOUT:
                out(f"  [LIMIT] セッション時間制限（{SESSION_TIMEOUT}秒）→ 打ち切り（{success}件処理済み）")
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
                out(f"[LIMIT] {account_key}: 時間あたり上限（{_hourly_max}件/時）到達 → 残りスキップ")
                break

            # ★ Failure Ceiling: 連続失敗上限に達したらスキップ
            if fc_enabled and failure_tracker.is_ceiling_hit(account_key):
                out(
                    f"  [CEILING] {account_key}: 連続{failure_tracker.consecutive_count(account_key)}回失敗 → "
                    f"このサイクル打ち切り"
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
                out(f"  [{global_idx}/{max_n}] [SKIP] ツイートURLではない: {clean_url[:55]}...")
                continue

            deadline_info: str = item.get("deadline", "") or "未設定"
            # ★ 締切切れチェック（過去日付は応募不可 → スキップ。無駄な404消費とRT失敗を防止）
            if deadline_info != "未設定":
                try:
                    if datetime.strptime(deadline_info, "%Y-%m-%d").date() < datetime.now().date():
                        out(f"  [{global_idx}/{max_n}] [SKIP] 締切切れ: {deadline_info}")
                        continue
                except ValueError:
                    pass
            wc_info: str = str(item.get("winner_count", "")) if item.get("winner_count", 0) > 0 else "?"
            elapsed_global: float = time.time() - t0

            try:
                out(
                    f"[{global_idx}/{max_n}] ⏱{elapsed_global / 60:.0f}分 "
                    f"〆{deadline_info} {wc_info}名 {clean_url[:50]}..."
                )

                # ★ URL→tweet_id/screen_name抽出
                tweet_id, screen_name = extract_tweet_id_and_screen_name(clean_url)
                if not tweet_id:
                    out(f"  [{global_idx}/{max_n}] [SKIP] URL解析失敗: {clean_url[:50]}")
                    continue

                # ── 保存済みtweet_textがあれば優先利用（収集時にtwscrapeが取得）──
                # ただし fixupx の og:description は168文字で打ち切られるため、
                # 保存テキストが短い場合（200字未満）は X内部APIから全文を取得する
                stored_text = item.get("tweet_text", "") or ""
                if stored_text:
                    body_text = stored_text
                    _body_from_api = True
                    _need_goto = False
                    out(f"  [STORE] ✓ 保存済みテキスト利用（{len(body_text)}文字）")

                    # ★ 保存テキストが短い場合、APIから全文を取得してNGフィルター用に上書き
                    if x_api_ok and len(stored_text) < 200:
                        _api_full = api_get_tweet_text(page, tweet_id, log_fn=out) or ""
                        if _api_full and len(_api_full) > len(stored_text) + 20:
                            body_text = _api_full
                            item["tweet_text"] = _api_full  # 書き戻し（state.saveで保存）
                            out(f"  [API] ⬆ 全文に置換（{len(stored_text)}→{len(body_text)}文字、NGフィルター用）")
                else:
                    # ── 本文取得（API優先、失敗時はpage.goto）──
                    _need_goto = not x_api_ok
                    _body_from_api = False
                    body_text = ""

                    if x_api_ok:
                        out(f"  [API] fetch中（tweet_id={tweet_id}）")
                        body_text = api_get_tweet_text(page, tweet_id, log_fn=out) or ""
                        if body_text:
                            _body_from_api = True
                            item["tweet_text"] = body_text  # 書き戻し（state.saveで保存）
                            out(f"  [API] ✓ テキスト取得成功（{len(body_text)}文字）")
                        else:
                            out("  [API] テキスト取得失敗 → page.gotoにフォールバック")
                            _need_goto = True

                # ── fixupx.comからツイート本文を取得（povo 30kbps / AiR-WiFi遅延: goto不可の最終手段）──
                if not body_text and _need_goto:
                    _fixupx_accounts = {"kudou", "chugakujuken", "zin20120731", "TankanNotes"}
                    if account_key in _fixupx_accounts:
                        out("  [FIXUPX] 低速回線: fixupx.comでテキスト取得試行...")
                        try:
                            _fx_url = clean_url.replace("x.com/", "fixupx.com/").replace("twitter.com/", "fixupx.com/")
                            _fx_resp = httpx.get(
                                _fx_url,
                                headers={
                                    "User-Agent": (
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/125.0.0.0 Safari/537.36"
                                    )
                                },
                                follow_redirects=True,
                                timeout=15,
                            )
                            if _fx_resp.status_code == 200 and _fx_resp.text:
                                _m = re.search(
                                    r'<meta\s+property="og:description"\s+content="([^"]*)"',
                                    _fx_resp.text,
                                )
                                if _m and _m.group(1).strip():
                                    body_text = _m.group(1).strip()
                                    _body_from_api = True
                                    _need_goto = False
                                    out(f"  [FIXUPX] ✓ テキスト取得成功（{len(body_text)}文字）")
                                else:
                                    out("  [FIXUPX] ✗ og:descriptionなし → gotoスキップ")
                            else:
                                out(f"  [FIXUPX] ✗ HTTP {_fx_resp.status_code} → gotoスキップ")
                        except Exception as _fx_e:
                            out(f"  [FIXUPX] ✗ {type(_fx_e).__name__}: {_fx_e} → gotoスキップ")

                if _need_goto:
                    # ★ 低速回線: gotoフォールバック不可（180秒以内にページ読み込み完了しない）
                    _fixupx_accounts = {"kudou", "chugakujuken", "zin20120731", "TankanNotes"}
                    if account_key in _fixupx_accounts:
                        out("  [SKIP] 低速回線: goto不可（180秒以内にページ読み込み完了しない）→ 次アイテムへ")
                        continue

                    # 速度別goto設定: 速い垢(commit+30s) / 遅い垢(domcontentloaded+60s)
                    _fast_accounts = {"atushi16"}
                    _slow_accounts = {"kudou", "chugakujuken", "zin20120731", "TankanNotes"}
                    _is_fast = account_key in _fast_accounts
                    _is_slow = account_key in _slow_accounts
                    _goto_wait = "commit" if _is_fast else "domcontentloaded"
                    _goto_timeout = 30000 if _is_fast else 180000
                    for _gr in range(3 if _is_fast else 1):
                        try:
                            # wait_until="commit" → サブリソースストール回避（X Bot検出対策）
                            _resp = page.goto(clean_url, timeout=_goto_timeout, wait_until=_goto_wait)
                            _status = _resp.status if _resp else "N/A"
                            out(f"  [GOTO] status={_status}")
                            # ★ tweetTextセレクタのレンダリングを待つ（domcontentloaded後にJSで描画される）
                            _wait_selector_timeout = 8000 if _is_fast else (60000 if _is_slow else 15000)
                            try:
                                page.wait_for_selector('[data-testid="tweetText"]', timeout=_wait_selector_timeout)
                            except Exception:
                                out("  [GOTO] tweetText selector not rendered yet")
                                pass
                            # ★ ツイート本文のみ抽出（data-testid="tweetText"）— body全体だとサイドバー/メニューのテキストが混入  # noqa: E501
                            body_text = (
                                page.evaluate(
                                    """() => {
                                        const el = document.querySelector('[data-testid="tweetText"]');
                                        return el ? el.textContent.trim() : '';
                                    }"""
                                )
                                or ""
                            )
                            if not body_text:
                                # フォールバック: article内のdata-testid付きdivのみ抽出（引用RT・画像alt等の混入防止）
                                out("  [GOTO] tweetText見つからず→article内div[data-testid]から抽出")
                                body_text = (
                                    page.evaluate(
                                        """() => {
                                            const article = document.querySelector('article');
                                            if (!article) return '';
                                            const divs = article.querySelectorAll('div[data-testid]');
                                            let texts = [];
                                            for (const d of divs) {
                                                const txt = d.textContent.trim();
                                                if (txt && txt.length > 5) texts.push(txt);
                                            }
                                            return texts.join('\\n');
                                        }"""
                                    )
                                    or ""
                                )
                                if not body_text:
                                    out("  [GOTO] 最終フォールバック: article要素全文 (JS polling)")
                                    _poll_timeout = 60 if _is_slow else 30
                                    article_text = ""
                                    for _ in range(_poll_timeout):
                                        article_text = (
                                            page.evaluate(
                                                """() => {
                                                    const art = document.querySelector('article');
                                                    if (!art) return '';
                                                    return art.textContent.trim();
                                                }"""
                                            )
                                            or ""
                                        )
                                        if article_text:
                                            break
                                        time.sleep(1)
                                    body_text = article_text
                            break
                        except Exception as _ge:
                            out(f"  [NG] Page.goto attempt {_gr + 1} failed: {str(_ge)[:80]}")
                            if _gr < 2:
                                time.sleep(2)
                    if not body_text:
                        raise RuntimeError(f"Goto+text failed for {clean_url[:60]}")

                # ★ NGワードフィルター
                _skip_ng = False
                if ng_words:
                    try:
                        for w in ng_words:
                            if w in body_text:
                                out(f"  [{global_idx}/{max_n}] [SKIP] NGワード: {w}")
                                _skip_ng = True
                                break
                    except Exception:
                        pass
                if _skip_ng:
                    continue

                # ★ 複数アカウントフォローチェック（「@A と @B をフォロー」案件）
                try:
                    if _MULTI_ACCOUNT_FOLLOW_PATTERN.search(body_text):
                        out(f"  [{global_idx}/{max_n}] [SKIP] 複数アカウントフォロー案件")
                        continue
                except Exception:
                    pass

                # ★ URLフィルター（URLを含む投稿はスキップ）
                if skip_url_posts:
                    try:
                        if re.search(r"https?://", body_text):
                            out(f"  [{global_idx}/{max_n}] [SKIP] URL含む投稿はNG")
                            continue
                    except Exception:
                        pass

                # ★ 必須ワードフィルター
                # 「フォロー」を含み、かつ「リポスト」「RT」「リプライ」のいずれかを含む
                if required_words:
                    try:
                        require_all = required_words.get("require_all", [])
                        require_any = required_words.get("require_any", [])
                        missing_all = [w for w in require_all if w not in body_text]
                        if missing_all:
                            out(f"  [{global_idx}/{max_n}] [SKIP] 必須ワード不足（{', '.join(missing_all)}が無い）")
                            continue
                        if require_any:
                            has_any = any(w in body_text for w in require_any)
                            if not has_any:
                                out(
                                    f"  [{global_idx}/{max_n}] [SKIP] 必須ワード不足（{', '.join(require_any)}のいずれかが必要）"  # noqa: E501
                                )
                                continue
                    except Exception:
                        pass

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
                rt_threshold: int = cfg.get("collection_filter", {}).get("min_retweet_threshold", 0)
                if rt_threshold > 0 and x_api_ok:
                    try:
                        # X APIからツイート詳細を取得してRT数を確認
                        _tweet_detail = api_get_tweet_text(page, tweet_id)  # HTTP get
                        # 簡易RT数抽出: bodyから"リポスト"や"件のリポスト"をスキャン
                        _rt_match = __import__("re").search(r"([\d,]+)\s*件のリポスト", str(_tweet_detail))
                        if _rt_match:
                            _rt_count = int(_rt_match.group(1).replace(",", ""))
                            if _rt_count < rt_threshold:
                                out(f"  [{global_idx}/{max_n}] [SKIP] RT不足: {_rt_count} < {rt_threshold}")
                                continue
                    except Exception:
                        pass

                # ── 読んだふり時間（ツイート閲覧）──
                base_read = random.uniform(3, 8)
                media_delay = 0.0
                if page.query_selector('[data-testid="tweetPhoto"]') or page.query_selector("video"):
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

                # ★ アクションスキップ確率（BOT検出回避：全アイテムに全アクションは不自然）
                # 各アクションの実行確率。フォローが最も危険、いいねは安全。
                # 2026-08-20 スキップ率低減: 応募量を増やしつつ、日次/時間上限+不定期間隔でBOT対策を維持。
                #   config.yaml の applier.skip_rates.{follow,rt,like,all} で調整可能（デフォルト: 15/20/30/5%）。
                _skip_cfg: dict = cfg.get("applier", {}).get("skip_rates", {})
                _skip_chance_follow: float = _skip_cfg.get("follow", 0.15)
                _skip_chance_rt: float = _skip_cfg.get("rt", 0.20)
                _skip_chance_like: float = _skip_cfg.get("like", 0.30)
                _skip_chance_all: float = _skip_cfg.get("all", 0.05)

                skip_follow: bool = random.random() < _skip_chance_follow
                skip_rt: bool = random.random() < _skip_chance_rt
                skip_like: bool = False  # 条件付きいいねは後で個別処理

                # ★ 条件付きいいね: 本文に「いいね」要件がない時はスキップ、あっても確率スキップ
                _like_in_text = "いいね" in body_text
                if not _like_in_text:
                    if random.random() < 0.90:
                        skip_like = True
                        out("  [SKIP] いいね: 本文に要件なし → スキップ")
                    else:
                        skip_like = False
                        out("  [i] いいね: 要件なしだが自然ないいね実行")
                elif random.random() < _skip_chance_like:
                    skip_like = True
                    out("  [SKIP] いいね: 要件はあるが確率スキップ（自然分散）")

                # ★ 稀に全アクションスキップ（人間らしい「読んだけど応募しない」動作）
                if not skip_follow and not skip_rt and not skip_like:
                    if random.random() < _skip_chance_all:  # 稀に全部スキップ（人間らしさ）
                        skip_follow = True
                        skip_rt = True
                        skip_like = True
                        out("  [SKIP] 全アクション: 見て終わり（人間らしさ）")

                # ★ 同一ツイートへの複数種アクション禁止（BOT検出回避・絶対ルール）
                # フォロー or RT が実行される(=応募本体)ツイートにはいいねを混ぜない。
                # いいねは「応募しない」ツイート(フォローもRTもしない)でのみ単独実行 = 自然な人間行動を維持。
                if not (skip_follow and skip_rt):
                    skip_like = True
                    out("  [SKIP] いいね: フォロー/RT実行中 → 同一ツイート複数アクション回避")

                # ── アクション順をランダムシャッフル（BOT対策） ──

                # ── アクションキュー: skip判定に従って全アクション（強度モード廃止）──
                action_queue: list[tuple[str, Any]] = []

                # ★ 過フォロー防止: 同一主催者へのフォロー上限チェック（BOT検出回避）
                if not skip_follow and screen_name:
                    from kensho.application.follow_state_manager import FollowStateManager

                    _fsm = FollowStateManager(account_key)
                    if not _fsm.should_follow(screen_name):
                        skip_follow = True
                        out(f"  [SKIP] フォロー: 同一主催者{screen_name}フォロー上限到達")

                def _make_follow_with_record(
                    _acct: str,
                    _sn: str,
                    _page: Any,
                    _out: Callable[[str], None],
                ) -> Callable[[], bool]:
                    def _fn() -> bool:
                        _r = api_follow_by_screen_name(_page, _sn, _acct, _out)
                        if _r:
                            from kensho.application.follow_state_manager import FollowStateManager

                            FollowStateManager(_acct).record_follow(_sn)
                        return _r

                    return _fn

                if not skip_follow:
                    if x_api_ok and screen_name:
                        action_queue.append((
                            "follow",
                            _make_follow_with_record(account_key, screen_name, page, out),
                        ))
                    else:
                        action_queue.append(("follow", lambda: do_follow(page, click_delay, out, account_key)))
                if not skip_rt:

                    def fallback_rt(
                        page=page,
                        click_delay=click_delay,
                        out=out,
                        account_key=account_key,
                        cfg=cfg,
                        clean_url=clean_url,
                        tweet_id=tweet_id,
                        item=item,
                    ):
                        # ★ 2026-08-23修正:
                        #   ① code327誤判定撤廃 → api_rtは原则UIフォールバックへFalseを返す
                        #   ② UIフォールバックを「実クリックで確実化」し、RT成否をboolで返す
                        try:
                            _rt_ok = api_rt(page, tweet_id, account_key, out)
                        except Exception as _re:
                            out(f"  [i] RT API例外: {str(_re)[:40]}")
                            _rt_ok = False
                        if _rt_ok is True:
                            return True
                        if _rt_ok is None:
                            # ★ 2026-08-25: ツイート削除/保護(stale) → これ以上の再試行は無駄なので
                            #   item に直接 DEFER(14日) を書く。収集ソースが削除済みツイートを返し続けても、
                            #   毎サイクル404アクセスするのを止める（8/24実測: 同一ツイート44回）。
                            try:
                                from datetime import timedelta

                                item.setdefault("results", {})[account_key] = "tweet_deleted"
                                _def_until = datetime.now() + timedelta(
                                    days=cfg.get("applier", {}).get("defer_deleted_days", 14)
                                )
                                item.setdefault("applied", {})[account_key] = f"{_DEFER_PREFIX}{_def_until.isoformat()}"
                                out(f"[DEFER] RT: 削除済み/非公開ツイート → {_def_until.date()}までスキップ")
                            except Exception:
                                pass
                            return False
                        # APIがAuthorizationError(code327)で全クエリ失敗 → この垢のRT APIは現状不通。
                        # UIフォールバックの90000ms×2 gotoで1アイテム90〜180秒浪費し、
                        # セッションが「6〜8件で打ち切り」→ 日次応募が頭打ちになるのが主因。
                        # フォールバックのgotoタイムアウトを短縮し、遅延リトライを1回に制限する。
                        out("[i] RT API失敗 → UIフォールバック（実クリックで確実化・短縮版）")
                        try:
                            # RTボタン既出（イベント中・遷移済み）なら再遷移不要
                            if not (
                                page.query_selector('[data-testid="retweet"]')
                                or page.query_selector('[data-testid="unretweet"]')
                            ):
                                _to: int = 20000 if account_key == "atushi16" else 25000
                                _goto_ok: bool = False
                                for _gr in range(2):  # 90000×2 → 25000×2 に短縮＋失敗検出
                                    try:
                                        page.goto(clean_url, timeout=_to, wait_until="domcontentloaded")
                                        _goto_ok = True
                                        break
                                    except Exception as _ge:
                                        out(f"  [NG] RT goto attempt {_gr + 1}: {str(_ge)[:50]}")
                                        if _gr == 0:
                                            time.sleep(3)  # 回線遅延を待って再試行
                                if not _goto_ok:
                                    # goto失敗＝ページ未ロード→no_rt_button量産を防ぐため次ツイートへ
                                    out("  [i] RT goto失敗 → RT実行スキップ（次ツイートへ）")
                                    return False
                                # RTボタン描画待ち（最大20秒）
                                for _w in range(20):
                                    if page.query_selector('[data-testid="retweet"]') or page.query_selector(
                                        '[data-testid="unretweet"]'
                                    ):
                                        break
                                    time.sleep(1)
                        except Exception as _ne:
                            out(f"  [i] RT UI遷移エラー: {str(_ne)[:50]}")
                        return do_rt(page, click_delay, out, account_key, cfg)

                    action_queue.append(("rt", fallback_rt))
                # ★ いいねアクション（条件付き）を別途保持
                like_action: tuple[str, Any] | None = None
                if not skip_like:
                    if x_api_ok and tweet_id:
                        like_action = ("like", lambda tid=tweet_id: api_like(page, tid, account_key, out))
                    else:
                        like_action = ("like", lambda: do_like(page, click_delay, out, account_key, cfg))

                # ★ アクション順: フォローは必ずRTより前。いいねだけランダム位置
                #   パターン（重み付き＋垢別バイアス＋毎回ジッター＝自然な分布）:
                #     フォロー→いいね→RT (45%基準): 読む→フォロー→いいね→RTの自然な流れ
                #     いいね→フォロー→RT (25%基準): 気軽にいいね先行
                #     フォロー→RT→いいね (30%基準): 応募優先、いいねは後回し
                _pat_weights = [25, 45, 30]  # [like先, follow→like→RT, follow→RT→like]
                # 垢別バイアス（人間は各自のクセがある）
                _account_bias = {
                    "atushi16": (+5, -5, 0),  # しっかり派: follow→like多め
                    "kudou": (-10, +5, +5),  # 気まま: いいね先行多め
                    "chugakujuken": (0, +5, -5),  # バランス型
                    "zin20120731": (+5, 0, -5),  # 安定志向
                    "TankanNotes": (0, -5, +5),  # ゆったり
                }.get(account_key, (0, 0, 0))
                _pat_weights = [max(1, w + b + random.randint(-8, 8)) for w, b in zip(_pat_weights, _account_bias)]
                if like_action is not None:
                    insert_pos = random.choices([0, 1, 2], weights=_pat_weights, k=1)[0]
                    action_queue.insert(insert_pos, like_action)

                false_count = 0
                # ★ アクション成否記録（応募成立判定に使用）
                _per_item_ok: dict[str, bool] = {"follow": False, "rt": False, "like": False}
                action_count = len(action_queue)
                for idx, (_name, _fn) in enumerate(action_queue):
                    result = _fn()
                    _rv = bool(result)
                    _per_item_ok[_name] = _per_item_ok.get(_name) or _rv
                    if result is False:
                        false_count += 1
                        if false_count >= 3:
                            out("  [FROZEN] 連続失敗3回 → アカウント凍結の可能性 → バッチ中断")
                            break
                    else:
                        false_count = 0
                    if idx < action_count - 1 and action_count >= 2:
                        if random.random() < 0.75:
                            delay = random.uniform(6, 25)
                        else:
                            delay = random.uniform(30, 90)
                        time.sleep(delay)
                    else:
                        time.sleep(random.uniform(1.0, 3.5))

                # ── Post-action browser verification ──
                # API calls may return false successes (200 with errors, 403 treated as "already done")
                # Navigate to tweet and verify actual button states
                total_v = 0
                fail_v = 0
                if cfg.get("verification", {}).get("enabled", False):
                    _vcfg: dict = cfg.get("verification", {})
                    time.sleep(random.uniform(1.0, 2.0))
                    try:
                        page.goto(clean_url, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(random.uniform(2.0, 3.5))
                        from kensho.application.verifier import ActionVerifier

                        if not skip_rt and tweet_id and _vcfg.get("verify_rt", False):
                            rt_result = ActionVerifier.verify_retweet(page, tweet_id, fallback_url=clean_url)
                            total_v += 1
                            if not rt_result.success:
                                fail_v += 1
                                out(f"  [VERIFY] RT: x {rt_result.detail}")
                            else:
                                out("  [VERIFY] RT: ok")
                        if not skip_like and tweet_id and _vcfg.get("verify_like", False):
                            like_result = ActionVerifier.verify_like(page, tweet_id, fallback_url=clean_url)
                            total_v += 1
                            if not like_result.success:
                                fail_v += 1
                                out(f"  [VERIFY] Like: x {like_result.detail}")
                            else:
                                out("  [VERIFY] Like: ok")
                        if not skip_follow and screen_name and _vcfg.get("verify_follow", False):
                            follow_result = ActionVerifier.verify_follow(page, screen_name)
                            total_v += 1
                            if not follow_result.success:
                                fail_v += 1
                                out(f"  [VERIFY] Follow: x {follow_result.detail}")
                            else:
                                out("  [VERIFY] Follow: ok")
                    except Exception as ve:
                        out(f"  [VERIFY] エラー: {ve}")
                        if fc_enabled:
                            failure_tracker.record_failure(account_key)

                # Verify全件失敗チェック
                if total_v > 0 and fail_v == total_v:
                    out(f"  [VERIFY] 全件失敗 ({fail_v}/{total_v}) → failure_tracker記録")
                    if fc_enabled:
                        failure_tracker.record_failure(account_key)
                        fc_count = failure_tracker.consecutive_count(account_key)
                        if fc_count >= fc_max:
                            out(f"  [CEILING] 連続{fc_count}回失敗 → 上限到達（残りスキップ）")
                            save_collected_safe(data, account_key, log)
                            break

                # リプライ: 応募はフォロー/いいね/RTのみで行うため無効化
                out("  [i] リプライ: 無効化（応募はフォロー/いいね/RTのみ）")

                # ── 応募結果チェック ──
                # ★ 2026-08-23修正: 「応募成立」は最低1アクション(follow/rt/like)の実成功に限定。
                #   ツイートが正常+1アクション成功 → ok。RT必須案件でRTだけ失敗 → rt_failedと記録
                #   し、appliedを付けない（次サイクルで再試行）。false成立(偽装)を防ぐ。
                tweet_result = _check_tweet_result(page, clean_url, out)
                _qualify: bool = (tweet_result == "tweet_ok" and any(_per_item_ok.values())) or len(
                    action_queue
                ) == 0  # 全スキップ(見て終わり)は自然な合格扱い
                if tweet_result and tweet_result != "tweet_ok":
                    item.setdefault("results", {})[account_key] = tweet_result
                    # ★ 2026-08-23修正: 削除済み/無効ツイートを DEFER で長期スキップし、
                    #   次のサイクルで無限に再処理（重複フォロー/RT・セッション時間浪費）するのを防ぐ。
                    #   実測: 同一ツイートへ RT を96回も失敗したケースあり。適用判定は
                    #   _should_process_item が DEFER 期限を尊重するため安全。
                    _defer_suppress: set[str] = {
                        "tweet_deleted",
                        "account_suspended",
                        "page_not_found",
                        "tweet_unavailable",
                        "tweet_withheld",
                    }
                    if tweet_result in _defer_suppress:
                        try:
                            from datetime import timedelta

                            _def_until = datetime.now() + timedelta(
                                days=cfg.get("applier", {}).get("defer_deleted_days", 14)
                            )
                            item.setdefault("applied", {})[account_key] = f"{_DEFER_PREFIX}{_def_until.isoformat()}"
                            out(f"  [DEFER] 削除/無効ツイート → {_def_until.date()}までスキップ")
                        except Exception:
                            pass
                elif _qualify:
                    item.setdefault("results", {})[account_key] = "ok"
                else:
                    _rt_was_demanded: bool = not skip_rt
                    if _rt_was_demanded and not _per_item_ok.get("rt"):
                        # ★ 2026-08-25: RT 404(削除済み)は fallback_rt 内で item に直接DEFER済み。
                        #   ここでは fallback_rt がDEFERしなかった単純RT失敗のみ再試行対象にする。
                        if item.get("results", {}).get(account_key) != "tweet_deleted":
                            item.setdefault("results", {})[account_key] = "rt_failed"
                            out("  [RESULT] ⚠ RT未成立 → 応募成立と記録せず（再試行対象）")
                    else:
                        item.setdefault("results", {})[account_key] = "no_action_applied"
                        out("  [RESULT] ⚠ アクション未成功 → 応募成立と記録せず")

                # ★ 気晴らしポーズ（稀に長め休憩｜人間らしい中断）
                if random.random() < 0.005:
                    distract_duration: float = random.uniform(20, 40)
                    out("  [DISTRACT] 気晴らし中…👀（人間らしさ）")
                    time.sleep(distract_duration)

                if _qualify:
                    item["applied"][account_key] = datetime.now().isoformat()
                    # ★ 連続失敗リセット（成功）
                    if fc_enabled:
                        failure_tracker.record_success(account_key)
                    success += 1
                    _hourly_count += 1
                else:
                    # 未成立: appliedを付けず次サイクルで再試行。失敗として記録。
                    out("  [CEILING] アクション未成立 → 成功扱いせず（applied付与なし→再試行）")
                    if fc_enabled:
                        failure_tracker.record_failure(account_key)

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
                # ★ Failure Ceiling: 連続失敗を記録
                if fc_enabled:
                    failure_tracker.record_failure(account_key)
                    fc_count = failure_tracker.consecutive_count(account_key)
                    if fc_count >= fc_max:
                        out(f"  [CEILING] 連続{fc_count}回失敗 → 上限到達（残りスキップ）")
                        save_collected_safe(data, account_key, log)
                        break
                time.sleep(random.uniform(10, 20))

        save_collected_safe(data, account_key, log)

        # ★ Failure Ceilingサマリー（連続失敗があった場合のみ）
        if fc_enabled:
            fc_count = failure_tracker.consecutive_count(account_key)
            if fc_count > 0:
                out(f"  [CEILING] このサイクルの連続失敗: {fc_count}回")
                if failure_tracker.is_ceiling_hit(account_key):
                    out(f"  [CEILING] → 上限到達のため次回{fc_cooldown}分後に再開予定")

        # ★ セッション状態保存（クッキー/ローカルストレージ更新）
        _save_session_cookies(ctx, account_key, session_path)
        out("  [SESSION] セッション状態更新")

        final_counts: dict[str, int] = load_daily_counts().get(account_key, {})
        out(f"\n[OK] 完了: {success}成功 / {errors}エラー")
        out(
            f"   本日累計: フォロー{final_counts.get('follow', 0)} RT{final_counts.get('rt', 0)} いいね{final_counts.get('like', 0)}"  # noqa: E501
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
