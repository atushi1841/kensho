"""
Kensho Config — YAML設定ファイルの読み込み・バリデーション
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH: Path = Path(__file__).parent.parent.parent / "config.yaml"


def load(path: str | Path | None = None) -> dict[str, Any]:
    """config.yaml を読み込み、バリデーションして返す"""
    resolved: Path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not resolved.exists():
        raise FileNotFoundError(f"Config not found: {resolved}")

    with open(resolved, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    validate(cfg)
    fill_defaults(cfg)
    return cfg


def validate(cfg: dict[str, Any]) -> None:
    """必須項目の存在チェック"""
    errors: list[str] = []

    if "accounts" not in cfg or not cfg["accounts"]:
        errors.append("accounts: 必須（1垢以上定義）")

    for i, acct in enumerate(cfg.get("accounts", [])):
        if "key" not in acct:
            errors.append(f"accounts[{i}]: key がありません")
        if "session" not in acct:
            errors.append(f"accounts[{i}]: session がありません")
        if "schedule" not in acct or "batches" not in acct.get("schedule", {}):
            errors.append(f"accounts[{i}]: schedule.batches がありません")

    if "collection" not in cfg:
        errors.append("collection: 必須")

    if "keepalive" not in cfg or "interfaces" not in cfg["keepalive"]:
        errors.append("keepalive.interfaces: 必須")

    if errors:
        raise ValueError("Config validation errors:\n" + "\n".join(errors))


def fill_defaults(cfg: dict[str, Any]) -> None:
    """デフォルト値で補完"""
    g: dict[str, Any] = cfg.setdefault("general", {})
    g.setdefault("project_dir", str(Path(__file__).parent.parent.parent))
    g.setdefault("log_retention_days", 30)
    g.setdefault("session_warn_days", 3)

    n: dict[str, Any] = cfg.setdefault("notify", {})
    n.setdefault("discord_webhook", "")
    n.setdefault("windows_toast", False)

    col: dict[str, Any] = cfg.setdefault("collection", {})
    col.setdefault("source", "https://knshow.com")
    col.setdefault("times", ["09:00", "13:00", "18:00"])
    col.setdefault("max_items", 200)

    ka: dict[str, Any] = cfg.setdefault("keepalive", {})
    ka.setdefault("interval_minutes", 5)
    ka.setdefault("interfaces", [])

    orch: dict[str, Any] = cfg.setdefault("orchestrator", {})
    orch.setdefault("interval_minutes", 15)
    orch.setdefault("max_accounts_per_run", 2)
    orch.setdefault("apply_timeout", 600)
    orch.setdefault("priority", "round_robin")

    rl: dict[str, Any] = cfg.setdefault("rate_limits", {})
    rl.setdefault("memory_reserve_mb", 2048)


# ════════════════════════════════════════════
# Pydantic 型安全設定モデル（v2）
# config.yaml を型安全に操作するためのモデル
# load_typed() で dict の代わりに KenshoConfig を取得
# ════════════════════════════════════════════

from pydantic import BaseModel  # noqa: E402


class BatchConfig(BaseModel):
    """1バッチの応募スケジュール"""

    time: str
    max: int = 5


class AccountSchedule(BaseModel):
    collects: bool = True
    batches: list[BatchConfig] = []


class AccountConfig(BaseModel):
    """Xアカウント設定"""

    key: str
    display: str | None = None
    session: str = ""
    disable_reply: bool = False
    schedule: AccountSchedule = AccountSchedule()
    session_max_age_days: int | None = None


class RateLimitConfig(BaseModel):
    """レート制限設定"""

    max_follow_per_day: int = 50
    max_rt_per_day: int = 15
    max_rt_jitter: int = 5
    max_like_per_day: int = 80
    max_reply_per_day: int = 10
    max_actions_per_hour: int = 15
    active_hours_start: str = "09:00"
    active_hours_end: str = "22:00"
    min_delay_between_actions: int = 15
    max_delay_between_actions: int = 50
    extra_long_pause_chance: float = 0.15
    break_after_n_items: int = 2
    break_min_seconds: int = 45
    break_max_seconds: int = 120
    memory_reserve_mb: int = 2048


class CollectionConfig(BaseModel):
    """収集設定"""

    source: str = "https://knshow.com"
    times: list[str] = ["09:00", "13:00", "18:00"]
    max_items: int = 200


class KeepaliveInterface(BaseModel):
    label: str
    type: str
    wifi_profile: str | None = None


class KeepaliveConfig(BaseModel):
    interval_minutes: int = 5
    interfaces: list[KeepaliveInterface] = []


class SafetyConfig(BaseModel):
    ip_separation_check: bool = True
    ip_check_timeout: int = 10
    cache_ttl_seconds: int = 1800


class OrchestratorConfig(BaseModel):
    interval_minutes: int = 15
    max_accounts_per_run: int = 2
    apply_timeout: int = 600
    priority: str = "round_robin"


class GeneralConfig(BaseModel):
    project_dir: str = "/mnt/d/Project2/kensho"
    python: str | None = None
    log_retention_days: int = 30
    session_warn_days: int = 3


class NotifyConfig(BaseModel):
    discord_webhook: str = ""
    windows_toast: bool = False


class KenshoConfig(BaseModel):
    """型安全な全体設定。config.yaml の内容を Pydantic で表現。"""

    general: GeneralConfig = GeneralConfig()
    notify: NotifyConfig = NotifyConfig()
    accounts: list[AccountConfig] = []
    collection: CollectionConfig = CollectionConfig()
    keepalive: KeepaliveConfig = KeepaliveConfig()
    rate_limits: RateLimitConfig = RateLimitConfig()
    safety: SafetyConfig = SafetyConfig()
    orchestrator: OrchestratorConfig = OrchestratorConfig()


def load_typed(path: str | Path | None = None) -> KenshoConfig:
    """config.yaml を読み込み、型安全な KenshoConfig オブジェクトとして返す"""
    raw = load(path)
    return KenshoConfig(**raw)
