"""
Kensho Session Manager — セッションファイルの管理・監視
v3.4: keyring対応（Credential Manager優先、ファイルフォールバック）
v3.5: Proactive session refresh & recovery (anti-freeze enhancement)
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from kensho.utils.keyring import load_session

# ============================================================================
# Session Management Configuration
# ============================================================================

# Session age thresholds (in days)
SESSION_THRESHOLDS = {
    "refresh_warning": 7,  # Start warning 7 days before expiry
    "refresh_recommended": 10,  # Recommend refresh 10 days before expiry
    "refresh_required": 14,  # Force refresh at 14 days
    "backup_age_days": 30,  # Keep backups for 30 days
}

# Track session refresh history
_SESSION_REFRESH_HISTORY: dict[str, list[dict[str, Any]]] = {}

# Session backup directory (relative to project dir)
SESSION_BACKUP_DIR = "data/session_backups"


def _get_session_age_days(session_path: Path) -> float:
    """Get the age of a session file in days."""
    if not session_path.exists():
        return -1
    mtime = os.path.getmtime(session_path)
    return (time.time() - mtime) / 86400


def _create_session_backup(session_path: Path, account_key: str) -> Path | None:
    """Create a backup of the session file before refresh.

    Returns the backup path or None if backup failed.
    """
    try:
        backup_dir = Path(SESSION_BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{account_key}_session_{timestamp}.json"
        backup_path = backup_dir / backup_name

        shutil.copy2(session_path, backup_path)

        # Clean old backups (older than SESSION_THRESHOLDS['backup_age_days'])
        cutoff = time.time() - (SESSION_THRESHOLDS["backup_age_days"] * 86400)
        for old_backup in backup_dir.glob(f"{account_key}_session_*.json"):
            if old_backup.stat().st_mtime < cutoff:
                old_backup.unlink()

        return backup_path
    except Exception as e:
        logging.getLogger(__name__).warning(f"Session backup failed for {account_key}: {e}")
        return None


def _validate_session_cookies(session_path: Path, account_key: str) -> dict[str, Any]:
    """Validate session cookies and return validation results.

    Returns dict with:
    - valid: bool - whether session is valid
    - age_days: float - age of session in days
    - missing_cookies: list[str] - cookies that are missing
    - expired_cookies: list[str] - cookies that are expired
    - needs_refresh: bool - whether session needs refresh
    - refresh_reason: str - reason for refresh recommendation
    """
    result = {
        "valid": False,
        "age_days": -1,
        "missing_cookies": [],
        "expired_cookies": [],
        "needs_refresh": False,
        "refresh_reason": "",
    }

    if not session_path.exists():
        result["missing_cookies"] = ["auth_token", "ct0"]
        result["needs_refresh"] = True
        result["refresh_reason"] = "Session file missing"
        return result

    # Check session age
    age_days = _get_session_age_days(session_path)
    result["age_days"] = age_days

    # Load session data
    try:
        from kensho.application.browser import _session_has_auth_cookies

        # Check for required cookies
        has_auth = _session_has_auth_cookies(account_key)
        if not has_auth:
            result["missing_cookies"] = ["auth_token", "ct0"]
            result["needs_refresh"] = True
            result["refresh_reason"] = "Missing auth cookies"
            return result

        # Check age thresholds
        if age_days > SESSION_THRESHOLDS["refresh_required"]:
            result["needs_refresh"] = True
            result["refresh_reason"] = f"Session too old ({age_days:.0f} days)"
        elif age_days > SESSION_THRESHOLDS["refresh_recommended"]:
            result["needs_refresh"] = True
            result["refresh_reason"] = f"Session aging ({age_days:.0f} days, recommend refresh)"

        result["valid"] = not result["needs_refresh"]

    except Exception as e:
        result["valid"] = False
        result["needs_refresh"] = True
        result["refresh_reason"] = f"Validation error: {str(e)}"

    return result


def proactive_session_refresh(
    account_key: str,
    config: dict[str, Any],
    log: Any = None,
) -> dict[str, Any]:
    """Proactively refresh a session before it expires.

    This function:
    1. Checks session age and validity
    2. Creates a backup before refresh
    3. Refreshes the session if needed
    4. Records refresh history

    Parameters
    ----------
    account_key : str
        Account key to refresh session for.
    config : dict
        Global configuration.
    log : optional logger

    Returns
    -------
    dict
        Refresh result with 'refreshed', 'reason', 'backup_path'.
    """
    if log is None:
        log = logging.getLogger(__name__)

    result = {
        "refreshed": False,
        "reason": "",
        "backup_path": None,
        "session_age_days": -1,
    }

    # Find account config
    acct = None
    for a in config.get("accounts", []):
        if a.get("key") == account_key:
            acct = a
            break

    if not acct:
        result["reason"] = f"Account {account_key} not found"
        return result

    # Get session path
    project_dir = Path(config["general"]["project_dir"])
    session_rel = acct.get("session", "")
    session_path = project_dir / session_rel

    if not session_path.exists():
        result["reason"] = "Session file missing"
        return result

    # Validate session
    validation = _validate_session_cookies(session_path, account_key)
    result["session_age_days"] = validation["age_days"]

    if not validation["needs_refresh"]:
        result["reason"] = "Session valid, no refresh needed"
        return result

    # Create backup before refresh
    backup_path = _create_session_backup(session_path, account_key)
    result["backup_path"] = str(backup_path) if backup_path else None

    log.info(f"Proactive session refresh for {account_key}: {validation['refresh_reason']}")

    # Record refresh attempt
    _SESSION_REFRESH_HISTORY.setdefault(account_key, []).append({
        "timestamp": time.time(),
        "reason": validation["refresh_reason"],
        "age_days": validation["age_days"],
        "backup_path": str(backup_path) if backup_path else None,
    })

    # Mark for refresh (actual refresh happens in applier.py)
    result["refreshed"] = True
    result["reason"] = validation["refresh_reason"]

    return result


def get_session_health_report(config: dict[str, Any], log: Any = None) -> dict[str, Any]:
    """Generate a comprehensive session health report.

    Parameters
    ----------
    config : dict
        Global configuration.
    log : optional logger

    Returns
    -------
    dict
        Session health report with account statuses and refresh recommendations.
    """
    if log is None:
        log = logging.getLogger(__name__)

    report = {
        "timestamp": datetime.now().isoformat(),
        "accounts": {},
        "summary": {"healthy": 0, "warning": 0, "stale": 0, "missing": 0},
        "refresh_recommendations": [],
    }

    for acct in config.get("accounts", []):
        account_key = acct.get("key")
        session_rel = acct.get("session", "")

        if not session_rel:
            report["accounts"][account_key] = {"status": "missing_config"}
            report["summary"]["missing"] += 1
            continue

        project_dir = Path(config["general"]["project_dir"])
        session_path = project_dir / session_rel

        if not session_path.exists():
            report["accounts"][account_key] = {
                "status": "missing",
                "age_days": -1,
            }
            report["summary"]["missing"] += 1
            report["refresh_recommendations"].append({
                "account": account_key,
                "action": "recreate_session",
                "reason": "Session file missing",
            })
            continue

        # Validate session
        validation = _validate_session_cookies(session_path, account_key)
        age_days = validation["age_days"]

        if validation["valid"]:
            status = "healthy"
            report["summary"]["healthy"] += 1
        elif age_days > SESSION_THRESHOLDS["refresh_required"]:
            status = "stale"
            report["summary"]["stale"] += 1
        else:
            status = "warning"
            report["summary"]["warning"] += 1

        report["accounts"][account_key] = {
            "status": status,
            "age_days": round(age_days, 1) if age_days >= 0 else -1,
            "missing_cookies": validation["missing_cookies"],
            "needs_refresh": validation["needs_refresh"],
            "refresh_reason": validation["refresh_reason"],
        }

        if validation["needs_refresh"]:
            report["refresh_recommendations"].append({
                "account": account_key,
                "action": "refresh_session",
                "reason": validation["refresh_reason"],
                "age_days": round(age_days, 1) if age_days >= 0 else -1,
            })

    return report


def recover_session(
    account_key: str,
    config: dict[str, Any],
    log: Any = None,
) -> dict[str, Any]:
    """Attempt to recover a failed session from backup.

    Parameters
    ----------
    account_key : str
        Account key to recover session for.
    config : dict
        Global configuration.
    log : optional logger

    Returns
    -------
    dict
        Recovery result with 'recovered', 'backup_path', 'message'.
    """
    if log is None:
        log = logging.getLogger(__name__)

    result = {
        "recovered": False,
        "backup_path": None,
        "message": "",
    }

    # Find backup files for this account
    backup_dir = Path(SESSION_BACKUP_DIR)
    if not backup_dir.exists():
        result["message"] = "No backup directory found"
        return result

    backups = sorted(backup_dir.glob(f"{account_key}_session_*.json"), reverse=True)
    if not backups:
        result["message"] = "No backups found"
        return result

    # Find the most recent backup that's not too old
    for backup_path in backups:
        age_hours = (time.time() - backup_path.stat().st_mtime) / 3600

        # Try backups within last 7 days
        if age_hours < 168:
            # Find account config
            acct = None
            for a in config.get("accounts", []):
                if a.get("key") == account_key:
                    acct = a
                    break

            if acct:
                project_dir = Path(config["general"]["project_dir"])
                session_rel = acct.get("session", "")
                session_path = project_dir / session_rel

                try:
                    # Restore from backup
                    shutil.copy2(backup_path, session_path)
                    result["recovered"] = True
                    result["backup_path"] = str(backup_path)
                    result["message"] = f"Recovered from backup ({age_hours:.0f} hours old)"
                    log.info(f"Session recovery successful for {account_key}")
                    return result
                except Exception as e:
                    result["message"] = f"Backup restore failed: {str(e)}"
                    continue

    result["message"] = "No suitable backup found"
    return result


def get_session_data(account_key: str) -> dict[str, Any] | None:
    """
    アカウントのセッションデータを取得。
    優先順位: Credential Manager → 従来のセッションファイル
    """
    return load_session(account_key)


def check_sessions(cfg: dict[str, Any], log: Any = None) -> list[tuple[str, str, float]]:
    """
    全アカウントのセッションファイルの最終更新日時を確認。
    閾値を超えているものがあれば警告をログに記録。

    戻り値: list of (account_key, display_name, days_since_update)
    """
    project_dir = Path(cfg["general"]["project_dir"])
    warn_days = cfg["general"].get("session_warn_days", 3)
    warnings: list[tuple[str, str, float]] = []

    now = time.time()

    for acct in cfg.get("accounts", []):
        key = acct["key"]
        display = acct.get("display", key)
        session_rel = acct["session"]
        session_path = project_dir / session_rel

        if not session_path.exists():
            warnings.append((key, display, -1))  # -1 = ファイルなし
            if log:
                log.write(f"[!] Session: {display} セッションファイルなし: {session_rel}")
            continue

        mtime = os.path.getmtime(session_path)
        days = (now - mtime) / 86400

        # アカウント別の閾値（あれば）
        acct_warn = acct.get("session_max_age_days", warn_days)

        if days > acct_warn:
            warnings.append((key, display, round(days, 1)))
            if log:
                log.write(f"[!] Session: {display} のセッションが {days:.0f}日間未更新（閾値: {acct_warn}日）")
        else:
            if log:
                log.write(f"[OK] Session: {display} OK（最終更新: {days:.0f}日前）")

    return warnings
