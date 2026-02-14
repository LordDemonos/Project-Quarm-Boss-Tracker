"""Test boss database operations."""
import sys
import io
from pathlib import Path
import tempfile
import shutil

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
import boss_database
BossDatabase = boss_database.BossDatabase


def test_boss_database():
    """Test boss database operations."""
    print("Testing Boss Database...")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test_bosses.json"
    
    try:
        # Create database
        db = BossDatabase(str(db_path))
        print("[OK] Database created")
        
        # Test adding boss
        boss1 = db.add_boss("Severilous", "The Emerald Jungle", enabled=False)
        print(f"[OK] Added boss: {boss1['name']} in {boss1['location']}")
        
        # Test adding boss with location
        boss2 = db.add_boss("Aten Ha Ra", "Vex Thal", enabled=True)
        print(f"[OK] Added boss: {boss2['name']} in {boss2['location']} (enabled)")
        
        # Test exists
        assert db.exists("Severilous"), "Boss should exist"
        assert not db.exists("NonExistent"), "Boss should not exist"
        print("[OK] Exists check works")
        
        # Test get_boss
        boss = db.get_boss("Severilous")
        assert boss is not None, "Should get boss"
        assert boss['name'] == "Severilous", "Boss name should match"
        print("[OK] Get boss works")
        
        # Test enable/disable
        db.enable_boss("Severilous")
        boss = db.get_boss("Severilous")
        assert boss['enabled'] == True, "Boss should be enabled"
        print("[OK] Enable boss works")
        
        db.disable_boss("Severilous")
        boss = db.get_boss("Severilous")
        assert boss['enabled'] == False, "Boss should be disabled"
        print("[OK] Disable boss works")
        
        # Test get_bosses_by_location
        bosses_by_zone = db.get_bosses_by_location()
        assert "The Emerald Jungle" in bosses_by_zone, "Should have Emerald Jungle zone"
        assert "Vex Thal" in bosses_by_zone, "Should have Vex Thal zone"
        print("[OK] Get bosses by location works")
        
        # Test increment_kill_count
        db.increment_kill_count("Severilous")
        boss = db.get_boss("Severilous")
        assert boss['kill_count'] == 1, "Kill count should be 1"
        print("[OK] Increment kill count works")
        
        # Test remove
        db.remove_boss("Severilous")
        assert not db.exists("Severilous"), "Boss should be removed"
        print("[OK] Remove boss works")
        
        # Test persistence
        db2 = BossDatabase(str(db_path))
        assert db2.exists("Aten Ha Ra"), "Boss should persist"
        print("[OK] Persistence works")
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temporary files: {temp_dir}")


if __name__ == "__main__":
    test_boss_database()
