"""Manage the boss database - loading, saving, and querying boss entries."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
import shutil

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)

# Default respawn time: 6 days 18 hours = 162 hours
DEFAULT_RESPAWN_HOURS = 162.0

# Debug instrumentation - import from main if available
try:
    import sys
    if 'main' in sys.modules:
        from main import debug_log
    else:
        # Fallback if main not imported yet
        def _get_debug_log_path():
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent.parent
            debug_path = base_dir / ".cursor" / "debug.log"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            return debug_path
        def debug_log(location, message, data=None, hypothesis_id=None, run_id="initial"):
            try:
                import json as json_lib
                import time
                log_entry = {"location": location, "message": message, "timestamp": time.time() * 1000, "runId": run_id}
                if data: log_entry["data"] = data
                if hypothesis_id: log_entry["hypothesisId"] = hypothesis_id
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json_lib.dumps(log_entry) + "\n")
            except: pass
except:
    def debug_log(*args, **kwargs): pass


class BossDatabase:
    """Manages the boss database stored in JSON format."""
    
    def __init__(self, db_path: str, app_dir: Optional[Path] = None):
        """
        Initialize the boss database.
        
        Args:
            db_path: Path to the bosses.json file
            app_dir: Application directory (for finding default bosses.json)
        """
        logger.info(f"[INIT] Initializing BossDatabase")
        logger.info(f"[INIT] Database path: {db_path}")
        logger.info(f"[INIT] App directory: {app_dir}")
        
        self.db_path = Path(db_path)
        self.app_dir = app_dir
        self.bosses: List[Dict] = []
        
        logger.info(f"[INIT] Step 1: Initializing with defaults")
        self._initialize_with_defaults()
        
        logger.info(f"[INIT] Step 2: Loading existing database")
        self.load()
        
        # After loading, merge defaults again to ensure respawn times are applied
        # (This handles the case where file existed but defaults weren't merged)
        logger.info(f"[INIT] Step 3: Merging defaults into loaded data")
        if self.app_dir:
            default_bosses_path = self.app_dir / "default_bosses.json"
            if not default_bosses_path.exists():
                default_bosses_path = self.app_dir / "data" / "bosses.json"
            if not default_bosses_path.exists():
                default_bosses_path = self.app_dir / "assets" / "bosses.json"
            if not default_bosses_path.exists():
                default_bosses_path = self.app_dir / "bosses.json"
            if default_bosses_path.exists():
                logger.info(f"[INIT] Found default file: {default_bosses_path}")
                self._merge_defaults(default_bosses_path)
            else:
                logger.info(f"[INIT] No default bosses.json found - skipping merge")
        
        logger.info(f"[INIT] Initialization complete: {len(self.bosses)} bosses loaded")
    
    def _initialize_with_defaults(self) -> None:
        """Initialize database with default bosses if it doesn't exist, or merge defaults into existing."""
        if not self.app_dir:
            return
        
        # Look for default bosses.json in app directory (for packaged apps)
        # Check in order: data/bosses.json, assets/bosses.json, bosses.json, default_bosses.json
        default_bosses_path = self.app_dir / "data" / "bosses.json"
        if not default_bosses_path.exists():
            default_bosses_path = self.app_dir / "assets" / "bosses.json"
        if not default_bosses_path.exists():
            default_bosses_path = self.app_dir / "bosses.json"
        if not default_bosses_path.exists():
            # Also check for default_bosses.json in root (for development)
            default_bosses_path = self.app_dir / "default_bosses.json"
        
        if not default_bosses_path.exists():
            logger.debug(f"[RESPAWN] No default bosses.json found, skipping initialization")
            return
        
        if not self.db_path.exists():
            # First time - copy defaults
            try:
                logger.info(f"[RESPAWN] Found default bosses.json at {default_bosses_path}, copying to user data directory")
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(default_bosses_path, self.db_path)
                logger.info(f"[RESPAWN] Copied default bosses.json to {self.db_path}")
            except Exception as e:
                logger.warning(f"Could not copy default bosses.json: {e}")
        else:
            # User file exists - don't merge here, wait until after load()
            # This prevents double-merging and potential data loss
            # Merge will happen in __init__ after load() completes
            logger.debug(f"[RESPAWN] User bosses.json exists - will merge defaults after load")
    
    def _merge_defaults(self, default_bosses_path: Path) -> None:
        """
        Merge default bosses into existing bosses, preserving user data but adding defaults.
        
        This ensures:
        - Respawn times from defaults are applied to existing bosses
        - User data (kill times, enabled status, notes) is preserved
        - New bosses from defaults are added
        """
        try:
            # Load defaults
            with open(default_bosses_path, 'r', encoding='utf-8') as f:
                default_data = json.load(f)
                default_bosses = default_data.get('bosses', [])
            
            # Load existing bosses (they're already loaded in self.bosses, but we need to check file)
            recovered_from_backup = False
            if not self.bosses:
                # Load from main file first
                if self.db_path.exists():
                    existing_bosses = self._load_bosses_from_path(self.db_path)
                    existing_bosses = existing_bosses if existing_bosses is not None else []
                else:
                    existing_bosses = []
                # If main file had no bosses (empty or corrupt), try most recent backup to avoid losing notes
                if not existing_bosses:
                    backup_path = self._get_most_recent_backup_path()
                    if backup_path:
                        from_backup = self._load_bosses_from_path(backup_path)
                        if from_backup:
                            existing_bosses = from_backup
                            recovered_from_backup = True
                            logger.warning(
                                f"[MERGE] Load failed or empty; recovered {len(existing_bosses)} boss(es) from backup {backup_path.name} to preserve notes"
                            )
            else:
                existing_bosses = self.bosses
            
            # Create lookup by name+location+note for existing bosses
            # This ensures duplicate bosses (same name, different notes) are handled correctly
            existing_lookup = {}
            notes_logged = {}  # Track notes for logging
            for boss in existing_bosses:
                # Use note in key to distinguish duplicate bosses (e.g., "Thall Va Xakra" North vs South)
                note = boss.get('note', '').strip()
                key = (boss['name'].lower(), boss.get('location', '').lower(), note.lower())
                existing_lookup[key] = boss
                # Track notes for logging
                boss_name = boss.get('name', 'unknown')
                if boss_name not in notes_logged:
                    notes_logged[boss_name] = []
                notes_logged[boss_name].append(note if note else '(no note)')
            
            # Log notes before merge
            logger.info(f"[MERGE] Existing bosses notes summary:")
            for boss_name, notes_list in sorted(notes_logged.items()):
                if len(notes_list) > 1 or (len(notes_list) == 1 and notes_list[0] != '(no note)'):
                    logger.info(f"[MERGE]   '{boss_name}': {notes_list}")
            
            # Track what we're merging
            respawn_times_added = 0
            respawn_times_updated = 0
            new_bosses_added = 0
            
            # Merge defaults into existing
            # CRITICAL: Only add missing entries, NEVER overwrite user notes or existing entries
            for default_boss in default_bosses:
                default_name = default_boss['name']
                default_location = default_boss.get('location', '')
                default_note = default_boss.get('note', '').strip()
                key = (default_name.lower(), default_location.lower(), default_note.lower())
                
                logger.debug(f"[MERGE] Processing default boss: '{default_name}' in '{default_location}' with note '{default_note}' (key: {key})")
                
                if key in existing_lookup:
                    logger.debug(f"[MERGE] Boss '{default_name}'{f' (note: {default_note})' if default_note else ''} already exists - preserving user data")
                    # Boss exists - ONLY merge respawn time if missing, NEVER touch notes or other user data
                    existing_boss = existing_lookup[key]
                    
                    # Add respawn time from defaults ONLY if field is completely missing (not just None)
                    # This preserves user data: if user explicitly set respawn_hours to None or removed it, we respect that
                    if 'respawn_hours' in default_boss and default_boss['respawn_hours'] is not None:
                        existing_respawn = existing_boss.get('respawn_hours')
                        
                        # Only add default if field doesn't exist at all (never been set)
                        # If field exists (even if None), user has explicitly managed it - don't overwrite
                        if 'respawn_hours' not in existing_boss:
                            # Use default from defaults file if available, otherwise use DEFAULT_RESPAWN_HOURS
                            default_respawn = default_boss.get('respawn_hours') or DEFAULT_RESPAWN_HOURS
                            existing_boss['respawn_hours'] = default_respawn
                            existing_boss['respawn_hours_is_default'] = True
                            respawn_times_added += 1
                            logger.info(f"[RESPAWN] Added respawn time {default_respawn}h to '{default_name}' from defaults (field was missing)")
                        elif existing_respawn is not None:
                            # Apply default file's respawn when existing has global default (162h)
                            # So lockout bosses in default_bosses with 66h (2d 18h) override the 162h
                            if (existing_respawn == DEFAULT_RESPAWN_HOURS and
                                default_boss['respawn_hours'] is not None and
                                default_boss['respawn_hours'] != DEFAULT_RESPAWN_HOURS):
                                existing_boss['respawn_hours'] = default_boss['respawn_hours']
                                existing_boss['respawn_hours_is_default'] = True
                                respawn_times_updated += 1
                                logger.info(f"[RESPAWN] Applied default respawn {default_boss['respawn_hours']}h to '{default_name}' from defaults (overrode 162h)")
                            elif existing_boss.get('respawn_hours_is_default'):
                                existing_boss.pop('respawn_hours_is_default', None)
                                logger.info(f"[RESPAWN] Cleared default flag for '{default_name}' - user has respawn time {existing_respawn}h set")
                            
                            if existing_respawn != default_boss['respawn_hours'] and not (existing_boss.get('respawn_hours') == default_boss['respawn_hours']):
                                # User has different respawn time - keep user's value (unless we just applied default above)
                                if existing_boss['respawn_hours'] == existing_respawn:
                                    logger.debug(f"[RESPAWN] Preserving user respawn time {existing_respawn}h for '{default_name}' (default is {default_boss['respawn_hours']}h)")
                            elif existing_boss.get('respawn_hours') == default_boss['respawn_hours']:
                                logger.debug(f"[RESPAWN] User respawn time matches default for '{default_name}' - kept default")
                        elif existing_respawn is None:
                            # Field exists but is None - user may have explicitly removed it
                            # Don't overwrite None values - respect user's choice
                            logger.debug(f"[RESPAWN] Preserving None respawn time for '{default_name}' (user may have explicitly removed it)")
                    
                    # Ensure location is set if missing (but don't overwrite existing)
                    if not existing_boss.get('location') and default_location:
                        existing_boss['location'] = default_location
                    
                    # CRITICAL: NEVER overwrite user notes - preserve them exactly as they are
                    # The note matching by key ensures we only merge entries with matching notes
                else:
                    # New boss from defaults - add it ONLY if no entry with same name+location exists
                    # Check if there's an existing entry with same name+location but different note
                    # If so, don't add - user may have custom notes
                    has_similar_entry = False
                    for existing_boss in existing_bosses:
                        if (existing_boss.get('name', '').lower() == default_name.lower() and
                            existing_boss.get('location', '').lower() == default_location.lower()):
                            # Found an entry with same name+location
                            existing_note = (existing_boss.get('note', '') or '').strip()
                            if existing_note != default_note:
                                # Different note - user has custom note, don't add default
                                logger.debug(f"[MERGE] Skipping default '{default_name}' (note: '{default_note}') - user has entry with note '{existing_note}'")
                                has_similar_entry = True
                                break
                    
                    if not has_similar_entry:
                        # Safe to add - no conflicting user entry
                        new_boss = default_boss.copy()
                        # Reset kill data for new bosses (they're defaults, not user kills)
                        new_boss['kill_count'] = 0
                        new_boss['last_killed'] = None
                        new_boss['last_killed_timestamp'] = None
                        # Keep enabled status from defaults
                        # If no respawn time in default, set default respawn time and mark as default
                        if 'respawn_hours' not in new_boss or new_boss.get('respawn_hours') is None:
                            new_boss['respawn_hours'] = DEFAULT_RESPAWN_HOURS
                            new_boss['respawn_hours_is_default'] = True
                            logger.debug(f"[RESPAWN] Set default respawn time {DEFAULT_RESPAWN_HOURS}h for new boss '{default_name}'")
                        existing_bosses.append(new_boss)
                        new_bosses_added += 1
                        note_info = f" (note: '{default_note}')" if default_note else " (no note)"
                        logger.info(f"[MERGE] Added new boss '{default_name}'{note_info} from defaults (location: {default_location})")
            
            # Cleanup: Remove incorrect duplicates for bosses that shouldn't be duplicated
            # Kaas Thox Xi Ans Dyek should NOT have North/South Blob variants - remove them if they exist
            cleanup_incorrect_duplicates = [
                ("Kaas Thox Xi Ans Dyek", "Vex Thal", ["North Blob", "South Blob"]),
            ]
            
            for boss_name, location, incorrect_notes in cleanup_incorrect_duplicates:
                bosses_to_remove = []
                for boss in existing_bosses:
                    if (boss.get('name', '').lower() == boss_name.lower() and 
                        boss.get('location', '').lower() == location.lower()):
                        note = (boss.get('note', '') or '').strip()
                        if note.lower() in [n.lower() for n in incorrect_notes]:
                            # This is an incorrect duplicate - remove it
                            bosses_to_remove.append(boss)
                            logger.warning(f"[MERGE] Removing incorrect duplicate '{boss_name}' with note '{note}' (should not be duplicated)")
                
                if bosses_to_remove:
                    for boss_to_remove in bosses_to_remove:
                        if boss_to_remove in existing_bosses:
                            existing_bosses.remove(boss_to_remove)
                            logger.info(f"[MERGE] Removed incorrect duplicate entry for '{boss_name}'")
            
            # Post-merge: Ensure duplicate bosses with notes are present
            # Check for known duplicate bosses that should have North/South variants
            # ONLY add if missing - NEVER overwrite user's custom notes
            # NOTE: Kaas Thox Xi Ans Dyek is NOT a duplicate - it's a single boss
            duplicate_boss_configs = [
                ("Thall Va Xakra", "Vex Thal", ["F1 North", "F1 South"]),
                ("Kaas Thox Xi Aten Ha Ra", "Vex Thal", ["North Blob", "South Blob"]),
            ]
            
            for boss_name, location, required_notes in duplicate_boss_configs:
                existing_notes = set()
                existing_bosses_for_name = []
                bosses_without_notes = []
                
                for boss in existing_bosses:
                    if (boss.get('name', '').lower() == boss_name.lower() and 
                        boss.get('location', '').lower() == location.lower()):
                        note = (boss.get('note', '') or '').strip()
                        existing_notes.add(note.lower())
                        existing_bosses_for_name.append((note, boss))
                        if not note:
                            bosses_without_notes.append(boss)
                
                logger.info(f"[MERGE] Checking duplicate boss '{boss_name}': found {len(existing_bosses_for_name)} entries")
                logger.info(f"[MERGE]   Existing notes: {sorted(existing_notes)}")
                logger.info(f"[MERGE]   Required notes: {required_notes}")
                logger.info(f"[MERGE]   Entries without notes: {len(bosses_without_notes)}")
                
                # Add missing North/South variants ONLY if they don't exist
                # NEVER overwrite or remove user's custom notes
                for required_note in required_notes:
                    note_lower = required_note.lower()
                    if note_lower not in existing_notes:
                        # Check if user has ANY entries with custom notes for this boss
                        # If so, don't add defaults - user may have their own system
                        has_custom_notes = any(note and note.lower() not in [n.lower() for n in required_notes] 
                                              for note in existing_notes if note)
                        
                        if has_custom_notes:
                            logger.info(f"[MERGE] Skipping default note '{required_note}' for '{boss_name}' - user has custom notes (preserving user data)")
                        else:
                            logger.info(f"[MERGE] Adding missing variant: '{boss_name}' (note: '{required_note}')")
                            new_boss = {
                                'name': boss_name,
                                'location': location,
                                'enabled': True,
                                'kill_count': 0,
                                'last_killed': None,
                                'last_killed_timestamp': None,
                                'respawn_hours': DEFAULT_RESPAWN_HOURS,
                                'respawn_hours_is_default': True,
                                'note': required_note
                            }
                            existing_bosses.append(new_boss)
                            new_bosses_added += 1
                            existing_notes.add(note_lower)
                            logger.info(f"[MERGE] ✓ Added '{boss_name}' with note '{required_note}'")
                    else:
                        logger.info(f"[MERGE] ✓ Boss '{boss_name}' with note '{required_note}' already exists")
                
                # Cleanup: Remove entries without notes when North/South variants exist
                # Since North/South are the canonical entries, remove generic entries even if they have data
                # (The data should have been recorded to North/South, not the generic entry)
                north_exists = any(note.lower() == required_notes[0].lower() for note in existing_notes)
                south_exists = any(note.lower() == required_notes[1].lower() for note in existing_notes)
                
                if north_exists and south_exists and len(bosses_without_notes) > 0:
                    bosses_to_remove = []
                    for boss_to_check in bosses_without_notes:
                        # Check if entry has kill data (for logging)
                        has_kill_data = (boss_to_check.get('last_killed') or 
                                        boss_to_check.get('kill_count', 0) > 0)
                        
                        # Remove entries without notes when North/South exist
                        # Even if they have data, they should be removed since North/South are the canonical entries
                        bosses_to_remove.append(boss_to_check)
                        
                        if has_kill_data:
                            logger.info(f"[MERGE] Removing '{boss_name}' entry without note (had kill data; North/South variants are canonical)")
                    
                    if bosses_to_remove:
                        logger.info(f"[MERGE] Removing {len(bosses_to_remove)} duplicate '{boss_name}' entries without notes (North/South variants exist)")
                        for boss_to_remove in bosses_to_remove:
                            if boss_to_remove in existing_bosses:
                                existing_bosses.remove(boss_to_remove)
                                logger.info(f"[MERGE] Removed duplicate entry without note (has North/South variants)")
            
            # Cleanup: Remove respawn_hours_is_default flag from bosses that shouldn't have it
            # This fixes cases where the flag was incorrectly set during previous merges
            cleanup_count = 0
            for boss in existing_bosses:
                if boss.get('respawn_hours_is_default') and boss.get('respawn_hours') is not None:
                    boss_name = boss.get('name', 'unknown')
                    boss_note = boss.get('note', '').strip()
                    # Clear flag if:
                    # 1. Boss has kill data (last_killed or kill_count > 0) - it's been used
                    # 2. Boss has a respawn time that's NOT the default (user set a custom time)
                    # 3. Boss has a respawn time that EXISTS (even if it matches default) - user may have set it manually
                    #    We can't distinguish between "user set 66.0" vs "default is 66.0", so if respawn_hours exists,
                    #    assume it was user-set and clear the flag
                    respawn_hours = boss.get('respawn_hours')
                    has_kill_data = boss.get('last_killed') or boss.get('kill_count', 0) > 0
                    is_custom_respawn = respawn_hours != DEFAULT_RESPAWN_HOURS
                    has_respawn_time = respawn_hours is not None
                    
                    # Clear flag if boss has any indication it was user-configured
                    # If respawn_hours exists and is not None, assume user set it (even if it matches default)
                    if has_kill_data or is_custom_respawn or has_respawn_time:
                        boss.pop('respawn_hours_is_default', None)
                        cleanup_count += 1
                        if has_kill_data:
                            reason = "has kill data"
                        elif is_custom_respawn:
                            reason = "has custom respawn time"
                        else:
                            reason = "has respawn time set (presumed user-configured)"
                        logger.info(f"[MERGE] Cleaned up default flag for '{boss_name}'{f' (note: {boss_note})' if boss_note else ''} - {reason}")
            
            if cleanup_count > 0:
                logger.info(f"[MERGE] Cleaned up respawn_hours_is_default flag for {cleanup_count} boss(es)")
            
            # Update self.bosses BEFORE checking for missing variants
            # This ensures we're working with the latest merged data
            self.bosses = existing_bosses
            logger.info(f"[MERGE] Updated in-memory boss list: {len(existing_bosses)} bosses")

            # If we recovered from backup, restore main file so next run loads normally
            if recovered_from_backup:
                logger.info("[MERGE] Restoring main bosses file from recovered data so notes persist")
                self.save()

            # Log notes after merge to verify they're preserved
            notes_after_merge = {}
            for boss in existing_bosses:
                boss_name = boss.get('name', 'unknown')
                note = boss.get('note', '').strip()
                if boss_name not in notes_after_merge:
                    notes_after_merge[boss_name] = []
                notes_after_merge[boss_name].append(note if note else '(no note)')
            
            logger.info(f"[MERGE] Bosses notes after merge:")
            for boss_name, notes_list in sorted(notes_after_merge.items()):
                if len(notes_list) > 1 or (len(notes_list) == 1 and notes_list[0] != '(no note)'):
                    logger.info(f"[MERGE]   '{boss_name}': {notes_list}")
            
            # Check for any notes that were lost (except intentional removal of no-note duplicate)
            for boss_name in set(notes_logged.keys()) | set(notes_after_merge.keys()):
                before_notes = set(notes_logged.get(boss_name, []))
                after_notes = set(notes_after_merge.get(boss_name, []))
                if before_notes != after_notes:
                    lost_notes = before_notes - after_notes
                    if lost_notes and lost_notes != {'(no note)'}:
                        logger.error(f"[MERGE] ERROR: Lost notes for '{boss_name}': {lost_notes}")
                    elif lost_notes == {'(no note)'}:
                        logger.info(f"[MERGE] Removed duplicate '{boss_name}' entry without note (North/South variants are canonical)")
            
            # Post-check: Only add missing North/South if user doesn't have custom notes
            # NEVER add defaults if user has custom notes - preserve user's system
            for boss_name, location, required_notes in duplicate_boss_configs:
                current_notes = set()
                has_custom_notes = False
                for boss in self.bosses:
                    if (boss.get('name', '').lower() == boss_name.lower() and 
                        boss.get('location', '').lower() == location.lower()):
                        note = (boss.get('note', '') or '').strip()
                        current_notes.add(note.lower())
                        # Check if user has custom notes (not in our required list)
                        if note and note.lower() not in [n.lower() for n in required_notes]:
                            has_custom_notes = True
                
                # Only add missing variants if user doesn't have custom notes
                if not has_custom_notes:
                    for required_note in required_notes:
                        if required_note.lower() not in current_notes:
                            logger.info(f"[MERGE] POST-CHECK: Adding missing '{boss_name}' (note: '{required_note}')")
                            new_boss = {
                                'name': boss_name,
                                'location': location,
                                'enabled': True,
                                'kill_count': 0,
                                'last_killed': None,
                                'last_killed_timestamp': None,
                                'respawn_hours': DEFAULT_RESPAWN_HOURS,
                                'respawn_hours_is_default': True,
                                'note': required_note
                            }
                            self.bosses.append(new_boss)
                            new_bosses_added += 1
                            logger.info(f"[MERGE] ✓ POST-CHECK: Added '{boss_name}' with note '{required_note}'")
                else:
                    logger.info(f"[MERGE] POST-CHECK: Skipping '{boss_name}' - user has custom notes (preserving user data)")
            
            # Save if any changes were made
            if respawn_times_added > 0 or respawn_times_updated > 0 or new_bosses_added > 0 or cleanup_count > 0:
                logger.info(f"[MERGE] Changes detected - saving database")
                logger.info(f"[MERGE] Summary: {respawn_times_added} respawn times added, "
                           f"{respawn_times_updated} updated, {new_bosses_added} new bosses added, "
                           f"{cleanup_count} default flags cleaned up")
                self.save()
                logger.info(f"[MERGE] Merge and save completed successfully")
            else:
                logger.info(f"[MERGE] No changes needed - all defaults already present in user data")
                
        except Exception as e:
            logger.error(f"[RESPAWN] Error merging defaults: {e}", exc_info=True)
    
    def load(self) -> None:
        """Load bosses from JSON file."""
        logger.info(f"[LOAD] Starting load operation from: {self.db_path}")
        
        if self.db_path.exists():
            try:
                file_size = self.db_path.stat().st_size
                file_mtime = datetime.fromtimestamp(self.db_path.stat().st_mtime)
                logger.info(f"[LOAD] File exists: {self.db_path}")
                logger.info(f"[LOAD] File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
                logger.info(f"[LOAD] File modified: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bosses = data.get('bosses', [])
                
                total_bosses = len(self.bosses)
                logger.info(f"[LOAD] Loaded {total_bosses} boss(es) from file")
                
                # Detailed statistics
                respawn_count = sum(1 for boss in self.bosses if boss.get('respawn_hours') is not None)
                enabled_count = sum(1 for boss in self.bosses if boss.get('enabled', False))
                kill_count_total = sum(boss.get('kill_count', 0) for boss in self.bosses)
                bosses_with_kills = sum(1 for boss in self.bosses if boss.get('kill_count', 0) > 0)
                bosses_with_notes = sum(1 for boss in self.bosses if boss.get('note', '').strip())
                
                logger.info(f"[LOAD] Boss statistics: enabled={enabled_count}, "
                           f"with_respawn_times={respawn_count}, with_kills={bosses_with_kills}, "
                           f"total_kills={kill_count_total}, with_notes={bosses_with_notes}")
                
                if respawn_count > 0:
                    logger.info(f"[LOAD] {respawn_count}/{total_bosses} boss(es) have respawn times")
                    if respawn_count < total_bosses:
                        missing = total_bosses - respawn_count
                        logger.info(f"[LOAD] {missing} boss(es) missing respawn times - defaults will be merged after load")
                else:
                    logger.info(f"[LOAD] No respawn times in loaded bosses - defaults will be merged after load")
                
                # #region agent log
                debug_log("boss_database.py:61", "Bosses loaded into memory", {
                    "boss_count": len(self.bosses),
                    "estimated_size_mb": len(str(data)) / 1024 / 1024
                }, hypothesis_id="B", run_id="initial")
                
                try:
                    import psutil
                    process = psutil.Process()
                    mem_info = process.memory_info()
                    debug_log("boss_database.py:61", "Memory after loading bosses", {
                        "rss_mb": mem_info.rss / 1024 / 1024,
                        "vms_mb": mem_info.vms / 1024 / 1024
                    }, hypothesis_id="B", run_id="initial")
                except ImportError:
                    pass
                # #endregion

                # Remove per-boss webhook_url if present (all bosses use settings webhook only)
                for boss in self.bosses:
                    boss.pop('webhook_url', None)

                # After loading, set default respawn times for bosses that don't have one
                # This ensures all bosses have a respawn time (default 6d 18h) until user sets it
                # BUT: Only set the default flag if the respawn time was actually missing (not just None)
                # IMPORTANT: Don't mark existing respawn times as default, even if they match DEFAULT_RESPAWN_HOURS
                default_set_count = 0
                for boss in self.bosses:
                    # Only set default if respawn_hours field is completely missing
                    # If it exists (even if None), don't touch it - user may have explicitly removed it
                    if 'respawn_hours' not in boss:
                        boss['respawn_hours'] = DEFAULT_RESPAWN_HOURS
                        boss['respawn_hours_is_default'] = True
                        default_set_count += 1
                        logger.info(f"[LOAD] Set default respawn time {DEFAULT_RESPAWN_HOURS}h for '{boss.get('name', 'unknown')}' (field was missing)")
                    elif boss.get('respawn_hours') is None:
                        # Field exists but is None - don't set default, user may have explicitly removed it
                        logger.debug(f"[LOAD] Boss '{boss.get('name', 'unknown')}' has respawn_hours=None - not setting default (user may have removed it)")
                    elif boss.get('respawn_hours_is_default') and boss.get('respawn_hours') is not None:
                        # Boss has respawn_hours_is_default flag but also has a respawn time
                        # This shouldn't happen, but if it does, clear the flag if respawn time exists
                        # (user may have set a respawn time but flag wasn't cleared)
                        logger.debug(f"[LOAD] Boss '{boss.get('name', 'unknown')}' has respawn_hours={boss.get('respawn_hours')} but also has default flag - keeping respawn time")
                    # If respawn_hours exists and has a value, don't touch it (preserve user data)
                
                if default_set_count > 0:
                    logger.info(f"[LOAD] Set default respawn times for {default_set_count} boss(es) missing respawn times")
                    # Save the updated bosses with default respawn times
                    self.save()
                
                logger.info(f"[LOAD] Load operation completed successfully")
            except json.JSONDecodeError as e:
                logger.error(f"[LOAD] ERROR: Invalid JSON in {self.db_path}: {e}", exc_info=True)
                logger.error(f"[LOAD] File may be corrupted. Check backups folder for previous version.")
                self.bosses = []
            except IOError as e:
                logger.error(f"[LOAD] ERROR: Could not read {self.db_path}: {e}", exc_info=True)
                self.bosses = []
            except Exception as e:
                logger.error(f"[LOAD] UNEXPECTED ERROR loading database: {e}", exc_info=True)
                self.bosses = []
        else:
            logger.warning(f"[LOAD] Boss database file not found at {self.db_path}")
            logger.info(f"[LOAD] Will create new database on first save")
            self.bosses = []
    
    def _get_backup_dir(self) -> Path:
        """Return the backups directory path (same as used by _create_backup)."""
        return self.db_path.parent / "backups"

    def _get_most_recent_backup_path(self) -> Optional[Path]:
        """Return the path of the most recent backup file, or None if none exist."""
        backup_dir = self._get_backup_dir()
        if not backup_dir.exists():
            return None
        backups = sorted(
            backup_dir.glob("bosses_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return backups[0] if backups else None

    def _load_bosses_from_path(self, path: Path) -> Optional[List[Dict]]:
        """Load and return bosses list from a JSON file, or None on error."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("bosses", [])
        except Exception as e:
            logger.warning(f"[RECOVERY] Could not load from {path.name}: {e}")
            return None

    def _create_backup(self) -> Optional[Path]:
        """Create a backup of the current bosses.json file before saving."""
        if not self.db_path.exists():
            logger.debug(f"[BACKUP] No existing file to backup: {self.db_path}")
            return None
        
        try:
            file_size = self.db_path.stat().st_size
            logger.info(f"[BACKUP] Creating backup of {self.db_path} (size: {file_size} bytes)")

            backup_dir = self._get_backup_dir()
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Create backup filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"bosses_backup_{timestamp}.json"
            
            shutil.copy2(self.db_path, backup_path)
            backup_size = backup_path.stat().st_size
            
            # Keep last 20 backups so users have more restore points if notes are lost
            backups = sorted(backup_dir.glob("bosses_backup_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            removed_count = 0
            for old_backup in backups[20:]:
                try:
                    old_backup.unlink()
                    removed_count += 1
                    logger.debug(f"[BACKUP] Removed old backup: {old_backup.name}")
                except Exception as e:
                    logger.warning(f"[BACKUP] Could not remove old backup {old_backup.name}: {e}")
            
            logger.info(f"[BACKUP] Backup created successfully: {backup_path.name} ({backup_size} bytes)")
            logger.info(f"[BACKUP] Total backups: {len(backups)}, removed {removed_count} old backups")
            return backup_path
        except Exception as e:
            logger.error(f"[BACKUP] ERROR creating backup: {e}", exc_info=True)
            return None
    
    def create_manual_backup(self) -> Optional[Path]:
        """
        Manually create a backup of the current bosses.json file.
        This can be called from the UI to create a backup on demand.
        
        Returns:
            Path to the created backup file, or None if backup failed
        """
        return self._create_backup()
    
    def save(self) -> None:
        """Save bosses to JSON file."""
        logger.info(f"[SAVE] Starting save operation - {len(self.bosses)} bosses in memory")
        logger.info(f"[SAVE] Target file: {self.db_path}")

        try:
            # Create backup before saving (if file exists)
            backup_path = self._create_backup()
            if backup_path:
                logger.info(f"[SAVE] Backup created: {backup_path.name}")
            elif self.db_path.exists():
                logger.warning(f"[SAVE] No backup created (file exists but backup failed)")

            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create a copy of bosses for saving; do not persist webhook_url (all bosses use settings webhook)
            bosses_to_save = []
            for boss in self.bosses:
                boss_copy = boss.copy()
                boss_copy.pop('webhook_url', None)
                bosses_to_save.append(boss_copy)

            # Log detailed statistics
            respawn_count = sum(1 for boss in bosses_to_save if boss.get('respawn_hours') is not None)
            enabled_count = sum(1 for boss in bosses_to_save if boss.get('enabled', False))
            kill_count_total = sum(boss.get('kill_count', 0) for boss in bosses_to_save)
            bosses_with_kills = sum(1 for boss in bosses_to_save if boss.get('kill_count', 0) > 0)
            bosses_with_notes = sum(1 for boss in bosses_to_save if boss.get('note', '').strip())

            logger.info(f"[SAVE] Boss statistics: total={len(bosses_to_save)}, enabled={enabled_count}, "
                       f"with_respawn_times={respawn_count}, with_kills={bosses_with_kills}, "
                       f"total_kills={kill_count_total}, with_notes={bosses_with_notes}")
            
            # Log bosses with notes to verify they're being saved
            if bosses_with_notes > 0:
                logger.info(f"[SAVE] Saving {bosses_with_notes} boss(es) with notes:")
                for boss in bosses_to_save:
                    note = boss.get('note', '').strip()
                    if note:
                        logger.info(f"[SAVE]   - '{boss.get('name')}': note='{note}'")
            
            # Log respawn times being saved
            if respawn_count > 0:
                logger.info(f"[SAVE] Saving {respawn_count} boss(es) with respawn times")
                for boss in bosses_to_save:
                    if boss.get('respawn_hours') is not None:
                        logger.info(f"[SAVE]   - '{boss.get('name')}': {boss.get('respawn_hours')} hours respawn")
            
            # Write file
            file_size_before = self.db_path.stat().st_size if self.db_path.exists() else 0
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({'bosses': bosses_to_save}, f, indent=2, ensure_ascii=False)
            
            file_size_after = self.db_path.stat().st_size
            logger.info(f"[SAVE] File written successfully: {self.db_path}")
            logger.info(f"[SAVE] File size: {file_size_before} -> {file_size_after} bytes "
                       f"({file_size_after - file_size_before:+d} bytes)")
            logger.info(f"[SAVE] Save operation completed successfully")
            
        except IOError as e:
            logger.error(f"[SAVE] ERROR saving boss database to {self.db_path}: {e}", exc_info=True)
            if backup_path:
                logger.info(f"[SAVE] Previous version backed up at: {backup_path}")
            raise
        except Exception as e:
            logger.error(f"[SAVE] UNEXPECTED ERROR during save: {e}", exc_info=True)
            if backup_path:
                logger.info(f"[SAVE] Previous version backed up at: {backup_path}")
            raise
    
    def exists(self, monster_name: str) -> bool:
        """Check if a monster exists in the database."""
        return any(boss['name'].lower() == monster_name.lower() for boss in self.bosses)
    
    def get_boss(self, monster_name: str) -> Optional[Dict]:
        """Get a boss entry by name."""
        for boss in self.bosses:
            if boss['name'].lower() == monster_name.lower():
                return boss
        return None
    
    def get_bosses_by_name(self, monster_name: str) -> List[Dict]:
        """
        Get all boss entries with the same name (case-insensitive).
        
        Args:
            monster_name: Name of the monster
            
        Returns:
            List of boss dictionaries with matching names
        """
        matching_bosses = []
        name_lower = monster_name.lower()
        for boss in self.bosses:
            if boss['name'].lower() == name_lower:
                matching_bosses.append(boss)
        return matching_bosses
    
    def add_boss(self, monster_name: str, location: Optional[str] = None,
                  enabled: bool = False, note: Optional[str] = None) -> Dict:
        """
        Add a new boss to the database.

        All bosses use the webhook URL from Options (settings); there is no per-boss webhook.

        Args:
            monster_name: Name of the monster
            location: Zone/location where the boss is found
            enabled: Whether Discord notifications are enabled for this boss
            note: Optional note/nickname for the boss

        Returns:
            The created boss entry
        """
        # Special cases: Allow duplicates for these two bosses (they have North/South versions)
        duplicate_allowed_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
        allow_duplicate = monster_name in duplicate_allowed_names
        
        if not allow_duplicate and self.exists(monster_name):
            boss = self.get_boss(monster_name)
            logger.debug(f"Boss '{monster_name}' already exists in database")
            # Update location if provided and not already set
            if location and not boss.get('location'):
                boss['location'] = location
                logger.info(f"Updated location for '{monster_name}': {location}")
                self.save()
            # Update note if provided and different
            if note and boss.get('note') != note:
                boss['note'] = note
                logger.info(f"Updated note for '{monster_name}': {note}")
                self.save()
            return boss
        
        boss = {
            'name': monster_name,
            'location': location or '',
            'enabled': enabled,
            'first_seen': datetime.now().isoformat(),
            'kill_count': 0,
            'last_killed': None,
            'last_killed_timestamp': None,  # Original log timestamp string
            'respawn_hours': None,  # Respawn time in hours (can be set later)
            'note': note or ''  # Optional note/nickname for the boss
        }
        
        self.bosses.append(boss)
        logger.info(f"[ADD] Added new boss: '{monster_name}' in '{location or 'Unknown'}' (enabled: {enabled}, note: '{note or 'none'}')")
        logger.info(f"[ADD] Total bosses now: {len(self.bosses)}")
        self.save()
        return boss
    
    def enable_boss(self, monster_name: str, note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Enable Discord notifications for a boss.
        
        Args:
            monster_name: Name of the monster
            note: Optional note to identify specific boss (for duplicates)
            boss: Optional boss dictionary to enable directly (most reliable for duplicates)
            
        Returns:
            True if boss was enabled, False otherwise
        """
        # If boss dict is provided, use it directly (most reliable for duplicates)
        if boss:
            boss['enabled'] = True
            logger.info(f"Enabled Discord notifications for '{monster_name}' ({boss.get('note', 'no note')})")
            self.save()
            return True
        
        # Otherwise, try to find by name and note
        if note:
            note_stripped = note.strip()
            boss = next(
                (b for b in self.bosses 
                 if b['name'].lower() == monster_name.lower() and (b.get('note', '').strip() == note_stripped)),
                None
            )
            if boss:
                boss['enabled'] = True
                logger.info(f"Enabled Discord notifications for '{monster_name}' (note: '{note}')")
                self.save()
                return True
        else:
            # Fallback: use get_boss (returns first match)
            boss = self.get_boss(monster_name)
            if boss:
                boss['enabled'] = True
                logger.info(f"Enabled Discord notifications for '{monster_name}'")
                self.save()
                return True
        
        logger.warning(f"Attempted to enable non-existent boss: {monster_name}")
        return False
    
    def disable_boss(self, monster_name: str, note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Disable Discord notifications for a boss.
        
        Args:
            monster_name: Name of the monster
            note: Optional note to identify specific boss (for duplicates)
            boss: Optional boss dictionary to disable directly (most reliable for duplicates)
            
        Returns:
            True if boss was disabled, False otherwise
        """
        # If boss dict is provided, use it directly (most reliable for duplicates)
        if boss:
            boss['enabled'] = False
            logger.info(f"Disabled Discord notifications for '{monster_name}' ({boss.get('note', 'no note')})")
            self.save()
            return True
        
        # Otherwise, try to find by name and note
        if note:
            note_stripped = note.strip()
            boss = next(
                (b for b in self.bosses 
                 if b['name'].lower() == monster_name.lower() and (b.get('note', '').strip() == note_stripped)),
                None
            )
            if boss:
                boss['enabled'] = False
                logger.info(f"Disabled Discord notifications for '{monster_name}' (note: '{note}')")
                self.save()
                return True
        else:
            # Fallback: use get_boss (returns first match)
            boss = self.get_boss(monster_name)
            if boss:
                boss['enabled'] = False
                logger.info(f"Disabled Discord notifications for '{monster_name}'")
                self.save()
                return True
        
        logger.warning(f"Attempted to disable non-existent boss: {monster_name}")
        return False
    
    def remove_boss(self, monster_name: str, note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Remove a boss from the database.
        
        Args:
            monster_name: Name of the monster
            note: Optional note to identify specific boss (for duplicates)
            boss: Optional boss dictionary to remove directly (most reliable for duplicates)
            
        Returns:
            True if boss was removed, False otherwise
        """
        initial_count = len(self.bosses)
        
        # If boss dict is provided, try identity first (same object as in self.bosses)
        if boss:
            self.bosses = [b for b in self.bosses if b is not boss]
            if len(self.bosses) < initial_count:
                logger.info(f"Removed boss '{monster_name}' ({boss.get('note', 'no note')}) from database")
                self.save()
                return True
            # Identity failed (e.g. boss from UI copy / different ref after reload); match by name and note
            name_to_match = (monster_name or (boss.get('name') or '')).strip()
            note_val = (boss.get('note') or '').strip()
            if name_to_match:
                self.bosses = [
                    b for b in self.bosses
                    if not (b['name'].lower() == name_to_match.lower() and (b.get('note') or '').strip() == note_val)
                ]
            if len(self.bosses) < initial_count:
                logger.info(f"Removed boss '{monster_name}' (note: '{note_val}') from database (by name+note match)")
                self.save()
                return True
        # Otherwise, try to match by name and note
        if note:
            note_stripped = note.strip()
            self.bosses = [
                b for b in self.bosses 
                if not (b['name'].lower() == monster_name.lower() and (b.get('note', '').strip() == note_stripped))
            ]
            if len(self.bosses) < initial_count:
                logger.info(f"Removed boss '{monster_name}' (note: '{note}') from database")
                self.save()
                return True
        # Fallback: remove by name only (removes all with that name)
        else:
            self.bosses = [boss for boss in self.bosses if boss['name'].lower() != monster_name.lower()]
            if len(self.bosses) < initial_count:
                logger.info(f"Removed boss '{monster_name}' from database")
                self.save()
                return True
        
        logger.warning(f"Attempted to remove non-existent boss: {monster_name}")
        return False
    
    def get_enabled_bosses(self) -> List[str]:
        """Get a list of enabled boss names."""
        return [boss['name'] for boss in self.bosses if boss.get('enabled', False)]
    
    def get_all_bosses(self) -> List[Dict]:
        """Get all boss entries."""
        return self.bosses.copy()
    
    def increment_kill_count(self, monster_name: str, kill_timestamp: Optional[str] = None, boss: Optional[Dict] = None) -> None:
        """
        Increment the kill count for a boss.
        
        Args:
            monster_name: Name of the monster (used for lookup if boss not provided)
            kill_timestamp: Optional timestamp string from log (format: "Sat Feb 07 12:34:56 2026")
                          If not provided, uses current datetime
            boss: Optional boss dictionary to update directly (useful for duplicate names)
        """
        # If boss dict is provided, use it directly (for duplicate name handling)
        if boss is None:
            boss = self.get_boss(monster_name)
        
        if boss:
            # Clear default flag if boss has a respawn time set (from UI) and was marked as default
            if boss.get('respawn_hours') is not None and boss.get('respawn_hours_is_default'):
                boss.pop('respawn_hours_is_default', None)
            
            old_count = boss.get('kill_count', 0)
            old_last_killed = boss.get('last_killed')
            boss['kill_count'] = old_count + 1
            
            # Store the actual kill timestamp from the log if provided
            if kill_timestamp:
                try:
                    # Parse log timestamp format: "Sat Feb 07 12:34:56 2026"
                    log_dt = datetime.strptime(kill_timestamp, "%a %b %d %H:%M:%S %Y")
                    boss['last_killed'] = log_dt.isoformat()
                    boss['last_killed_timestamp'] = kill_timestamp  # Store original log timestamp
                    logger.info(f"[KILL] Incremented kill count for '{monster_name}': {old_count} -> {boss['kill_count']}")
                    logger.info(f"[KILL]   Last killed: {kill_timestamp} (was: {old_last_killed or 'never'})")
                except ValueError:
                    # If parsing fails, fall back to current time
                    boss['last_killed'] = datetime.now().isoformat()
                    logger.warning(f"[KILL] Could not parse kill timestamp '{kill_timestamp}' for '{monster_name}', using current time")
                    logger.info(f"[KILL] Incremented kill count for '{monster_name}': {old_count} -> {boss['kill_count']}")
            else:
                boss['last_killed'] = datetime.now().isoformat()
                logger.info(f"[KILL] Incremented kill count for '{monster_name}': {old_count} -> {boss['kill_count']}")
                logger.info(f"[KILL]   Last killed: {boss['last_killed']} (was: {old_last_killed or 'never'})")
            
            self.save()
        else:
            logger.warning(f"[KILL] Attempted to increment kill count for non-existent boss: {monster_name}")
    
    def set_note(self, monster_name: str, note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Set the note/nickname for a boss.
        
        Args:
            monster_name: Name of the monster
            note: Note/nickname text (None or empty string to remove)
            boss: Optional boss dictionary to update directly (useful for duplicate names)
            
        Returns:
            True if note was set, False if boss not found
        """
        # If boss dict is provided, use it directly (for duplicate name handling)
        if boss:
            if note:
                boss['note'] = note.strip()
                logger.info(f"Set note for '{monster_name}' ({boss.get('note', 'no note')}): {note.strip()}")
            else:
                boss.pop('note', None)
                logger.info(f"Removed note for '{monster_name}'")
            self.save()
            return True
        
        # Otherwise, try to find by name and note
        if note:
            note_stripped = note.strip()
            boss = next(
                (b for b in self.bosses 
                 if b['name'].lower() == monster_name.lower() and (b.get('note', '').strip() == note_stripped)),
                None
            )
            if boss:
                boss['note'] = note_stripped
                logger.info(f"Set note for '{monster_name}' (note: '{note}'): {note_stripped}")
                self.save()
                return True
        else:
            # Fallback: use get_boss (returns first match)
            boss = self.get_boss(monster_name)
            if boss:
                boss.pop('note', None)
                logger.info(f"Removed note for '{monster_name}'")
                self.save()
                return True
        
        logger.warning(f"Attempted to set note for non-existent boss: {monster_name}")
        return False
    
    def set_respawn_time(self, monster_name: str, respawn_hours: Optional[float] = None, 
                         note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Set the respawn time for a boss in hours.
        
        Args:
            monster_name: Name of the monster
            respawn_hours: Respawn time in hours (None to remove respawn time)
            note: Optional note to identify specific boss (for duplicates)
            boss: Optional boss dictionary to update directly (useful for duplicate names)
            
        Returns:
            True if boss was found and updated, False otherwise
        """
        # If boss dict is provided, use it directly (for duplicate name handling)
        if boss:
            old_respawn = boss.get('respawn_hours')
            if respawn_hours is not None:
                boss['respawn_hours'] = respawn_hours
                # Clear default flag when user sets a custom respawn time
                boss.pop('respawn_hours_is_default', None)
                note_str = f" (note: '{boss.get('note')}')" if boss.get('note') else ""
                logger.info(f"[RESPAWN] Set respawn time for '{monster_name}'{note_str}: {old_respawn} -> {respawn_hours} hours")
            else:
                boss.pop('respawn_hours', None)
                boss.pop('respawn_hours_is_default', None)
                note_str = f" (note: '{boss.get('note')}')" if boss.get('note') else ""
                logger.info(f"[RESPAWN] Removed respawn time for '{monster_name}'{note_str} (was: {old_respawn} hours)")
            self.save()
            return True
        
        # Otherwise, try to find by name and note
        if note:
            note_stripped = note.strip()
            boss = next(
                (b for b in self.bosses 
                 if b['name'].lower() == monster_name.lower() and (b.get('note', '').strip() == note_stripped)),
                None
            )
            if boss:
                if respawn_hours is not None:
                    boss['respawn_hours'] = respawn_hours
                    # Clear default flag when user sets a custom respawn time
                    boss.pop('respawn_hours_is_default', None)
                    logger.info(f"Set respawn time for '{monster_name}' (note: '{note}'): {respawn_hours} hours")
                else:
                    boss.pop('respawn_hours', None)
                    boss.pop('respawn_hours_is_default', None)
                    logger.info(f"Removed respawn time for '{monster_name}' (note: '{note}')")
                self.save()
                return True
        else:
            # Fallback: use get_boss (returns first match)
            boss = self.get_boss(monster_name)
            if boss:
                if respawn_hours is not None:
                    boss['respawn_hours'] = respawn_hours
                    # Clear default flag when user sets a custom respawn time
                    boss.pop('respawn_hours_is_default', None)
                    logger.info(f"Set respawn time for '{monster_name}': {respawn_hours} hours")
                else:
                    boss.pop('respawn_hours', None)
                    boss.pop('respawn_hours_is_default', None)
                    logger.info(f"Removed respawn time for '{monster_name}'")
                self.save()
                return True
        
        logger.warning(f"Attempted to set respawn time for non-existent boss: {monster_name}")
        return False
    
    def remove_respawn_time(self, monster_name: str, note: Optional[str] = None, boss: Optional[Dict] = None) -> bool:
        """
        Remove respawn time for a boss (convenience method).
        
        Args:
            monster_name: Name of the monster
            note: Optional note to identify specific boss (for duplicates)
            boss: Optional boss dictionary to update directly (useful for duplicate names)
            
        Returns:
            True if boss was found and updated, False otherwise
        """
        return self.set_respawn_time(monster_name, None, note=note, boss=boss)
    
    def get_time_until_respawn(self, monster_name: str) -> Optional[Dict[str, any]]:
        """
        Calculate time until respawn for a boss based on last kill time.
        
        Args:
            monster_name: Name of the monster
            
        Returns:
            Dictionary with:
            - 'hours_remaining': float - hours until respawn (negative if already respawned)
            - 'minutes_remaining': float - minutes until respawn
            - 'is_respawned': bool - True if respawn time has passed
            - 'respawn_time': datetime - when the boss will respawn
            None if boss not found, no respawn time set, or no kill recorded
        """
        boss = self.get_boss(monster_name)
        if not boss:
            return None
        
        respawn_hours = boss.get('respawn_hours')
        if respawn_hours is None:
            return None
        
        last_killed_str = boss.get('last_killed')
        if not last_killed_str:
            return None
        
        try:
            # Parse ISO format datetime
            last_killed = datetime.fromisoformat(last_killed_str)
            
            # Handle timezone-aware vs timezone-naive datetimes
            # If last_killed is timezone-aware, convert to naive (EST) for consistency
            # If it's naive, use as-is
            if last_killed.tzinfo is not None:
                # Convert timezone-aware to naive by removing timezone info
                # (We store in EST, so this is safe)
                last_killed = last_killed.replace(tzinfo=None)
            
            respawn_time = last_killed + timedelta(hours=respawn_hours)
            now = datetime.now()  # This is always naive
            
            time_remaining = respawn_time - now
            hours_remaining = time_remaining.total_seconds() / 3600
            minutes_remaining = time_remaining.total_seconds() / 60
            
            return {
                'hours_remaining': hours_remaining,
                'minutes_remaining': minutes_remaining,
                'is_respawned': hours_remaining <= 0,
                'respawn_time': respawn_time,
                'respawn_time_str': respawn_time.strftime("%a %b %d %H:%M:%S %Y")
            }
        except (ValueError, TypeError) as e:
            logger.warning(f"Error calculating respawn time for '{monster_name}': {e}")
            return None
    
    def get_bosses_by_location(self) -> Dict[str, List[Dict]]:
        """
        Get bosses grouped by location/zone.
        
        Returns:
            Dictionary mapping location names to lists of boss entries
        """
        grouped = {}
        for boss in self.bosses:
            location = boss.get('location', 'Unknown')
            if location not in grouped:
                grouped[location] = []
            grouped[location].append(boss)
        return grouped
    
    def get_locations(self) -> List[str]:
        """Get list of all unique locations/zones."""
        locations = set()
        for boss in self.bosses:
            location = boss.get('location', 'Unknown')
            if location:
                locations.add(location)
        return sorted(list(locations))

