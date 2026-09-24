"""Self-healing loop for Kensho collect / apply pipelines.

Implements the Loop Engineering 4-layer pattern:
  Layer 1 — Verifier:      custom validator or exception classifier
  Layer 2 — Failure Ceiling: consecutive failures + cooldown
  Layer 3 — Health Check:   network + crash-history check before retry
  Layer 4 — PolicyEngine:   default recoveries, AI advisor (opt-in), guardrails

Default recovery order (name based):
  jitter_retry → ai_consult → network_check → transport_fallback → scope_reduction

  ai_consult はプラン上2番目に置く（実効順の従来動作を維持）。ai_assisted=false / 対象外
  パイプラインのアクションはプランから除外され、その分だけ後続アクションが前倒しになる。

t_8946706e (2026-09-24) の恒久修正:
  - failure ceiling は **キー単位**（apply は `apply:<account_key>`）で数える。全体キーだと
    1垢の失効失敗が他垢の成功で毎回リセットされ、遮断が一度も発動しない（実測 count=0）。
  - ceiling の遮断判定は `first_fail_time`（初回固定）ではなく `last_fail_time` + `blocked_until`
    （しきい値到達時点で cooldown ぶん遮断）で行う。毎時cron（間隔60分 > cooldown30分）でも発動する。
  - session/auth 系の失敗は **リトライ対象外**（回復不能）。1回で停止＋当該キーのみ遮断＋通知。
    失効セッション垢への盲目的リトライがブラウザ起動とXログインを再実行し、BOTシグナルを
    増幅していた（goto failed 63→227件/日・ログイン試行 55→108回/日）。
  - 回復プランは永続カーソルで段階的に消費する。max_attempts を増やさずに
    transport_fallback / scope_reduction へ到達可能（プラン枯渇時はリトライせず停止）。
  - 回復イベントは必ず `[SELF-HEAL]` の構造化1行として logger へ出す（可観測性）。

The AI advisor calls OpenRouter-compatible endpoint directly and never
modifies files; it only returns an action recommendation.
"""
from __future__ import annotations

import copy
import json
import os
import random
import re
import traceback
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class ErrorKind(Enum):
    network = "network"
    selector = "selector"
    session = "session"
    rate_limit = "rate_limit"
    crash_loop = "crash_loop"
    silent = "silent"
    runtime = "runtime"


@dataclass
class ErrorInfo:
    kind: ErrorKind = ErrorKind.runtime
    message: str = ""
    traceback_snippet: str = ""


@dataclass
class RecoverySignal:
    kind: str = ""
    recoverable: bool = False
    message: str = ""
    severity: str = "warn"
    context: dict[str, Any] = field(default_factory=dict)
    allowlist: tuple[str, ...] = ()


@dataclass
class HealingEvent:
    attempt: int = 0
    error_kind: str = ""
    message: str = ""
    action: str = ""
    detail: str = ""
    timestamp: str = ""
    key: str = ""


@dataclass
class HealingResult:
    ok: bool = False
    value: Any = None
    error: str = ""
    events: list[HealingEvent] = field(default_factory=list)
    attempts: int = 0
    recovered: bool = False

    def value_or_raise(self) -> Any:
        if self.ok:
            return self.value
        raise RuntimeError(f"self_heal failed: {self.error} (attempts={self.attempts})")


DEFAULT_MIN_DELAY = 3.0
DEFAULT_MAX_DELAY = 10.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RECOVERY_ORDER = "jitter_retry,ai_consult,network_check,transport_fallback,scope_reduction"
# 自己修復では回復不能な種類（リトライすると露出＝BOTシグナルが増えるだけ）。
DEFAULT_FATAL_SIGNAL_KINDS = (
    "session,auth,dead_proxy,rate_limit,rate_limited,suspended,frozen,"
    "no_auth_session,needs_login,login_failed,goto_failed,challenge"
)
DEFAULT_FATAL_SIGNAL_MARKERS = (
    "auth_token,no_auth_session,needs_login,not logged in,login failed,ログイン失敗,"
    "invalid session,cookie expired,session expired,"
    "dead_proxy,http_0,goto_failed,goto failed,proxy is dead,プロキシ死骸,"
    "rate_limited,account suspended,frozen,読み取り専用"
)

_NETWORK_MARKERS = ("timeout", "connect", "connection", "httpx", "proxy", "socks", "network", "dns", "refused", "reset", "502", "503", "504")
_SELECTOR_MARKERS = ("selector", "css", "query_selector", "no element", "not found", "attribute", "element not", "regex", "extract", "tdp")
_SESSION_MARKERS = ("session", "cookie", "auth", "csrf", "login", "401", "403")
_RATE_MARKERS = ("429", "rate limit", "ratelimit", "too many requests")
_CRASH_MARKERS = ("crash", "segfault", "stack overflow")

_SENSITIVE_RE = re.compile(r"(api[_-]?key|token|password|secret|auth|cookie|session|authorization)", re.I)
_SENSITIVE_VALUE_RE = re.compile(r"(Bearer |Basic |token=|key=|password=|token:)\S+", re.I)


def _sanitize(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        line = _SENSITIVE_VALUE_RE.sub(r"\1<redacted>", line)
        if _SENSITIVE_RE.search(line):
            line = re.sub(r":\s*\S+", ": <redacted>", line, count=1)
        out_lines.append(line)
    return "\n".join(out_lines)


def capture_error_log(project_dir: str | Path, limit: int = 60) -> str:
    root = Path(project_dir)
    candidates: list[Path] = []
    for pattern in ("logs/**/*.log", "logs/*.log", "**/*auto*.log", "**/*cron*.log"):
        candidates.extend(root.glob(pattern))
    candidates = [p for p in candidates if p.is_file()]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    lines: list[str] = []
    for p in candidates[:3]:
        try:
            data = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        tail = data.splitlines()[-limit:]
        lines.append(f"--- {p} (tail {len(tail)}) ---")
        lines.extend(tail[-20:])
    return "\n".join(lines[-limit * 2:])


def classify_error(exc: BaseException) -> ErrorInfo:
    msg = f"{type(exc).__name__}: {exc}"
    tb = "".join(traceback.format_exception_only(type(exc), exc))
    low = msg.lower()
    kind = ErrorKind.runtime
    if any(m in low for m in _CRASH_MARKERS):
        kind = ErrorKind.crash_loop
    elif any(m in low for m in _NETWORK_MARKERS):
        kind = ErrorKind.network
    elif any(m in low for m in _SELECTOR_MARKERS):
        kind = ErrorKind.selector
    elif any(m in low for m in _SESSION_MARKERS):
        kind = ErrorKind.session
    elif any(m in low for m in _RATE_MARKERS):
        kind = ErrorKind.rate_limit
    return ErrorInfo(kind=kind, message=msg, traceback_snippet=tb.strip())


def _csv_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [p.strip().lower() for p in str(value or "").split(",") if p.strip()]


def _parse_ts(value: Any) -> datetime | None:
    """壊れたタイムスタンプでも例外を出さない ISO パーサ。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def is_fatal_signal(signal: RecoverySignal, cfg: dict[str, Any] | None = None) -> bool:
    """自己修復では回復不能な失敗（セッション失効・認証・プロキシ死骸）か。

    F3: validator 由来のシグナルは classify_error を通らないため、
    `apply 0 success 1 errors` のような認証失敗が「一般エラー」に見えて3回リトライされていた。
    kind とメッセージの両方から判定する。
    """
    cfg = cfg or {}
    kinds = set(_csv_list(cfg.get("fatal_signal_kinds", DEFAULT_FATAL_SIGNAL_KINDS)))
    markers = _csv_list(cfg.get("fatal_signal_markers", DEFAULT_FATAL_SIGNAL_MARKERS))
    kind = str(getattr(signal, "kind", "") or "").strip().lower()
    if kind and kind in kinds:
        return True
    text = f"{kind} {getattr(signal, 'message', '') or ''}".lower()
    return any(m in text for m in markers)


def _resolve_state_path(cfg: dict[str, Any], project_dir: Path) -> Path:
    """state_file を project_dir 基準に解決する。

    ★ t_8946706e: config.yaml の `state_file: data/self_heal_state.json`（相対）が
    `Path(...)` にそのまま渡ると **CWD基準** で解決され、プロジェクトルート以外から
    実行された run は別の場所に状態を書き込んでしまう（=failure ceiling が読むカウンタが
    実質リセットされ遮断が発火しない）。相対パスは必ず project_dir 配下へ固定する。
    """
    raw = str(cfg.get("state_file") or "data/self_heal_state.json")
    path = Path(raw)
    return path if path.is_absolute() else Path(project_dir) / path


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _default_config(project_dir: str | Path) -> dict[str, Any]:
    return {
        "enabled": True,
        "max_attempts": DEFAULT_MAX_ATTEMPTS,
        "min_delay_sec": DEFAULT_MIN_DELAY,
        "max_delay_sec": DEFAULT_MAX_DELAY,
        "failure_ceiling_consecutive": 3,
        "failure_ceiling_cooldown_minutes": 30,
        "state_file": str(Path(project_dir) / "data" / "self_heal_state.json"),
        "log_tail_lines": 60,
        "ai_assisted": False,
        "ai_timeout_sec": 25,
        "ai_model": "",
        "retry_empty_collection": False,
        "retry_partial_apply": False,
        "notify_on_error": True,
        "allowed_ai_actions": "retry,switch_transport,reduce_scope",
        "recovery_order": DEFAULT_RECOVERY_ORDER,
        "fatal_signal_kinds": DEFAULT_FATAL_SIGNAL_KINDS,
        "fatal_signal_markers": DEFAULT_FATAL_SIGNAL_MARKERS,
    }


def _merge_config(cfg: dict[str, Any] | None, project_dir: str | Path) -> dict[str, Any]:
    merged = _default_config(project_dir)
    if cfg:
        user = cfg.get("self_healing", {}) or {}
        merged.update(user)
        # F4: 回復アクション（transport_fallback / scope_reduction）が対象パイプラインの設定を
        #     実際に書き換えられるよう、生configも取り込む。呼出側の config を汚さないよう複製する。
        for _k, _v in cfg.items():
            if _k == "self_healing":
                continue
            merged.setdefault(_k, copy.deepcopy(_v))
    merged["project_dir"] = str(project_dir)
    return merged


def _jitter_delay(min_sec: float, max_sec: float) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def _builtin_action(name: str, cfg: dict[str, Any], ctx: dict[str, Any]) -> str:
    if name == "jitter_retry":
        _jitter_delay(float(cfg.get("min_delay_sec", DEFAULT_MIN_DELAY)),
                      float(cfg.get("max_delay_sec", DEFAULT_MAX_DELAY)))
        return "retrying"
    if name == "network_check":
        try:
            from kensho.keepalive.checker import check_all
            interfaces, ok = check_all(cfg)
            if ok:
                return "network_ok"
            return "network_unhealthy"
        except Exception as e:
            return f"network_check_failed:{e}"
    if name == "transport_fallback":
        coll = cfg.get("collection", {})
        cur = bool(coll.get("use_scrapling"))
        coll["use_scrapling"] = not cur
        return f"toggled_scrapling:{cur}->{not cur}"
    if name == "scope_reduction":
        coll = cfg.get("collection", {})
        if "max_pages" in coll and coll["max_pages"] > 1:
            coll["max_pages"] = 1
            return "max_pages_set_1"
        return "scope_noop"
    if name == "session_retry":
        return "retrying"
    return name


def _parse_ai_response(text: str) -> tuple[str, str]:
    text = text.strip()
    m = re.search(r"\{[^}]*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            action = str(data.get("action", data.get("recommended_action", "none"))).strip().lower()
            reason = str(data.get("reason", data.get("detail", ""))).strip()
            return action, reason
        except json.JSONDecodeError:
            pass
    m = re.search(r"(retry|switch_transport|reduce_scope|manual_intervention|none|session_retry|ai_consult)", text, re.I)
    if m:
        return m.group(1).lower(), text
    return "none", text


def _ai_consult(
    cfg: dict[str, Any],
    pipeline: str,
    context: dict[str, Any],
    error_info: str,
    log_tail: str,
) -> tuple[str, str]:
    model = cfg.get("ai_model") or os.environ.get("SELF_HEAL_AI_MODEL", "")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return "none", "no_openrouter_api_key"
    url = "https://openrouter.ai/api/v1/chat/completions"
    allowed = [a.strip() for a in cfg.get("allowed_ai_actions", "").split(",") if a.strip()]
    allowed = allowed or ["retry", "switch_transport", "reduce_scope"]
    payload = {
        "model": model or "openrouter/nemotron-3.5-lightning:free",
        "max_tokens": 512,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": (
                "You are a Kensho self-healing advisor. "
                "Return ONLY a JSON object with keys action and reason. "
                "Allowed actions: " + ",".join(allowed) + ". "
                "If the issue looks transient, choose retry. "
                "If a selector changed, choose switch_transport only for HTTP fetch pipelines, "
                "otherwise reduce_scope or manual_intervention. "
                "Never recommend deleting session files or sending raw API keys."
            )},
            {"role": "user", "content": (
                f"pipeline={pipeline}\ncontext={json.dumps(context)}\n"
                f"error={error_info[:1500]}\nlog_tail={_sanitize(log_tail)[-1500:]}"
            )},
        ],
    }
    try:
        import httpx

        resp = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/kensho",
                "X-Title": "kensho-self-heal",
                "Content-Type": "application/json",
            },
            timeout=float(cfg.get("ai_timeout_sec", 25)),
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_ai_response(content)
    except Exception as e:
        return "none", f"ai_error:{e}"


class SelfHealingLoop:
    """Reusable self-healing loop.

    Usage:
        loop = SelfHealingLoop(cfg, pipeline="collection")
        result = loop.run(lambda: collect(...), validator=...)
        if not result.ok: ...
    """

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        pipeline: str = "",
        logger: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        project_dir = Path(cfg.get("general", {}).get("project_dir", ".")) if cfg else Path(".")
        self.raw_cfg: dict[str, Any] = dict(cfg or {})
        self.cfg = _merge_config(cfg, project_dir)
        self.pipeline = pipeline
        self.logger = logger
        self.context = dict(context or {})
        self.state_path = _resolve_state_path(self.cfg, project_dir)
        self.config = self.cfg
        self.events: list[HealingEvent] = []
        self._ceiling_hits: dict[str, float] = {}

    # ── failure ceiling ─────────────────────────────────────
    def _ceiling_info(self, key: str) -> dict[str, Any]:
        info = _load_state(self.state_path).get("ceilings", {}).get(key, {})
        return info if isinstance(info, dict) else {}

    @property
    def _ceiling_limit(self) -> int:
        return max(1, int(self.cfg.get("failure_ceiling_consecutive", 3)))

    @property
    def _ceiling_cooldown_minutes(self) -> float:
        return float(self.cfg.get("failure_ceiling_cooldown_minutes", 30))

    def _is_ceiling_hit(self, key: str) -> bool:
        """しきい値到達かつ遮断期限内か。

        F5: `first_fail_time`（初回固定・以後更新なし）基準だと cooldown 30分 < cron間隔60分 で
        毎時runでは構造的に発動しなかった。`blocked_until`（しきい値到達時に設定）→
        無ければ `last_fail_time`（毎回更新）基準で判定する。
        """
        info = self._ceiling_info(key)
        if int(info.get("count", 0) or 0) < self._ceiling_limit:
            return False
        until = _parse_ts(info.get("blocked_until"))
        if until is not None:
            return datetime.now() < until
        last = _parse_ts(info.get("last_fail_time")) or _parse_ts(info.get("first_fail_time"))
        if last is None:
            return False
        return (datetime.now() - last).total_seconds() < self._ceiling_cooldown_minutes * 60

    def _record_ceiling(self, key: str, hit: bool) -> None:
        st = _load_state(self.state_path)
        ceilings = st.setdefault("ceilings", {})
        now = datetime.now()
        if hit:
            entry = ceilings.setdefault(key, {"count": 0})
            entry["count"] = int(entry.get("count", 0) or 0) + 1
            entry.setdefault("first_fail_time", now.isoformat())
            entry["last_fail_time"] = now.isoformat()
            if entry["count"] >= self._ceiling_limit:
                # F5: しきい値到達時点で cooldown ぶん遮断（毎時cronでも発動する）
                entry["blocked_until"] = (
                    now + timedelta(minutes=self._ceiling_cooldown_minutes)
                ).isoformat()
                entry["blocked_reason"] = "failure_ceiling"
        elif key in ceilings:
            # 成功したキーだけカウンタ・遮断・回復カーソルをリセットする（キー単位＝垢単位）
            ceilings[key] = {"count": 0, "first_fail_time": ""}
        st["updated"] = now.isoformat()
        if not hit:
            st.setdefault("recovery_cursor", {}).pop(key, None)
        _save_state(self.state_path, st)

    def _block(self, key: str, reason: str) -> None:
        """回復不能な失敗でそのキー（垢）だけを cooldown ぶん遮断する。"""
        st = _load_state(self.state_path)
        ceilings = st.setdefault("ceilings", {})
        now = datetime.now()
        entry = ceilings.setdefault(key, {"count": 0})
        entry["count"] = max(int(entry.get("count", 0) or 0), self._ceiling_limit)
        entry.setdefault("first_fail_time", now.isoformat())
        entry["last_fail_time"] = now.isoformat()
        entry["blocked_until"] = (now + timedelta(minutes=self._ceiling_cooldown_minutes)).isoformat()
        entry["blocked_reason"] = reason
        st["updated"] = now.isoformat()
        _save_state(self.state_path, st)

    # ── recovery plan（段階消費カーソル） ───────────────────
    def _recovery_plan(self) -> list[str]:
        order = _csv_list(self.cfg.get("recovery_order", DEFAULT_RECOVERY_ORDER))
        return [name for name in order if self._action_applicable(name)]

    def _action_applicable(self, name: str) -> bool:
        """その回復アクションが対象パイプラインで意味を持つか（意味の無い設定を残さない）。"""
        if name == "ai_consult":
            # F2: ai_assisted=false（本番にOPENROUTERキーなし）では no-op attempt を作らない
            return bool(self.cfg.get("ai_assisted", False))
        if name == "transport_fallback":
            # collection の fetch 経路（use_scrapling）を切り替えるアクション
            return self.pipeline == "collection"
        if name == "scope_reduction":
            coll = self.cfg.get("collection", {}) or {}
            try:
                return self.pipeline == "collection" and int(coll.get("max_pages", 0) or 0) > 1
            except Exception:
                return False
        return True

    def _cursor(self, key: str, advance: int | None = None) -> int:
        st = _load_state(self.state_path)
        cursor = st.setdefault("recovery_cursor", {})
        pos = int(cursor.get(key, 0) or 0)
        if advance:
            cursor[key] = pos + advance
            st["updated"] = datetime.now().isoformat()
            _save_state(self.state_path, st)
        return pos

    # ── observability（F1） ─────────────────────────────────
    def _log_event(self, event: HealingEvent) -> None:
        line = (
            f"[SELF-HEAL] pipeline={self.pipeline} key={event.key} attempt={event.attempt} "
            f"error_kind={event.error_kind} action={event.action} detail={event.detail}"
        )
        if event.message:
            line += f" message={_sanitize(str(event.message))[:200]}"
        lg = self.logger
        if lg is not None and hasattr(lg, "write"):
            try:
                lg.write(line)
                return
            except Exception:
                pass
        try:
            print(line, flush=True)
        except Exception:
            pass

    def _record(self, event: HealingEvent) -> None:
        self.events.append(event)
        self._log_event(event)

    # ── public helpers ──────────────────────────────────────
    def is_blocked(self, key: str | None = None) -> bool:
        key = key or self.pipeline
        if self._is_ceiling_hit(key):
            return True
        st = _load_state(self.state_path)
        until = st.get("blocked_until", "")
        if until and datetime.now().isoformat() < until:
            return True
        return False

    def reset(self, key: str | None = None) -> None:
        key = key or self.pipeline
        st = _load_state(self.state_path)
        st.setdefault("ceilings", {})[key] = {"count": 0, "first_fail_time": ""}
        st.setdefault("recovery_cursor", {}).pop(key, None)
        st.pop("blocked_until", None)
        st["updated"] = datetime.now().isoformat()
        _save_state(self.state_path, st)

    # ── main run ────────────────────────────────────────────
    def run(
        self,
        operation: Callable[..., Any],
        *,
        context: dict[str, Any] | None = None,
        validator: Callable[..., RecoverySignal | None] | None = None,
        recoveries: list[str] | None = None,
    ) -> HealingResult:
        ctx = dict(self.context)
        ctx.update(context or {})
        ctx.setdefault("pipeline", self.pipeline)
        key = ctx.get("key") or self.pipeline
        result = HealingResult()
        if self.is_blocked(key):
            result.error = "failure_ceiling_blocked"
            self._record(HealingEvent(attempt=0, error_kind="ceiling",
                                      key=str(key),
                                      message="failure ceiling blocked",
                                      action="blocked", timestamp=datetime.now().isoformat()))
            return result

        plan = list(recoveries) if recoveries else self._recovery_plan()
        max_attempts = int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS))
        last_exc: BaseException | None = None
        last_value: Any = None
        ai_used = False
        signal: RecoverySignal | None = None
        actions_run = 0
        stopped = ""  # "fatal" | "plan_exhausted" | "ceiling" | ""

        for attempt in range(max_attempts):
            result.attempts = attempt + 1
            info: ErrorInfo | None = None
            try:
                last_value = operation()
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except Exception as exc:
                last_exc = exc
                info = classify_error(exc)
                signal = RecoverySignal(kind=info.kind.value, recoverable=True,
                                        message=info.message, severity="error")
                if validator is not None:
                    try:
                        vs = validator(exception=exc, value=None, context=ctx)
                        if vs:
                            signal = vs
                    except Exception:
                        pass
            else:
                info = None
                signal = None
                if validator is not None:
                    try:
                        signal = validator(value=last_value, exception=None, context=ctx)
                    except Exception:
                        pass
                if signal is None:
                    result.ok = True
                    result.value = last_value
                    result.recovered = result.attempts > 1
                    self._record_ceiling(key, False)
                    return result
                info = classify_error(RuntimeError(signal.message or signal.kind))

            err_kind = signal.kind or (info.kind.value if info else "none")
            err_msg = signal.message or (info.message if info else "")

            # F3: セッション失効・認証・プロキシ死骸は自己修復では回復不能。
            #     3回リトライせず1回で停止し、当該キー（垢）だけを遮断＋通知する。
            if is_fatal_signal(signal, self.cfg):
                # キー（垢）単位で即遮断（count をしきい値まで引き上げて blocked_until を立てる）。
                # final failure 側の _record_ceiling がさらに+1するが、遮断判定は count>=limit なので
                # 影響はない（遮断期間は fatal 発生時刻 + cooldown）。
                self._block(key, reason=f"fatal_signal:{err_kind}")
                self._record(HealingEvent(attempt=result.attempts, error_kind=err_kind, key=str(key),
                                          message=err_msg, action="stop_fatal",
                                          detail=f"non_retryable:{err_kind}",
                                          timestamp=datetime.now().isoformat()))
                result.error = err_msg
                stopped = "fatal"
                break

            if not signal.recoverable or attempt >= max_attempts - 1:
                if last_exc is None:
                    result.value = last_value
                    result.error = err_msg
                break

            action = self._choose(signal, plan, attempt, ai_used, ctx)
            if not action:
                # 回復プラン枯渇: 同じリトライを繰り返さず即停止（露出＝BOTシグナルを増やさない）
                self._record(HealingEvent(attempt=result.attempts, error_kind=err_kind, key=str(key),
                                          message=err_msg, action="stop_no_recovery",
                                          detail="recovery_plan_exhausted",
                                          timestamp=datetime.now().isoformat()))
                if last_exc is None:
                    result.value = last_value
                result.error = err_msg
                stopped = "plan_exhausted"
                break

            detail = self._execute(action, attempt)
            actions_run += 1
            self._record(HealingEvent(attempt=attempt + 1, error_kind=err_kind, key=str(key),
                                      message=err_msg, action=action, detail=detail,
                                      timestamp=datetime.now().isoformat()))
            if action == "ai_consult":
                ai_used = True
            if self._is_ceiling_hit(key):
                result.error = err_msg
                stopped = "ceiling"
                break
            continue

        if actions_run:
            # 計画は run 単位で段階的に消費する（次runは未実施の回復から始まる）
            self._cursor(key, advance=actions_run)

        # final failure
        result.ok = False
        result.error = str(last_exc) if last_exc else result.error
        self._record(HealingEvent(attempt=result.attempts,
                                  error_kind=(classify_error(last_exc).kind.value if last_exc else "none"),
                                  key=str(key),
                                  message=result.error, action="final",
                                  detail=stopped or "",
                                  timestamp=datetime.now().isoformat()))
        self._record_ceiling(key, True)
        if self.cfg.get("notify_on_error", True):
            try:
                from kensho.core.notifier import notify_error
                notify_error(
                    f"SelfHeal final failure: {self.pipeline}:{key}",
                    f"{result.error}\nattempts={result.attempts} events={len(self.events)}"
                    f" stopped={stopped or 'exhausted'}",
                    cfg=self.cfg,
                )
            except Exception:
                pass
        return result

    def _choose(self, signal: RecoverySignal, plan: list[str], attempt: int, ai_used: bool, ctx: dict[str, Any]) -> str:
        """この attempt で実行する回復アクションを選ぶ。空文字は「回復手段なし＝停止」を意味する。

        F4: 以前は毎回 jitter_retry → ai_consult を返すだけで、試行3回では
        transport_fallback / scope_reduction に構造的に到達しなかった。max_attempts を
        増やさずに到達可能にするため、プランは run をまたぐ永続カーソルで段階消費する
        （この run の attempt 番目 = seq[cursor + attempt]。プラン枯渇時は空文字＝即停止）。
        """
        allowlist = [a for a in (_csv_list(signal.allowlist) or plan) if a]
        seq = [a for a in plan if a in allowlist]
        if not seq:
            return ""
        key = str(ctx.get("key") or self.pipeline)
        pos = self._cursor(key) + attempt
        if pos >= len(seq):
            return ""
        action = seq[pos]
        if action == "ai_consult" and ai_used:
            return ""
        return action


    def _execute(self, action: str, attempt: int) -> str:
        if action == "ai_consult":
            log_tail = capture_error_log(self.cfg.get("project_dir", "."),
                                         int(self.cfg.get("log_tail_lines", 60)))
            action, reason = _ai_consult(self.cfg, self.pipeline, {}, "", log_tail)
            if action in ("none", ""):
                return f"ai_none:{reason[:80]}"
            detail = _builtin_action(action, self.cfg, {})
            return f"ai={action}:{detail}:{reason[:60]}"
        detail = _builtin_action(action, self.cfg, {})
        if detail in ("network_unhealthy",):
            _jitter_delay(float(self.cfg.get("max_delay_sec", DEFAULT_MAX_DELAY)),
                          float(self.cfg.get("max_delay_sec", DEFAULT_MAX_DELAY)) * 2)
        return detail
