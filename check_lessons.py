#!/usr/bin/env python3
import sqlite3
from pathlib import Path

PROFILES_GLOB = "/home/atushi/.hermes/profiles"
for p in Path(PROFILES_GLOB).glob("*/cron/notepad.db"):
    print(f"=== {p} ===")
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("SELECT job_id, key, value FROM cron_notepad WHERE key='lessons'")
        rows = cur.fetchall()
        for job_id, key, val in rows:
            if not val:
                continue
            bullets = sum(1 for line in val.splitlines() if line.strip().startswith(("- ", "* ")))
            print(f"  job {job_id}: {bullets} bullets")
            if bullets > 5:
                print("  Too many bullets!")
                # Show first 10 lines
                for line in val.splitlines()[:10]:
                    print(f"    {line}")
        con.close()
    except Exception as e:
        print(f"  error: {e}")