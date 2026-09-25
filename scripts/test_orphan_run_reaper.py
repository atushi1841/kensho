#!/usr/bin/env python3
"""
Unit tests for scripts/orphan_run_reaper.py
Fixture 3 cases: orphan / stale-heartbeat / normal
"""
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from orphan_run_reaper import detect_orphan_runs

DB_SCHEMA = """
CREATE TABLE tasks (id TEXT PRIMARY KEY);
CREATE TABLE task_runs (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    status TEXT,
    worker_pid INTEGER,
    last_heartbeat_at INTEGER,
    started_at INTEGER
);
"""

def make_db(tmp_dir):
    db_path = Path(tmp_dir) / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(DB_SCHEMA)
    conn.commit()
    return db_path

def seed_orphan(db_path):
    conn = sqlite3.connect(str(db_path))
    now = int(time.time())
    conn.execute("INSERT INTO task_runs(id,task_id,status,worker_pid,last_heartbeat_at,started_at) VALUES (1,'t_missing','running',12345,?,?)", (now-500, now-600))
    conn.commit()
    conn.close()

def seed_stale_heartbeat(db_path):
    conn = sqlite3.connect(str(db_path))
    now = int(time.time())
    # orphan with stale heartbeat > 1800
    conn.execute("INSERT INTO task_runs(id,task_id,status,worker_pid,last_heartbeat_at,started_at) VALUES (2,'t_missing2','running',123,?,?)", (now-4000, now-5000))
    conn.commit()
    conn.close()

def seed_normal(db_path):
    conn = sqlite3.connect(str(db_path))
    now = int(time.time())
    conn.execute("INSERT INTO tasks(id) VALUES ('t_ok')")
    conn.execute("INSERT INTO task_runs(id,task_id,status,worker_pid,last_heartbeat_at,started_at) VALUES (3,'t_ok','running',999,?,?)", (now-100, now-200))
    conn.commit()
    conn.close()

def test_orphan_run():
    with tempfile.TemporaryDirectory() as td:
        db = make_db(td)
        seed_orphan(db)
        now = int(time.time())
        res = detect_orphan_runs(db, now, stale_threshold=1800)
        assert res["orphan_runs"] == 1, f"expected 1 orphan, got {res['orphan_runs']}"
        assert res["details"][0]["task_id"] == "t_missing"
        print("test_orphan_run PASS")

def test_stale_heartbeat():
    with tempfile.TemporaryDirectory() as td:
        db = make_db(td)
        seed_stale_heartbeat(db)
        now = int(time.time())
        res = detect_orphan_runs(db, now, stale_threshold=1800)
        assert res["orphan_runs"] == 1
        assert res["stale_heartbeat_runs"] == 1, f"expected stale 1, got {res['stale_heartbeat_runs']}"
        print("test_stale_heartbeat PASS")

def test_normal_no_orphan():
    with tempfile.TemporaryDirectory() as td:
        db = make_db(td)
        seed_normal(db)
        now = int(time.time())
        res = detect_orphan_runs(db, now, stale_threshold=1800)
        assert res["orphan_runs"] == 0, f"expected 0 orphan, got {res['orphan_runs']}"
        assert res["stale_heartbeat_runs"] == 0
        print("test_normal_no_orphan PASS")

if __name__ == "__main__":
    test_orphan_run()
    test_stale_heartbeat()
    test_normal_no_orphan()
    print("All 3 fixture tests passed")
