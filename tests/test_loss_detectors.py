import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

def test_salvage_import():
    try:
        import salvage_lost_commits
        assert True
    except Exception as e:
        assert False, f"Import failed: {e}"

def test_detector_import():
    try:
        import detect_shared_repo_rewind
        assert True
    except Exception as e:
        assert False, f"Import failed: {e}"

def test_parse_iso_datetime():
    from salvage_lost_commits import parse_iso_datetime
    from datetime import datetime, timezone
    # Test with timezone
    dt = parse_iso_datetime('2026-09-25 06:43:31 +0900')
    assert dt.year == 2026
    assert dt.month == 9
    assert dt.day == 25
    assert dt.hour == 6
    assert dt.minute == 43
    assert dt.second == 31
    # Test without seconds
    dt2 = parse_iso_datetime('2026-09-25 06:40')
    assert dt2.year == 2026
    assert dt2.month == 9
    assert dt2.day == 25
    assert dt2.hour == 6
    assert dt2.minute == 40
    assert dt2.second == 0  # because we set seconds to zero? Actually our function sets seconds from strptime which will be 0 if not given? Wait, strptime with %H:%M will set seconds to 0. Good.

def test_is_within_range():
    from salvage_lost_commits import is_within_range, parse_iso_datetime
    dt1 = parse_iso_datetime('2026-09-25 06:00')
    dt2 = parse_iso_datetime('2026-09-25 07:00')
    dt3 = parse_iso_datetime('2026-09-25 06:30')
    dt4 = parse_iso_datetime('2026-09-25 05:00')
    dt5 = parse_iso_datetime('2026-09-25 08:00')
    assert is_within_range(dt3, dt1, dt2) == True
    assert is_within_range(dt4, dt1, dt2) == False
    assert is_within_range(dt5, dt1, dt2) == False

def test_salvage_main_runs():
    # We'll just test that main function exists and can be called with args that cause early exit due to missing git repo? 
    # Instead we'll test that the script can be run as module without error (it will error due to git but that's okay for import test)
    import salvage_lost_commits
    # We'll not actually call main because it would try to run git and fail. We'll just check that the module has a main function.
    assert hasattr(salvage_lost_commits, 'main')