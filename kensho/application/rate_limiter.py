"""
Kensho Rate Limiter — 日次/時間あたりの上限管理
v3.3: application/applier.py から抽出、公開関数化
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psutil

from kensho.utils.backup import safe_save_json

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
DAILY_COUNTS_FILE: Path = DATA_DIR / "daily_counts.json"
DAILY_LOCK: Path = DATA_DIR / "daily_counts.lock"


def _lock_daily_counts(timeout: float = 15.0) -> bool:
    """日次カウンターファイルの排他ロック（並列垢実行時の更新ロスト防止）"""
    deadline: float = time.time() + timeout
    _span: float = random.uniform(0.3, 0.7)
    while time.time() < deadline:
        try:
            fd: int = os.open(str(DAILY_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except (FileExistsError, OSError):
            try:
                with open(DAILY_LOCK) as f:
                    _old_pid: int = int(f.read().strip())
                if not psutil.pid_exists(_old_pid):
                    DAILY_LOCK.unlink(missing_ok=True)
                    continue
            except Exception as e:
                print(f"[LOCK] daily_counts 古いロック読み込み失敗: {e}", flush=True)
            time.sleep(_span)
            continue
    return False


def _unlock_daily_counts() -> None:
    try:
        DAILY_LOCK.unlink(missing_ok=True)
    except Exception:
        pass


def load_daily_counts() -> dict[str, Any]:
    """本日のカウンター読み込み（公開関数）"""
    today: str = date.today().isoformat()
    if DAILY_COUNTS_FILE.exists():
        try:
            with open(DAILY_COUNTS_FILE, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)  # type: ignore[no-any-return]
            if data.get("date") == today:
                return data.get("counts", {})
        except Exception as e:
            print(f"[LIMIT] 日次カウンター読み込み失敗: {e}", flush=True)
    return {}


def save_daily_counts(counts: dict[str, Any]) -> None:
    """本日のカウンター保存（公開関数、バックアップ付き）"""
    today: str = date.today().isoformat()
    DAILY_COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    safe_save_json(DAILY_COUNTS_FILE, {"date": today, "counts": counts}, "daily_counts.json")


def check_rate_limit(account_key: str, cfg: dict[str, Any]) -> bool:
    """
    日次上限＋時間あたり上限に達してないかチェック。
    達していれば True（これ以上処理しない）、達していなければ False。
    """
    limits: dict[str, Any] = cfg.get("rate_limits", {})
    max_follow: int = limits.get("max_follow_per_day", 50)
    max_rt: int = limits.get("max_rt_per_day", 15)
    max_like: int = limits.get("max_like_per_day", 80)
    max_reply: int = limits.get("max_reply_per_day", 10)
    max_total: int = limits.get("max_total_actions_per_day", 0)  # 0=無効（旧config互換）
    max_per_hour: int = limits.get("max_actions_per_hour", 15)

    # ★ 日次ジッター（毎回±15%変動：BOT対策）
    jitter: float = random.uniform(0.85, 1.15)
    max_follow = int(max_follow * jitter)
    max_rt = int(max_rt * jitter)
    max_like = int(max_like * jitter)

    counts: dict[str, Any] = load_daily_counts()
    acct: dict[str, Any] = counts.get(account_key, {"follow": 0, "rt": 0, "like": 0, "reply": 0})
    f: int = acct.get("follow", 0)
    r: int = acct.get("rt", 0)
    lk: int = acct.get("like", 0)
    rep: int = acct.get("reply", 0)

    if f >= max_follow:
        print(f"[LIMIT] {account_key}: フォロー上限到達 ({f}/{max_follow})")
        return True
    if r >= max_rt:
        print(f"[LIMIT] {account_key}: RT上限到達 ({r}/{max_rt})")
        return True
    if lk >= max_like:
        print(f"[LIMIT] {account_key}: いいね上限到達 ({lk}/{max_like})")
        return True
    if rep >= max_reply:
        print(f"[LIMIT] {account_key}: リプライ上限到達 ({rep}/{max_reply})")
        return True

    # ★ 2026-08-31提案98: 日次総アクション上限（follow+rt+like+reply の合計）
    if max_total > 0:
        total: int = f + r + lk + rep
        if total >= max_total:
            print(f"[LIMIT] {account_key}: 日次総量上限到達 ({total}/{max_total})")
            return True

    # 時間あたり上限
    hourly: dict[str, int] = acct.get("hourly", {})
    current_hour: str = datetime.now().strftime("%H")
    hour_total: int = hourly.get(current_hour, 0)
    if hour_total >= max_per_hour:
        print(f"[LIMIT] {account_key}: 時間あたり上限到達 ({hour_total}/{max_per_hour}/時)")
        return True

    return False


def daily_total_limit_reached(account_key: str, cfg: dict[str, Any]) -> bool:
    """日次総量上限に達したかチェック（totalのみ・アクション単位で使う）。

    hourly_limit_reached と同様、action_queueループ内で各アクション実行前に
    呼ばれる。日次総量（follow+rt+like+reply）が max_total_actions_per_day 以上
    なら True を返し、残りアクションをスキップさせる。
    （2026-08-31提案100: prop98のitem単位チェックでは1item内の複数アクション
    F+R+Lでtotalが100→108まで跳ねる。アクション単位で厳格チェックする。）
    """
    limits: dict[str, Any] = cfg.get("rate_limits", {})
    max_total: int = limits.get("max_total_actions_per_day", 0)  # 0=無効（旧config互換）
    if max_total <= 0:
        return False
    counts: dict[str, Any] = load_daily_counts()
    acct: dict[str, Any] = counts.get(account_key, {})
    f: int = acct.get("follow", 0)
    r: int = acct.get("rt", 0)
    lk: int = acct.get("like", 0)
    rep: int = acct.get("reply", 0)
    total: int = f + r + lk + rep
    if total >= max_total:
        print(f"[LIMIT] {account_key}: 日次総量上限到達（アクション単位）({total}/{max_total})", flush=True)
        return True
    return False


def hourly_limit_reached(account_key: str, cfg: dict[str, Any]) -> bool:
    """時間あたり上限に達したかチェック（hourlyのみ・アクション単位で使う）。

    check_rate_limit は日次上限（フォロー50等）も含むため、action_queueループ内で
    使うと「フォロー上限到達」でRT/いいねまで止まる。hourly 専用に分離した。
    （2026-08-30提案94: 従来はitem単位チェックのため1item内の複数アクション
    F+R+Lでhourly counterが15→17まで跳ねた。実測: kudou 08時=17）
    """
    limits: dict[str, Any] = cfg.get("rate_limits", {})
    max_per_hour: int = limits.get("max_actions_per_hour", 15)
    counts: dict[str, Any] = load_daily_counts()
    acct: dict[str, Any] = counts.get(account_key, {})
    hourly: dict[str, int] = acct.get("hourly", {})
    current_hour: str = datetime.now().strftime("%H")
    hour_total: int = hourly.get(current_hour, 0)
    if hour_total >= max_per_hour:
        print(f"[LIMIT] {account_key}: 時間あたり上限到達 ({hour_total}/{max_per_hour}/時)")
        return True
    return False


def increment_daily_count(account_key: str, action_type: str, n: int = 1) -> None:
    """日次カウンターと時間別カウンターを増やす（公開関数、並列更新ロスト防止）"""
    locked: bool = _lock_daily_counts()
    try:
        # ロック保持中に再読込 → 他プロセスの増分をマージしてから+1
        counts: dict[str, Any] = load_daily_counts()
        if account_key not in counts:
            counts[account_key] = {
                "follow": 0,
                "rt": 0,
                "like": 0,
                "reply": 0,
                "hourly": {},
            }
        counts[account_key][action_type] = counts[account_key].get(action_type, 0) + n
        current_hour: str = datetime.now().strftime("%H")
        if "hourly" not in counts[account_key]:
            counts[account_key]["hourly"] = {}
        counts[account_key]["hourly"][current_hour] = counts[account_key]["hourly"].get(current_hour, 0) + n
        save_daily_counts(counts)
    finally:
        if locked:
            _unlock_daily_counts()


def is_active_hours(cfg: dict[str, Any]) -> bool:
    """現在時刻が動作許可時間帯かチェック（公開関数）"""
    limits: dict[str, Any] = cfg.get("rate_limits", {})
    start_s: str = limits.get("active_hours_start", "09:00")
    end_s: str = limits.get("active_hours_end", "23:59")
    now: datetime = datetime.now()
    now_m: int = now.hour * 60 + now.minute
    start_m: int = int(start_s.split(":")[0]) * 60 + int(start_s.split(":")[1])
    end_m: int = int(end_s.split(":")[0]) * 60 + int(end_s.split(":")[1])
    return start_m <= now_m <= end_m
