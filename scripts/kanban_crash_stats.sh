#!/bin/bash

# This script calculates 24-hour crash statistics for kensho-ai-team kanban board.
# Outputs JSON: {"window_h":24,"crashed_total":N,"max_crashes_per_task":M,"waste_ratio_pct":P,"ready_zero_run":Q}

KANBAN_DB="/home/atushi/.hermes/kanban/kanban.db"
BOARD="kensho-ai-team"
PROFILE="kensho-worker"
WINDOW_H=24
NOW=$(date +%s)
ONE_DAY_AGO=$((NOW - WINDOW_H * 3600))

# Temporary file for SQL output
SQL_OUTPUT=$(mktemp)

# Query for crash statistics and total run time for the profile
sqlite3 "$KANBAN_DB" <<EOF > "$SQL_OUTPUT"
.mode json
.headers off

WITH ProfileRuns AS (
    SELECT
        strftime('%s', started_at) AS start_ts,
        strftime('%s', ended_at) AS end_ts,
        outcome,
        task_id,
        profile
    FROM task_runs
    WHERE profile = '$PROFILE'
      AND started_at >= datetime($ONE_DAY_AGO, 'unixepoch')
),
CrashStats AS (
    SELECT
        task_id,
        COUNT(*) AS crashes_24h
    FROM ProfileRuns
    WHERE outcome = 'crashed'
    GROUP BY task_id
),
TotalProfileTime AS (
    SELECT
        SUM(CASE WHEN end_ts IS NOT NULL THEN (end_ts - start_ts) ELSE (CAST(strftime('%s', 'now') AS INTEGER) - start_ts) END) AS total_wall_time,
        SUM(CASE WHEN outcome IN ('crashed', 'reclaimed') AND end_ts IS NOT NULL THEN (end_ts - start_ts) ELSE 0 END) AS waste_wall_time
    FROM ProfileRuns
),
ReadyZeroRun AS (
    SELECT
        COUNT(DISTINCT t.id)
    FROM tasks t
    LEFT JOIN task_runs tr ON t.id = tr.task_id
    WHERE t.board = '$BOARD'
      AND t.assignee = '$PROFILE'
      AND t.status = 'ready'
      AND NOT EXISTS (
            SELECT 1 FROM task_runs
            WHERE task_id = t.id AND profile = '$PROFILE'
              AND started_at >= datetime($ONE_DAY_AGO, 'unixepoch')
        )
)
SELECT
    json_object(
        'window_h', $WINDOW_H,
        'crashed_total', (SELECT COUNT(*) FROM ProfileRuns WHERE outcome = 'crashed'),
        'max_crashes_per_task', IFNULL((SELECT MAX(crashes_24h) FROM CrashStats), 0),
        'waste_ratio_pct', IFNULL(CAST((SELECT SUM(waste_wall_time) FROM TotalProfileTime) * 100.0 / (SELECT SUM(total_wall_time) FROM TotalProfileTime) AS REAL), 0.0),
        'ready_zero_run', (SELECT * FROM ReadyZeroRun)
    );
EOF

# Read the JSON output and print
cat "$SQL_OUTPUT"

# Clean up temporary file
rm "$SQL_OUTPUT"
