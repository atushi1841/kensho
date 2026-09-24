# Verification Report for t_53838249

## verification_evidence
Fixed kensho-ready-watchdog.sh to resolve HERMES_BIN CLI path for cron compatibility

## Changes Made
1. Added HERMES_BIN resolution block after `set -euo pipefail` (lines 24-37) mirroring loop_health.sh v141 / t_5af1b5d8 pattern
2. Updated all `hermes kanban` calls to use `$HERMES_BIN` instead of bare `hermes` (lines 66, 150, 159, 169)
3. Preserved all existing script behavior for --dry-run, --apply, and threshold logic
4. Maintained silent operation (SILENT=1) when no issues found

## Verification Steps
1. Verified script exits 0 with --dry-run under minimal PATH: `env -i HOME=/home/atushi PATH=/usr/bin:/bin bash scripts/kensho-ready-watchdog.sh --dry-run`
2. Verified script exits 0 with --apply --dry-run under minimal PATH: `env -i HOME=/home/atushi PATH=/usr/bin:/bin bash scripts/kensho-ready-watchdog.sh --apply --dry-run`
3. Confirmed hermes CLI resolution works: Added checks for hermes CLI using `command -v hermes` with fallback to HERMES_VENV_BIN
4. Verified error handling: Script exits with code 127 when hermes CLI not found in minimal cron PATH
5. Verified symlink consistency: Profile script symlinks to repo script for consistency

## Test Results
- Test 1: Script execution with --dry-run under minimal PATH ✓ (exit 0)
- Test 2: Script execution with --apply --dry-run under minimal PATH ✓ (exit 0)
- Test 3: All hermes kanban calls now use $HERMES_BIN variable ✓
- Test 4: Error handling for missing hermes CLI ✓ (exits 127)

## Before/After
Before: Script would fail silently with exit 127 under cron's minimal PATH, leaving ready tasks unprocessed
After: Script properly resolves hermes CLI path and processes ready/warning/escalation/archive logic correctly

## Files Changed
- scripts/kensho-ready-watchdog.sh (20 insertions(+), 4 deletions(-))

## Commit
bf56e2f fix(kensho-ready-watchdog.sh): resolve HERMES_BIN CLI path for cron compatibility