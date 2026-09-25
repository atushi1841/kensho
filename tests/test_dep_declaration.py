"""Test for dependency declaration of invisible_playwright in pyproject.toml.

This test ensures that:
1. kensho/application/browser.py imports InvisiblePlaywright from invisible_playwright.
2. pyproject.toml declares the dependency on invisible-playwright with the exact git commit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
BROWSER_PATH = ROOT / "kensho" / "application" / "browser.py"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def test_browser_imports_invisible_playwright():
    """kensho/application/browser.py must import InvisiblePlaywright from invisible_playwright."""
    content = BROWSER_PATH.read_text(encoding="utf-8")
    # Look for the import line (allowing for whitespace and comments)
    pattern = r"^\s*from\s+invisible_playwright\s+import\s+InvisiblePlaywright"
    assert re.search(pattern, content, re.MULTILINE), (
        "Expected to find 'from invisible_playwright import InvisiblePlaywright' in "
        f"{BROWSER_PATH}"
    )


def test_pyproject_declares_invisible_playwright_git():
    """pyproject.toml must declare invisible-playwright with the exact git commit."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    # We look for the line that starts with the package and contains the commit.
    # The line may have leading/trailing spaces and may be inside the dependencies list.
    # We'll check for the presence of the commit hash.
    commit_hash = "2184f6f3c296e5bedcf1539914b3a7d307ce9fe0"
    # Also check for the package name and the git URL pattern.
    assert "invisible-playwright" in content, "Package name not found in pyproject.toml"
    assert commit_hash in content, f"Commit hash {commit_hash} not found in pyproject.toml"
    # Additionally, check that it's a git dependency (optional but good)
    assert "git+https://github.com/feder-cr/invisible_playwright.git" in content, (
        "Expected git URL for invisible-playwright not found in pyproject.toml"
    )