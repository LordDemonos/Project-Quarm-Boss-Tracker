"""
Script to restore bosses.json from a backup file.
This will help you recover your notes if they were lost.

Usage:
    python restore_backup.py [backup_file_path]

If no backup file is provided, it will list available backups.
"""
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

def get_backup_dir():
    """Get the backup directory path."""
    # Same logic as boss_database.py
    app_data = Path.home() / "AppData" / "Roaming" / "boss tracker"
    backup_dir = app_data / "backups"
    return backup_dir

def get_bosses_json_path():
    """Get the bosses.json file path."""
    app_data = Path.home() / "AppData" / "Roaming" / "boss tracker"
    return app_data / "bosses.json"

def list_backups():
    """List all available backups."""
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        print(f"Backup directory not found: {backup_dir}")
        return []
    
    backups = sorted(backup_dir.glob("bosses_backup_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"\nFound {len(backups)} backup(s) in: {backup_dir}\n")
    for i, backup in enumerate(backups, 1):
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        size = backup.stat().st_size
        print(f"{i}. {backup.name}")
        print(f"   Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Size: {size:,} bytes")
        
        # Check how many bosses have notes in this backup
        try:
            with open(backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
                bosses = data.get('bosses', [])
                bosses_with_notes = sum(1 for b in bosses if b.get('note', '').strip())
                print(f"   Bosses with notes: {bosses_with_notes}/{len(bosses)}")
        except Exception as e:
            print(f"   Error reading backup: {e}")
        print()
    
    return backups

def restore_backup(backup_path: Path):
    """Restore bosses.json from a backup file."""
    bosses_json = get_bosses_json_path()
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        print(f"Error: Backup file not found: {backup_path}")
        return False
    
    # Create a backup of current file before restoring
    if bosses_json.exists():
        current_backup = bosses_json.parent / f"bosses_backup_BEFORE_RESTORE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy2(bosses_json, current_backup)
        print(f"Created backup of current file: {current_backup.name}")
    
    # Restore from backup
    try:
        shutil.copy2(backup_path, bosses_json)
        print(f"\n✓ Successfully restored from: {backup_path.name}")
        print(f"  Restored to: {bosses_json}")
        
        # Show summary
        with open(bosses_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            bosses = data.get('bosses', [])
            bosses_with_notes = sum(1 for b in bosses if b.get('note', '').strip())
            print(f"\n  Total bosses: {len(bosses)}")
            print(f"  Bosses with notes: {bosses_with_notes}")
        
        return True
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        # Restore from specified backup
        backup_path = Path(sys.argv[1])
        restore_backup(backup_path)
    else:
        # List backups and let user choose
        backups = list_backups()
        if not backups:
            print("No backups found.")
            return
        
        print("To restore a backup, run:")
        print(f"  python restore_backup.py \"{backups[0]}\"")
        print("\nOr specify the backup file path directly.")

if __name__ == "__main__":
    main()
