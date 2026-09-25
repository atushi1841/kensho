#!/usr/bin/env python3
"""Simple verification that removing gen_start check breaks the filtering."""

import re
from datetime import datetime

def filter_with_gen_start_check(txt: str, gen_start: datetime):
    """Current implementation with gen_start check."""
    lines = txt.splitlines()
    result_ts = None
    result_alive = []
    result_dead = []
    result_restored = 0
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("[PROXY-CHECK]"):
            # 直前のタイムSTAMP行を探す（ backwards search）
            prev_ts: datetime | None = None
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip()
                # 正規表現で YYYY-MM-DD HH:MM:SS 形式の時刻行をマッチ
                m = re.match(r"\\[(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})\\]", prev_line)
                if m:
                    prev_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    break  # 最初に見つかった（最新の）タイムSTAMPを採用
                j -= 1
            
            # タイムSTAMPが見つからない、または生成時刻より前ならスキップ
            if prev_ts is None or prev_ts < gen_start:
                i += 1
                continue
            
            # 1行から alive/dead/restored を抽出する
            proxy_line = line
            alive = []
            dead = []
            restored = 0
            alive_match = re.search(r"alive=\\[(.*?)\\]", proxy_line)
            if alive_match:
                alive_str = alive_match.group(1)
                alive = [int(x.strip()) for x in alive_str.split(",") if x.strip()]
            dead_match = re.search(r"dead=\\[(.*?)\\]", proxy_line)
            if dead_match:
                dead_str = dead_match.group(1)
                dead = [int(x.strip()) for x in dead_str.split(",") if x.strip()]
            restored_match = re.search(r"restored=(\\d+)", proxy_line)
            if restored_match:
                restored = int(restored_match.group(1))
            
            # 現在の結果をこの行で上書き（常に最新の1行だけを保持）
            result_ts = prev_ts
            result_alive = alive
            result_dead = dead
            result_restored = restored
        
        i += 1
    
    # 結果を返す
    if result_ts is not None:
        return result_ts, result_alive, result_dead, result_restored, result_ts
    else:
        return None, [], [], 0, None

def filter_without_gen_start_check(txt: str, gen_start: datetime):
    """Modified implementation WITHOUT gen_start check."""
    lines = txt.splitlines()
    result_ts = None
    result_alive = []
    result_dead = []
    result_restored = 0
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("[PROXY-CHECK]"):
            # 直前のタイムSTAMP行を探す（ backwards search）
            prev_ts: datetime | None = None
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip()
                # 正規表現で YYYY-MM-DD HH:MM:SS 形式の時刻行をマッチ
                m = re.match(r"\\[(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})\\]", prev_line)
                if m:
                    prev_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    break  # 最初に見つかった（最新の）タイムSTAMPを採用
                j -= 1
            
            # タイムSTAMPが見つからない場合のみスキップ（gen_startチェックを削除）
            if prev_ts is None:
                i += 1
                continue
            
            # 1行から alive/dead/restored を抽出する
            proxy_line = line
            alive = []
            dead = []
            restored = 0
            alive_match = re.search(r"alive=\\[(.*?)\\]", proxy_line)
            if alive_match:
                alive_str = alive_match.group(1)
                alive = [int(x.strip()) for x in alive_str.split(",") if x.strip()]
            dead_match = re.search(r"dead=\\[(.*?)\\]", proxy_line)
            if dead_match:
                dead_str = dead_match.group(1)
                dead = [int(x.strip()) for x in dead_str.split(",") if x.strip()]
            restored_match = re.search(r"restored=(\\d+)", proxy_line)
            if restored_match:
                restored = int(restored_match.group(1))
            
            # 現在の結果をこの行で上書き（常に最新の1行だけを保持）
            result_ts = prev_ts
            result_alive = alive
            result_dead = dead
            result_restored = restored
        
        i += 1
    
    # 結果を返す
    if result_ts is not None:
        return result_ts, result_alive, result_dead, result_restored, result_ts
    else:
        return None, [], [], 0, None

# Test data from test_skips_row_before_gen_start
txt = (
    "[2026-09-25 04:15:01] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）\\n"
    "Proxy zin20120731:1084 is dead\\n"
    "WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'\\n"
    "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)\\n"
)
gen = datetime(2026, 9, 25, 4, 30, 0)

print("Testing with gen_start check (current implementation):")
ts_with, alive_with, dead_with, restored_with, _ = filter_with_gen_start_check(txt, gen)
print(f"  result_ts: {ts_with}")
print(f"  alive: {alive_with}")
print(f"  dead: {dead_with}")
print(f"  restored: {restored_with}")

print("\\nTesting without gen_start check (modified implementation):")
ts_without, alive_without, dead_without, restored_without, _ = filter_without_gen_start_check(txt, gen)
print(f"  result_ts: {ts_without}")
print(f"  alive: {alive_without}")
print(f"  dead: {dead_without}")
print(f"  restored: {restored_without}")

print("\\nExpected behavior:")
print("- With gen_start check: Should SKIP the row (result_ts=None, alive=[], dead=[], restored=0)")
print("- Without gen_start check: Should NOT skip the row (result_ts=timestamp, alive=[1081,1082,1085], dead=[1084], restored=0)")

print("\\nVerification:")
success = (ts_with is None and len(alive_with) == 0 and len(dead_with) == 0 and restored_with == 0 and
           ts_without is not None and alive_without == [1081, 1082, 1085] and dead_without == [1084] and restored_without == 0)

if success:
    print("\\n✓ VERIFICATION PASSED: Removing gen_start check would break the filtering as expected")
else:
    print("\\n✗ VERIFICATION FAILED: Unexpected behavior")
    print(f"  With check: ts={ts_with}, alive={alive_with}, dead={dead_with}, restored={restored_with}")
    print(f"  Without check: ts={ts_without}, alive={alive_without}, dead={dead_without}, restored={restored_without}")