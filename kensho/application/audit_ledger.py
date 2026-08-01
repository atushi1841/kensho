"""AuditLedger — SHA256チェーン監査ログ（JSONL形式）"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from collections import defaultdict
from typing import Any

_AUDIT_DIR = pathlib.Path(__file__).parent.parent.parent / "data"
_AUDIT_FILE = _AUDIT_DIR / "audit.jsonl"


def _ensure_dir() -> None:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _get_last_entry() -> dict[str, Any] | None:
    _ensure_dir()
    if not _AUDIT_FILE.exists():
        return None
    with _AUDIT_FILE.open("rb") as f:
        try:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        last_line = b""
        for line in f:
            last_line = line
    if not last_line:
        return None
    try:
        return json.loads(last_line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _compute_hash(prev_hash: str, data: dict[str, Any]) -> str:
    """prev_hash + 全フィールド（hashは除外）のSHA256"""
    d = {k: v for k, v in data.items() if k != "hash"}
    d_json = json.dumps(d, sort_keys=True, ensure_ascii=False)
    raw = prev_hash + d_json
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuditLedger:
    def log(
        self,
        account: str,
        action_type: str,
        target: str,
        decision: str,
        status: str,
        reason: str = "",
        error: str = "",
        delay_ms: int = 0,
    ) -> dict[str, Any]:
        _ensure_dir()
        prev = _get_last_entry()
        prev_hash = prev["hash"] if prev else "0" * 64
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        entry: dict[str, Any] = {
            "timestamp": now_ts,
            "account": account,
            "action_type": action_type,
            "target": target,
            "decision": decision,  # "allow" or "deny"
            "status": status,  # "success","failed","skipped"
            "reason": reason,
            "error": error,
            "delay_ms": delay_ms,
            "prev_hash": prev_hash,
        }
        entry_hash = _compute_hash(prev_hash, entry)
        entry["hash"] = entry_hash

        with _AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def get_recent(self, n: int = 20) -> list[dict[str, Any]]:
        _ensure_dir()
        if not _AUDIT_FILE.exists():
            return []
        with _AUDIT_FILE.open("r", encoding="utf-8") as f:
            all_lines = f.readlines()
        recent = [json.loads(line) for line in all_lines[-n:] if line.strip()]
        return recent

    def get_account_summary(self, account: str, date_str: str | None = None) -> dict[str, Any]:
        _ensure_dir()
        if not _AUDIT_FILE.exists():
            return {}
        today = date_str or time.strftime("%Y-%m-%d")
        result: dict[str, Any] = {
            "account": account,
            "date": today,
            "total": 0,
            "allowed": 0,
            "denied": 0,
            "success": 0,
            "failed": 0,
            "by_action": defaultdict(lambda: {"total": 0, "success": 0}),
        }
        with _AUDIT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("account") != account:
                    continue
                entry_date = entry.get("timestamp", "")[:10]
                if entry_date != today:
                    continue
                result["total"] += 1
                action = entry.get("action_type", "?")
                result["by_action"][action]["total"] += 1
                if entry.get("decision") == "allow":
                    result["allowed"] += 1
                else:
                    result["denied"] += 1
                if entry.get("status") == "success":
                    result["success"] += 1
                    result["by_action"][action]["success"] += 1
                elif entry.get("status") == "failed":
                    result["failed"] += 1
        # convert defaultdict to plain dict
        result["by_action"] = dict(result["by_action"])
        return result

    def get_daily_report(self) -> str:
        _ensure_dir()
        if not _AUDIT_FILE.exists():
            return "No audit data today."
        today = time.strftime("%Y-%m-%d")
        accounts: dict[str, dict[str, int]] = {}
        lines_text: list[str] = []
        with _AUDIT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("timestamp", "")[:10] != today:
                    continue
                acc = entry.get("account", "?")
                action = entry.get("action_type", "?")
                dec = entry.get("decision", "?")
                status = entry.get("status", "?")
                if acc not in accounts:
                    accounts[acc] = {}
                key = f"{action}:{dec}:{status}"
                accounts[acc][key] = accounts[acc].get(key, 0) + 1
        for acc, counters in sorted(accounts.items()):
            parts = [f"{acc}:"]
            for k, v in counters.items():
                parts.append(f" {k}={v}")
            lines_text.append("".join(parts))
        return "\n".join(lines_text)


audit_ledger = AuditLedger()
