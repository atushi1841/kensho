#!/usr/bin/env python3
"""
Scan for uncommitted code and attempt to identify owning kanban cards.

Usage:
  python3 scripts/wip_orphan_scan.py [--dry-run] [--json]

Options:
  --dry-run      Only output, do not comment on cards or send warnings
  --json         Output in JSON format with owned/unowned counts

Behavior:
1. Enumerate uncommitted code files from git status --porcelain
2. Search through task_events and task_comments to estimate ownership
3. If owner is blocked/triage, comment with ownership info
4. If no owner, send Telegram warning (only if not dry-run)
5. Always output which files are owned/unowned
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Try to import kanban tools
try:
    from hermes_tools import kanban_show, kanban_comment
    HAS_KANBAN = True
except ImportError:
    HAS_KANBAN = False

# Try to import Telegram notifier
try:
    from telegram_notifier import send_warning
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


def get_uncommitted_code_files(repo_path: str) -> List[str]:
    """Get list of uncommitted code files from git status --porcelain"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git status: {e}", file=sys.stderr)
        return []
    
    # Files that matter for code review
    code_patterns = [
        r'\.py$', r'\.sh$', r'\.js$', r'\.toml$', r'\.yaml$', r'\.yml$',
        r'\.json$', r'\.cfg$', r'\.ini$', r'\.md$'
    ]
    
    files = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        
        # Extract filename (ignore status prefix)
        parts = line.split()
        if len(parts) < 2:
            continue
            
        status = parts[0]
        filename = parts[1]
        
        # Check if it's a code file
        if any(re.search(pattern, filename, re.IGNORECASE) for pattern in code_patterns):
            files.append(filename)
    
    return files


def find_owning_card_for_file(filename: str, kanban_db_path: str) -> Tuple[str, str]:
    """
    Search through kanban tasks and comments to find which card owns a file.
    
    Returns:
        Tuple of (card_id, card_title) or (None, None) if not found
    """
    try:
        # Try to find the card in the kanban board
        # This is a simplified approach - in reality we'd need to search through
        # the database or use the kanban API to find all tasks
        
        # For now, use a simple heuristic: look for task IDs in the filename
        # or search for patterns in recent commits/comments
        card_pattern = r't_[a-zA-Z0-9]{8}'
        
        # Try to find the file in recent commits
        try:
            result = subprocess.run(
                ["git", "log", "-20", "--oneline", "--all"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.split('\n'):
                if filename in line:
                    # Extract task ID from commit message
                    match = re.search(card_pattern, line)
                    if match:
                        card_id = match.group(0)
                        
                        # Try to get card title
                        try:
                            card_result = subprocess.run(
                                ["hermes", "kanban", "show", card_id],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            
                            # Parse card info (simplified)
                            title_match = re.search(r'title:\s*([^\n]+)', card_result.stdout)
                            if title_match:
                                card_title = title_match.group(1).strip()
                                return card_id, card_title
                        except:
                            pass
        except:
            pass
            
    except Exception as e:
        print(f"Error finding owning card for {filename}: {e}", file=sys.stderr)
    
    return None, None


def get_card_status(card_id: str) -> str:
    """Get the status of a kanban card"""
    try:
        # This would require actual kanban API integration
        # For now, return 'unknown'
        return 'unknown'
    except:
        return 'unknown'


def comment_on_card(card_id: str, filename: str, ownership_info: str, dry_run: bool):
    """Comment on a kanban card about file ownership"""
    if dry_run:
        print(f"[DRY RUN] Would comment on card {card_id}: {ownership_info}")
        return
    
    if not HAS_KANBAN:
        print(f"[SKIP] kanban tools not available, cannot comment on card {card_id}")
        return
    
    try:
        comment_body = f"""**Orphan File Detected**
File: `{filename}`
Owner identified: {ownership_info}
Please review and commit or transfer ownership as needed.
---
*Automated scan from wip_orphan_scan.py*"""
        kanban_comment(task_id=card_id, body=comment_body)
        print(f"Commented on card {card_id} for file {filename}")
        
    except Exception as e:
        print(f"Error commenting on card {card_id}: {e}", file=sys.stderr)


def send_telegram_warning(filename: str, owner_unknown: bool, dry_run: bool):
    """Send warning to Telegram about unowned code"""
    if dry_run:
        print(f"[DRY RUN] Would send Telegram warning for unowned file: {filename}")
        return
    
    if not HAS_TELEGRAM:
        print(f"[SKIP] Telegram notifier not available, cannot send warning for {filename}")
        return
    
    try:
        message = (
            f"🔍 **Orphan Code Alert**\n\n"
            f"File: `{filename}`\n"
            f"Status: {'No owner identified' if owner_unknown else 'Uncommitted'}\n\n"
            f"This file is in the working tree but no kanban card ownership found.\n\n"
            f"Please review and either:\n"
            f"1. Commit changes to existing card\n"
            f"2. Create a new card for this work\n"
            f"3. Transfer ownership from another card"
        )
        
        send_warning(message)
        print(f"Sent Telegram warning for unowned file: {filename}")
        
    except Exception as e:
        print(f"Error sending Telegram warning: {e}", file=sys.stderr)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan for uncommitted code and identify owning kanban cards")
    parser.add_argument('--dry-run', action='store_true', help='Only output, do not comment or send warnings')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    args = parser.parse_args()
    
    repo_path = "/mnt/d/Project2/kensho"
    
    # Get uncommitted code files
    uncommitted_files = get_uncommitted_code_files(repo_path)
    
    if args.json:
        # JSON output format
        owned_files = []
        unowned_files = []
        
        for filename in uncommitted_files:
            card_id, card_title = find_owning_card_for_file(filename, repo_path)
            if card_id and card_title:
                card_status = get_card_status(card_id)
                owned_files.append({
                    "filename": filename,
                    "card_id": card_id,
                    "card_title": card_title,
                    "card_status": card_status
                })
            else:
                unowned_files.append(filename)
        
        result = {
            "owned": len(owned_files),
            "unowned": len(unowned_files),
            "owned_files": owned_files,
            "unowned_files": unowned_files,
            "dry_run": args.dry_run
        }
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    # Standard output
    print(f"Found {len(uncommitted_files)} uncommitted code files")
    print("=" * 60)
    
    owned_count = 0
    unowned_count = 0
    
    for filename in uncommitted_files:
        card_id, card_title = find_owning_card_for_file(filename, repo_path)
        
        if card_id and card_title:
            print(f"✓ {filename}")
            print(f"  Owner: {card_title} ({card_id})")
            
            # Check if card is blocked/triage
            card_status = get_card_status(card_id)
            if card_status in ['blocked', 'triage']:
                print(f"  Status: {card_status} - COMMENTING")
                comment_info = f"Owner: {card_title}, Status: {card_status}"
                comment_on_card(card_id, filename, comment_info, args.dry_run)
            
            owned_count += 1
        else:
            print(f"✗ {filename}")
            print(f"  Owner: UNKNOWN (no kanban card found)")
            unowned_count += 1
            
            # Send warning for unowned files
            if not args.dry_run:
                send_telegram_warning(filename, True, args.dry_run)
    
    print("=" * 60)
    print(f"Summary: {owned_count} owned, {unowned_count} unowned")
    
    if args.dry_run:
        print("[DRY RUN] No actions were taken")


if __name__ == "__main__":
    main()