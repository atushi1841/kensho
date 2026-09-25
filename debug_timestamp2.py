#!/usr/bin/env python3
"""Debug the timestamp extraction"""

import re
from datetime import datetime

def debug_timestamp_extraction(txt: str):
    lines = txt.splitlines()
    print(f"Number of lines: {len(lines)}")
    for i, line in enumerate(lines):
        print(f"Line {i}: '{line}'")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        print(f"\nChecking Line {i}: '{line}'")
        
        if line.startswith("[PROXY-CHECK]"):
            print(f"  Found PROXY-CHECK at line {i}")
            # 直前のタイムSTAMP行を探す（ backwards search）
            prev_ts: datetime | None = None
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip()
                print(f"    Checking line {j}: '{prev_line}'")
                # 正規表現で YYYY-MM-DD HH:MM:SS 形式の時刻行をマッチ
                m = re.match(r"\\[(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})\\]", prev_line)
                if m:
                    time_str = m.group(1)
                    print(f"      Matched timestamp: {time_str}")
                    prev_ts = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    print(f"      Parsed timestamp: {prev_ts}")
                    break  # 最初に見つかった（最新の）タイムSTAMPを採用
                j -= 1
            
            print(f"  Final prev_ts: {prev_ts}")
            break
        
        i += 1

# Test data from test_skips_row_before_gen_start - properly formatted with actual newlines
txt = """[2026-09-25 04:15:01] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）
Proxy zin20120731:1084 is dead
WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'
[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)"""

debug_timestamp_extraction(txt)