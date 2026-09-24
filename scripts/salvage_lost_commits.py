#!/usr/bin/env python3
"""
salvage_lost_commits.py

Find dangling commits within a given time range that are not ancestors of HEAD or origin/main.
Output JSON with list of commits.

Usage:
    python3 scripts/salvage_lost_commits.py --since '2026-09-25 06:40' --until '2026-09-25 07:10' --json
"""

import argparse
import json
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


def get_dangling_commits():
    """Return list of dangling commit SHA1s."""
    output = run_git("fsck", "--dangling")
    commits = []
    for line in output.splitlines():
        if line.startswith("dangling commit "):
            commits.append(line.split()[2])
    return commits


def get_commit_info(commit_sha):
    """Return dict with commit, date, subject, files."""
    # Get commit date
    date_str = run_git("show", "-s", "--format=%ci", commit_sha)
    commit_dt = parse_iso_datetime(date_str)
    # Get subject
    subject = run_git("show", "-s", "--format=%s", commit_sha)
    # Get list of files changed
    files_output = run_git("diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha)
    files = [f for f in files_output.splitlines() if f]
    return {
        "commit": commit_sha,
        "date": date_str,
        "subject": subject,
        "files": files,
    }


def is_ancestor(commit, ref):
    """Return True if commit is ancestor of ref."""
    try:
        run_git("merge-base", "--is-ancestor", commit, ref, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Find lost commits.")
    parser.add_argument("--since", required=False, help="Start time (ISO format)")
    parser.add_argument("--until", required=False, help="End time (ISO format)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    # Parse since/until if provided
    since_dt = None
    until_dt = None
    if args.since:
        since_dt = parse_iso_datetime(args.since)
    if args.until:
        until_dt = parse_iso_datetime(args.until)

    dangling = get_dangling_commits()
    results = []
    for sha in dangling:
        info = get_commit_info(sha)
        commit_dt = parse_iso_datetime(info["date"])
        # Filter by date range
        if since_dt and not is_within_range(commit_dt, since_dt, until_dt):
            continue
        if until_dt and not is_within_range(commit_dt, since_dt, until_dt):
            continue
        # Filter: not ancestor of HEAD nor origin/main
        if is_ancestor(sha, "HEAD") or is_ancestor(sha, "origin/main"):
            continue
        results.append(info)

    if args.json:
        output = {"commits": results}
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            print(f"{r['commit']} {r['date']} {r['subject']}")


if __name__ == "__main__":
    main()