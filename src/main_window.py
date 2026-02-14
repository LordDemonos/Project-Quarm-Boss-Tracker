"""Main application window with target list and activity log."""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QStatusBar, QLabel, QPushButton, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from typing import Optional, Callable, Dict, List

try:
    from .logger import get_logger
    from .zone_group_widget import ZoneGroupWidget
    from .activity_log import ActivityLogWidget
    from .about_dialog import AboutDialog
    from .quick_start_dialog import QuickStartDialog
except ImportError:
    from logger import get_logger
    from zone_group_widget import ZoneGroupWidget
    from activity_log import ActivityLogWidget
    from about_dialog import AboutDialog
    from quick_start_dialog import QuickStartDialog

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    boss_enabled_changed = pyqtSignal(object, bool)  # boss dict, enabled (changed to object to pass dict)
    zone_enabled_changed = pyqtSignal(str, bool)  # zone_name, enabled
    all_bosses_enabled_changed = pyqtSignal(bool)  # enabled (for all bosses)
    add_boss_requested = pyqtSignal()
    remove_boss_requested = pyqtSignal(str)  # boss_name
    settings_requested = pyqtSignal()
    message_format_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    theme_switch_requested = pyqtSignal()  # Request to switch theme
    scan_requested = pyqtSignal()  # Request to scan a log file
    discord_sync_requested = pyqtSignal()  # Request to sync kill times from Discord
    edit_respawn_times_requested = pyqtSignal()  # Request to edit respawn times
    edit_boss_requested = pyqtSignal(object)  # Request to edit a specific boss (boss dict)
    boss_capture_requested = pyqtSignal()
    boss_simulation_requested = pyqtSignal()
    def __init__(self, parent=None, debug_mode: bool = False):
        """Initialize the main window."""
        super().__init__(parent)
        self.debug_mode = debug_mode
        self.setWindowTitle("Project Quarm Boss Tracker")
        self.setMinimumSize(800, 600)
        
        # Icon will be set by QApplication.setWindowIcon, but we can also set it explicitly
        # The window icon inherits from the application icon automatically
        
        # Callbacks
        self.on_boss_enable_change: Optional[Callable] = None
        self.on_zone_enable_change: Optional[Callable] = None
        self.on_add_boss: Optional[Callable] = None
        self.on_remove_boss: Optional[Callable] = None  # Takes boss dict as parameter
        
        # Settings callback for saving window state
        self.on_save_window_state: Optional[Callable] = None
        
        logger.info("Initializing main window")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Target list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Target list header (right-click for Enable All / Disable All)
        targets_header = QHBoxLayout()
        self.targets_label = QLabel("Targets (Grouped by Zone)")
        self.targets_label.setProperty("class", "heading")
        self.targets_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.targets_label.customContextMenuRequested.connect(self._show_targets_context_menu)
        self.targets_label.setToolTip("Right-click for Enable All / Disable All")
        targets_header.addWidget(self.targets_label)
        targets_header.addStretch()
        
        left_layout.addLayout(targets_header)
        
        # Zone groups widget (scrollable)
        self.zone_widget = ZoneGroupWidget()
        self.zone_widget.boss_enabled_changed.connect(self._on_boss_enabled_changed)
        self.zone_widget.zone_enabled_changed.connect(self._on_zone_enabled_changed)
        self.zone_widget.edit_boss_requested.connect(self.edit_boss_requested.emit)
        left_layout.addWidget(self.zone_widget)
        
        # Right panel: Activity log
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        activity_label = QLabel("Activity Log (Today)")
        activity_label.setProperty("class", "heading")
        right_layout.addWidget(activity_label)
        
        self.activity_log = ActivityLogWidget()
        self.activity_log.set_debug_mode(self.debug_mode)
        right_layout.addWidget(self.activity_log)
        
        # Add panels to splitter
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 2)  # Left panel takes 2/3
        self.splitter.setStretchFactor(1, 1)  # Right panel takes 1/3
        
        # Connect splitter moved signal to save position
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        
        main_layout.addWidget(self.splitter)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        settings_action = file_menu.addAction("Settings")
        settings_action.triggered.connect(self.settings_requested.emit)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Tools menu (utility functions and configuration)
        tools_menu = menubar.addMenu("Tools")
        
        # Target Management Section
        add_target_action = tools_menu.addAction("Add Target")
        add_target_action.triggered.connect(self.add_boss_requested.emit)
        
        remove_target_action = tools_menu.addAction("Remove Target")
        remove_target_action.triggered.connect(self._remove_selected_boss)
        
        edit_respawn_action = tools_menu.addAction("Edit Bosses")
        edit_respawn_action.triggered.connect(self.edit_respawn_times_requested.emit)
        
        tools_menu.addSeparator()
        
        # Data Operations Section
        scan_action = tools_menu.addAction("Scan")
        scan_action.triggered.connect(self.scan_requested.emit)
        
        discord_sync_action = tools_menu.addAction("Sync from Discord")
        discord_sync_action.triggered.connect(self.discord_sync_requested.emit)
        
        refresh_action = tools_menu.addAction("Refresh")
        refresh_action.triggered.connect(self.refresh_requested.emit)
        
        tools_menu.addSeparator()
        
        # Settings/Configuration Section
        message_format_action = tools_menu.addAction("Message Format")
        message_format_action.triggered.connect(self.message_format_requested.emit)
        
        # Theme switcher - dynamically shows opposite mode
        self.theme_switch_action = tools_menu.addAction("Switch to Light Mode")
        self.theme_switch_action.triggered.connect(self.theme_switch_requested.emit)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        quick_start_action = help_menu.addAction("Quick Start")
        quick_start_action.triggered.connect(self._show_quick_start_dialog)
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._show_about_dialog)
        
        # Debug menu (only when debug_mode is True)
        if self.debug_mode:
            debug_menu = menubar.addMenu("Debug")
            boss_capture_action = debug_menu.addAction("Boss Capture")
            boss_capture_action.triggered.connect(self.boss_capture_requested.emit)
            boss_simulation_action = debug_menu.addAction("Boss Simulation")
            boss_simulation_action.triggered.connect(self.boss_simulation_requested.emit)
            # Advanced Settings removed - use main settings / manual webhook change for testing
    
    def update_theme_menu(self, current_theme: str) -> None:
        """Update the theme switch menu item text based on current theme."""
        if current_theme == "dark":
            self.theme_switch_action.setText("Switch to Light Mode")
        else:
            self.theme_switch_action.setText("Switch to Dark Mode")
    
    def set_bosses(self, bosses: List[Dict]) -> None:
        """Set the list of bosses to display."""
        logger.debug(f"Setting {len(bosses)} bosses in main window")
        self.zone_widget.set_bosses(bosses)
    
    def add_activity(self, timestamp: str, monster: str, location: str, 
                    status: str) -> None:
        """Add an entry to the activity log."""
        logger.debug(f"Adding activity: {monster} in {location} - {status}")
        self.activity_log.add_entry(timestamp, monster, location, status)
    
    def set_active_character(self, character_name: Optional[str]) -> None:
        """Update status bar with active character."""
        if character_name:
            self.status_bar.showMessage(f"Monitoring: {character_name}")
            logger.debug(f"Active character updated: {character_name}")
        else:
            self.status_bar.showMessage("No active character")
            logger.debug("No active character")
    
    def _on_boss_enabled_changed(self, boss: Dict, enabled: bool) -> None:
        """Handle boss enable/disable change."""
        boss_name = boss.get('name', 'Unknown')
        note = boss.get('note', '').strip()
        logger.info(f"Boss '{boss_name}' ({note or 'no note'}) {'enabled' if enabled else 'disabled'}")
        # Only emit signal - don't call callback directly to avoid double-calling
        # Pass boss dict for proper duplicate handling
        self.boss_enabled_changed.emit(boss, enabled)
    
    def _on_zone_enabled_changed(self, zone_name: str, enabled: bool) -> None:
        """Handle zone enable/disable change."""
        logger.info(f"Zone '{zone_name}' {'enabled' if enabled else 'disabled'} for all targets")
        # Only emit signal - don't call callback directly to avoid double-calling
        self.zone_enabled_changed.emit(zone_name, enabled)
    
    def _show_targets_context_menu(self, pos) -> None:
        """Show context menu for bulk Enable All / Disable All on the Targets header."""
        menu = QMenu(self)
        enable_action = menu.addAction("Enable All")
        enable_action.triggered.connect(lambda: self.all_bosses_enabled_changed.emit(True))
        disable_action = menu.addAction("Disable All")
        disable_action.triggered.connect(lambda: self.all_bosses_enabled_changed.emit(False))
        menu.exec(self.targets_label.mapToGlobal(pos))
    
    def _remove_selected_boss(self) -> None:
        """Remove a boss using the remove boss dialog."""
        try:
            from .remove_boss_dialog import RemoveBossDialog
            
            # Get current list of bosses from the zone widget
            bosses = []
            if hasattr(self, 'zone_widget') and hasattr(self.zone_widget, 'bosses'):
                bosses = self.zone_widget.bosses
            
            if not bosses:
                QMessageBox.information(
                    self,
                    "No Targets",
                    "No targets available to remove."
                )
                return
            
            dialog = RemoveBossDialog(bosses, self)
            if dialog.exec():
                selected_boss = dialog.get_selected_boss()
                if selected_boss:
                    boss_name = selected_boss.get('name')
                    logger.info(f"User selected boss to remove: {boss_name} ({selected_boss.get('note', 'no note')})")
                    if self.on_remove_boss:
                        # Pass the boss dict for proper removal (handles duplicates correctly)
                        self.on_remove_boss(selected_boss)
                    # Also emit signal for backwards compatibility
                    self.remove_boss_requested.emit(boss_name)
        except ImportError as e:
            logger.error(f"Error importing remove boss dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open remove target dialog: {e}"
            )
        except Exception as e:
            logger.error(f"Error showing remove boss dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open remove target dialog: {e}"
            )
    
    def closeEvent(self, event) -> None:
        """Handle window close event - minimize to tray instead."""
        logger.debug("Main window close event - hiding to tray")
        # Save window state before hiding
        self._save_window_state()
        event.ignore()
        self.hide()  # Hide instead of closing
    
    def resizeEvent(self, event) -> None:
        """Handle window resize - save state after a short delay."""
        super().resizeEvent(event)
        # Defer saving to avoid excessive saves during resize
        if not hasattr(self, '_resize_timer'):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_window_state)
        self._resize_timer.stop()
        self._resize_timer.start(500)  # Save 500ms after resize stops
    
    def moveEvent(self, event) -> None:
        """Handle window move - save state after a short delay."""
        super().moveEvent(event)
        # Defer saving to avoid excessive saves during move
        if not hasattr(self, '_move_timer'):
            self._move_timer = QTimer()
            self._move_timer.setSingleShot(True)
            self._move_timer.timeout.connect(self._save_window_state)
        self._move_timer.stop()
        self._move_timer.start(500)  # Save 500ms after move stops
    
    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """Handle splitter movement - save position after a short delay."""
        # Defer saving to avoid excessive saves during drag
        if not hasattr(self, '_splitter_timer'):
            self._splitter_timer = QTimer()
            self._splitter_timer.setSingleShot(True)
            self._splitter_timer.timeout.connect(self._save_window_state)
        self._splitter_timer.stop()
        self._splitter_timer.start(300)  # Save 300ms after splitter stops moving
    
    def _save_window_state(self) -> None:
        """Save window geometry, splitter state, and Targets by Zone scroll position."""
        if self.on_save_window_state:
            geometry = self.saveGeometry()
            splitter_sizes = self.splitter.sizes()
            zone_scroll = 0
            if hasattr(self, "zone_widget") and self.zone_widget is not None:
                zone_scroll = self.zone_widget.verticalScrollBar().value()
            self.on_save_window_state(geometry, splitter_sizes, zone_scroll)
    
    def restore_window_state(self, geometry: bytes, splitter_sizes: list, zone_scroll_position: Optional[int] = None) -> None:
        """Restore window geometry, splitter state, and Targets by Zone scroll position."""
        if geometry:
            try:
                self.restoreGeometry(geometry)
                logger.debug("Window geometry restored")
            except Exception as e:
                logger.warning(f"Could not restore window geometry: {e}")
        
        if splitter_sizes and len(splitter_sizes) == 2:
            try:
                self.splitter.setSizes(splitter_sizes)
                logger.debug(f"Splitter sizes restored: {splitter_sizes}")
            except Exception as e:
                logger.warning(f"Could not restore splitter sizes: {e}")
        
        if zone_scroll_position is not None and zone_scroll_position >= 0 and hasattr(self, "zone_widget") and self.zone_widget is not None:
            sb = self.zone_widget.verticalScrollBar()
            # Defer so layout is complete and maximum() is valid
            QTimer.singleShot(200, lambda: sb.setValue(min(zone_scroll_position, sb.maximum())))
    
    def _show_quick_start_dialog(self) -> None:
        """Show the Quick Start dialog."""
        dialog = QuickStartDialog(self)
        dialog.exec()

    def _show_about_dialog(self) -> None:
        """Show the about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()
