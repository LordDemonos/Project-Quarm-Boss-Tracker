"""Options window for application settings."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QGroupBox, QFileDialog, QComboBox, QFormLayout, QMessageBox,
    QRadioButton, QButtonGroup, QColorDialog, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from typing import Optional, Callable
from pathlib import Path

try:
    from .backup_restore_dialog import BackupRestoreDialog
except ImportError:
    from backup_restore_dialog import BackupRestoreDialog

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger
import logging

logger = get_logger(__name__)
# Root app logger - always has console handler; use for critical "Settings saved" lines
_app_log = logging.getLogger('eq_boss_tracker')


class OptionsWindow(QDialog):
    """Options window for configuring the application."""
    
    # Signals
    settings_changed = pyqtSignal()
    
    # Common timezones (IANA names; formatter supports any pytz/IANA zone)
    TIMEZONES = [
        ("Auto-detect", ""),
        # US
        ("Eastern Time (EST/EDT)", "US/Eastern"),
        ("Central Time (CST/CDT)", "US/Central"),
        ("Mountain Time (MST/MDT)", "US/Mountain"),
        ("Pacific Time (PST/PDT)", "US/Pacific"),
        ("Alaska Time (AKST/AKDT)", "US/Alaska"),
        ("Hawaii Time (HST)", "US/Hawaii"),
        # Europe
        ("GMT / London (GMT/BST)", "Europe/London"),
        ("Central European (CET/CEST)", "Europe/Paris"),
        ("Eastern European (EET/EEST)", "Europe/Athens"),
        ("UTC", "UTC"),
        # Australia
        ("Australia Eastern (AEST/AEDT)", "Australia/Sydney"),
        ("Australia Central (ACST/ACDT)", "Australia/Adelaide"),
        ("Australia Western (AWST)", "Australia/Perth"),
        # Asia
        ("Japan (JST)", "Asia/Tokyo"),
        ("Singapore / Hong Kong", "Asia/Singapore"),
    ]
    
    def __init__(self, parent=None):
        """Initialize the options window."""
        super().__init__(parent)
        self.setWindowTitle("Project Quarm Boss Tracker - Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        self.settings = {}
        self.on_settings_save: Optional[Callable] = None
        self._selected_color = QColor('#007acc')  # Default blue
        self.on_test_notification: Optional[Callable] = None  # Callback to test notification
        self.bosses_json_path: Optional[Path] = None  # Path to bosses.json for backup restore
        self.on_create_backup: Optional[Callable] = None  # Callback to create backup
        
        logger.debug("Initializing options window")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()
        
        # Log directory
        self.log_directory_edit = QLineEdit()
        log_browse_btn = QPushButton("Browse...")
        log_browse_btn.clicked.connect(self._browse_log_directory)
        log_layout = QHBoxLayout()
        log_layout.addWidget(self.log_directory_edit)
        log_layout.addWidget(log_browse_btn)
        settings_layout.addRow("Log Directory:", log_layout)
        
        # Discord webhook URL
        self.webhook_url_edit = QLineEdit()
        self.webhook_url_edit.setPlaceholderText("https://discord.com/api/webhooks/...")
        settings_layout.addRow("Discord Webhook URL:", self.webhook_url_edit)
        
        # Discord bot token
        self.bot_token_edit = QLineEdit()
        self.bot_token_edit.setPlaceholderText("Bot token for duplicate detection")
        self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        settings_layout.addRow("Discord Bot Token:", self.bot_token_edit)
        
        # Discord sync interval (hours) — min 1h (API safety), max 168h / 1 week
        self.discord_sync_interval_spin = QSpinBox()
        self.discord_sync_interval_spin.setMinimum(1)
        self.discord_sync_interval_spin.setMaximum(168)
        self.discord_sync_interval_spin.setSuffix(" hours")
        self.discord_sync_interval_spin.setToolTip(
            "How often to automatically sync kill times from Discord. "
            "Allowed: 1–168 hours (1h minimum for API safety, 1 week maximum). Default 12h."
        )
        discord_sync_row = QHBoxLayout()
        discord_sync_row.addWidget(self.discord_sync_interval_spin)
        discord_sync_hint = QLabel("(1 hour – 1 week)")
        discord_sync_hint.setStyleSheet("color: #888888; font-size: 11px;")
        discord_sync_row.addWidget(discord_sync_hint)
        discord_sync_row.addStretch()
        settings_layout.addRow("Sync from Discord interval:", discord_sync_row)
        
        # Timezone
        self.timezone_combo = QComboBox()
        for display_name, tz_name in self.TIMEZONES:
            self.timezone_combo.addItem(display_name, tz_name)
        settings_layout.addRow("Timezone:", self.timezone_combo)
        
        # Time format
        self.military_time_checkbox = QCheckBox("Use 24-hour (military) time format")
        settings_layout.addRow("Time Format:", self.military_time_checkbox)
        
        # Sound settings
        self.sound_enabled_checkbox = QCheckBox("Enable sound notifications")
        settings_layout.addRow("", self.sound_enabled_checkbox)
        
        # Sound file picker
        self.sound_file_edit = QLineEdit()
        sound_browse_btn = QPushButton("Browse...")
        sound_browse_btn.clicked.connect(self._browse_sound_file)
        sound_reset_btn = QPushButton("Reset to Default")
        sound_reset_btn.clicked.connect(self._reset_sound_file)
        sound_file_layout = QHBoxLayout()
        sound_file_layout.addWidget(self.sound_file_edit)
        sound_file_layout.addWidget(sound_browse_btn)
        sound_file_layout.addWidget(sound_reset_btn)
        settings_layout.addRow("Sound File:", sound_file_layout)
        
        # Window behavior
        self.window_popup_checkbox = QCheckBox("Pop up window when new boss detected")
        settings_layout.addRow("", self.window_popup_checkbox)
        
        self.windows_notification_checkbox = QCheckBox("Show system notifications when boss is killed")
        windows_notification_test_btn = QPushButton("Test")
        windows_notification_test_btn.clicked.connect(self._test_windows_notification)
        windows_notification_layout = QHBoxLayout()
        windows_notification_layout.addWidget(self.windows_notification_checkbox)
        windows_notification_layout.addStretch()
        windows_notification_layout.addWidget(windows_notification_test_btn)
        settings_layout.addRow("", windows_notification_layout)
        
        # New boss default action
        new_boss_group = QGroupBox("New Target Default Action")
        new_boss_layout = QVBoxLayout()
        
        self.new_boss_button_group = QButtonGroup(self)
        self.new_boss_enable_radio = QRadioButton("Enable by default (auto-post to Discord)")
        self.new_boss_disable_radio = QRadioButton("Disable by default")
        self.new_boss_button_group.addButton(self.new_boss_enable_radio, 0)
        self.new_boss_button_group.addButton(self.new_boss_disable_radio, 1)
        
        new_boss_layout.addWidget(self.new_boss_enable_radio)
        new_boss_layout.addWidget(self.new_boss_disable_radio)
        new_boss_group.setLayout(new_boss_layout)
        settings_layout.addRow("", new_boss_group)
        
        # Accent color picker
        self.color_picker_btn = QPushButton()
        self.color_picker_btn.setFixedWidth(60)
        self.color_picker_btn.setFixedHeight(30)
        self.color_picker_btn.clicked.connect(self._pick_color)
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.color_picker_btn)
        color_layout.addStretch()
        settings_layout.addRow("Accent Color:", color_layout)
        
        # Active character display
        self.active_character_label = QLabel("No active character")
        settings_layout.addRow("Active Character:", self.active_character_label)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Backup & Restore group
        backup_group = QGroupBox("Backup & Restore")
        backup_layout = QVBoxLayout()
        
        backup_info = QLabel(
            "Create a backup of your current boss data, or restore from a previous backup. "
            "Backups are automatically created when the app saves, but you can create one manually anytime."
        )
        backup_info.setWordWrap(True)
        backup_layout.addWidget(backup_info)
        
        backup_buttons_layout = QHBoxLayout()
        
        self.create_backup_btn = QPushButton("Create Backup Now")
        self.create_backup_btn.clicked.connect(self._create_backup_now)
        backup_buttons_layout.addWidget(self.create_backup_btn)
        
        self.restore_backup_btn = QPushButton("Restore from Backup...")
        self.restore_backup_btn.clicked.connect(self._show_restore_dialog)
        backup_buttons_layout.addWidget(self.restore_backup_btn)
        
        backup_layout.addLayout(backup_buttons_layout)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_settings)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def set_settings(self, settings: dict) -> None:
        """Set the settings to display."""
        self.settings = settings
        logger.debug("Options window: loading settings into form (default_webhook_url present: %s, log_directory: %s)",
                    bool(settings.get('default_webhook_url')), bool(settings.get('log_directory')))
        self.log_directory_edit.setText(settings.get('log_directory', ''))
        self.webhook_url_edit.setText(settings.get('default_webhook_url', ''))
        self.bot_token_edit.setText(settings.get('discord_bot_token', ''))
        self.discord_sync_interval_spin.setValue(max(1, min(168, int(settings.get('discord_sync_interval_hours', 12)))))
        self.sound_enabled_checkbox.setChecked(settings.get('sound_enabled', True))
        
        # Set sound file path
        sound_file_path = settings.get('sound_file_path', 'fanfare.mp3')
        self.sound_file_edit.setText(sound_file_path)
        
        self.window_popup_checkbox.setChecked(settings.get('window_popup_on_new_boss', True))
        self.windows_notification_checkbox.setChecked(settings.get('windows_notification', False))
        
        # Set new boss default action
        new_boss_default = settings.get('new_boss_default_action', 'disable')
        if new_boss_default == 'enable':
            self.new_boss_enable_radio.setChecked(True)
        else:
            self.new_boss_disable_radio.setChecked(True)
        
        # Set timezone
        timezone = settings.get('timezone', '')
        index = 0  # Default to auto-detect
        for i, (_, tz_name) in enumerate(self.TIMEZONES):
            if tz_name == timezone:
                index = i
                break
        self.timezone_combo.setCurrentIndex(index)
        
        # Set time format
        use_military_time = settings.get('use_military_time', False)
        self.military_time_checkbox.setChecked(use_military_time)
        
        # Set accent color (default to blue: #007acc)
        accent_color = settings.get('accent_color', '#007acc')
        color = QColor(accent_color)
        if not color.isValid():
            color = QColor('#007acc')  # Fallback to default blue
        self._update_color_button(color)
        
        logger.debug("Settings loaded into options window")
    
    def set_active_character(self, character_name: Optional[str]) -> None:
        """Update the active character display."""
        if character_name:
            self.active_character_label.setText(character_name)
        else:
            self.active_character_label.setText("No active character")
    
    def _browse_log_directory(self) -> None:
        """Open directory browser for log directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Log Directory",
            self.log_directory_edit.text() or str(Path.home())
        )
        if directory:
            logger.debug(f"User selected log directory: {directory}")
            self.log_directory_edit.setText(directory)
    
    def _browse_sound_file(self) -> None:
        """Open file browser for sound file."""
        # Common audio formats
        file_filter = "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound File",
            self.sound_file_edit.text() or str(Path.home()),
            file_filter
        )
        if file_path:
            logger.debug(f"User selected sound file: {file_path}")
            self.sound_file_edit.setText(file_path)
    
    def _reset_sound_file(self) -> None:
        """Reset sound file to default."""
        default_sound = "fanfare.mp3"
        logger.debug(f"Resetting sound file to default: {default_sound}")
        self.sound_file_edit.setText(default_sound)
    
    def _test_windows_notification(self) -> None:
        """Test Windows notification functionality."""
        if self.on_test_notification:
            self.on_test_notification()
        else:
            logger.warning("No test notification callback set")
    
    def _pick_color(self) -> None:
        """Open color picker dialog."""
        # Use the currently selected color, or fall back to settings/default
        if hasattr(self, '_selected_color') and self._selected_color.isValid():
            current_color = self._selected_color
        else:
            accent_color = self.settings.get('accent_color', '#007acc')
            current_color = QColor(accent_color)
            if not current_color.isValid():
                current_color = QColor('#007acc')
        
        color = QColorDialog.getColor(current_color, self, "Choose Accent Color")
        if color.isValid():
            self._update_color_button(color)
            logger.debug(f"User selected accent color: {color.name()}")
    
    def _update_color_button(self, color: QColor) -> None:
        """Update the color picker button appearance."""
        self.color_picker_btn.setStyleSheet(
            f"background-color: {color.name()}; "
            f"border: 2px solid #2a2a2a; "
            f"border-radius: 4px;"
        )
        # Store the color for saving
        self._selected_color = color
    
    def _save_settings(self) -> None:
        """Save settings and close."""
        webhook_text = self.webhook_url_edit.text().strip()
        webhook_status = "EMPTY" if not webhook_text else "set ({} chars)".format(len(webhook_text))
        # Log to root app logger so this always appears in the terminal
        _app_log.info("=" * 60)
        _app_log.info("OPTIONS: Save button clicked")
        _app_log.info("OPTIONS: default_webhook_url in form: %s", webhook_status)
        _app_log.info("OPTIONS: log_directory in form: %s", "set" if self.log_directory_edit.text().strip() else "empty")
        _app_log.info("OPTIONS: Calling on_settings_save callback")

        if self.on_settings_save:
            timezone_data = self.timezone_combo.currentData()
            # Get new boss default action
            new_boss_default = 'enable' if self.new_boss_enable_radio.isChecked() else 'disable'
            
            # Ensure _selected_color is set (fallback to current settings if somehow not set)
            if hasattr(self, '_selected_color') and self._selected_color.isValid():
                accent_color = self._selected_color.name()
            else:
                # Fallback: try to get from settings, or use default
                accent_color = self.settings.get('accent_color', '#007acc')
                logger.warning(f"_selected_color was not set, using accent_color from settings: {accent_color}")
            
            sound_file_path = self.sound_file_edit.text().strip()
            if not sound_file_path:
                sound_file_path = 'fanfare.mp3'  # Default if empty
            
            settings = {
                'log_directory': self.log_directory_edit.text(),
                'default_webhook_url': self.webhook_url_edit.text(),
                'discord_bot_token': self.bot_token_edit.text(),
                'discord_sync_interval_hours': max(1, min(168, self.discord_sync_interval_spin.value())),
                'timezone': timezone_data if timezone_data else '',
                'use_military_time': self.military_time_checkbox.isChecked(),
                'sound_enabled': self.sound_enabled_checkbox.isChecked(),
                'sound_file_path': sound_file_path,
                'window_popup_on_new_boss': self.window_popup_checkbox.isChecked(),
                'windows_notification': self.windows_notification_checkbox.isChecked(),
                'new_boss_default_action': new_boss_default,
                'accent_color': accent_color
            }
            logger.debug(f"Saving accent color: {accent_color}")
            logger.debug(f"Saving sound file path: {sound_file_path}")
            logger.debug(f"Full settings dict being saved: {list(settings.keys())}")
            logger.debug(f"accent_color value: {settings.get('accent_color', 'MISSING')}")
            _app_log.info("OPTIONS: Invoking on_settings_save(settings) now")
            self.on_settings_save(settings)
            _app_log.info("OPTIONS: on_settings_save returned (settings written)")
        else:
            _app_log.warning("OPTIONS: on_settings_save is None - settings NOT saved")

        self.accept()
        self.settings_changed.emit()
    
    def set_bosses_json_path(self, path: Path) -> None:
        """Set the path to bosses.json for backup restore functionality."""
        self.bosses_json_path = Path(path)
        logger.debug(f"Set bosses.json path for backup restore: {self.bosses_json_path}")
    
    def _create_backup_now(self) -> None:
        """Create a manual backup of bosses.json."""
        if self.on_create_backup:
            try:
                backup_path = self.on_create_backup()
                if backup_path:
                    QMessageBox.information(
                        self,
                        "Backup Created",
                        f"✓ Backup created successfully!\n\n"
                        f"File: {backup_path.name}\n"
                        f"Location: {backup_path.parent}\n\n"
                        f"Your current boss data has been saved."
                    )
                    logger.info(f"[BACKUP] Manual backup created from settings: {backup_path.name}")
                else:
                    QMessageBox.warning(
                        self,
                        "Backup Failed",
                        "Could not create backup.\n\n"
                        "Please check the logs for more details."
                    )
            except Exception as e:
                logger.error(f"[BACKUP] Error creating manual backup: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Backup Error",
                    f"An error occurred while creating the backup:\n\n{str(e)}\n\n"
                    f"Please check the logs for more details."
                )
        else:
            QMessageBox.warning(
                self,
                "Backup Not Available",
                "Backup functionality is not available.\n\n"
                "Please ensure the application is fully initialized."
            )
    
    def _show_restore_dialog(self) -> None:
        """Show the backup restore dialog."""
        if not self.bosses_json_path:
            # Try to infer from default location
            app_data = Path.home() / "AppData" / "Roaming" / "boss tracker"
            self.bosses_json_path = app_data / "bosses.json"
            logger.info(f"[BACKUP RESTORE] No path set, using default: {self.bosses_json_path}")
        
        if not self.bosses_json_path:
            QMessageBox.warning(
                self,
                "Backup Restore",
                "Could not determine bosses.json location.\n\n"
                "Please ensure the application has been initialized."
            )
            return
        
        dialog = BackupRestoreDialog(self.bosses_json_path, self)
        if dialog.exec():
            logger.info("[BACKUP RESTORE] User restored a backup from settings")
            # Show reminder to restart
            QMessageBox.information(
                self,
                "Restore Complete",
                "Backup restored successfully!\n\n"
                "⚠️ Please restart the application for changes to take effect."
            )
