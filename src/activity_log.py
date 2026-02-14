"""Activity log widget showing today's activity."""
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional
from datetime import datetime

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class ActivityLogWidget(QListWidget):
    """Widget displaying activity log entries."""
    
    start_simulation_requested = pyqtSignal()
    stop_simulation_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize the activity log widget."""
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self._debug_mode = False
    
    def set_debug_mode(self, debug_mode: bool) -> None:
        """Show debug context menu (Start/Stop Simulation) when True."""
        self._debug_mode = bool(debug_mode)
    
    def contextMenuEvent(self, event) -> None:
        """Show Start/Stop Simulation when in debug mode; otherwise no context menu."""
        if not self._debug_mode:
            event.ignore()
            return
        menu = QMenu(self)
        start_act = menu.addAction("Start Simulation")
        start_act.triggered.connect(self.start_simulation_requested.emit)
        stop_act = menu.addAction("Stop Simulation")
        stop_act.triggered.connect(self.stop_simulation_requested.emit)
        menu.exec(self.mapToGlobal(event.pos()))
        event.accept()
    
    def add_entry(self, timestamp: str, monster: str, location: str, 
                  status: str) -> None:
        """
        Add an entry to the activity log.
        
        Args:
            timestamp: Timestamp string
            monster: Monster/boss name
            location: Zone/location
            status: Status message (e.g., "Posted to Discord" or "Duplicate detected, skipped")
        """
        logger.debug(f"Adding activity log entry: {monster} in {location} - {status}")
        
        # Format timestamp (extract time part)
        try:
            dt = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")
            time_str = dt.strftime("%H:%M:%S")
        except ValueError:
            time_str = timestamp.split()[-2] if len(timestamp.split()) >= 2 else timestamp
        
        # Create entry text
        entry_text = f"[{time_str}] {monster} ({location}) - {status}"
        
        # Create list item
        item = QListWidgetItem(entry_text)
        
        # Color code based on status (dark theme colors)
        if "Posted" in status or "posted" in status.lower():
            item.setForeground(Qt.GlobalColor.green)  # Bright green for dark theme
        elif "Duplicate" in status or "duplicate" in status.lower():
            item.setForeground(Qt.GlobalColor.yellow)  # Bright yellow for dark theme
        elif "Error" in status or "error" in status.lower():
            item.setForeground(Qt.GlobalColor.red)  # Bright red for dark theme
        elif "disabled" in status.lower() or "not in database" in status.lower():
            item.setForeground(Qt.GlobalColor.gray)  # Gray for disabled/not tracked
        elif "detected" in status.lower():
            item.setForeground(Qt.GlobalColor.cyan)  # Cyan for detected (before posting)
        else:
            item.setForeground(Qt.GlobalColor.white)  # White text for dark theme
        
        # Insert at top so newest messages appear at top and fall downward
        self.insertItem(0, item)
        # Do not change scroll position — preserves where the user was; if at top, new message is visible

        # Limit to 1000 entries (remove oldest from bottom)
        if self.count() > 1000:
            self.takeItem(self.count() - 1)
            logger.debug(f"Removed oldest activity entry (limit reached)")
    
    def clear_today(self) -> None:
        """Clear all entries (today's view)."""
        self.clear()
    
    def set_activities(self, activities: list) -> None:
        """Set activities from database (today's entries only). Newest at top, oldest at bottom."""
        logger.debug(f"Setting {len(activities)} activities in activity log")
        self.clear()
        
        # Sort by timestamp (newest first) so insertItem(0) in add_entry yields newest at top
        sorted_activities = sorted(
            activities,
            key=lambda a: a.get('timestamp', ''),
            reverse=True
        )
        
        for activity in sorted_activities:
            timestamp = activity.get('timestamp', '')
            monster = activity.get('monster', 'Unknown')
            location = activity.get('location', 'Unknown')
            
            # Use stored status if available, otherwise derive from posted_to_discord
            status = activity.get('status')
            if not status:
                if activity.get('posted_to_discord', False):
                    status = "Posted to Discord"
                else:
                    status = "Skipped"
            
            self.add_entry(timestamp, monster, location, status)
        # After full load, show latest (top)
        self.scrollToTop()
