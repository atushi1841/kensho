"""Regression tests for scripts/kanban_skill_preflight.py (t_36410815).

Covers success metric (b): when any board profile's sdlc-review is moved to
skills_disabled/, the preflight must exit 1 and list the offending profile.
Uses --fast (filesystem-only) mode with KANBAN_PREFLIGHT_PROFILES_DIR /
KANBAN_PREFLIGHT_GLOBAL_SKILLS_DIR overrides so no hermes CLI spawn or real
profile mutation is needed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "kanban_skill_preflight.py"

PROFILES = [
    "kensho-worker",
    "kensho-qa",
    "kensho-critic",
    "kensho-revenue-worker",
    "kensho-revenue-qa",
    "kensho-sweeps",
]


def _make_skill(root: Path, category: str = "devops", name: str = "sdlc-review"):
    d = root / category / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: sdlc-review\n---\n# stub\n")


@pytest.fixture()
def fake_tree(tmp_path):
    """Build a fake profiles dir + global skills dir with all skills enabled."""
    profiles = tmp_path / "profiles"
    for p in PROFILES:
        _make_skill(profiles / p / "skills")
    global_skills = tmp_path / "global_skills"
    _make_skill(global_skills)
    return profiles, global_skills


def _run(profiles: Path, global_skills: Path, *extra: str):
    env = dict(os.environ)
    env["KANBAN_PREFLIGHT_PROFILES_DIR"] = str(profiles)
    env["KANBAN_PREFLIGHT_GLOBAL_SKILLS_DIR"] = str(global_skills)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--fast", "--json", *extra],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_all_profiles_ok(fake_tree):
    profiles, global_skills = fake_tree
    r = _run(profiles, global_skills)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["checked_profiles"] == PROFILES


def test_disabled_skill_fails_and_names_profile(fake_tree):
    """Success metric (b): move one profile's sdlc-review to skills_disabled/."""
    profiles, global_skills = fake_tree
    victim = "kensho-qa"
    src = profiles / victim / "skills" / "devops" / "sdlc-review"
    dst = profiles / victim / "skills_disabled" / "devops" / "sdlc-review"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)

    r = _run(profiles, global_skills)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["ok"] is False
    names = [o["profile"] for o in data["offending_profiles"]]
    assert victim in names
    reasons = {o["profile"]: o["reason"] for o in data["offending_profiles"]}
    assert "skills_disabled" in reasons[victim]


def test_missing_skill_entirely_fails(fake_tree):
    profiles, global_skills = fake_tree
    victim = "kensho-critic"
    # remove profile copy AND global copy -> unresolvable
    import shutil

    shutil.rmtree(profiles / victim / "skills" / "devops" / "sdlc-review")
    shutil.rmtree(global_skills / "devops" / "sdlc-review")
    r = _run(profiles, global_skills)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["ok"] is False
    names = [o["profile"] for o in data["offending_profiles"]]
    assert victim in names


def test_global_builtin_satisfies_profile_without_local_copy(fake_tree):
    """A profile with no local copy still resolves via the global builtin tree."""
    profiles, global_skills = fake_tree
    import shutil

    shutil.rmtree(profiles / "kensho-sweeps" / "skills" / "devops" / "sdlc-review")
    r = _run(profiles, global_skills)
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
