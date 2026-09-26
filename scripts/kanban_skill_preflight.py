#!/usr/bin/env python3
"""
Preflight check: verify that when kanban.review_dispatch=true,
the forced skill 'sdlc-review' is resolvable for ALL profiles
that own the kanban board (kensho-worker, kensho-qa, kensho-critic,
kensho-revenue-worker, kensho-revenue-qa, kensho-sweeps).

Background (t_36410815): review_dispatch force-loads 'sdlc-review'
(hermes_cli/kanban_db_dispatch.py). When the skill was moved to
skills_disabled/ on 3 profiles, EVERY review run died at startup for
a month while loop_health stayed at score=100 (blind spot).

Modes:
- default: ask `hermes -p <profile> skills list --enabled-only` (authoritative,
  but slow — one CLI spawn per profile).
- --fast: filesystem-only check (profile skills/ tree + global builtin tree).
  Cheap enough to run inside loop_health.sh on every tick.

Profiles root can be overridden with KANBAN_PREFLIGHT_PROFILES_DIR (tests).

Exits:
- 0 with {"ok": true, ...} if all profiles can resolve sdlc-review
- 1 with {"ok": false, "offending_profiles": [...]} if any profile cannot
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Profiles that participate in the kanban review pipeline
BOARD_PROFILES = [
    "kensho-worker",
    "kensho-qa",
    "kensho-critic",
    "kensho-revenue-worker",
    "kensho-revenue-qa",
    "kensho-sweeps",
]

# The mandatory skill for review dispatch
MANDATORY_SKILL = "sdlc-review"


def _profiles_dir() -> Path:
    override = os.environ.get("KANBAN_PREFLIGHT_PROFILES_DIR")
    if override:
        return Path(override)
    return Path.home() / ".hermes" / "profiles"


def _global_skills_dirs() -> list[Path]:
    """Global/builtin skill roots that every profile inherits."""
    override = os.environ.get("KANBAN_PREFLIGHT_GLOBAL_SKILLS_DIR")
    if override:
        return [Path(override)]
    return [Path.home() / ".hermes" / "skills"]


def _find_skill_under(root: Path, skill: str) -> Path | None:
    """Find <root>/<category>/<skill>/SKILL.md or <root>/<skill>/SKILL.md."""
    direct = root / skill / "SKILL.md"
    if direct.exists():
        return direct
    if root.is_dir():
        for child in root.iterdir():
            cand = child / skill / "SKILL.md"
            if cand.exists():
                return cand
    return None


def check_profile_fast(profile: str, skill: str) -> tuple[bool, str]:
    """Filesystem-only resolvability check (no hermes CLI spawn)."""
    pdir = _profiles_dir() / profile
    if not pdir.exists():
        return False, f"profile dir missing: {pdir}"
    # disabled copy shadows nothing but explains the failure mode
    disabled = _find_skill_under(pdir / "skills_disabled", skill)
    enabled = _find_skill_under(pdir / "skills", skill)
    if enabled:
        return True, "enabled (profile skills/)"
    for gdir in _global_skills_dirs():
        if _find_skill_under(gdir, skill):
            if disabled:
                # profile explicitly disabled it — treat as unresolvable
                return False, "skill moved to skills_disabled/ (global copy shadowed)"
            return True, "enabled (global builtin)"
    if disabled:
        return False, "skill moved to skills_disabled/"
    return False, "skill not found in profile or global skills tree"


def check_profile_can_resolve_skill(profile: str, skill: str) -> tuple[bool, str]:
    """Check via hermes CLI if a profile can load a given skill.
    Returns (can_resolve, reason)."""
    try:
        result = subprocess.run(
            ["hermes", "-p", profile, "skills", "list", "--enabled-only"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False, f"hermes skills list failed: {result.stderr.strip()}"

        if skill in result.stdout:
            return True, "enabled"

        disabled_dir = (
            _profiles_dir() / profile / "skills_disabled" / "devops" / skill
        )
        if disabled_dir.exists():
            return False, "skill moved to skills_disabled/"

        return False, "skill not found in enabled list"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        # hermes CLI unavailable (e.g. minimal cron PATH) — fall back to fs check
        return check_profile_fast(profile, skill)
    except Exception as e:  # pragma: no cover
        return False, f"error: {e}"


def get_review_dispatch_config() -> bool:
    """Get kanban.review_dispatch from main config."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        return bool(cfg.get("kanban", {}).get("review_dispatch", True))
    except Exception:
        return True  # default is True


def run_check(fast: bool) -> dict:
    checker = check_profile_fast if fast else check_profile_can_resolve_skill
    offending = []
    for profile in BOARD_PROFILES:
        can_resolve, reason = checker(profile, MANDATORY_SKILL)
        if not can_resolve:
            offending.append({"profile": profile, "reason": reason})
    if offending:
        return {
            "ok": False,
            "review_dispatch": True,
            "mandatory_skill": MANDATORY_SKILL,
            "mode": "fast" if fast else "cli",
            "offending_profiles": offending,
        }
    return {
        "ok": True,
        "review_dispatch": True,
        "mandatory_skill": MANDATORY_SKILL,
        "mode": "fast" if fast else "cli",
        "checked_profiles": BOARD_PROFILES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Filesystem-only check (no hermes CLI spawn; safe for loop_health)",
    )
    args = parser.parse_args()

    if not get_review_dispatch_config():
        result = {
            "ok": True,
            "review_dispatch": False,
            "message": "review_dispatch disabled, preflight skipped",
        }
        if args.json:
            print(json.dumps(result))
        else:
            print("OK: review_dispatch disabled")
        return 0

    result = run_check(fast=args.fast)

    if args.json:
        print(json.dumps(result))
    elif result["ok"]:
        print(
            f"OK: all {len(BOARD_PROFILES)} profiles can resolve {MANDATORY_SKILL}"
        )
    else:
        offending = result["offending_profiles"]
        print(
            f"FAIL: {len(offending)} profiles cannot resolve {MANDATORY_SKILL}"
        )
        for o in offending:
            print(f"  {o['profile']}: {o['reason']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
