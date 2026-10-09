#!/usr/bin/env python3
"""Add Smithery + Apify Store links to MCP READMEs.

Purpose: 10 MCP servers on Smithery namespace=atushi1841 all have useCount=0.
Adding Apify Store links + Smithery connection URLs to GitHub READMEs creates
discoverability paths through search engines and developer documentation.

Usage:
  python3 scripts/add_mcp_smithery_links.py --apply
  python3 scripts/add_mcp_smithery_links.py --dry-run
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path("/mnt/d/Project2/kensho")
MCP_DIR = PROJECT_DIR / "mcp"

# MCP name -> (Smithery qualified name, Apify actor ID, Apify actor name, description)
MCP_CONFIG = {
    "kensho-sweep-mcp": ("atushi1841/kensho-sweep-mcp", "kjf9ZKQ5zWyOQxzvL", "kensho-sweep-mcp", "Japan sweepstakes from knshow.com, kenshou.club, ken-kaku.com, cp.meikan.org"),
    "kensho-kaku": ("atushi1841/kensho-kaku", "kjf9ZKQ5zWyOQxzvL", "kensho-sweep-mcp", "Ken-kaku.com sweepstakes data"),
    "kensho-kclub": ("atushi1841/kensho-kclub", "kjf9ZKQ5zWyOQxzvL", "kensho-sweep-mcp", "Kenshou.club sweepstakes data"),
    "kensho-kema": ("atushi1841/kensho-kema", "kjf9ZKQ5zWyOQxzvL", "kensho-sweep-mcp", "Ke-ma.net sweepstakes data"),
    "tcg-price-japan": ("atushi1841/tcg-price-japan", "F8Hl0a8Cx9bpJBrxR", "surugaya-japan-hobby-prices", "TCG prices from suruga-ya.jp"),
    "japan-anime-figure-mcp": ("atushi1841/japan-anime-figure-mcp", "DKzufUSvmuXNKHeYx", "japan-anime-figure-price-data", "Anime figure prices from mandarake"),
    "japan-ec-apify-mcp": ("atushi1841/japan-ec-apify-mcp", "whSePszWpMtfeLYBp", "mercari-japan-search-scraper", "Mercari/Yahoo/Rakuten/SUU_MO/Kakaku via Apify"),
    "japan-ec-mcp": ("atushi1841/japan-ec-mcp", "whSePszWpMtfeLYBp", "mercari-japan-search-scraper", "Japanese E-Commerce search via FastMCP"),
    "japan-fuel-price-mcp": ("atushi1841/japan-fuel-price-mcp", "57SNehd4cHNFyUCj3", "japan-market-mcp", "Japan fuel prices from METI"),
    "japan-market-mcp": ("atushi1841/japan-market-mcp", "57SNehd4cHNFyUCj3", "japan-market-mcp", "Cross-shop price comparison for Japanese second-hand market"),
}

SMITHERY_NS = "atushi1841"


def get_readme_path(mcp_name: str) -> Path | None:
    """Find README.md for an MCP."""
    # Check local directory first
    local = MCP_DIR / mcp_name / "README.md"
    if local.exists():
        return local
    # Check git-tracked
    result = subprocess.run(
        ["git", "show", f"HEAD:mcp/{mcp_name}/README.md"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    if result.returncode == 0:
        return local  # Return local path for editing
    return None


def get_current_readme(mcp_name: str) -> str | None:
    """Get current README content (local or git)."""
    local = MCP_DIR / mcp_name / "README.md"
    if local.exists():
        return local.read_text(encoding="utf-8")
    result = subprocess.run(
        ["git", "show", f"HEAD:mcp/{mcp_name}/README.md"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    if result.returncode == 0:
        return result.stdout
    return None


def needs_update(mcp_name: str) -> bool:
    """Check if README needs Smithery/Apify links added."""
    content = get_current_readme(mcp_name)
    if not content:
        return False  # No README to update
    has_smithery = "smithery.ai" in content.lower()
    # Check for proper Apify Store links (not just apify.com/username)
    apify_store_links = re.findall(r'https://apify\.com/\w+/acts/\w+', content)
    has_apify_store = len(apify_store_links) > 0
    return not has_smithery or not has_apify_store


def generate_smithery_section(mcp_name: str) -> str:
    """Generate Smithery + Apify Store section for README."""
    config = MCP_CONFIG.get(mcp_name)
    if not config:
        return ""
    _, smithery_name, actor_id, actor_name = config
    desc = actor_name  # Use actor name as fallback description
    connection_url = f"https://server.smithery.ai/{smithery_name}"
    apify_url = f"https://apify.com/fruitful_quintessence/acts/{actor_id}"

    section = f"""
## Data Source: Apify Store & Smithery Registry

This MCP server is available on:

- **Apify Store**: [{actor_name}]({apify_url}) — {desc}
- **Smithery Registry**: [Install via Smithery]({connection_url}) — MCP server for AI agents

Install via Smithery:
```bash
npx @smithery/cli install {smithery_name} --client claude
```
"""
    return section


def update_readme(mcp_name: str, dry_run: bool = False) -> tuple[bool, str]:
    """Update README with Smithery + Apify links. Returns (success, message)."""
    config = MCP_CONFIG.get(mcp_name)
    if not config:
        return False, f"No config for {mcp_name}"

    content = get_current_readme(mcp_name)
    if not content:
        return False, f"No README found for {mcp_name}"

    # Check if already has Smithery links
    if "smithery.ai" in content.lower():
        return True, f"Already has Smithery links"

    # Generate new section
    new_section = generate_smithery_section(mcp_name)

    # Append to end of README
    if content.rstrip().endswith("```"):
        # If ends with code block, add newline first
        new_content = content.rstrip() + "\n" + new_section
    else:
        new_content = content.rstrip() + "\n" + new_section

    if dry_run:
        print(f"  [DRY-RUN] Would update: mcp/{mcp_name}/README.md")
        print(f"  Added section length: {len(new_section)} chars")
        return True, "dry-run-ok"

    # Write to local file
    local_path = MCP_DIR / mcp_name / "README.md"
    local_path.write_text(new_content, encoding="utf-8")
    print(f"  Updated: mcp/{mcp_name}/README.md")
    return True, "updated"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually update files")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview changes")
    parser.add_argument("--mcp", help="Update specific MCP only")
    args = parser.parse_args()

    mcps = [args.mcp] if args.mcp else list(MCP_CONFIG.keys())
    results = []

    for mcp in mcps:
        success, msg = update_readme(mcp, dry_run=not args.apply)
        results.append((mcp, success, msg))
        status = "OK" if success else "FAIL"
        print(f"[{status}] {mcp}: {msg}")

    # Summary
    updated = sum(1 for _, s, _ in results if s)
    print(f"\nSummary: {updated}/{len(results)} MCPs updated")

    if args.apply and updated > 0:
        print("\nTo commit changes:")
        print(f"  cd {PROJECT_DIR}")
        print("  git add mcp/*/README.md")
        print("  git commit -m 'Add Smithery + Apify Store links to MCP READMEs'")
        print("  git push")

    return 0 if updated == len(mcps) else 1


if __name__ == "__main__":
    sys.exit(main())
