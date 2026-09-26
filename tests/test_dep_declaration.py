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


def test_pyproject_declares_invisible_playwright_pypi():
    """pyproject.toml must declare invisible-playwright with the PyPI pin (0.25.7)."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    # Check for the package name and the PyPI version pin.
    assert "invisible-playwright==0.25.7" in content, (
        "Expected 'invisible-playwright==0.25.7' in pyproject.toml"
    )
    # Also verify playwright version is declared and compatible
    assert "playwright==1.61.0" in content, (
        "Expected 'playwright==1.61.0' in pyproject.toml"
    )