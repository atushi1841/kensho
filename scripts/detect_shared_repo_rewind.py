#!/usr/bin/env python3
"""
detect_shared_repo_rewind.py

Detect shared repo rewinds (git reset --hard HEAD~1) in reflog.
Exit 1 if 1+ rewinds found in time range, exit 0 otherwise.

Usage:
    python3 scripts/detect_shared_repo_rewind.py --since '2026-09-25 06:40' --until '2026-09-25 07:10'
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone


def run_git(*args, check=True):
    """Run git command and return stdout as string."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Git command failed: {' '.join(e.cmd)}", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
            sys.exit(1)
        else:
            return None


def parse_iso_datetime(s: str) -> datetime:
    """Parse datetime string with possible missing seconds and timezone.
    Try formats:
    - '%Y-%m-%d %H:%M:%S %z'
    - '%Y-%m-%d %H:%M:%S'
    - '%Y-%m-%d %H:%M'
    If no timezone, assume local system timezone.
    """
    formats = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            # If format doesn't include timezone, attach local timezone
            if fmt == "%Y-%m-%d %H:%M:%S" or fmt == "%Y-%m-%d %H:%M":
                # Get local timezone offset
                local_offset = datetime.now().astimezone().utcoffset()
                if local_offset is not None:
                    dt = dt.replace(tzinfo=timezone(local_offset))
                else:
                    dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"time data {s!r} does not match any expected format")


def is_within_range(commit_dt: datetime, since: datetime, until: datetime) -> bool:
    """Check if commit_dt is within [since, until] inclusive."""
    return since <= commit_dt <= until


def main():
    parser = argparse.ArgumentParser(description="Detect shared repo rewinds.")
    parser.add_argument("--since", required=True, help="Start time (ISO format)")
    parser.add_argument("--until", required=True, help="End time (ISO format)")
    args = parser.parse_args()

    # Parse since/until
    since_dt = parse_iso_datetime(args.since)
    until_dt = parse_iso_datetime(args.until)

    # Get reflog entries
    reflog_output = run_git("reflog", "--date=iso")
    rewinds = 0

    for line in reflog_output.splitlines():
        # Example reflog line:
        # 4842d94 HEAD@{2026-09-25 22:30:19 +0900}: commit: tcg-price-collect: append dataset snapshot
        parts = line.split(": ", 1)
        if len(parts) < 2:
            continue
        reflog_entry = parts[1]
        if "reset: moving to HEAD~" in reflog_entry:
            # Extract timestamp from reflog line
            # Format: 'HEAD@{2026-09-25 22:30:19 +0900}'
            timestamp_str = line.split("HEAD@{")[1].split("}")[0]
            try:
                reflog_dt = parse_iso_datetime(timestamp_str)
                if is_within_range(reflog_dt, since_dt, until_dt):
                    rewinds += 1
            except ValueError:
                print(f"Failed to parse reflog timestamp: {timestamp_str}", file=sys.stderr)
                continue

    if rewinds > 0:
        print(f"Found {rewinds} shared repo rewinds in time range", file=sys.stderr)
        sys.exit(1)
    else:
        print("No shared repo rewinds found", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()