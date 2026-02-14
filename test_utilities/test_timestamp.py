"""Test timestamp formatting."""
import sys
import io
from pathlib import Path

# Fix Windows console encoding (only if not already wrapped)
if sys.platform == 'win32':
    if not isinstance(sys.stdout, io.TextIOWrapper) or (hasattr(sys.stdout, 'encoding') and sys.stdout.encoding != 'utf-8'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if not isinstance(sys.stderr, io.TextIOWrapper) or (hasattr(sys.stderr, 'encoding') and sys.stderr.encoding != 'utf-8'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Import module
import timestamp_formatter
TimestampFormatter = timestamp_formatter.TimestampFormatter


def test_timestamp_formatter():
    """Test timestamp formatter."""
    print("Testing Timestamp Formatter...")
    print("=" * 60)
    
    # Create formatter
    formatter = TimestampFormatter("US/Eastern")
    print("[OK] Formatter created")
    
    # Test parsing
    timestamp_str = "Sat Jan 31 23:30:48 2026"
    dt = formatter.parse_log_timestamp(timestamp_str)
    assert dt is not None, "Should parse timestamp"
    print(f"[OK] Parsed timestamp: {timestamp_str}")
    
    # Test Discord timestamp formatting
    discord_ts = formatter.format_discord_timestamp_full(timestamp_str)
    assert discord_ts.startswith("<t:"), "Should be Discord timestamp format"
    print(f"[OK] Discord timestamp (full): {discord_ts}")
    
    discord_ts_rel = formatter.format_discord_timestamp_relative(timestamp_str)
    assert discord_ts_rel.startswith("<t:"), "Should be Discord timestamp format"
    print(f"[OK] Discord timestamp (relative): {discord_ts_rel}")
    
    # Test timezone conversion
    formatter.set_timezone("US/Pacific")
    discord_ts_pst = formatter.format_discord_timestamp_full(timestamp_str)
    print(f"[OK] Discord timestamp (PST): {discord_ts_pst}")
    
    # Test timestamp comparison
    timestamp1 = "Sat Jan 31 23:30:48 2026"
    timestamp2 = "Sat Jan 31 23:32:00 2026"  # 1 minute 12 seconds later
    is_close = formatter.compare_timestamps(timestamp1, timestamp2, tolerance_minutes=3)
    assert is_close == True, "Timestamps should be within tolerance"
    print("[OK] Timestamp comparison works")
    
    timestamp3 = "Sat Jan 31 23:35:00 2026"  # 4 minutes 12 seconds later
    is_close = formatter.compare_timestamps(timestamp1, timestamp3, tolerance_minutes=3)
    assert is_close == False, "Timestamps should not be within tolerance"
    print("[OK] Timestamp comparison (outside tolerance) works")
    
    print("\n" + "=" * 60)
    print("All tests passed!")


if __name__ == "__main__":
    test_timestamp_formatter()
