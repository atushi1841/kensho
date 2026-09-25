#!/usr/bin/env python3
import sqlite3
from pathlib import Path

PROFILES_GLOB = "/home/atushi/.hermes/profiles"

# Find the problematic lessons entry
for p in Path(PROFILES_GLOB).glob("*/cron/notepad.db"):
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("SELECT job_id, value FROM cron_notepad WHERE key='lessons'")
        for job_id, val in cur.fetchall():
            if val:
                bullets = sum(1 for line in val.splitlines() if line.strip().startswith(("- ", "* ")))
                if bullets > 5:
                    print(f"\n=== PROBLEMATIC ENTRY ===")
                    print(f"File: {p}")
                    print(f"Job ID: {job_id}")
                    print(f"Bullets: {bullets}")
                    print(f"Content:")
                    print(val)
                    print("\n=== END ===\n")
        con.close()
    except Exception as e:
        print(f"Error reading {p}: {e}")