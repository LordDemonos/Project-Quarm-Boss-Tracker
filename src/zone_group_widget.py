"""Zone grouping widget for displaying targets grouped by zone."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGroupBox, QCheckBox,
    QHBoxLayout, QLabel, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from typing import List, Dict, Optional
from datetime import datetime, timedelta

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


def _get_boss_key(boss: Dict) -> str:
    """
    Generate a unique key for a boss to handle duplicates.
    Uses name + note combination to ensure uniqueness.
    
    Args:
        boss: Boss dictionary
        
    Returns:
        Unique key string
    """
    name = boss.get('name', '')
    note = boss.get('note', '').strip()
    if note:
        return f"{name}|{note}"
    return name


class ZoneGroupWidget(QScrollArea):
    """Widget that displays targets grouped by zone."""
    
    # Signals
    boss_enabled_changed = pyqtSignal(object, bool)  # boss dict, enabled (changed to object to pass dict)
    zone_enabled_changed = pyqtSignal(str, bool)  # zone_name, enabled
    edit_boss_requested = pyqtSignal(object)  # boss dict - open Edit Boss for this target
    
    def __init__(self, parent=None):
        """Initialize the zone group widget."""
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container widget
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self.container)
        
        # Store zone groups
        self.zone_groups: Dict[str, QGroupBox] = {}
        self.boss_checkboxes: Dict[str, QCheckBox] = {}
        self.zone_checkboxes: Dict[str, QCheckBox] = {}  # Zone name -> zone checkbox
        self.boss_info_labels: Dict[str, QLabel] = {}  # boss_name -> info label
        
        # Store bosses data
        self.bosses: List[Dict] = []
        
        # Timer to update respawn times periodically
        # Update every minute (60000 ms) so respawn countdowns stay current
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_respawn_times)
        self.update_timer.start(60000)  # Update every minute (60000 ms = 60 seconds)
        
        # Reference to boss database for respawn calculations
        self.boss_db = None
        
        # Time format setting (False = 12-hour AM/PM, True = 24-hour military)
        self.use_military_time = False
    
    def set_bosses(self, bosses: List[Dict]) -> None:
        """Set the list of bosses to display, grouped by zone."""
        try:
            self.bosses = bosses
            
            # Debug: Log duplicate bosses to verify notes are present
            for boss_name in ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]:
                matching = [b for b in bosses if b.get('name') == boss_name]
                if len(matching) > 1:
                    logger.info(f"[DUPLICATE DEBUG] Found {len(matching)} entries for '{boss_name}':")
                    for i, b in enumerate(matching):
                        note_val = b.get('note')
                        logger.info(f"  Entry {i+1}: Note: '{note_val}' (type: {type(note_val)}, raw: {repr(note_val)}, enabled: {b.get('enabled')})")
                elif len(matching) == 1:
                    logger.info(f"[DUPLICATE DEBUG] Found 1 entry for '{boss_name}': Note: '{matching[0].get('note')}'")
                else:
                    logger.info(f"[DUPLICATE DEBUG] Found 0 entries for '{boss_name}'")
            
            logger.debug(f"Setting {len(bosses)} bosses in zone widget")
            
            # Save scroll position before clearing widgets
            scroll_position = self.verticalScrollBar().value()
            
            # Clear existing widgets
            self._clear_widgets()
            
            # Group bosses by location
            bosses_by_zone: Dict[str, List[Dict]] = {}
            for boss in bosses:
                zone = boss.get('location', 'Unknown')
                if zone not in bosses_by_zone:
                    bosses_by_zone[zone] = []
                bosses_by_zone[zone].append(boss)
            
            logger.debug(f"Grouped bosses into {len(bosses_by_zone)} zones")
            
            # Create zone groups - sort alphabetically A-Z (case-insensitive)
            for zone in sorted(bosses_by_zone.keys(), key=str.lower):
                try:
                    self._create_zone_group(zone, bosses_by_zone[zone])
                except Exception as e:
                    logger.error(f"Error creating zone group for '{zone}': {e}", exc_info=True)
            
            # Add stretch at end
            self.container_layout.addStretch()
            
            # Update all boss info labels after creating widgets
            QTimer.singleShot(0, self._update_all_boss_info)
            
            # Restore scroll position after widgets are created
            # Use QTimer to ensure widgets are fully laid out before scrolling
            QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(scroll_position))
        except Exception as e:
            logger.error(f"Error setting bosses: {e}", exc_info=True)
    
    def _clear_widgets(self) -> None:
        """Clear all zone group widgets."""
        try:
            # Disconnect all signals first to prevent callbacks during cleanup
            for checkbox in self.boss_checkboxes.values():
                try:
                    checkbox.stateChanged.disconnect()
                except:
                    pass
            
            for checkbox in self.zone_checkboxes.values():
                try:
                    checkbox.stateChanged.disconnect()
                except:
                    pass
            
            # Remove widgets from layout
            while self.container_layout.count():
                item = self.container_layout.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    widget.setParent(None)
                    widget.deleteLater()
            
            self.zone_groups.clear()
            self.boss_checkboxes.clear()
            self.zone_checkboxes.clear()
            self.boss_info_labels.clear()
        except Exception as e:
            logger.error(f"Error clearing widgets: {e}", exc_info=True)
    
    def _create_zone_group(self, zone_name: str, bosses: List[Dict]) -> None:
        """Create a zone group widget."""
        group_box = QGroupBox()
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(5)  # Consistent spacing
        
        # Zone header with checkbox (aligned with boss checkboxes)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)  # Space between checkbox and label
        
        # Zone checkbox - controls all bosses in zone
        zone_checkbox = QCheckBox()
        # Check if all bosses in zone are enabled
        all_enabled = all(b.get('enabled', False) for b in bosses)
        zone_checkbox.setChecked(all_enabled)
        zone_checkbox.stateChanged.connect(
            lambda state, z=zone_name: self._on_zone_checkbox_changed(z, state)
        )
        header_layout.addWidget(zone_checkbox)
        self.zone_checkboxes[zone_name] = zone_checkbox
        
        # Zone label (aligned with boss names)
        zone_label = QLabel(zone_name)
        zone_label.setProperty("class", "zone-title")
        zone_label.setStyleSheet("font-family: 'Segoe UI', 'Fira Sans', Arial, sans-serif; font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(zone_label)
        
        # Count enabled targets
        enabled_count = sum(1 for b in bosses if b.get('enabled', False))
        count_label = QLabel(f"({len(bosses)} targets, {enabled_count} enabled)")
        count_label.setProperty("class", "zone-count")
        header_layout.addWidget(count_label)
        
        header_layout.addStretch()
        group_layout.addLayout(header_layout)
        
        # Boss checkboxes with kill time and respawn info
        # Sort by name, then by note to keep duplicates together
        for boss in sorted(bosses, key=lambda b: (b['name'], b.get('note', ''))):
            boss_row = QHBoxLayout()
            boss_row.setSpacing(8)
            
            # Build display text: name + note (if available)
            boss_name = boss['name']
            note_raw = boss.get('note')
            note = (note_raw or '').strip() if note_raw else ''
            
            # Debug logging for duplicate names
            if boss_name in ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]:
                logger.info(f"[DUPLICATE DEBUG] Creating checkbox for '{boss_name}' - note_raw: {repr(note_raw)}, note: '{note}', full boss: {boss}")
            
            if note:
                display_text = f"{boss_name} ({note})"
            else:
                display_text = boss_name
            
            boss_checkbox = QCheckBox(display_text)

            # Right-click context menu: Edit (opens Edit Boss for this target)
            boss_checkbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            boss_checkbox.customContextMenuRequested.connect(
                lambda pos, b=boss, w=boss_checkbox: self._show_boss_context_menu(b, pos, w)
            )
            boss_checkbox.setToolTip("Right-click to edit this target")

            # Additional debug for duplicate names
            if boss_name in ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]:
                logger.info(f"[DUPLICATE DEBUG] Checkbox created with text: '{display_text}'")
            boss_checkbox.setChecked(boss.get('enabled', False))

            # Connect signal with boss dict reference (for duplicate handling)
            def make_handler(boss_dict, zone=zone_name):
                return lambda state: self._on_boss_checkbox_changed(boss_dict, state, zone)

            boss_checkbox.stateChanged.connect(make_handler(boss, zone_name))

            boss_row.addWidget(boss_checkbox)
            
            # Info label for last kill time and respawn time
            info_label = QLabel()
            info_label.setProperty("class", "boss-info")
            info_label.setStyleSheet("color: #999999; font-size: 9pt;")
            self._update_boss_info_label(boss['name'], boss, info_label, boss_checkbox)
            boss_row.addWidget(info_label)
            
            boss_row.addStretch()
            
            # Create container widget for the row
            boss_widget = QWidget()
            boss_widget.setLayout(boss_row)
            group_layout.addWidget(boss_widget)
            
            # Use unique key (name + note) to handle duplicate names
            boss_key = _get_boss_key(boss)
            self.boss_checkboxes[boss_key] = boss_checkbox
            self.boss_info_labels[boss_key] = info_label
            
            # Debug logging for duplicate names
            if boss_name in ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]:
                logger.info(f"[DUPLICATE DEBUG] Stored checkbox/label with key: '{boss_key}' for '{boss_name}' (note: '{note}')")
        
        # Store zone group
        self.zone_groups[zone_name] = group_box
        self.container_layout.addWidget(group_box)
    
    def _on_boss_checkbox_changed(self, boss: Dict, state: int, zone_name: str) -> None:
        """Handle boss checkbox state change."""
        enabled = state == Qt.CheckState.Checked.value
        boss_name = boss.get('name', 'Unknown')
        note = boss.get('note', '').strip()
        
        logger.debug(f"Boss checkbox changed: {boss_name} ({note or 'no note'}) -> {enabled}")
        
        # Update zone checkbox based on all bosses in zone
        if zone_name in self.zone_checkboxes:
            zone_checkbox = self.zone_checkboxes[zone_name]
            # Check if all bosses in this zone are now enabled
            zone_bosses = [b for b in self.bosses if b.get('location') == zone_name]
            all_enabled = all(
                self.boss_checkboxes[_get_boss_key(b)].isChecked()
                if _get_boss_key(b) in self.boss_checkboxes
                else False
                for b in zone_bosses
            )
            
            # Update zone checkbox without triggering its signal
            zone_checkbox.blockSignals(True)
            zone_checkbox.setChecked(all_enabled)
            zone_checkbox.blockSignals(False)
        
        # Emit signal with boss dict for proper duplicate handling
        self.boss_enabled_changed.emit(boss, enabled)
    
    def _on_zone_checkbox_changed(self, zone_name: str, state: int) -> None:
        """Handle zone checkbox state change - enable/disable all bosses in zone."""
        enabled = state == Qt.CheckState.Checked.value
        logger.debug(f"Zone checkbox changed: {zone_name} -> {enabled}")
        self._enable_all_in_zone(zone_name, enabled)

    def _show_boss_context_menu(self, boss: Dict, pos, widget: QWidget) -> None:
        """Show context menu for a single boss (right-click on target name): Edit."""
        menu = QMenu(self)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.edit_boss_requested.emit(boss))
        menu.exec(widget.mapToGlobal(pos))

    def _enable_all_in_zone(self, zone_name: str, enabled: bool) -> None:
        """Enable or disable all targets in a zone."""
        try:
            # Find all bosses in this zone
            zone_bosses = [b for b in self.bosses if b.get('location') == zone_name]
            
            logger.info(f"{'Enabling' if enabled else 'Disabling'} all {len(zone_bosses)} targets in zone '{zone_name}'")
            
            # Block signals while updating checkboxes to prevent individual signals
            # The zone signal will handle all updates at once
            for boss in zone_bosses:
                try:
                    boss_key = _get_boss_key(boss)
                    if boss_key in self.boss_checkboxes:
                        checkbox = self.boss_checkboxes[boss_key]
                        checkbox.blockSignals(True)  # Block individual checkbox signals
                        checkbox.setChecked(enabled)
                        checkbox.blockSignals(False)  # Re-enable signals
                except Exception as e:
                    logger.error(f"Error updating checkbox for boss '{boss.get('name', 'unknown')}': {e}", exc_info=True)
            
            # Emit zone signal once - this will handle all bosses in the zone
            # Use QTimer to defer signal emission to avoid issues during widget updates
            QTimer.singleShot(0, lambda: self.zone_enabled_changed.emit(zone_name, enabled))
        except Exception as e:
            logger.error(f"Error enabling/disabling all in zone '{zone_name}': {e}", exc_info=True)
    
    def get_selected_boss(self) -> Optional[str]:
        """Get the currently selected boss name."""
        # For now, return first checked boss (can be enhanced with selection)
        for boss_name, checkbox in self.boss_checkboxes.items():
            if checkbox.isChecked():
                return boss_name
        return None
    
    def set_boss_database(self, boss_db) -> None:
        """Set reference to boss database for respawn calculations."""
        self.boss_db = boss_db
    
    def set_time_format(self, use_military_time: bool) -> None:
        """Set time format preference (False = 12-hour AM/PM, True = 24-hour military)."""
        self.use_military_time = use_military_time
        # Refresh all boss info labels when format changes
        self._update_all_boss_info()
    
    def _update_boss_info_label(self, boss_name: str, boss: Dict, label: QLabel, checkbox: QCheckBox) -> None:
        """Update the info label for a boss with last kill time and respawn time."""
        try:
            parts = []
            
            # Last kill time
            last_killed_str = boss.get('last_killed')
            if last_killed_str:
                try:
                    # Parse ISO format datetime (stored in UTC/local time)
                    kill_time = datetime.fromisoformat(last_killed_str)
                    # Format relative to user's timezone (already in local time from datetime.now())
                    # Use 12-hour format with AM/PM or 24-hour format based on setting
                    if self.use_military_time:
                        time_str = kill_time.strftime("%m/%d %H:%M")  # 24-hour format
                    else:
                        time_str = kill_time.strftime("%m/%d %I:%M %p")  # 12-hour format with AM/PM
                    parts.append(f"Last: {time_str}")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse last_killed '{last_killed_str}' for '{boss_name}': {e}")
            
            # Respawn time - recalculates based on current time
            respawn_hours = boss.get('respawn_hours')
            respawn_is_default = boss.get('respawn_hours_is_default', False)
            tooltip_text = ""
            
            if self.boss_db:
                # Check if respawn time is default (needs to be set by user)
                if respawn_is_default:
                    # Show "Unknown" to indicate respawn time needs to be set
                    parts.append("Respawn: Unknown")
                    tooltip_text = "Respawn Time: Unknown (default 6d 18h - please set actual respawn time)"
                else:
                    respawn_info = self.boss_db.get_time_until_respawn(boss_name)
                    if respawn_info:
                        if respawn_info['is_respawned']:
                            parts.append("Respawned!")
                        else:
                            days = int(respawn_info['hours_remaining'] // 24)
                            hours = int(respawn_info['hours_remaining'] % 24)
                            if days > 0:
                                parts.append(f"Respawn: {days}d {hours}h")
                            else:
                                parts.append(f"Respawn: {hours}h")
                    
                    # Set tooltip on checkbox if respawn time is defined
                    if respawn_hours is not None:
                        # Format tooltip: convert hours to days and hours for readability
                        total_hours = respawn_hours
                        tooltip_days = int(total_hours // 24)
                        tooltip_hours = int(total_hours % 24)
                        
                        if tooltip_days > 0:
                            if tooltip_hours > 0:
                                tooltip_text = f"Respawn Time: {tooltip_days} day{'s' if tooltip_days != 1 else ''} {tooltip_hours} hour{'s' if tooltip_hours != 1 else ''}"
                            else:
                                tooltip_text = f"Respawn Time: {tooltip_days} day{'s' if tooltip_days != 1 else ''}"
                        else:
                            tooltip_text = f"Respawn Time: {tooltip_hours} hour{'s' if tooltip_hours != 1 else ''}"
            
            if parts:
                label.setText(" | ".join(parts))
            else:
                label.setText("")
            
            # Set tooltip on checkbox (boss name) if respawn time is defined
            if tooltip_text:
                checkbox.setToolTip(tooltip_text)
            else:
                checkbox.setToolTip("")
        except Exception as e:
            logger.error(f"Error updating boss info label for '{boss_name}': {e}", exc_info=True)
            label.setText("")
            if checkbox:
                checkbox.setToolTip("")
    
    def _update_all_boss_info(self) -> None:
        """Update all boss info labels and checkbox text."""
        for boss_key, label in self.boss_info_labels.items():
            # Find boss by matching the unique key
            boss = next((b for b in self.bosses if _get_boss_key(b) == boss_key), None)
            if boss and boss_key in self.boss_checkboxes:
                checkbox = self.boss_checkboxes[boss_key]
                
                # Update checkbox text with note if available
                boss_name = boss.get('name', '')
                note_raw = boss.get('note')
                note = (note_raw or '').strip() if note_raw else ''
                
                # Debug logging for duplicate names
                if boss_name in ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]:
                    logger.info(f"[DUPLICATE DEBUG] _update_all_boss_info - Updating checkbox for '{boss_name}' with note: '{note}' (key: '{boss_key}', raw: {repr(note_raw)}, boss dict note: {repr(boss.get('note'))})")
                
                if note:
                    display_text = f"{boss_name} ({note})"
                else:
                    display_text = boss_name
                
                current_text = checkbox.text()
                if current_text != display_text:
                    logger.info(f"[DUPLICATE DEBUG] Changing checkbox text from '{current_text}' to '{display_text}' for key '{boss_key}'")
                    checkbox.setText(display_text)
                
                self._update_boss_info_label(boss_name, boss, label, checkbox)
    
    def _update_respawn_times(self) -> None:
        """Update all respawn time displays (called every minute)."""
        self._update_all_boss_info()
    
    def refresh_boss_info(self, boss_name: str, note: Optional[str] = None) -> None:
        """
        Refresh the info label and checkbox text for a specific boss.
        
        Args:
            boss_name: Name of the boss
            note: Optional note to identify specific boss (for duplicates)
        """
        # Find boss by name (and note if provided)
        boss = None
        if note:
            # Note provided - find exact match
            boss = next((b for b in self.bosses if b.get('name') == boss_name and (b.get('note', '') or '').strip() == note.strip()), None)
        else:
            # No note provided - try to find unique boss or first match
            matching_bosses = [b for b in self.bosses if b.get('name') == boss_name]
            if len(matching_bosses) == 1:
                boss = matching_bosses[0]
            elif len(matching_bosses) > 1:
                # Multiple matches - refresh each one directly to avoid infinite recursion
                for b in matching_bosses:
                    boss_key = _get_boss_key(b)
                    if boss_key in self.boss_info_labels and boss_key in self.boss_checkboxes:
                        label = self.boss_info_labels[boss_key]
                        checkbox = self.boss_checkboxes[boss_key]
                        
                        # Update checkbox text with note if available
                        note_text = (b.get('note', '') or '').strip()
                        if note_text:
                            display_text = f"{boss_name} ({note_text})"
                        else:
                            display_text = boss_name
                        checkbox.setText(display_text)
                        
                        self._update_boss_info_label(boss_name, b, label, checkbox)
                return
        
        if boss:
            boss_key = _get_boss_key(boss)
            if boss_key in self.boss_info_labels and boss_key in self.boss_checkboxes:
                label = self.boss_info_labels[boss_key]
                checkbox = self.boss_checkboxes[boss_key]
                
                # Update checkbox text with note if available
                note_text = boss.get('note', '').strip()
                if note_text:
                    display_text = f"{boss_name} ({note_text})"
                else:
                    display_text = boss_name
                checkbox.setText(display_text)
                
                self._update_boss_info_label(boss_name, boss, label, checkbox)
    
    def update_boss(self, boss_name: str, enabled: Optional[bool] = None, note: Optional[str] = None) -> None:
        """
        Update a boss checkbox state and refresh info.
        
        Args:
            boss_name: Name of the boss
            enabled: Optional enabled state
            note: Optional note to identify specific boss (for duplicates)
        """
        # Find boss by name (and note if provided)
        boss = None
        if note:
            boss = next((b for b in self.bosses if b.get('name') == boss_name and b.get('note', '').strip() == note.strip()), None)
        else:
            matching_bosses = [b for b in self.bosses if b.get('name') == boss_name]
            if len(matching_bosses) == 1:
                boss = matching_bosses[0]
        
        if boss:
            boss_key = _get_boss_key(boss)
            if boss_key in self.boss_checkboxes:
                checkbox = self.boss_checkboxes[boss_key]
                if enabled is not None:
                    checkbox.setChecked(enabled)
            
            # Refresh boss info when updated
            self.refresh_boss_info(boss_name, boss.get('note'))
