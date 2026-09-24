#!/usr/bin/env python3
"""
Script to add direction indicators (up/down) to all KPI metrics in outcome-review-2026-09-24.md
"""

from pathlib import Path
import re

def add_direction_to_metric(line):
    """Add direction indicator to a KPI metric line"""
    # Skip if already has direction
    if "方向:" in line:
        return line
    
    # Look for before→after patterns in different formats
    # Pattern 1: "X→Y" (arrow without spaces)
    arrow_pattern = r'([0-9]+\.?[0-9]*)→([0-9]+\.?[0-9]*)'
    
    # Pattern 2: "X→Y: " (arrow with colon after)
    arrow_pattern_colon = r'([0-9]+\.?[0-9]*)→([0-9]+\.?[0-9]*):\s*'
    
    # Pattern 3: Japanese format "X→Y" within text
    # Find all occurrences and add direction
    
    def add_direction_to_match(match):
        before_value = float(match.group(1))
        after_value = float(match.group(2))
        
        if after_value < before_value:
            direction = "方向: down"
        elif after_value > before_value:
            direction = "方向: up"
        else:
            direction = "方向: equal"
        
        # Add direction indicator in parentheses
        return f"{match.group(1)}→{match.group(2)} ({direction})"
    
    # Process all matches in the line
    # First handle arrow with colon pattern (for lines like "3→1: ")
    processed = re.sub(arrow_pattern_colon, add_direction_to_match, line)
    
    # If no matches from the first pattern, try the basic pattern
    if processed == line:
        # Replace all occurrences
        processed = re.sub(arrow_pattern, add_direction_to_match, line)
    
    return processed

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
        updated_line = add_direction_to_metric(line)
        updated_lines.append(updated_line)
    
    updated_content = '\n'.join(updated_lines)
    
    # Write back to file
    report_path.write_text(updated_content, encoding="utf-8")
    
    print(f"Report updated: Added direction indicators to all KPI metrics")
    
    # Verify the changes
    new_direction_count = updated_content.count("方向:")
    print(f"Total direction indicator count: {new_direction_count}")
    
    # Show some examples
    print("\nSample updated lines with direction indicators:")
    for line in updated_lines:
        if "方向:" in line:
            print(f"  {line}")

if __name__ == "__main__":
    main()