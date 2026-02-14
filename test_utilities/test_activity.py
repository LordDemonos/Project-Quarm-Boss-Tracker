"""Test activity database."""
import sys
import io
from pathlib import Path
import tempfile
import shutil
from datetime import date, datetime

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
import activity_database
ActivityDatabase = activity_database.ActivityDatabase


def test_activity_database():
    """Test activity database operations."""
    print("Testing Activity Database...")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test_activity.json"
    
    try:
        # Create database
        db = ActivityDatabase(str(db_path))
        print("[OK] Database created")
        
        # Use today's date for the test timestamp
        today = datetime.now()
        timestamp_str = today.strftime("%a %b %d %H:%M:%S %Y")
        
        # Test adding activity
        activity1 = db.add_activity(
            timestamp=timestamp_str,
            monster="Severilous",
            location="The Emerald Jungle",
            player="TestPlayer",
            guild="Test Guild",
            posted_to_discord=True,
            discord_message="Test message"
        )
        assert activity1 is not None, "Should add activity"
        print("[OK] Added activity")
        
        # Test today's activities
        today_activities = db.get_today_activities()
        assert len(today_activities) >= 1, f"Should have today's activities (found {len(today_activities)}, date stored: {activity1.get('date')}, today: {date.today().isoformat()})"
        print(f"[OK] Today's activities: {len(today_activities)}")
        
        # Test all activities
        all_activities = db.get_all_activities()
        assert len(all_activities) >= 1, "Should have all activities"
        print(f"[OK] All activities: {len(all_activities)}")
        
        # Test persistence
        db2 = ActivityDatabase(str(db_path))
        today_activities2 = db2.get_today_activities()
        assert len(today_activities2) >= 1, "Activities should persist"
        print("[OK] Persistence works")
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temporary files: {temp_dir}")


if __name__ == "__main__":
    test_activity_database()
