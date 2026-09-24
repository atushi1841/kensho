#!/usr/bin/env python3
"""
Script to add direction indicators (up/down) to KPI metrics in outcome-review-2026-09-24.md
"""

from pathlib import Path

def add_direction_indicators_to_line(line):
    """Add direction indicator to a KPI metric line"""
    # Check if line contains "->" (before/after pattern)
    if "->" not in line:
        return line
    
    # Check if it already has "方向:" 
    if "方向:" in line:
        return line
    
    # Extract the metric name and value change
    parts = line.split("->")
    if len(parts) != 2:
        return line
    
    before_after = parts[1].strip()
    
    # Find the numeric pattern "X→Y" (with different arrow characters)
    import re
    
    # Look for patterns like "3→1", "0.952→0.186", "36→0", etc.
    arrow_pattern = r'([0-9]+\.?[0-9]*)→([0-9]+\.?[0-9]*)'
    match = re.search(arrow_pattern, before_after)
    
    if not match:
        return line
    
    before_value = float(match.group(1))
    after_value = float(match.group(2))
    
    # Determine direction
    if after_value < before_value:
        direction = "方向: down"
    elif after_value > before_value:
        direction = "方向: up"
    else:
        direction = "方向: equal"
    
    # Insert direction indicator before the numeric pattern
    new_before_after = re.sub(
        arrow_pattern, 
        f"{match.group(1)}→{match.group(2)} ({direction})", 
        before_after,
        count=1
    )
    
    return f"{parts[0].strip()} -> {new_before_after}"

def main():
    report_path = Path("/mnt/d/Project2/kensho/reports/outcome-review-2026-09-24.md")
    
    if not report_path.exists():
        print(f"Error: Report file not found at {report_path}")
        return
    
    content = report_path.read_text(encoding="utf-8")
    lines = content.split('\n')
    
    # Process each line to add direction indicators
    updated_lines = []
    for line in lines:
        updated_line = add_direction_indicators_to_line(line)
        updated_lines.append(updated_line)
    
    updated_content = '\n'.join(updated_lines)
    
    # Write back to file
    report_path.write_text(updated_content, encoding="utf-8")
    
    print(f"Report updated: Added direction indicators to KPI metrics")
    
    # Verify the changes
    new_direction_count = updated_content.count("方向:")
    print(f"Direction indicator count: {new_direction_count}")
    
    # Show some examples
    print("\nSample updated lines:")
    for line in updated_lines:
        if "方向:" in line:
            print(f"  {line}")

if __name__ == "__main__":
    main()