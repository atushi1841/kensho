#!/usr/bin/env python3
"""
Execution Trace → Textual Gradient Collector (TPGO Textual Gradient)
Converts job execution traces from notepad and outputs to structured JSON
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = "/mnt/d/Project2/kensho/data"
GRADIENTS_FILE = os.path.join(DATA_DIR, "textual_gradients.json")
NOTEPAD_DB = "/home/atushi/.hermes/profiles/kensho-sweeps/cron/notepad.db"

def load_existing_gradients():
    """Load existing gradients from JSON file"""
    if os.path.exists(GRADIENTS_FILE):
        with open(GRADIENTS_FILE, 'r') as f:
            return json.load(f)
    return {"gradients": [], "schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat()}

def save_gradients(data):
    """Save gradients to JSON file"""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(GRADIENTS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_gradient_from_notepad_entry(job_id, entry, updated_at):
    """Convert notepad entry to textual gradient format"""
    lines = entry.split('\n')
    
    failure_node = "unknown"
    severity = "medium"
    
    if "FAIL" in entry or "ERROR" in entry or "blocked" in entry.lower():
        severity = "high"
        failure_node = "execution_failure"
    elif "WARN" in entry or "warning" in entry.lower():
        severity = "medium"
        failure_node = "warning"
    elif "stagnation" in entry.lower() or "backlog" in entry.lower():
        severity = "low"
        failure_node = "loop_stagnation"
    
    suggested_modification = "improve_error_handling"
    
    if "board" in entry.lower() and "ready=0" in entry:
        suggested_modification = "enhance_pattern_mining_from_past_gradients"
    elif "reddit" in entry.lower() and "gate" in entry:
        suggested_modification = "strengthen_reddit_account_validation"
    elif "apify" in entry.lower() and "external_users=0" in entry:
        suggested_modification = "optimize_apify_actor_discovery"
    elif "revenue" in entry.lower() and "bash" in entry:
        suggested_modification = "implement_revenue_monitoring_fallback"
    
    import hashlib
    content_hash = hashlib.sha256((entry + job_id).encode()).hexdigest()[:16]
    
    return {
        "trace_id": f"{job_id}_{updated_at}",
        "failure_node": failure_node,
        "severity": severity,
        "suggested_granular_modification": suggested_modification,
        "evidence_hash": f"sha256:{content_hash}",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source_job_id": job_id,
        "raw_entry": entry[:500]
    }

def collect_gradients():
    """Collect gradients from notepad entries"""
    print("Collecting textual gradients from notepad...")
    
    data = load_existing_gradients()
    
    try:
        conn = sqlite3.connect(NOTEPAD_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT job_id, key, value, updated_at 
            FROM cron_notepad 
            WHERE key = 'lessons' 
            AND updated_at >= datetime('now', '-7 days')
            ORDER BY updated_at DESC
        """)
        
        new_gradients = []
        for job_id, key, value, updated_at in cursor.fetchall():
            if job_id in ['4baf143523e0', '5e8ec4984bba', '033ff6065ef7']:
                gradient = extract_gradient_from_notepad_entry(job_id, value, updated_at)
                new_gradients.append(gradient)
        
        for gradient in new_gradients:
            data["gradients"].append(gradient)
        
        if len(data["gradients"]) > 100:
            data["gradients"] = data["gradients"][-100:]
        
        save_gradients(data)
        
        print(f"Collected {len(new_gradients)} new gradients")
        print(f"Total gradients: {len(data['gradients'])}")
        
        return len(new_gradients)
        
    except Exception as e:
        print(f"Error collecting gradients: {e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--collect":
        count = collect_gradients()
        print(f"Collected {count} gradients")
    else:
        print("Usage: python3 trace_gradient_collector.py --collect")
