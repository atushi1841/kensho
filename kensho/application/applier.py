"""
Kensho Applier — X懸賞応募（フォロー・RT・いいね）
v3.3: 機能を rate_limiter, reply_generator, state, actions に分割
"""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import random
import re
import time
from collections import deque
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
    get_automation_block_minutes,
    is_automation_blocked,
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
    daily_total_limit_reached,
    hourly_limit_reached,
    is_active_hours,
    load_daily_counts,
)
from kensho.application.state import save_collected_safe
from kensho.application.verifier import AccountHealthVerifier, ConsecutiveFailureTracker
from kensho.core.config import load as load_config
from kensho.core.notifier import notify_warning
from kensho.scraping.scorer import format_prize_info, score_prize
from kensho.scraping.sources.common import has_skip_keyword
from kensho.scraping.pathway_classifier import is_auto_applyable, classify_pathway
from kensho.utils.safety import dead_proxy_reason as _dead_proxy_reason
from kensho.utils.safety import verify_ip_separation

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
COLLECTED_FILE: Path = DATA_DIR / "collected.json"

_DEFER_PREFIX: str = "DEFER:"


# ★ 2026-08-30提案93: code 326 一時ロック用ファイル
#   フォローAPIが code 326（一時ロック）を返したアカウントのフォローを期限付きで停止する。
#   データ形式: {account_key: "ISO datetime (locked_until)"}
_FOLLOW_LOCK_FILE: Path = DATA_DIR / "follow_lock.json"


def _recent_success_count(account_key: str, window_sec: int = 3600) -> int:
    """audit.jsonl から直近 window_sec 以内の当該垢の成功アクション数を実測する。

    2026-10-05: 従来の時間上限はプロセス内カウンタのみで、orchestrator が15分毎に再起動
    するたび 0 に戻り、実質無効化されていた（実測: atushi16 が 16-17件/時、上限15）。
    プロセスを跨いだレート制限を担保するため、追記専用の audit 台帳から実測する。
    """
    import json as _json
    import os as _os
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    audit_path: Path = DATA_DIR / "audit.jsonl"
    if not audit_path.exists():
        return 0
    cutoff = _dt.now(_tz.utc) - _td(seconds=window_sec)
    count = 0
    try:
        with open(audit_path, "rb") as fh:
            fh.seek(0, _os.SEEK_END)
            size = fh.tell()
            back = min(size, 500_000)
            fh.seek(size - back)
            blob = fh.read().decode("utf-8", "replace")
        for line in blob.splitlines()[-2000:]:
            if account_key not in line or '"success"' not in line:
                continue
            try:
                d = _json.loads(line)
            except Exception:
                continue
            if d.get("account") != account_key or d.get("status") != "success":
                continue
            try:
                t = _dt.strptime(str(d.get("timestamp", "")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_tz.utc)
            except Exception:
                continue
            if t >= cutoff:
                count += 1
    except Exception:
        return 0
    return count


def _get_follow_lock(account_key: str, state_path: Path | None = None) -> datetime | None:
    """code 326一時ロックの解除予定時刻を返す。期限切れなら自動クリアしてNone。

    Args:
        account_key: アカウントキー
        state_path: テスト用パス（デフォルトは _FOLLOW_LOCK_FILE）
    Returns:
        解除予定時刻（datetime）、または None（ロックなし/期限切れ）
    """
    path = state_path or _FOLLOW_LOCK_FILE
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get(account_key)
        if not raw:
            return None
        until = datetime.fromisoformat(raw)
        if until > datetime.now():
            return until
        # 期限切れ → 自動クリア
        data.pop(account_key, None)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def _set_follow_lock(account_key: str, hours: float = 4.0, state_path: Path | None = None) -> None:
    """code 326一時ロックを記録（有効期限 = 現在時刻 + hours）。

    Args:
        account_key: アカウントキー
        hours: ロック時間（デフォルト4時間）
        state_path: テスト用パス（デフォルトは _FOLLOW_LOCK_FILE）
    """
    path = state_path or _FOLLOW_LOCK_FILE
    try:
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        until = datetime.now() + dt.timedelta(hours=hours)
        data[account_key] = until.isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _clear_follow_lock(account_key: str, state_path: Path | None = None) -> None:
    """アカウントのフォローロックを強制クリア（フォロー成功時の自動解除用）。"""
    path = state_path or _FOLLOW_LOCK_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if account_key in data:
                del data[account_key]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass


# ★ 2026-09-18提案: CAPTCHA連続ロックの24hスキップ（ステートマシン）
#   inobase1-4でCAPTCHA連続→一時ロック（数時間〜数日）が再発した際、
#   修正コードの反映はflock解放後の再起動からしかないが、再試行猶予期間中の
#   自動制御がないという問題への対処。
#   方針: check_x_login が "challenge"（reCAPTCHA/Cloudflare）を検出した回数を
#   端末別・アカウント別に永続カウントし、連続3回でそのアカウントを24hスキップ＋
#   アラート。24h後に自動再試行（ロック期限切れで自動クリア）。
#   データ形式: {account_key: {"consecutive": int, "lock_until": ISO datetime | null}}
_CAPTCHA_LOCK_FILE: Path = DATA_DIR / "captcha_lock.json"
_CAPTCHA_LOCK_THRESHOLD: int = 3  # 連続CAPTCHA失敗でロックする回数
_CAPTCHA_LOCK_HOURS: float = 24.0  # ロック期間（24h）
_CAPTCHA_LOG_MARKER: str = "CAPTCHA_LOCK"  # 検証コマンド grep用マーカー

# ★ t_8946706e (2026-09-24): 自己修復で回復不能な失敗理由（リトライ対象外）。
#   セッション失効・認証失敗・プロキシ死骸は3回リトライしても回復せず、
#   ブラウザ起動＋Xログインを再実行するだけ（=goto failed / ログイン試行が倍増し BOTシグナルを増幅）。
#   実測: 最終失敗32件中29件が1垢（zin20120731）のセッション失効で、goto failed は 63件/日(09-20)
#   →227件/日(09-23)、ログイン試行は約55→108回/日 に増幅していた。
#   これらは validator で recoverable=False として返し、self_heal が1回で停止＋当該垢のみ遮断する。
_FATAL_APPLY_REASONS: frozenset[str] = frozenset({
    "no_auth_session",  # auth_token/ct0 欠落（セッション失効）
    "goto_failed",      # x.com/home へのgoto失敗（プロキシ死骸 or セッション失効）
    "needs_login",      # ログイン/flow/signup 画面＝セッション失効
    "login_failed",     # 上記以外のログイン失敗
    "challenge",        # reCAPTCHA/Cloudflare（24hロック対象・リトライ無意味）
    "rate_limited",     # Xレート制限（同一run内リトライは露出を増やすだけ）
    "suspended",        # アカウント停止
    "frozen",           # 凍結・読み取り専用
    "dead_proxy",       # プロキシ死骸（自宅IPへフォールバックしない絶対ルール）
})


def _get_captcha_lock(account_key: str, state_path: Path | None = None) -> datetime | None:
    """CAPTCHAロックの解除予定時刻を返す。期限切れなら自動クリアしてNone。

    Args:
        account_key: アカウントキー
        state_path: テスト用パス（デフォルトは _CAPTCHA_LOCK_FILE）
    Returns:
        解除予定時刻（datetime）、または None（ロックなし/期限切れ）
    """
    path = state_path or _CAPTCHA_LOCK_FILE
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get(account_key)
        if not raw or not isinstance(raw, dict):
            return None
        until_raw = raw.get("lock_until")
        if not until_raw:
            return None
        until = datetime.fromisoformat(until_raw)
        if until > datetime.now():
            return until
        # 期限切れ → 自動クリア（連続カウントもリセット → 24h後の自動再試行）
        data.pop(account_key, None)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def _get_captcha_consecutive(account_key: str, state_path: Path | None = None) -> int:
    """現在の連続CAPTCHA失敗カウントを返す（ロックされていなければ）。"""
    path = state_path or _CAPTCHA_LOCK_FILE
    try:
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get(account_key)
        if isinstance(raw, dict):
            return int(raw.get("consecutive", 0))
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return 0


def _clear_captcha_lock(account_key: str, state_path: Path | None = None) -> None:
    """アカウントのCAPTCHAロック＋連続カウントを強制クリア（正常ログイン時の自動解除用）。"""
    path = state_path or _CAPTCHA_LOCK_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if account_key in data:
                del data[account_key]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass


def _record_captcha_failure(account_key: str, state_path: Path | None = None) -> bool:
    """CAPTCHA失敗を永続カウント。閾値（3回）到達で24hロックを設定。

    Args:
        account_key: アカウントキー
        state_path: テスト用パス（デフォルトは _CAPTCHA_LOCK_FILE）
    Returns:
        True = 今回の失敗でロックが新規発動した（スキップ処理が必要）
        False = まだカウント段階（1〜2回目）
    """
    path = state_path or _CAPTCHA_LOCK_FILE
    try:
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        raw = data.get(account_key)
        count = int(raw.get("consecutive", 0)) if isinstance(raw, dict) else 0
        count += 1
        became_locked = count >= _CAPTCHA_LOCK_THRESHOLD
        entry: dict[str, Any] = {"consecutive": count, "lock_until": None}
        if became_locked:
            entry["lock_until"] = (datetime.now() + dt.timedelta(hours=_CAPTCHA_LOCK_HOURS)).isoformat()
        data[account_key] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return became_locked
    except (json.JSONDecodeError, OSError):
        return False


def _merge_verify_result(current: bool, verify_success: bool) -> bool:
    """VERIFY結果をアクション成否に反映する（2026-08-26提案8）。

    API成功(current=True)はVERIFY失敗で覆されない。VERIFYは「偽装成功の
    検出器」であり「成功の取り消し器」ではない。API未成功時のみVERIFY結果で確定する。
    """
    if current:
        return True
    return verify_success


def _speed_guard_needed(recent_times: deque[float], window_sec: float, max_actions: int) -> bool:
    """★ 2026-08-28提案53: セッション内速度ガード判定（Error 226対策）。

    - 直近window_sec秒より古い記録を除去（スライディングウィンドウ）
    - 残り件数がmax_actions以上ならTrue（強制休止すべき）
    """
    now = time.time()
    while recent_times and now - recent_times[0] > window_sec:
        recent_times.popleft()
    return len(recent_times) >= max_actions


def _load_audit_done_set(account_key: str) -> tuple[set[str], set[str], set[str]]:
    """当日(JST)のaudit.jsonlから、この垢が既に成功したRT/follow/likeのtarget setを構築する。

    2026-08-26提案10: セッション跨ぎの重複アクション防止（BOT検出回避）。
    提案12: like_doneも追加し、同一ツイートへのlike+rt/follow多重を防止。
    applied(collected.json)は収集マージで消失しうるため、追記専用で消えない
    audit.jsonl（完全履歴）を信頼源にする。当日JST分のみ対象。

    Returns:
        (rt_done, follow_done, like_done):
            RT成功tweet_id集合 / フォロー成功screen_name集合 / いいね成功tweet_id集合
    """
    rt_done: set[str] = set()
    follow_done: set[str] = set()
    like_done: set[str] = set()
    audit_path: Path = DATA_DIR / "audit.jsonl"
    if not audit_path.exists():
        return rt_done, follow_done, like_done
    # auditのtimestampはUTC。JST日付（UTC+9）で「当日」を判定
    jst_today: str = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    try:
        with audit_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("account") != account_key:
                    continue
                if r.get("status") != "success" or r.get("decision") != "allow":
                    continue
                ts = r.get("timestamp", "")
                if len(ts) < 10 or not ts.startswith("20"):
                    continue
                try:
                    utc_dt = dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
                    jd = (utc_dt + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
                except ValueError:
                    continue
                if jd != jst_today:
                    continue
                tgt = r.get("target", "")
                if not tgt or tgt == "n/a":
                    continue
                at = r.get("action_type", "")
                if at == "rt":
                    rt_done.add(tgt)
                elif at == "follow":
                    follow_done.add(tgt)
                elif at == "like":
                    like_done.add(tgt)
    except OSError:
        pass
    return rt_done, follow_done, like_done


def _is_deferred(val: Any) -> bool:
    """applied値がDEFERスキップ中か判定"""
    return val is not None and isinstance(val, str) and val.startswith(_DEFER_PREFIX)


def _get_defer_time(val: str) -> dt.datetime | None:
    """DEFERの予定時刻をパース"""
    try:
        return dt.datetime.fromisoformat(val[len(_DEFER_PREFIX) :])
    except Exception:
        return None


def _is_defer_expired(val: Any) -> bool:
    """applied値が「期限切れDEFER」か判定（2026-08-29提案63 root-cause fix）

    `_is_deferred` はプレフィクス判定のみのため、期限切れDEFER文字列でも True を返す。
    期限切れDEFERは `_should_process_item` で再ピック対象になるが、失敗ハンドラ側の
    `not _is_deferred(...)` ガードでは再DEFER/appliedが書かれず「30分ごと再ピックループ」が
    発生する。ここでは `_get_defer_time` で実際の期限を比較し、期限切れのみ True を返す。
    """
    if not isinstance(val, str) or not val.startswith(_DEFER_PREFIX):
        return False
    t = _get_defer_time(val)
    if t is None:
        return False
    # 保存形式は naive(datetime.now().isoformat()) だが、テスト等でtz付きもあり得る。
    # 比較は同一tzinfoで行う（naiveはそのまま、awareは同一tzでnowを生成）。
    now = dt.datetime.now(t.tzinfo) if t.tzinfo else dt.datetime.now()
    return now >= t


def _dedupe_batch_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """バッチ候補を x_url/tweet_id 単位で一意化する（2026-08-29提案82）。

    collector は収集マージ時に _dedup_x_url_merge で一意化するが、applierロード時点の
    collected.json に重複が残っていると1バッチ内で同一ツイートを複数回ピックする
    （実測: inobase1-4 が geass_survivor を1バッチ内7回ピック → BOT検出リスク）。
    ここでは正規化x_url（または tweet_id）単位で先頭エントリのみ残す。
    """
    seen: set[str] = set()
    out_items: list[dict[str, Any]] = []
    for _item in items:
        _xu = _item.get("x_url", "") or ""
        _xu_key = _xu.split("#")[0].split("?")[0].rstrip("/")
        _tid_m = re.search(r"/status/(\d+)", _xu_key)
        if _tid_m:
            _xu_key = f"tweet_id:{_tid_m.group(1)}"
        elif _xu_key:
            _xu_key = f"x_url:{_xu_key}"
        if _xu_key in seen:
            continue
        seen.add(_xu_key)
        out_items.append(_item)
    return out_items


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


def _cross_account_proximity_defer(item: dict[str, Any], account_key: str, cfg: dict, log: Any) -> bool:
    """クロスアカウント近接ガード（2026-08-30提案88）。

    別垢が6時間以内に同一ツイートを処理済みなら、自垢にDEFER(4〜8h)を書いてスキップする。
    Xのネットワーク分析は「複数アカウントが同一投稿クラスタと短時間に相互作用」を
    リンク判定に使うため、別垢の近接アクションを防止する（連座凍結対策）。

    戻り値: True=近接検出でDEFERを書いた（このitemはスキップすべき）。
    """
    proximity_hours: float = float(cfg.get("applier", {}).get("cross_account_proximity_hours", 6))
    defer_min: float = float(cfg.get("applier", {}).get("cross_account_defer_min_hours", 4))
    defer_max: float = float(cfg.get("applier", {}).get("cross_account_defer_max_hours", 8))
    applied: dict = item.get("applied") or {}
    now: datetime = datetime.now()
    window: dt.timedelta = dt.timedelta(hours=proximity_hours)

    for other_key, val in applied.items():
        if other_key == account_key:
            continue
        if val is None or not isinstance(val, str) or val.startswith(_DEFER_PREFIX):
            continue  # 未処理 or DEFER中（他垢が実際にアクションしていない）
        try:
            other_dt: datetime = dt.datetime.fromisoformat(val)
        except Exception:
            continue
        # aware/naive → nowを合わせる
        now_cmp: datetime = datetime.now(other_dt.tzinfo) if other_dt.tzinfo else now
        if now_cmp - other_dt <= window:
            # 近接検出 → 自垢にDEFER(4〜8hランダム)
            defer_hours: float = random.uniform(defer_min, defer_max)
            defer_until: datetime = now + dt.timedelta(hours=defer_hours)
            item.setdefault("applied", {})[account_key] = f"{_DEFER_PREFIX}{defer_until.isoformat()}"
            _msg = (
                f"  [XPROX] 他垢({other_key})が{proximity_hours}h以内処理済み"
                f" → DEFER {defer_until.strftime('%H:%M')}までスキップ（提案88）"
            )
            if log is not None:
                log.write(_msg)
            return True
    return False


# ★ 2026-09-18提案: 複数同時刻応答検知（軽量版）
#   Xスパムフィルター2026年3月以降厳格化。Kenshoはマルチアカウント運用で、複数垢が
#   同一キャンペーン(tweet)へ短時間窓内に重複応募すると、Xのネットワーク分析が
#   「同一クラスター」としてリンク判定し連座凍結される。提案88（近接DEFER 6h）が
#   通常これを防ぐため、本検知は通常ゼロ発火=スリップスルー監視・アラート専用。
#   障害時の代替はログ出力のみ（検知してもブロックはManual）に留める軽量版。
_MULTI_RESPONSE_FILE: Path = DATA_DIR / "multi_response.json"
_SAME_CAMPAIGN_MARKER: str = "same_campaign_multi"


def _multi_response_record(tweet_id: str, account_key: str, cfg: dict, log: Any, state_path: Path | None = None) -> int:
    """同一キャンペーン(tweet)への複数同時刻応答を共有状態で検知してログ出力（軽量版）。

    垢別ワーカーは独立プロセスで並列実行されるため、応答時刻は共有ファイル
    （multi_response.json）で追跡する。読み書きは fcntl.flock（LOCK_EX）で直列化し、
    並列垢ワーカー間の lost update（一方の応答記録が他方の書き込みで消える）を防ぐ。
    窓内（config applier.multi_response_window_sec、既定1800秒=30分）で同一tweetへ
    threshold（既定2）垢以上が応募成功した場合、same_campaign_multi をログ出力＋
    notify_warning。ブロックは行わない（対応はManual・提案88近接DEFERのスリップスルー監視）。

    Args:
        tweet_id: 応募対象ツイートID（同一キャンペーン判別キー）
        account_key: 応募成功した垢のキー
        cfg: 設定（applier.multi_response_window_sec / multi_response_threshold）
        log: ログライター（None可）
        state_path: テスト用パス（デフォルトは _MULTI_RESPONSE_FILE）
    Returns:
        窓内で応答したアカウント数（検知しなければ 0）。
    """
    window_sec = float(cfg.get("applier", {}).get("multi_response_window_sec", 1800))
    threshold = int(cfg.get("applier", {}).get("multi_response_threshold", 2))
    path = state_path or _MULTI_RESPONSE_FILE
    now = datetime.now()
    count = 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.seek(0)
                content = fh.read()
                loaded: Any = json.loads(content) if content.strip() else {}
            except (json.JSONDecodeError, ValueError):
                loaded = None
            data: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
            raw_entry = data.get(tweet_id)
            rec: dict[str, Any] = {"accounts": {}, "alerted": False}
            if isinstance(raw_entry, dict):
                rec = raw_entry
            raw_accounts = rec.get("accounts")
            accounts: dict[str, Any] = raw_accounts if isinstance(raw_accounts, dict) else {}
            # 窓より古い応答は剪定（連続運用でファイルが肥大化しないように）
            cutoff = now - dt.timedelta(seconds=window_sec)
            for acct, iso in list(accounts.items()):
                try:
                    if dt.datetime.fromisoformat(str(iso)) < cutoff:
                        del accounts[acct]
                except (ValueError, TypeError):
                    del accounts[acct]
            accounts[account_key] = now.isoformat()
            rec["accounts"] = accounts
            count = len(accounts)
            if count < threshold:
                rec["alerted"] = False
            elif not rec.get("alerted"):
                rec["alerted"] = True
                msg = (
                    f"  [{_SAME_CAMPAIGN_MARKER}] 同一キャンペーン(tweet {tweet_id})へ"
                    f" {count}垢が {window_sec:.0f}s 内に応答: {', '.join(sorted(accounts))}"
                    f" → BOT検出リスク（対応はManual）"
                )
                # ★ t_64f60f04: log は None / LogWriter(.write) / callable のいずれでも可。
                #   呼出し元が closure 関数（out）を渡した場合の AttributeError を防ぎ、
                #   将来の認配線でも警告が死なないよう汎容化する。
                _emit = log.write if hasattr(log, "write") else (log if callable(log) else None)
                if _emit is not None:
                    _emit(msg)
                try:
                    notify_warning(
                        "同一キャンペーン複数同時刻応答",
                        f"{count}垢({', '.join(sorted(accounts))})が{window_sec:.0f}s内に"
                        f"同一tweet({str(tweet_id)[:20]}...)へ応募成功。（提案88近接DEFERのスリップスルー）",
                        cfg=cfg,
                    )
                except Exception:
                    pass
            data[tweet_id] = rec
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(data, ensure_ascii=False, indent=2))
            fh.flush()
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return count
    except (OSError, ValueError):
        return 0


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
            page.goto(tweet_url, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            # ★ 2026-08-25 修正: goto失敗は「ツイート状態不明」として正常扱い(None)にする。
            #   「goto_failed」を返すと applied が付与されず、応募済みツイートが毎セッション
            #   再処理されて applier が空回りする無限ループの主因だった。
            #   タイムアウト30s→15s に短縮し、X応答遅延時の無駄待ちも削減。
            #   （フォロー/RTアクションがAPIで成功していれば応募成立として扱う）
            return None
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


def _is_application_complete(
    follow_ok: bool,
    follow_already_done: bool,
    rt_ok: bool,
    like_ok: bool,
    like_skipped: bool,
) -> bool:
    """応募成立判定（2026-08-29ユーザー定義: フォロー状態+いいね）

    ルール:
    - フォローを実行/既フォロー → いいね成功で成立。
      いいねが意図的スキップ(BOT対策の自然分散)なら成立扱い、実失敗なら不成立。
    - RTのみの案件（フォロー非関与） → RT成功で成立（従来通り）。
    - いいねのみ・何もアクションなし → 不成立。

    like_skipped: いいねが「意図的にスキップされた」か（skip_like=True）。
        Trueなら実失敗(False)と区別し成立扱いとする（無限リトライ防止）。
    """
    like_settled = like_ok or like_skipped
    if follow_ok or follow_already_done:
        return like_settled
    if rt_ok:
        return True
    return False


def apply_for_account(
    account_key: str,
    max_n: int,
    cfg: dict[str, Any] | None = None,
    log: Any = None,
    dry_run: bool = False,
    shared_browser: Any = None,
    shared_ipw: Any = None,
) -> tuple[int, int]:
    """指定されたアカウントで未応募の懸賞に応募する。自己修復ループで例外をリカバリする。"""
    from kensho.core.self_heal import RecoverySignal, SelfHealingLoop

    # ★ t_8946706e: 自己修復の失敗理由シンク。_apply_impl が「なぜ失敗したか」を書き、
    #   validator がそれを見て非リトライ（セッション失効/認証/プロキシ死骸）を判定する。
    #   従来はこの情報が無く、auth失効が「apply 0 success 1 errors」＝一般エラーに見えて
    #   3回リトライされ、ブラウザ起動＋Xログインを反復して BOTシグナルを増幅していた。
    _fatal: dict[str, str] = {}

    def _validate_apply(
        value: Any,
        *,
        exception: BaseException | None = None,
        context: dict[str, Any] | None = None,
    ) -> RecoverySignal | None:
        if not isinstance(value, tuple) or len(value) != 2:
            return RecoverySignal(kind="invalid_return", recoverable=True, severity="error", message="apply が tuple[int,int] を返さない")
        _succ, _errs = value
        if _errs > 0 and _succ == 0:
            _why = str(_fatal.get("kind", ""))
            if _why in _FATAL_APPLY_REASONS:
                # 回復不能: リトライせず即停止（self_heal 側が当該垢を遮断＋通知する）
                return RecoverySignal(kind=_why, recoverable=False, severity="error",
                                      message=f"apply 0 success {_errs} errors ({_why})")
            return RecoverySignal(kind="apply_zero_success", recoverable=True, severity="error", message=f"apply 0 success {_errs} errors")
        if (context or {}).get("retry_partial") and _errs > 0 and _succ > 0:
            return RecoverySignal(kind="apply_partial", recoverable=True, severity="warn", message=f"apply partial {_succ}/{_errs}")
        return None

    _cfg = dict(cfg) if cfg is not None else load_config()
    _sh: dict[str, Any] = _cfg.get("self_healing", {}) or {}
    _loop = SelfHealingLoop(
        cfg=_cfg, pipeline="apply", logger=log,
        # F6: retry_partial を config から読む（従来は False 固定で config が無効）。
        # P0: failure ceiling を垢単位にする（全体キーだと他垢の成功で毎回リセットされ遮断が不発）。
        context={"retry_partial": bool(_sh.get("retry_partial_apply", False)),
                 "key": f"apply:{account_key}"},
    )

    def _run() -> tuple[int, int]:
        _fatal.clear()
        return _apply_impl(
            account_key=account_key, max_n=max_n, cfg=_cfg, log=log,
            dry_run=dry_run, shared_browser=shared_browser, shared_ipw=shared_ipw,
            reason_out=_fatal,
        )

    result = _loop.run(_run, validator=_validate_apply)
    _crash = _cfg.get("general", {}).get("project_dir", ".") + "/data/crash_history.json"
    try:
        _cd = Path(_crash)
    except Exception:
        _cd = None
    if result.ok:
        if _cd and _cd.exists():
            try:
                _cd.write_text("[]", encoding="utf-8")
            except Exception:
                pass
    else:
        if _cd:
            try:
                _hist: list[Any] = []
                if _cd.exists():
                    _hist = json.loads(_cd.read_text(encoding="utf-8"))
                _hist.append({"account_key": account_key, "ts": time.time(), "error": str(result.error)})
                _cd.write_text(json.dumps(_hist, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
    return result.value_or_raise()


def _apply_impl(
    account_key: str,
    max_n: int,
    cfg: dict[str, Any] | None = None,
    log: Any = None,
    dry_run: bool = False,
    shared_browser: Any = None,
    shared_ipw: Any = None,
    reason_out: dict[str, str] | None = None,
) -> tuple[int, int]:
    t0: float = time.time()
    if cfg is None:
        cfg = load_config()

    def _set_reason(kind: str) -> None:
        """自己修復に「なぜ失敗したか」を伝える（リトライ可否の判定入力）。"""
        if reason_out is not None:
            reason_out["kind"] = kind

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

    # ★ t_8946706e: プロキシ死骸垢は応募を一切試行しない。
    #   data/status/<acct>.json が dead_proxy（=proxy_watchdog が死骸と判定）なら、ブラウザを起動せず即スキップ。
    #   死骸プロキシのままブラウザを起動すると goto 失敗→ログイン再試行を繰り返し、BOTシグナルを増幅する
    #   （実測: goto failed 63→227件/日・ログイン試行 約55→108回/日）。自宅IPへフォールバックさせない
    #   絶対ルール（2026-08-01 確定）を守ったまま、試行回数そのものをゼロにする。
    _dead = _dead_proxy_reason(cfg, account_key)
    if _dead:
        _set_reason("dead_proxy")
        msg = (
            f"[SKIP] {account_key}: プロキシ死骸（{_dead}）→ 応募を試行しない"
            f"（dead_proxy / 自宅IPフォールバック禁止）"
        )
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)
        return (0, 0)

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

    # ★ t_37e25225: ネットワーク圏外垢スキップ（条件2）
    #   wifi_watchdog が検出した SSID圏外/電源OFF/バックOFF中のアカウントは、
    #   募集前にスキップし、dead_proxy_reason 相当の軽量チェックでBOTシグナル増幅を防ぐ。
    try:
        from kensho.utils.safety import network_outage_reason
        skip_reason = network_outage_reason(cfg, account_key)
        if skip_reason:
            _set_reason("network_outage_skip")
            msg = f"[SKIP] {account_key}: ネットワーク圏外/電源OFF/バックOFF（wifi_watchdog検出） → スキップ"
            if log:
                log.write(msg)
            else:
                print(msg, flush=True)
            return (0, 0)
    except Exception:
        # 補助的チェック、失敗時は従来の死骸チェックのみ使用
        pass

    # ★ 時間あたりアクション制限（ループ内でカウント）
    _hourly_max: int = limits.get("max_actions_per_hour", 20)
    _hourly_start: float = time.time()
    # 2026-10-05: プロセス跨ぎの実測値で初期化（15分毎の再起動で 0 に戻り実効上限が崩れていた）。
    _hourly_count: int = _recent_success_count(account_key, 3600)

    # ★ 2026-08-28提案53: セッション内速度ガード（Error 226対策）
    #   Xは2-3分で20件超の連続アクションを検出する。既存の時間あたり上限に加え、
    #   直近window_sec秒以内にmax_actions件を超えたらpause_sec秒の強制休止を入れる最終防衛線。
    _speed_window: float = limits.get("speed_guard_window_sec", 180)
    _speed_max: int = limits.get("speed_guard_max_actions", 15)
    _speed_pause: float = limits.get("speed_guard_pause_sec", 30)
    _recent_action_times: deque[float] = deque()

    # ★ 連続いいねカウンタ（2026年3月Xスパム判定強化対策）:
    #   セッション内で「いいね4〜5連続→強制ログアウト→サーチバン」が多発したため、
    #   いいね単独連続を4件で一時停止する（フォロー/RTは続行可）。
    consecutive_likes: int = 0

    # ★ t_c189d8d8 提案1: 連続RT/いいね異常検知カウンタ。
    #   2026年春のスパム判定強化（5ch「短時間RP連続」「いいね4-5連続」を検出対象に）を受け、
    #   RT or いいね が anomaly_max_consecutive_rt_like 回 連続成功したらセッション強制終了する。
    #   フォロー成功 or 何らかの失敗でリセット（フォローは応募成立=人為的介入ポイントで安定化）。
    #   既存 consecutive_likes は「いいね単独の一時停止」であり、これは「RT+いいね連続の強制終了」。
    consecutive_rt_like: int = 0
    # ★ 提案1: 連続RT/いいね異常フラグ（外側while頭で検知してバッチ即時終了）。
    _anomaly_abort: bool = False

    # ★ アクションパターン記憶（人間らしい行動のための機能追加）:
    #   最近のアクションシーケンスを記憶し、あまりにも規則的なパターンを避ける
    _recent_action_sequence: list[str] = []
    _max_sequence_memory: int = 8  # 記憶するアクション数

    # ★ 2026-08-30提案90: フォロー403専用カウンタ（バッチ単位）
    #   フォローHTTP 403はアカウント制限の初動シグナル（atushi1840凍結時8/9-11に21件）。
    #   既存false_countは全アクション連続失敗を数えRT/いいね成功でリセットされるため、
    #   フォロー特化の403（8/30朝ib×6/rk×2）を検出できない。専用カウンタで3回で中断。
    _follow_403_count: int = 0
    # ★ 2026-08-30提案91: フォロー403による凍結疑いフラグ（外側ループ伝播用）。
    #   提案90の `break` (line 1585 旧) は内側 action_queue ループのみ抜ける。
    #   外側 `while success < max_n and idx < len(account_applied)` (line 752) は継続するため、
    #   凍結疑い垢で残りの item を全部処理しログに [FROZEN] がN回連続出る（実測: 8/30昼 ib×11回）。
    #   フラグで外側ループの頭で break し、提案90の意図通りバッチ即時中断する。
    _frozen_by_follow_403: bool = False

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    # ★ 2026-08-30提案93: code 326 一時ロックによるフォロー停止（バッチ開始時に読み込み）
    #   フォローAPIが code 326（temporarily locked）を返した垢は、当日中フォローのみ停止し、
    #   like/RTは継続する。ロック中は skip_follow を強制し、API無駄打ちを防ぐ。
    _follow_locked_until: datetime | None = _get_follow_lock(account_key)
    if _follow_locked_until is not None:
        out(
            f"  [LOCK93] code 326 一時ロック検出 → {account_key} フォローのみ停止"
            f"（{_follow_locked_until.strftime('%H:%M')}まで・提案93）。like/RTは継続"
        )

    # ★ 2026-09-18提案: CAPTCHA連続ロック中はバッチ開始前にスキップ（無駄dispatch・再ロック回避）
    #   _record_captcha_failure() が連続3回で24hロックを設定した垢は、この時点で早期リターン。
    #   ロック期限切れ（24h後）に自動クリアされ、次バッチで自動再試行される。
    _captcha_locked_until: datetime | None = _get_captcha_lock(account_key)
    if _captcha_locked_until is not None:
        out(
            f"  [{_CAPTCHA_LOG_MARKER}] {account_key}: CAPTCHAロック中"
            f"（{_captcha_locked_until.strftime('%m-%d %H:%M')}まで）→ この垢をスキップ"
        )
        return (0, 0)

    # ★ Failure Ceiling設定読み込み（Loop Engineering）
    fc_cfg: dict = cfg.get("failure_ceiling", {})
    fc_enabled: bool = fc_cfg.get("enabled", True)
    fc_max: int = fc_cfg.get("max_consecutive_failures", 3)
    fc_cooldown: int = fc_cfg.get("cooldown_minutes", 30)

    # ★ t_c189d8d8 提案1: 連続RT/いいね異常検知しきい値（デフォルト5 = BAN祭り分析の検出境界）
    anomaly_cfg: dict = cfg.get("applier", {})
    anomaly_max_rt_like: int = int(anomaly_cfg.get("anomaly_max_consecutive_rt_like", 5))

    # ★ 検証設定読み込み
    verif_cfg: dict = cfg.get("verification", {})
    verif_account_health: bool = verif_cfg.get("verify_account_health", True)

    # ★ ConsecutiveFailureTracker（このサイクル用）
    failure_tracker = ConsecutiveFailureTracker(max_consecutive=fc_max, cooldown_minutes=fc_cooldown)

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
    _xprox_deferred: bool = False
    for item in items:
        if not _should_process_item(item, account_key):
            continue
        # ★ 2026-08-30提案88: クロスアカウント近接ガード
        #   別垢が6時間以内に同一ツイートを処理済みなら、自垢にDEFER(4〜8h)を書いて
        #   バッチ候補から除外。Xのネットワーク分析（クラスター検出）による連座凍結防止。
        if _cross_account_proximity_defer(item, account_key, cfg, log):
            _xprox_deferred = True
            continue
        # ★ 2026-08-28提案54: 事前フィルタリング — 引用/コメント応募（keyword_flag+スキップKW）を
        #   バッチ候補から除外。処理中SKIPで枠と時間を消費するのを防ぐ。
        #   過検出（収集時tweet_textにキーワードなし）は処理継続するため、
        #   ここでは「収集時tweet_textで確定SKIP」だけ除外する。
        # ★ 2026-08-29: keyword_flag有無にかかわらず、リプライ/返信要件ツイートは常に除外
        #   （ユーザー指示: リプライは自動で行わない → リプライ必須の懸賞は応募しない）
        _pre_text2 = item.get("tweet_text", "") or ""
        if _pre_text2 and has_skip_keyword(_pre_text2):
            continue
        if item.get("keyword_flag", False):
            _pre_text = item.get("tweet_text", "") or ""
            if _pre_text and has_skip_keyword(_pre_text):
                continue
        # ★ 2026-08-28: LLM判定FLAG（追加操作が必要な案件）をバッチ候補から除外
        #   simple_rt_ok == "FLAG" はフォロー+RTでは当選条件を満たせないため処理しない
        if item.get("simple_rt_ok") == "FLAG":
            continue
        # ★ t_f7b0d3bd: 非X応募導線を自動応募対象から除外（安全）
        #   導入ラベルが X 以外（LINE/Instagram/アプリ/レシート/会員ID/外部フォーム/
        #   DM/メール/要確認/未判定）は、X操作だけでは応募成立せず自動操作は
        #   TOS/個人情報リスクが高いため必ず手動・要確認扱いにする。
        #   ラベル無し(旧データ)は本文から即時分類（安全側・過剰フルストップを回避）。
        # 2026-10-07 fix (実測): 収集データは「導線」キーを "未判定" で保持するため、
        # `item.get("導線") or classify_pathway(...)` では右辺に落ちず、
        # 283/283 が自動応募対象外になり応募が 27件/日まで枯渇していた。
        # "未判定"/空のときは本文から分類し直す（X導線だけが自動応募対象になる安全側設計は不変）。
        _entry_label = item.get("導線")
        if not _entry_label or _entry_label == "未判定":
            _entry_label = classify_pathway(item.get("tweet_text") or "")
        if not is_auto_applyable(_entry_label):
            _cand_url: str = item.get("x_url") or item.get("url") or ""
            out(f"  [SKIP] 非X導線({_entry_label}) → 自動応募対象外: {_cand_url[:60]}")
            continue
        if check_rate_limit(account_key, cfg):
            out(f"[LIMIT] {account_key}: 処理中に上限到達 → 残りスキップ")
            break
        account_applied.append(item)

    out(f"[Kensho] この垢の未応募: {len(account_applied)}件")

    # ★ 2026-08-30提案88: 近接ガードでDEFERを書いた分を永続化。
    #   collected.json は並列垢プロセスと共有。次バッチが読む前に保存しておく。
    if _xprox_deferred:
        save_collected_safe(data, account_key, log)
        out("[XPROX] 近接ガードDEFERを保存（提案88）")

    # ★ 2026-08-29提案82: バッチ構築時の x_url/tweet_id dedupe
    #   collectorは収集マージ時に _dedup_x_url_merge で一意化するが、applierロード時点の
    #   collected.jsonに重複が残っていると1バッチ内で同一ツイートを複数回ピックする
    #   （実測: inobase1-4 がgeass_survivorを1バッチ内7回ピック・18:01）。
    #   → バッチ効率低下 + 同一ツイート短時間反復アクセス = BOT検出リスク。
    #   ここで正規化x_url（またはtweet_id）単位で先頭エントリのみ残す。
    _dup_removed: int = len(account_applied) - len(_dedupe_batch_items(account_applied))
    if _dup_removed > 0:
        out(f"[DEDUPE] バッチ内同一ツイート重複 {_dup_removed}件を除外（提案82）")
        account_applied = _dedupe_batch_items(account_applied)

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

        login_reason: dict[str, str] = {}
        login_success = check_x_login(page, log, screen_name=account_key, reason_out=login_reason)
        if not login_success:
            # ★ t_8946706e: 「なぜログインできなかったか」を自己修復へ伝える。
            #   reason が無い旧経路でも auth 系として扱い、3回リトライ（=ブラウザ起動＋ログイン再試行）を防ぐ。
            _set_reason(login_reason.get("reason") or "login_failed")
            # ★ 2026-09-18提案: CAPTCHA連続ロックの24hスキップ
            #   check_x_login が "challenge"（reCAPTCHA/Cloudflare）を検出した場合、
            #   連続3回でこのアカウントを24hスキップ＋アラート。1〜2回目は従来通り
            #   auth_tokenエラーとして扱う（アラートなし・無駄ログ最小化）。
            if login_reason.get("reason") == "challenge":
                became_locked = _record_captcha_failure(account_key)
                consecutive = _get_captcha_consecutive(account_key)
                out(
                    f"  [{_CAPTCHA_LOG_MARKER}] challenge検出: {account_key} "
                    f"連続CAPTCHA失敗 {consecutive}/{_CAPTCHA_LOCK_THRESHOLD} 回"
                )
                if became_locked:
                    out(
                        f"  [{_CAPTCHA_LOG_MARKER}] {account_key}: 連続CAPTCHA失敗{_CAPTCHA_LOCK_THRESHOLD}回"
                        f" → {_CAPTCHA_LOCK_HOURS:.0f}hスキップ（自動再試行）"
                    )
                    try:
                        notify_warning(
                            f"CAPTCHAロック: {account_key}",
                            f"連続CAPTCHA失敗{_CAPTCHA_LOCK_THRESHOLD}回→{_CAPTCHA_LOCK_HOURS:.0f}hスキップ。"
                            f"{_CAPTCHA_LOCK_HOURS:.0f}h後に自動再試行。",
                            cfg=cfg,
                        )
                    except Exception:
                        pass
                return (0, 1)  # finally will close browser / context
            out("[NG] ログイン失敗 - auth_tokenが必要")
            return (0, 1)  # finally will close browser / context

        # ★ 2026-09-18提案: ログイン成功 = CAPTCHA解除 → それまでの連続カウント/ロックをクリア
        _clear_captcha_lock(account_key)

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
        # 低速回線垢(kudou/zin/Tankan)はgoto180s・選択待ち等で1アイテム2〜3分消費し、
        # 30分だとmax 12-14件に達せず6〜8件で打ち切られる。40分に延ばし目標件数まで到達させる。
        SESSION_TIMEOUT: int = 2400  # 30分→40分

        success: int = 0
        errors: int = 0
        idx: int = 0  # account_applied のインデックス（補充用）
        # ★ 2026-08-26: セッション内重複アクション防止（BOT検出回避）
        rt_done_ids: set[str] = set()  # セッション内でRT成功したtweet_id
        like_done_ids: set[str] = set()  # セッション内でいいね成功したtweet_id（2026-08-28追加）
        followed_owners_session: set[str] = set()  # セッション内でフォロー成功した主催者
        # ★ 2026-08-26提案10: セッション跨ぎ重複アクション防止（audit.jsonlベース）
        #   applied(collected.json)は収集マージで消失しうるため、追記専用のaudit.jsonlから
        #   当日JSTの成功済みtargetを読み込み、再ピックによる同一ツイートへの再アクションを防ぐ。
        rt_done_all, follow_done_all, like_done_all = _load_audit_done_set(account_key)
        if rt_done_all or follow_done_all or like_done_all:
            out(
                f"  [AUDIT] 本日成功済み: RT {len(rt_done_all)}件 / follow {len(follow_done_all)}件 / like {len(like_done_all)}件"  # noqa: E501
                "（セッション跨ぎ重複防止セット）"
            )

        while success < max_n and idx < len(account_applied):
            # ★ t_c189d8d8 提案1: 連続RT/いいね異常フラグ検知でバッチ即時終了。
            #   内側ループで anomaly_max_consecutive_rt_like 回連続成功を検知したら、
            #   残りitemを処理せずこの垢のバッチを打ち切る（スパム判定回避）。
            if _anomaly_abort:
                out(
                    f"  [ANOMALY_ABORT] t_c189d8d8提案1: 連続RT/いいね{anomaly_max_rt_like}回検知"
                    f" → {account_key} バッチ強制終了（{success}件処理済み）"
                )
                break

            # ★ 2026-08-30提案91: 提案90の `break` は内側 action_queue ループしか抜けず、
            #   外側 `while` (line 752) は継続→凍結疑い垢で残 item を全部処理し[FROZEN]がN回出る。
            #   内側で立てたフラグを外側ループ頭で検知して即時バッチ終了する。
            if _frozen_by_follow_403:
                out(
                    f"  [FROZEN_ABORT] 提案91: フォロー403凍結疑いフラグ検知"
                    f" → {account_key} バッチ即時中断（残item処理スキップ）"
                )
                break

            # ★ 2026-08-29提案76: Error 226（automated block）ブロック中なら即停止
            if is_automation_blocked(account_key):
                rem = get_automation_block_minutes(account_key)
                out(f"  [AUTOBLOCK] {account_key}: 自動ブロック中（残り約{rem}分）→ このバッチ打ち切り")
                break

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
                # 1時間経過 → 実測値でリセット（プロセス内カウントでは跨ぎを担保できない）
                _hourly_start = time.time()
                _hourly_count = _recent_success_count(account_key, 3600)
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

            # ★ 2026-08-28: LLM判定で「追加操作が必要」な案件はスキップ（フォロー+RTでは当選条件を満たせない）
            if item.get("simple_rt_ok") == "FLAG":
                out(f"  [{global_idx}/{max_n}] [SKIP] simple_rt=FLAG（追加操作必要）→ スキップ")
                continue

            # ★ 引用RT・コメント応募のスキップ（AI対応不可 — 通常RT/フォローでは当選条件を満たせない）
            if item.get("keyword_flag", False):
                # ★ 2026-08-27提案38: 収集時tweet_textを優先で再判定（281件の過検出を確実に解除）
                #   収集時tweet_textが全件存在するため、CDN再フェッチ（ネットワーク依存）はフォールバックに
                _flag_tweet_id, _ = extract_tweet_id_and_screen_name(clean_url)
                # 収集時tweet_textを優先（CDN再フェッチ不要）
                _flag_recheck_text = item.get("tweet_text", "") or ""
                if not _flag_recheck_text and _flag_tweet_id:
                    try:
                        _flag_recheck_text = api_get_tweet_text(page, _flag_tweet_id, log_fn=out)
                    except Exception:
                        _flag_recheck_text = ""
                if _flag_recheck_text and not has_skip_keyword(_flag_recheck_text):
                    # tweet_textにキーワードなし → 収集時の誤判定（過検出）。応募機会を損失しないため処理継続
                    out(
                        f"  [{global_idx}/{max_n}] [INFO] 引用/コメント判定を収集時tweet_textで解除（過検出）→ 処理継続"  # noqa: E501
                    )
                    if not item.get("tweet_text"):
                        item["tweet_text"] = _flag_recheck_text  # NGフィルター用に書き戻し（state.saveで保存）
                else:
                    out(f"  [{global_idx}/{max_n}] [SKIP] 引用/コメント応募 → AI対応不可のためスキップ")
                    continue

            try:
                out(
                    f"[{global_idx}/{max_n}] ⏱{elapsed_global / 60:.0f}分 "
                    f"〆{deadline_info} {wc_info}名 {clean_url[:50]}..."
                )

                # ★ URL→tweet_id/screen_name抽出
                tweet_id, screen_name = extract_tweet_id_and_screen_name(clean_url)
                # ★ 2026-08-26: セッション内重複アクション検出用
                _rt_already_done = False
                _follow_already_done = False
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

                    # ★ 2026-08-27 スループット改善①: 収集時tweet_textで必須ワード早期判定
                    #    必須ワードなしのツイートは本文取得（API全文/goto）をせずに即スキップ。
                    #    実測: 181件/1186件が必須ワードなし。全垢で毎バッチ開かれていた無駄を排除。
                    if required_words:
                        _req_any = required_words.get("require_any", [])
                        _req_all = required_words.get("require_all", [])
                        if _req_any and not any(w in stored_text for w in _req_any):
                            out(f"  [{global_idx}/{max_n}] [SKIP] 必須ワード不足（早期判定）")
                            continue
                        if _req_all and not all(w in stored_text for w in _req_all):
                            out(f"  [{global_idx}/{max_n}] [SKIP] 必須ワード不足（早期判定）")
                            continue

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
                    _fixupx_accounts = {
                        "kudou",
                        "zin20120731",
                        "TankanNotes",
                        "inobase1-4",
                        "toushiwatch",
                    }  # 2026-08-27: povo低速垢も追加
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
                    # ★ 低速回線: gotoフォールバック不可（60秒以内にページ読み込み完了しない）
                    _fixupx_accounts = {
                        "kudou",
                        "zin20120731",
                        "TankanNotes",
                        "inobase1-4",
                        "toushiwatch",
                    }  # 2026-08-27: povo低速垢も追加
                    if account_key in _fixupx_accounts:
                        out("  [SKIP] 低速回線: goto不可（180秒以内にページ読み込み完了しない）→ 次アイテムへ")
                        continue

                    # 速度別goto設定: 全垢commitに統一（2026-08-27 スループット改善③）
                    #   domcontentloadedだとサブリソースストール（X Bot検出）でタイムアウトしやすい。
                    #   commitで速攻レスポンス取得→tweetTextセレクタ待ちに変更。低速も180s→60sに短縮。
                    _fast_accounts = {"atushi16"}
                    _slow_accounts = {
                        "kudou",
                        "zin20120731",
                        "TankanNotes",
                        "inobase1-4",
                        "toushiwatch",
                    }
                    _is_fast = account_key in _fast_accounts
                    _is_slow = account_key in _slow_accounts
                    _goto_wait = "commit"  # 全垢commit統一（サブリソースストール回避）
                    _goto_timeout = 30000 if _is_fast else 60000  # 低速も60s（旧180s）
                    for _gr in range(3 if _is_fast else 2):
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
                # ツイート本文から金額・アイテムを抽出し優先度を計算（当選人数・締切も反映）
                try:
                    prize = score_prize(
                        body_text,
                        winner_count=item.get("winner_count", 0) or 0,
                        deadline=str(item.get("deadline", "") or ""),
                    )
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
                # Enhanced human-like reading time with Gaussian distribution
                # More natural variation: most reads are 3-6 seconds, occasional longer reads
                if random.random() < 0.85:  # 85% of the time: normal reading
                    enhanced_read_time = max(1.0, random.gauss(read_time * 0.7, read_time * 0.3))
                else:  # 15% of the time: deeper reading or distraction
                    enhanced_read_time = max(1.0, random.gauss(read_time * 1.5, read_time * 0.5))
                time.sleep(min(enhanced_read_time, read_time * 3))  # Cap at 3x original

                # Enhanced human-like scrolling with more natural patterns
                # Mix of quick glances and deliberate reading patterns
                _scroll_cfg: dict[str, Any] = {
                    "smooth": {
                        "count": (2, 6),  # Fewer scroll actions for more natural reading
                        "dy": (15, 100),  # Shorter scroll distances
                        "delay": (0.1, 0.8),  # Faster, more natural scrolling
                        "subdivide": True,
                        "up_chance": 0.2,  # More frequent small adjustments
                        "mouse_move": 0.3,
                    },
                    "aggressive": {
                        "count": (1, 3),
                        "dy": (40, 200),
                        "delay": (0.05, 0.3),
                        "subdivide": False,
                        "up_chance": 0.1,
                        "mouse_move": 0.1,
                    },
                    "erratic": {
                        "count": (3, 8),
                        "dy": (-80, 150),
                        "delay": (0.1, 1.5),
                        "subdivide": True,
                        "up_chance": 0.35,
                        "mouse_move": 0.4,
                    },
                    "measured": {
                        "count": (2, 5),
                        "dy": (25, 120),
                        "delay": (0.3, 2.0),
                        "subdivide": True,
                        "up_chance": 0.25,
                        "mouse_move": 0.35,
                    },
                    "explorative": {
                        "count": (4, 10),
                        "dy": (-150, 250),
                        "delay": (0.2, 1.2),
                        "subdivide": True,
                        "up_chance": 0.4,
                        "mouse_move": 0.5,
                    },
                }.get(
                    scroll_pattern,
                    {
                        "count": (2, 5),
                        "dy": (-50, 180),
                        "delay": (0.15, 1.0),
                        "subdivide": True,
                        "up_chance": 0.2,
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
                # ★ 2026-08-29: フォロー+いいね伴走のいいねスキップ率。
                #   応募成立=フォロー状態+いいねのため、通常いいねスキップ(30%)より低くし
                #   完了率を上げる。5%残すのは「たまにいいね忘れ」の人間らしさ（BOT対策）。
                _like_with_follow_skip: float = float(cfg.get("applier", {}).get("like_with_follow_skip", 0.05))
                # ★ 2026-08-29 提案83: フォロー非関連（RTのみ等）ツイートへのいいね単独実行スキップ率。
                #   speed_guard(15件/180s) + 連続いいね4件カウンタ制限内で単独いいねを許可し、
                #   L/F比率95%以上達成に寄与する。10%実行→40%実行に引き上げ（configで調整可）。
                _like_standalone_skip: float = float(cfg.get("applier", {}).get("like_standalone_skip", 0.60))

                # ★ 応募成立条件: フォロー状態+いいね（2026-08-29改修）
                #   従来は「いいね要件が本文にないと90%スキップ」で、フォロー応募の当選条件
                #   （フォロー&いいね）を満たせていなかった（実測: いいね成功が日0〜1件）。
                #   → フォロー実行/既フォローの場合はいいねを伴走実行し、応募を完了させる。
                #   BOT対策は「いつ応募するか」の確率分散（skip_rates）+ランダム遅延+セッション上限で担保し、
                #   応募したのに要件未達という実態との剥離を解消する。
                skip_follow: bool = random.random() < _skip_chance_follow
                skip_rt: bool = random.random() < _skip_chance_rt
                skip_like: bool = False  # 後で条件確定

                # ★ 2026-08-30提案93: code 326 一時ロック中はフォローのみ強制スキップ
                #   like/RTは継続し、部分当選のチャンスを維持する。ロックは期限切れで自動復帰。
                if _follow_locked_until is not None and not skip_follow:
                    skip_follow = True
                    out(
                        "  [SKIP] フォロー: code 326 一時ロック中（提案93）"
                        f" → {_follow_locked_until.strftime('%H:%M')}までフォローのみ停止（like/RT継続）"
                    )

                # 既フォローの検出（いいね伴走判定に使用）
                #   従来は後段(1179行)で判定していたため、いいねの決定より遅く参照できなかった。
                #   ここで先行判定し、既フォローなら「いいねのみで応募成立」を決める。
                _follow_relevant = not skip_follow
                _follow_already_done = False
                if _follow_relevant and screen_name:
                    from kensho.application.follow_state_manager import FollowStateManager

                    _fsm = FollowStateManager(account_key)
                    if _fsm.get_total_follows(screen_name) >= 1:
                        _follow_already_done = True
                        skip_follow = True
                        out(f"  [SKIP] フォロー: {screen_name}は過去にフォロー済み → いいねのみで応募成立")

                # ★ いいね伴走実行（応募成立条件: フォロー状態+いいね）
                _like_req_pattern = re.compile(r"いいね|♡|♥|❤|💗|💖|💕|ハート|LIKE", re.IGNORECASE)
                _like_in_text = bool(_like_req_pattern.search(body_text))

                if _follow_already_done:
                    # 既フォロー: いいねのみで応募成立。自然分散のため少量スキップ可
                    if random.random() < _like_with_follow_skip:
                        skip_like = True
                        out("  [SKIP] いいね: フォロー済みだが確率スキップ（自然分散）")
                    else:
                        skip_like = False
                        out("  [i] いいね: フォロー済み → いいねのみで応募成立")
                elif _follow_relevant:
                    # フォロー実行: いいねを伴走（応募成立条件を満たす）
                    if random.random() < _like_with_follow_skip:
                        skip_like = True
                        out("  [SKIP] いいね: フォロー+いいねだが確率スキップ（自然分散）")
                    else:
                        skip_like = False
                        out("  [i] いいね: フォロー+いいね実行（応募成立条件を満たす）")
                else:
                    # フォロー非関連（RTのみ等）: 従来通り本文要件で判定。
                    # ★ 2026-08-29 提案83: 本文に要件なしでもいいね単独実行を許可
                    #   （旧: 90%スキップ=10%実行 → 新: like_standalone_skip 60%スキップ=40%実行）。
                    #   speed_guard + 連続いいね4件カウンタ（下段）がBOT検出の最終防衛線。
                    if not _like_in_text:
                        if random.random() < _like_standalone_skip:
                            skip_like = True
                            out("  [SKIP] いいね: 本文に要件なし → スキップ")
                        else:
                            skip_like = False
                            out("  [i] いいね: 要件なしだがいいね単独実行（提案83・L/F比率向上）")
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

                # ★ 連続いいね制限（BAN祭り対策 2026-08-25）:
                #   いいね単独連続4件に達したら一時停止（フォロー/RTは続行可）。
                #   当選条件の「フォロー+いいね」はフォローを挟むため制限対象外。
                if not skip_like and consecutive_likes >= 4:
                    skip_like = True
                    out("  [SKIP] いいね: 連続4件到達 → 一時停止（BOT検出回避）")

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
                    # ★ 2026-08-30提案87: 無駄な失敗（no_follow_button等）で当日ブロックされた主催者への再試行防止
                    elif _fsm.is_blocked(screen_name):
                        skip_follow = True
                        out(f"  [SKIP] フォロー: 主催者{screen_name}は当日ブロック済み（無駄な失敗防止・提案87）")
                    # ★ t_33113bb7 (C): 同一垢の「再試行しても無駄な失敗」連続→垢単位サーキットブレーカ。
                    #   提案87の owner ブロックでは捕捉できない（kudou は複数主催者で no_follow_button
                    #   が連続: korehamiro×3/削除済み垢・Rakuten_Wallet×4/zin・steakgusto029×2/zin）。
                    #   同一エラー種別が threshold 回連続 → 当該垢のフォロー試行を 2h 停止。
                    elif _fsm.account_follow_blocked()[0]:
                        skip_follow = True
                        out(
                            "  [SKIP] フォロー: 当該垢のサーキットブレーカ作動中（再試行しても無駄な失敗連続）"
                            " → フォロー試行停止（提案C・t_33113bb7）"
                        )
                # ★ 2026-08-26: セッション内フォロー重複防止
                if not skip_follow and screen_name and screen_name in followed_owners_session:
                    skip_follow = True
                    out("  [SKIP] フォロー: セッション内で既にフォロー成功済み → スキップ（重複アクション防止）")
                # ★ 2026-08-26提案10: セッション跨ぎフォロー重複防止（当日audit成功済み）
                if not skip_follow and screen_name and screen_name in follow_done_all:
                    skip_follow = True
                    out("  [SKIP] フォロー: 本日既にフォロー成功済み（前セッション）→ スキップ（重複アクション防止）")
                # ★ 2026-08-26提案12: いいね済みツイートへのフォロー禁止（同一ツイート多重アクション防止）
                #   すでにいいねで応募完了しているツイートへのフォローはBOT検出リスクを上げるだけ。
                if not skip_follow and tweet_id and (tweet_id in like_done_all or tweet_id in like_done_ids):
                    skip_follow = True
                    out(
                        "  [SKIP] フォロー: 本日既にいいね成功済み（前セッション）→ スキップ（同一ツイート多重アクション防止）"  # noqa: E501
                    )
                # （過去フォロー済みの検出はいいね判定のため前段で実施済み。_follow_already_done を参照）

                def _make_follow_with_record(
                    _acct: str,
                    _sn: str,
                    _page: Any,
                    _out: Callable[[str], None],
                ) -> Callable[[], tuple[bool, str | None]]:
                    def _fn() -> tuple[bool, str | None]:
                        _ok, _err = api_follow_by_screen_name(_page, _sn, _acct, _out)
                        if _ok:
                            from kensho.application.follow_state_manager import FollowStateManager

                            FollowStateManager(_acct).record_follow(_sn)
                        return (_ok, _err)

                    return _fn

                if not skip_follow:
                    if x_api_ok and screen_name:
                        action_queue.append((
                            "follow",
                            _make_follow_with_record(account_key, screen_name, page, out),
                        ))
                    else:
                        # ★ 2026-08-26: UIフォールバックでもフォロー成功を記録（過フォロー・監査n/aの根本対策）
                        # ★ 2026-08-28提案68: do_follow戻り値を (success, error_code) タプルに変更し、
                        #   失敗時のエラー種別を上位に伝える。no_follow_button 等の「再試行しても無駄な失敗」を
                        #   当該バッチ内で再ピックせず applied を即時付与する判定に使う。
                        def _ui_follow_with_record() -> tuple[bool, str | None]:
                            _ok, _err = do_follow(page, click_delay, out, account_key, target=screen_name or "")
                            if _ok and screen_name:
                                from kensho.application.follow_state_manager import FollowStateManager

                                FollowStateManager(account_key).record_follow(screen_name)
                            return (_ok, _err)

                        action_queue.append(("follow", _ui_follow_with_record))
                if not skip_rt:
                    # ★ 2026-08-26: セッション内RT重複防止（チェックをキュー追加前に移動）
                    if tweet_id in rt_done_ids:
                        skip_rt = True
                        _rt_already_done = True
                        out("  [SKIP] RT: セッション内で既にRT成功済み → スキップ（重複アクション防止）")
                    # ★ 2026-08-26提案10: セッション跨ぎRT重複防止（当日audit成功済み）
                    elif tweet_id in rt_done_all:
                        skip_rt = True
                        _rt_already_done = True
                        out("  [SKIP] RT: 本日既にRT成功済み（前セッション）→ スキップ（重複アクション防止）")
                    # ★ 2026-08-26提案12: いいね済みツイートへのRT禁止（同一ツイート多重アクション防止）
                    elif tweet_id in like_done_all or tweet_id in like_done_ids:
                        skip_rt = True
                        _rt_already_done = True
                        out(
                            "  [SKIP] RT: 本日既にいいね成功済み（前セッション）→ スキップ（同一ツイート多重アクション防止）"  # noqa: E501
                        )

                if not skip_rt:

                    def fallback_rt(
                        page: Any = page,
                        click_delay: int = click_delay,
                        out: Callable[[str], None] = out,
                        account_key: str = account_key,
                        cfg: dict[str, Any] = cfg,
                        clean_url: str = clean_url,
                        tweet_id: str = tweet_id,
                        item: dict[str, Any] = item,
                    ) -> bool:
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
                                # ★ 2026-08-25: 327 AuthorizationError + gotoタイムアウトが連続する環境では
                                #   2回目のgotoはほぼ確実に同じ結果（タイムアウト）になるため1回に削減。
                                #   バッチの時間浪費(50s→25s)を防ぎ、フォロー/いいね対象の処理量を維持する。
                                for _gr in range(1):
                                    try:
                                        page.goto(clean_url, timeout=_to, wait_until="domcontentloaded")
                                        _goto_ok = True
                                        break
                                    except Exception as _ge:
                                        out(f"  [NG] RT goto attempt {_gr + 1}: {str(_ge)[:50]}")
                                        if _gr == 0:
                                            time.sleep(3)
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
                        return do_rt(page, click_delay, out, account_key, cfg, target=tweet_id)

                    action_queue.append(("rt", fallback_rt))
                # ★ 2026-08-26提案12: セッション跨ぎ多重アクション防止
                #   本日既にRT/いいね成功済み（前セッション）のツイートへのいいねをスキップ。
                #   RT済みツイートへの再いいね（kudou rt→like 8分)・いいね済みツイートへの再いいねを防止。
                if (
                    not skip_like
                    and tweet_id
                    and (
                        tweet_id in rt_done_all
                        or tweet_id in like_done_all
                        or tweet_id in rt_done_ids
                        or tweet_id in like_done_ids
                    )
                ):  # noqa: E501
                    skip_like = True
                    out(
                        "  [SKIP] いいね: 本日既にRT/いいね成功済み（前セッション/同セッション）→ スキップ（同一ツイート多重アクション防止）"  # noqa: E501
                    )
                # ★ いいねアクション（条件付き）を別途保持
                like_action: tuple[str, Any] | None = None
                if not skip_like:
                    if x_api_ok and tweet_id:
                        like_action = ("like", lambda tid=tweet_id: api_like(page, tid, account_key, out))
                    else:
                        like_action = (
                            "like",
                            lambda: do_like(page, click_delay, out, account_key, cfg, target=tweet_id),
                        )

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
                    "zin20120731": (+5, 0, -5),  # 安定志向
                    "TankanNotes": (0, -5, +5),  # ゆったり
                }.get(account_key, (0, 0, 0))
                _pat_weights = [max(1, w + b + random.randint(-8, 8)) for w, b in zip(_pat_weights, _account_bias)]
                if like_action is not None:
                    insert_pos = random.choices([0, 1, 2], weights=_pat_weights, k=1)[0]
                    action_queue.insert(insert_pos, like_action)

                false_count = 0
                # ★ アクション成否記録（応募成立判定に使用）
                # ★ 2026-08-28提案68: フォロー失敗時のエラーコード(no_follow_button等)を保持し、
                #   下の失敗ハンドラで「再試行しても無駄な失敗」を即時 applied 付与する判定に使う。
                _per_item_ok: dict[str, bool] = {"follow": False, "rt": False, "like": False}
                _follow_error_code: str | None = None
                action_count = len(action_queue)
                for idx, (_name, _fn) in enumerate(action_queue):
                    # ★ 2026-08-31提案100: 日次総量上限をアクション単位で厳格チェック
                    #   prop98のitem単位チェック（check_rate_limit）は1item内の複数
                    #   アクション（F+R+L）でtotalが100→108まで跳ねる（実測: atushi16
                    #   =104/Tankan=108）。各アクション実行前にtotal専用チェックで
                    #   100丁度に抑える（hourly_limit_reachedと同構造）。
                    if daily_total_limit_reached(account_key, cfg):
                        out(
                            f"  [LIMIT] {account_key}: 日次総量上限到達"
                            f" → 残り{action_count - idx}アクションをスキップ（提案100）"
                        )
                        break
                    # ★ 2026-08-30提案94: hourly上限をアクション単位で厳格チェック
                    #   item単位チェック（check_rate_limit）は1item内の複数アクション
                    #   （F+R+L）でhourly counterが15→17まで跳ねる（実測: kudou 08時=17）。
                    #   各アクション実行前にhourly専用チェックで15超を防止する。
                    if hourly_limit_reached(account_key, cfg):
                        out(
                            f"  [LIMIT] {account_key}: 時間あたり上限（15件/時）到達"
                            f" → 残り{action_count - idx}アクションをスキップ（提案94）"
                        )
                        break
                    # ★ 2026-08-28提案53: 速度ガード（直近3分で15件超なら強制休止）
                    #   通常の間隔（12-40秒×各アクション）では到達しないが、
                    #   API高速成功が連続した最悪ケースの最終防衛線。
                    if _speed_guard_needed(_recent_action_times, _speed_window, _speed_max):
                        out(
                            f"  [SPEED] 直近{int(_speed_window)}秒で{len(_recent_action_times)}件"
                            f" → 強制休止{int(_speed_pause)}秒（Error 226対策）"
                        )
                        time.sleep(_speed_pause)
                        _recent_action_times.clear()
                    result = _fn()
                    # ★ 2026-08-28提案68: do_follow は (success, error_code) タプルを返す。
                    #   他の関数(bool)との後方互換を保つ: タプルは展開し、それ以外は bool 化。
                    if isinstance(result, tuple) and len(result) == 2:
                        _raw_ok, _raw_err = result
                        if _name == "follow":
                            _follow_error_code = _raw_err if not _raw_ok else None
                        result = _raw_ok
                    # result is True なら成功、それ以外(False/タプル等)は失敗
                    _rv = result is True
                    if _rv:
                        _recent_action_times.append(time.time())
                        # Track successful actions for sequence memory
                        _recent_action_sequence.append(_name)
                        # Keep memory manageable
                        if len(_recent_action_sequence) > _max_sequence_memory:
                            _recent_action_sequence.pop(0)
                    else:
                        # Track failed actions too (they affect behavior)
                        _recent_action_sequence.append(f"{_name}_failed")
                        if len(_recent_action_sequence) > _max_sequence_memory:
                            _recent_action_sequence.pop(0)
                    _per_item_ok[_name] = _per_item_ok.get(_name) or _rv
                    # ★ 連続いいねカウンタ更新: いいね成功で+1、フォロー/RT成功でリセット
                    if _rv:
                        if _name == "like":
                            consecutive_likes += 1
                        else:
                            consecutive_likes = 0
                    else:
                        if _name == "like":
                            consecutive_likes = 0  # Reset on failure
                    # ★ t_c189d8d8 提案1: 連続RT/いいね異常カウンタ更新。
                    #   RT/いいね成功で+1 → しきい値到達で _anomaly_abort フラグを立てる。
                    #   フォロー成功 or いずれかの失敗でリセット（人為的介入で安定化）。
                    if _rv:
                        if _name in ("rt", "like"):
                            consecutive_rt_like += 1
                            if consecutive_rt_like >= anomaly_max_rt_like:
                                out(
                                    f"  [ANOMALY] 提案1: RT/いいね{consecutive_rt_like}連続成功"
                                    f"（閾値{anomaly_max_rt_like}）→ セッション異常と判定、強制終了"
                                )
                                _anomaly_abort = True
                        else:
                            consecutive_rt_like = 0  # フォロー等でリセット
                    else:
                        consecutive_rt_like = 0  # 失敗でリセット
                    if result is False:
                        false_count += 1
                        if false_count >= 3:
                            out("  [FROZEN] 連続失敗3回 → アカウント凍結の可能性 → バッチ中断")
                            break
                        # ★ 2026-08-30提案90: フォロー403専用カウンタ
                        #   フォローHTTP 403のみカウント。他エラー/成功でリセット。
                        #   フォロー403はアカウント制限の初動シグナル（atushi1840凍結時の先触れ）。
                        #   既存false_countはRT/いいね成功でリセットされ検出不能なため専用カウンタで中断。
                        if _name == "follow" and _follow_error_code == "temp_lock_326":
                            # ★ 2026-08-30提案93: code 326（一時ロック）→ フォロー停止マーカー書込
                            #   凍結（code 64・提案90/91のFROZEN_ABORT対象）ではなく一時ロックなので、
                            #   バッチ中断せずフォローのみ停止して like/RT を継続する。
                            _lock_hours = float(cfg.get("applier", {}).get("follow_lock_hours", 4))
                            _set_follow_lock(account_key, _lock_hours)
                            _follow_locked_until = _get_follow_lock(account_key)
                            # 326は凍結でないので403カウンタはリセット
                            _follow_403_count = 0
                            out(
                                f"  [LOCK93] code 326 一時ロック検出 → {account_key}"
                                f" フォローを{int(_lock_hours)}時間停止（like/RT継続・提案93）"
                            )
                        elif _name == "follow" and _follow_error_code == "follow_suspended_64":
                            # ★ 2026-09-01提案102: code 64（アカウント停止）→ 当日フォロー完全停止
                            #   code 326より深刻。フォローは当日中完全停止（~12h）、
                            #   実質応募不能のためフォロー制限としては最長の停止期間。
                            #   翌日バッチで自動ログイン→再度code 64→再度LOCK102のループになるが、
                            #   「無駄な1バッチで済む」＝config除外よりソフトな停止。
                            _suspend_hours = float(cfg.get("applier", {}).get("follow_suspend_hours", 12))
                            _set_follow_lock(account_key, _suspend_hours)
                            _follow_locked_until = _get_follow_lock(account_key)
                            # 64は凍結判定に近いので403カウンタは触らない（通常パスでリセット）
                            out(
                                f"  [LOCK102] code 64 アカウント停止検出 → {account_key}"
                                f" フォローを{int(_suspend_hours)}時間停止（提案102）"
                            )
                        elif _name == "follow" and _follow_error_code == "http_403":
                            _follow_403_count += 1
                            out(f"  [i] フォロー403検出 {_follow_403_count}回目（フォロー制限シグナル・提案90）")
                            if _follow_403_count >= 3:
                                out(
                                    "  [FROZEN] フォロー403連続3回 → フォロー制限/アカウント制限検出"
                                    " → バッチ中断（提案90）"
                                )
                                # ★ 2026-08-30提案91: 内側ループbreakのみでは外側 `while` が
                                #   残りitemを全部処理して[FROZEN]がN回連続する（実測: 8/30 ib×11回）。
                                #   フラグを立てて外側ループ頭で即時中断させる。
                                _frozen_by_follow_403 = True
                                break
                        elif _name == "follow":
                            # フォローが403以外のエラー → カウンタリセット
                            _follow_403_count = 0
                    else:
                        false_count = 0
                        # ★ フォロー成功 → カウンタリセット（提案90）
                        if _name == "follow":
                            _follow_403_count = 0
                            # ★ 2026-08-30提案93: フォロー成功 → 一時ロック自動解除
                            #   ロック中はフォローがスキップされるため、ここに到達できるのは
                            #   ロック期限切れ後にフォローが成功したケース（自動復帰の完了）。
                            if _follow_locked_until is not None:
                                _clear_follow_lock(account_key)
                                _follow_locked_until = None
                                out("  [LOCK93] フォロー成功 → code 326 一時ロック解除（自動復帰・提案93）")
                    if idx < action_count - 1 and action_count >= 2:
                        # Enhanced human-like delay with simple pattern awareness
                        base_delay = random.uniform(5, 35)  # Base range

                        # Simple pattern avoidance: if we just did the same action, wait longer
                        if (
                            len(_recent_action_sequence) >= 2
                            and _recent_action_sequence[-1] == _recent_action_sequence[-2]
                        ):
                            base_delay *= random.uniform(1.5, 2.5)  # Increase delay for repeats

                        # Time of day adjustment
                        hour = datetime.now().hour
                        if 6 <= hour < 9:  # Morning: slightly faster
                            time_factor = 0.8
                        elif 9 <= hour < 17:  # Daytime: normal
                            time_factor = 1.0
                        elif 17 <= hour < 21:  # Evening: slightly relaxed
                            time_factor = 1.1
                        else:  # Night: slower, more deliberate
                            time_factor = 1.3

                        # Work style adjustments
                        if work_style == "morning_person":
                            time_factor *= 0.9
                        elif work_style == "burst":
                            if random.random() < 0.3:  # Occasional long pause
                                time_factor *= random.uniform(2.0, 4.0)
                        elif work_style == "night_owl":
                            if 20 <= hour or hour < 6:  # Night active
                                time_factor *= 0.8
                            else:  # Day inactive
                                time_factor *= 1.2

                        # Add natural variation
                        final_delay = base_delay * time_factor * random.uniform(0.7, 1.3)
                        final_delay = max(1.0, min(final_delay, 120))  # Reasonable bounds

                        time.sleep(final_delay)
                    else:
                        time.sleep(random.uniform(1.0, 3.5))

                # ★ セッション内set更新（成功したアクションのみ記録）
                if _per_item_ok.get("rt"):
                    rt_done_ids.add(tweet_id)
                if _per_item_ok.get("like") and tweet_id:
                    like_done_ids.add(tweet_id)  # 2026-08-28追加: いいね済みツイートの再アクション防止
                if _per_item_ok.get("follow") and screen_name:
                    followed_owners_session.add(screen_name)

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
                                # ★ 2026-08-26提案8: API成功(_per_item_ok["rt"]=True)をVERIFY失敗で覆さない。
                                #   VERIFYは「偽装成功の検出器」であり「成功の取り消し器」ではない。
                                _per_item_ok["rt"] = _merge_verify_result(_per_item_ok.get("rt", False), False)
                                out(f"  [VERIFY] RT: x {rt_result.detail}")
                            else:
                                out("  [VERIFY] RT: ok")
                        if not skip_like and tweet_id and _vcfg.get("verify_like", False):
                            like_result = ActionVerifier.verify_like(page, tweet_id, fallback_url=clean_url)
                            total_v += 1
                            if not like_result.success:
                                fail_v += 1
                                # ★ 2026-08-26提案8: API成功をVERIFY失敗で覆さない（rtと同じ）。
                                _per_item_ok["like"] = _merge_verify_result(_per_item_ok.get("like", False), False)
                                out(f"  [VERIFY] Like: x {like_result.detail}")
                            else:
                                out("  [VERIFY] Like: ok")
                        if not skip_follow and screen_name and _vcfg.get("verify_follow", False):
                            follow_result = ActionVerifier.verify_follow(page, screen_name)
                            total_v += 1
                            if not follow_result.success:
                                fail_v += 1
                                # ★ 2026-08-26提案8: API成功をVERIFY失敗で覆さない（rt/likeと同じ）。
                                _per_item_ok["follow"] = _merge_verify_result(_per_item_ok.get("follow", False), False)
                                out(f"  [VERIFY] Follow: x {follow_result.detail}")
                            else:
                                out("  [VERIFY] Follow: ok")
                    except Exception as ve:
                        # ★ 2026-08-26提案8: Page.gotoタイムアウト等のナビゲーションエラーは
                        #   アクション失敗ではない（X側遅延・プロキシ不安定）。failure_tracker/CEILING除外。
                        out(f"  [VERIFY] エラー: {ve}（ナビゲーションエラー → failure_tracker除外）")

                # Verify全件失敗チェック
                # ★ 2026-08-26提案8: VERIFY失敗はfailure_tracker/CEILINGの対象外。
                #   CEILINGは「アクション実行自体の失敗」（API失敗・UIフォールバック失敗）に限定。
                #   VERIFYは成功判定に不参加（API成功の維持・監視のみ）。
                if total_v > 0 and fail_v == total_v:
                    if any(_per_item_ok.values()):
                        out(f"  [VERIFY] 全件失敗 ({fail_v}/{total_v}) → API成功のため応募成立維持")
                    else:
                        out(f"  [VERIFY] 全件失敗 ({fail_v}/{total_v}) → failure_tracker記録なし（VERIFYは監視のみ）")

                # リプライ: 応募はフォロー/いいね/RTのみで行うため無効化
                out("  [i] リプライ: 無効化（応募はフォロー/いいね/RTのみ）")

                # ── 応募結果チェック ──
                # ★ 2026-08-29改修: 「応募成立」= フォロー状態+いいね（ユーザー定義）。
                #   フォローを実行/既フォローの場合、いいね成功（またはBOT対策の自然分散スキップ）で成立。
                #   RTのみの案件はRT成功で成立（従来通り）。いいねのみ・何もなしは成立扱いしない。
                #   ツイートが正常+1アクション成功 → ok。RT必須案件でRTだけ失敗 → rt_failedと記録
                #   し、appliedを付けない（次サイクルで再試行）。false成立(偽装)を防ぐ。
                tweet_result = _check_tweet_result(page, clean_url, out)
                # ★ 2026-08-25 修正: goto失敗(None)でもアクション成功なら応募成立。
                #   goto_failed で applied が付かず無限再処理→空回りする問題の修正。
                # ★ 2026-08-26 修正: 「全スキップ(見て終わり)」は成功扱いしない。
                #   従来 len(action_queue)==0 でも success 扱いになり、実際はアクション0件なのに
                #   「12成功」と水増し計上されていた（atushi16実測: ログ12成功/実アクション7件）。
                #   スキップのみは applied 付与（再処理防止）するが success には数えない。
                _follow_ok = bool(_per_item_ok.get("follow"))
                _rt_ok = bool(_per_item_ok.get("rt")) or _rt_already_done
                _like_ok = bool(_per_item_ok.get("like"))
                _qualify = tweet_result in ("tweet_ok", None) and _is_application_complete(
                    _follow_ok, _follow_already_done, _rt_ok, _like_ok, skip_like
                )
                _skipped_only: bool = len(action_queue) == 0
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
                elif _skipped_only:
                    # ★ 2026-08-26: スキップのみ（アクション0件）は「見て終わり」。
                    #   appliedは付与（再処理防止）するが success にはカウントしない。
                    item.setdefault("results", {})[account_key] = "skipped"
                    out("  [RESULT] ⏭ スキップのみ → 成功扱いせず（applied付与のみ）")
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
                    # ★ 2026-09-18提案: 複数同時刻応答検知（軽量版）
                    #   同一キャンペーン(tweet)へ他垢が窓期内に応募成功済みならログで検知
                    #   （same_campaign_multi）。アラートのみでブロックはしない（対応はManual）。
                    #   tweet_id無し（フォロー限定案件等）は同一キャンペーン識別不可のため対象外。
                    if tweet_id:
                        _multi_response_record(tweet_id, account_key, cfg, log)
                    # ★ 2026-08-25: applied付与を即時保存。
                    #   並列垢ワーカーが同じcollected.jsonを保存するため、バッチ中にappliedが
                    #   他プロセスの保存で失われる問題（実測: 応募成立10件中1件しか保存されず）。
                    #   save_collected_safe はロック+ディスク再読込+マージで競合を防ぐ。
                    save_collected_safe(data, account_key, log)
                elif _skipped_only:
                    # ★ 2026-08-26: スキップのみは再処理防止のため applied のみ付与。
                    #   success にはカウントしない（実アクション0件の水増し防止）。
                    item["applied"][account_key] = datetime.now().isoformat()
                    save_collected_safe(data, account_key, log)
                else:
                    # 未成立: appliedを付けず次サイクルで再試行。失敗として記録。
                    out("  [CEILING] アクション未成立 → 成功扱いせず（applied付与なし→再試行）")
                    if fc_enabled:
                        failure_tracker.record_failure(account_key)
                    # ★ 2026-08-28提案63: 失敗アクションの短時間DEFER（30分）で同一ターゲット再ピックを抑制。
                    #   フォロー/RT失敗は applied 未書き込みのため次バッチで再ピックされ、ネットワーク不安定期に
                    #   同一ターゲットへ複数回アクセス（実測: kudou comicowl_fg×3/10分、zin HMV_Japan×2）する
                    #   機械的パターンになる。DEFER:now+30min を書くことで30分以内の再ピックを防ぎ、
                    #   30分後は自然再試行（プロキシ復旧後の再試行を阻害しない）。
                    #   既存のDEFER（削除済み14日等・fallback_rt が書いた長期DEFER）は上書きしない。
                    # ★ 2026-08-28提案68: no_follow_button 等の「再試行しても無駄な失敗」は
                    #   30分DEFERでも無駄（同結果を返す）なので即時 applied 付与で完全停止する。
                    #   実測: korehamiro×3回（削除済み垢）・Rakuten_Wallet×4回/zin・steakgusto029×2回/zin
                    #   が同一バッチ内で連続アクセス → 機械的パターンのBOT検出リスクあり。
                    #   root cause: line 1551 旧 `is None` 判定は、DEFER(30分)期限切れ後の再ピックのたびに
                    #   DEFERを上書きせず素通り → 無限ループ。`not _is_deferred(val)` でDEFER期限切れも対象に。
                    # ★ 2026-08-29提案63 root-cause fix: `_is_deferred` はプレフィクス判定のみで
                    #   DEFER期限切れ文字列でも True を返すため、`not _is_deferred(...)` では
                    #   「期限切れDEFER→再ピック→失敗→素通り→30分ごと再ピックループ」が残る。
                    #   `_is_defer_expired` で実際の期限を比較し、期限切れDEFERのみ再対象化する。
                    _cur_applied_val = item.get("applied", {}).get(account_key)
                    if _cur_applied_val is None or _is_defer_expired(_cur_applied_val):
                        try:
                            from datetime import timedelta

                            # 提案68: no_follow_button / follow_confirm_missing / policy_denied 等の
                            # 「再試行しても無駄な失敗」は即時 applied(現在時刻) を付与して完全停止。
                            # 一方 http_0 / ネットワークエラー等の一時的失敗は30分DEFERで再試行可能に。
                            _waste_failure_codes = {"no_follow_button", "follow_confirm_missing", "policy_denied"}
                            _is_waste_failure = _follow_error_code in _waste_failure_codes
                            if _is_waste_failure:
                                item["applied"][account_key] = datetime.now().isoformat()
                                out(
                                    f"  [APPLIED] 無駄な失敗({_follow_error_code})"
                                    " → 即時 applied 付与（再処理停止・提案68）"
                                )
                                # ★ 2026-08-30提案87: 無駄な失敗主催者を当日ブロック
                                from kensho.application.follow_state_manager import FollowStateManager

                                if screen_name:
                                    FollowStateManager(account_key).record_follow_failure(
                                        screen_name, _follow_error_code
                                    )
                                    out(f"  [BLOCK] 主催者{screen_name}を当日ブロック（提案87）")
                                # ★ t_33113bb7 (C): 垢単位サーキットブレーカ記録（提案87と併用）。
                                #   同一エラー種別が連続 threshold 回で当該垢のフォロー試行を一時停止。
                                _cb_fsm = FollowStateManager(account_key)
                                if _cb_fsm.record_account_follow_failure(_follow_error_code):
                                    out(
                                        f"  [CB] 垢{account_key} サーキットブレーカ作動: "
                                        f"{_follow_error_code} が連続閾値到達 → フォロー試行を一時停止（提案C・t_33113bb7）"
                                    )
                            else:
                                _short_def_until: dt.datetime = datetime.now() + timedelta(
                                    minutes=cfg.get("applier", {}).get("retry_defer_minutes", 30)
                                )
                                item.setdefault("applied", {})[account_key] = (
                                    f"{_DEFER_PREFIX}{_short_def_until.isoformat()}"
                                )
                                _short_def_ts: str = _short_def_until.strftime("%H:%M")
                                out(f"  [DEFER] 失敗アクション → {_short_def_ts}まで再試行抑制（提案63）")
                            # 即時保存: 次バッチ（別プロセス）がディスクから再読込する前にDEFERを永続化。
                            save_collected_safe(data, account_key, log)
                        except Exception:
                            pass

                if global_idx % break_after_n == 0:
                    save_collected_safe(data, account_key, log)
                    out(f"  [SAVE] 保存 ({success}/{max_n})")
                    # Enhanced human-like break patterns with more variety and timing
                    if work_style == "burst":
                        # Burst style: shorter work periods, longer breaks
                        rest = random.uniform(break_min * 1.2, break_max * 1.5)
                    elif work_style == "night_owl":
                        # Night owls: longer breaks during their active hours
                        hour = datetime.now().hour
                        if 20 <= hour or hour < 6:  # Night time
                            rest = random.uniform(break_min * 0.8, break_max * 1.1)
                        else:  # Daytime for night owls - shorter breaks
                            rest = random.uniform(break_min * 0.5, break_max * 0.8)
                    elif work_style == "morning_person":
                        # Morning people: shorter breaks in morning, longer in afternoon
                        hour = datetime.now().hour
                        if hour < 12:  # Morning
                            rest = random.uniform(break_min * 0.6, break_max * 0.9)
                        else:  # Afternoon
                            rest = random.uniform(break_min * 0.8, break_max * 1.2)
                    else:
                        # Enhanced steady style with time-of-day variation
                        hour = datetime.now().hour
                        if 9 <= hour < 12:  # Late morning - peak productivity
                            rest = random.uniform(break_min * 0.7, break_max * 1.0)
                        elif 12 <= hour < 15:  # Early afternoon - post-lunch dip
                            rest = random.uniform(break_min * 1.2, break_max * 1.6)
                        elif 15 <= hour < 18:  # Late afternoon - recovery
                            rest = random.uniform(break_min * 0.9, break_max * 1.2)
                        else:  # Other times
                            rest = random.uniform(break_min, break_max)

                    # Add occasional micro-breaks and mega-breaks for human-like patterns
                    if random.random() < 0.1:  # 10% chance of micro-break
                        rest = random.uniform(5, 15)  # Very short break
                    elif random.random() < 0.02:  # 2% chance of mega-break
                        rest = random.uniform(120, 300)  # 2-5 minute break

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
                        # Enhanced human-like action delays with time-of-day variation
                        # More natural patterns that mimic human behavior throughout the day
                        hour = datetime.now().hour

                        # Adjust delays based on time of day (humans behave differently)
                        if 6 <= hour < 9:  # Morning - slightly faster, more alert
                            time_of_day_factor = 0.8
                        elif 9 <= hour < 17:  # Daytime - normal pace
                            time_of_day_factor = 1.0
                        elif 17 <= hour < 21:  # Evening - slightly relaxed
                            time_of_day_factor = 1.1
                        else:  # Night - slower, more deliberate
                            time_of_day_factor = 1.3

                        # Work style adjustments
                        if work_style == "morning_person":
                            _min_d = min_delay * 0.6 * time_of_day_factor
                            _max_d = max_delay * 0.7 * time_of_day_factor
                        elif work_style == "steady":
                            _min_d = min_delay * 1.1 * time_of_day_factor
                            _max_d = max_delay * 1.0 * time_of_day_factor
                        elif work_style == "burst":
                            # Burst style: quick actions followed by longer pauses
                            if random.random() < 0.3:  # 30% chance of pause after burst
                                _min_d = min_delay * 2.0 * time_of_day_factor
                                _max_d = max_delay * 3.0 * time_of_day_factor
                            else:
                                _min_d = min_delay * 0.5 * time_of_day_factor
                                _max_d = max_delay * 0.8 * time_of_day_factor
                        else:
                            _min_d = min_delay * time_of_day_factor
                            _max_d = max_delay * time_of_day_factor

                        # Add some Gaussian noise for more natural variation
                        base_delay = random.uniform(_min_d, _max_d)
                        enhanced_delay = max(0.5, base_delay * random.gauss(1.0, 0.2))  # 20% Gaussian variation
                        time.sleep(min(enhanced_delay, _max_d * 2))  # Reasonable cap

            except Exception as e:
                err_msg: str = str(e)[:60]
                # try to get page url
                try:
                    cur_url = page.url[:80]
                except Exception:
                    cur_url = "?"
                out(f"  [NG] {err_msg} (url={cur_url})")
                errors += 1
                # ★ 2026-08-29提案82: 例外時も失敗ハンドラを必ず実行し、当該アイテムへ
                #   DEFER(短時間)を書く。exceptパスにハンドラが無いと applied/DEFER が未書き込みの
                #   まま残り、次サイクルで同一ツイートが再ピックされて反復アクセスになる
                #   （実測: geass_survivor 1バッチ内7回ピック = 同一ツイート短時間反復 → BOT検出リスク）。
                #   例外は一時的失敗(プロキシ不安定等)の可能性が高いため30分DEFERで再試行可能にし、
                #   無闇な即時appliedはしない（_is_defer_expired で期限切れ後は自然再試行）。
                try:
                    _cur_exc_applied = item.get("applied", {}).get(account_key)
                    if _cur_exc_applied is None or _is_defer_expired(_cur_exc_applied):
                        from datetime import timedelta as _td

                        _exc_def_until: dt.datetime = datetime.now() + _td(
                            minutes=cfg.get("applier", {}).get("retry_defer_minutes", 30)
                        )
                        item.setdefault("applied", {})[account_key] = f"{_DEFER_PREFIX}{_exc_def_until.isoformat()}"
                        _exc_def_ts: str = _exc_def_until.strftime("%H:%M")
                        out(f"  [DEFER] 例外(再試行抑制) → {_exc_def_ts}（提案82）")
                        save_collected_safe(data, account_key, log)
                except Exception:
                    pass
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
