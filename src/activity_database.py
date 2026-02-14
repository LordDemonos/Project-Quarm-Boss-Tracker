"""Manage activity log - storing and filtering activity entries."""
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)

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


class ActivityDatabase:
    """Manages the activity log database."""
    
    def __init__(self, db_path: str):
        """
        Initialize the activity database.
        
        Args:
            db_path: Path to the activity.json file
        """
        self.db_path = Path(db_path)
        self.activities: List[Dict] = []
        self.load()
    
    def load(self) -> None:
        """Load activities from JSON file."""
        if self.db_path.exists():
            try:
                # #region agent log
                file_size = self.db_path.stat().st_size
                debug_log("activity_database.py:29", "Loading activity.json", {
                    "file_path": str(self.db_path),
                    "file_size_bytes": file_size,
                    "file_size_mb": file_size / 1024 / 1024
                }, hypothesis_id="B", run_id="initial")
                # #endregion
                
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.activities = data.get('activity', [])
                
                # #region agent log
                debug_log("activity_database.py:35", "Activities loaded into memory", {
                    "activity_count": len(self.activities),
                    "estimated_size_mb": len(str(data)) / 1024 / 1024
                }, hypothesis_id="B", run_id="initial")
                # #endregion
                
                logger.info(f"Loaded {len(self.activities)} activity entries from {self.db_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading activity database from {self.db_path}: {e}")
                self.activities = []
        else:
            logger.info(f"Activity database not found at {self.db_path}, creating new database")
            self.activities = []
            self.save()
    
    def save(self) -> None:
        """Save activities to JSON file."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({'activity': self.activities}, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.activities)} activity entries to {self.db_path}")
        except IOError as e:
            logger.error(f"Error saving activity database to {self.db_path}: {e}")
    
    def add_activity(self, timestamp: str, monster: str, location: str,
                     player: str, guild: str, posted_to_discord: bool,
                     discord_message: Optional[str] = None,
                     discord_message_id: Optional[str] = None,
                     status: Optional[str] = None) -> Dict:
        """
        Add an activity entry.
        
        Args:
            timestamp: Timestamp string from log
            monster: Monster/boss name
            location: Zone/location
            player: Player name
            guild: Guild name
            posted_to_discord: Whether message was posted to Discord
            discord_message: The message that was posted
            discord_message_id: Discord message ID if posted
            
        Returns:
            The created activity entry
        """
        # Parse date from timestamp
        try:
            dt = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")
            activity_date = dt.date().isoformat()
        except ValueError:
            activity_date = date.today().isoformat()
        
        activity = {
            'timestamp': timestamp,
            'date': activity_date,
            'monster': monster,
            'location': location,
            'player': player,
            'guild': guild,
            'posted_to_discord': posted_to_discord,
            'discord_message': discord_message,
            'discord_message_id': discord_message_id,
            'status': status or ("Posted to Discord" if posted_to_discord else "Skipped"),
            'created_at': datetime.now().isoformat()
        }
        
        self.activities.append(activity)
        logger.info(f"Added activity: {monster} in {location} - {'Posted' if posted_to_discord else 'Skipped'}")
        self.save()
        return activity
    
    def get_today_activities(self) -> List[Dict]:
        """Get activities from today only."""
        today = date.today().isoformat()
        today_activities = [a for a in self.activities if a.get('date') == today]
        logger.debug(f"Retrieved {len(today_activities)} activities for today")
        return today_activities
    
    def get_all_activities(self) -> List[Dict]:
        """Get all activities."""
        return self.activities.copy()
    
    def get_recent_activities(self, limit: int = 100) -> List[Dict]:
        """Get most recent activities."""
        return self.activities[-limit:]
    
    def clear_old_activities(self, days: int = 30) -> int:
        """
        Remove activities older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of activities removed
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        initial_count = len(self.activities)
        self.activities = [a for a in self.activities if a.get('date', '') >= cutoff_date]
        removed = initial_count - len(self.activities)
        if removed > 0:
            logger.info(f"Cleared {removed} old activity entries (older than {days} days)")
            self.save()
        return removed
