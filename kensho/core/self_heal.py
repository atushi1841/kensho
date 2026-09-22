"""Self-healing loop for Kensho collect / apply pipelines.

Implements the Loop Engineering 4-layer pattern:
  Layer 1 — Verifier:      custom validator or exception classifier
  Layer 2 — Failure Ceiling: consecutive failures + cooldown
  Layer 3 — Health Check:   network + crash-history check before retry
  Layer 4 — PolicyEngine:   default recoveries, AI advisor (opt-in), guardrails

Default recovery order (name based):
  jitter_retry → network_check → ai_consult → transport_fallback → scope_reduction

The AI advisor calls OpenRouter-compatible endpoint directly and never
modifies files; it only returns an action recommendation.
"""
from __future__ import annotations

import json
import os
import random
import re
import traceback
import time
from dataclasses import dataclass, field
from datetime import datetime
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
    }


def _merge_config(cfg: dict[str, Any] | None, project_dir: str | Path) -> dict[str, Any]:
    merged = _default_config(project_dir)
    if cfg:
        user = cfg.get("self_healing", {}) or {}
        merged.update(user)
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
        self.cfg = _merge_config(cfg, project_dir)
        self.pipeline = pipeline
        self.logger = logger
        self.context = dict(context or {})
        self.state_path = Path(self.cfg["state_file"])
        self.config = self.cfg
        self.events: list[HealingEvent] = []
        self._ceiling_hits: dict[str, float] = {}

    # ── failure ceiling ─────────────────────────────────────
    def _is_ceiling_hit(self, key: str) -> bool:
        limit = int(self.cfg.get("failure_ceiling_consecutive", 3))
        cooldown_min = float(self.cfg.get("failure_ceiling_cooldown_minutes", 30))
        info = _load_state(self.state_path).get("ceilings", {}).get(key, {})
        if info.get("count", 0) < limit:
            return False
        then = datetime.fromisoformat(info.get("first_fail_time", ""))
        if (datetime.now() - then).total_seconds() < cooldown_min * 60:
            return True
        return False

    def _record_ceiling(self, key: str, hit: bool) -> None:
        st = _load_state(self.state_path)
        ceilings = st.setdefault("ceilings", {})
        now = datetime.now().isoformat()
        if hit:
            entry = ceilings.setdefault(key, {"count": 0, "first_fail_time": now})
            entry["count"] = entry.get("count", 0) + 1
            entry["first_fail_time"] = entry.get("first_fail_time", now)
        elif key in ceilings:
            ceilings[key]["count"] = 0
        st["updated"] = now
        _save_state(self.state_path, st)

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
            result.events.append(HealingEvent(attempt=0, error_kind="ceiling",
                                              message="failure ceiling blocked",
                                              action="blocked", timestamp=datetime.now().isoformat()))
            return result

        order = recoveries or [
            "jitter_retry",
            "network_check",
            "ai_consult",
            "transport_fallback",
            "scope_reduction",
        ]
        last_exc: BaseException | None = None
        last_value: Any = None
        ai_used = False
        signal: RecoverySignal | None = None

        for attempt in range(int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS))):
            result.attempts = attempt + 1
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
                if not signal.recoverable or attempt >= int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS)) - 1:
                    break
                action = self._choose(signal, order, attempt, ai_used, ctx)
                detail = self._execute(action, attempt)
                self.events.append(HealingEvent(attempt=attempt + 1, error_kind=info.kind.value,
                                                message=info.message, action=action, detail=detail,
                                                timestamp=datetime.now().isoformat()))
                if action == "ai_consult":
                    ai_used = True
                if self._is_ceiling_hit(key):
                    result.error = info.message
                    break
                continue
            else:
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
                if not signal.recoverable or attempt >= int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS)) - 1:
                    result.value = last_value
                    result.error = signal.message
                    break
                action = self._choose(signal, order, attempt, ai_used, ctx)
                detail = self._execute(action, attempt)
                self.events.append(HealingEvent(attempt=attempt + 1, error_kind=signal.kind,
                                                message=signal.message, action=action, detail=detail,
                                                timestamp=datetime.now().isoformat()))
                if action == "ai_consult":
                    ai_used = True
                continue

        # final failure
        result.ok = False
        result.error = str(last_exc) if last_exc else result.error
        result.events.append(HealingEvent(attempt=result.attempts, error_kind=(classify_error(last_exc).kind.value if last_exc else "none"),
                                          message=result.error, action="final", detail="",
                                          timestamp=datetime.now().isoformat()))
        self._record_ceiling(key, True)
        if self.cfg.get("notify_on_error", True):
            try:
                from kensho.core.notifier import notify_error
                notify_error(
                    f"SelfHeal final failure: {self.pipeline}",
                    f"{result.error}\nattempts={result.attempts} events={len(self.events)}",
                    cfg=self.cfg,
                )
            except Exception:
                pass
        return result

    def _choose(self, signal: RecoverySignal, order: list[str], attempt: int, ai_used: bool, ctx: dict[str, Any]) -> str:
        allowlist = list(signal.allowlist) or list(order)
        if attempt == 0 and "jitter_retry" in allowlist:
            return "jitter_retry"
        if not ai_used and "ai_consult" in allowlist and attempt >= 1:
            return "ai_consult"
        for name in order:
            if name in allowlist and name not in ("jitter_retry", "ai_consult"):
                return name
        return "jitter_retry"

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
