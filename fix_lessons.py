#!/usr/bin/env python3
import sqlite3
from pathlib import Path

PROFILES_GLOB = "/home/atushi/.hermes/profiles"

# Fix the problematic lessons entry
problematic_path = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron/notepad.db")
problematic_job_id = "d340ec02d57e"

con = sqlite3.connect(f"file:{problematic_path}?mode=rwc", uri=True)
try:
    cur = con.cursor()
    cur.execute("SELECT value FROM cron_notepad WHERE job_id=? AND key='lessons'", (problematic_job_id,))
    row = cur.fetchone()
    if row:
        original_val = row[0]
        if original_val:
            lines = original_val.splitlines()
            bullet_lines = [line for line in lines if line.strip().startswith(("- ", "* "))]
            print(f"Original bullets: {len(bullet_lines)}")
            
            # Keep only first 5 bullet lines across all dates
            # Build new lines by filtering bullet lines to max 5 total
            new_lines = []
            bullet_count = 0
            
            for line in lines:
                if line.startswith("2026-"):
                    new_lines.append(line)
                elif line.strip().startswith(("- ", "* ")):
                    if bullet_count < 5:
                        new_lines.append(line)
                        bullet_count += 1
                else:
                    # Keep other lines (empty lines, etc.)
                    new_lines.append(line)
            
            new_val = '\n'.join(new_lines)
            
            bullet_count_new = sum(1 for line in new_val.splitlines() if line.strip().startswith(("- ", "* ")))
            print(f"New bullets: {bullet_count_new}")
            print(f"Original length: {len(original_val)} chars")
            print(f"New length: {len(new_val)} chars")
            
            if bullet_count_new < 6:
                # Update the lessons entry
                cur.execute("UPDATE cron_notepad SET value=? WHERE job_id=? AND key='lessons'", (new_val, problematic_job_id))
                con.commit()
                print("Fixed!")
            else:
                print("Still has >5 bullets, need manual intervention")
                print(f"Content:\n{new_val}")
        else:
            print("No value found for the problematic entry")
    else:
        print(f"No entry found for job_id {problematic_job_id}")
finally:
    con.close()