"""Main application entry point."""
import sys
import json
import os
import time
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QDialog
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QPalette, QColor
from typing import Optional, List, Dict
from queue import Queue

# Same-name kill dedup: two kills of the same monster name within this window are treated as one (e.g. lockout + zone).
# Set below simulation min interval (10s) so North/South back-to-back at 10s replay both get a dialog/post.
SAME_KILL_WINDOW_SECONDS = 9

# Debug instrumentation
def _get_debug_log_path():
    """Get debug log path, handling both frozen and non-frozen modes."""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as executable - use executable's directory
        base_dir = Path(sys.executable).parent
    else:
        # Running as script - use project root
        base_dir = Path(__file__).parent.parent
    debug_path = base_dir / ".cursor" / "debug.log"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    return debug_path

def debug_log(location, message, data=None, hypothesis_id=None, run_id="initial"):
    """Write debug log entry."""
    try:
        import json as json_lib
        import time
        log_entry = {
            "location": location,
            "message": message,
            "timestamp": time.time() * 1000,
            "runId": run_id,
        }
        if data:
            log_entry["data"] = data
        if hypothesis_id:
            log_entry["hypothesisId"] = hypothesis_id
        debug_path = _get_debug_log_path()
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(json_lib.dumps(log_entry) + "\n")
    except Exception as e:
        # Log to stderr if debug logging fails (for troubleshooting)
        try:
            import sys
            print(f"Debug log error: {e}", file=sys.stderr)
        except:
            pass


def _mask_webhook(url: str) -> str:
    """Return a safe string for logging (avoid exposing full webhook URL)."""
    if not url or not isinstance(url, str):
        return "(empty)"
    s = url.strip()
    if len(s) <= 20:
        return "****"
    # Show start and end: https://discord.com/api/webhooks/1234...abcd
    return f"{s[:30]}...{s[-4:]}" if len(s) > 40 else f"{s[:15]}...{s[-4:]}"


def _webhook_id_from_url(url: str) -> str:
    """Extract Discord webhook ID (first long number in path) for logging. Returns '' if not found."""
    if not url or not isinstance(url, str):
        return ""
    import re
    m = re.search(r"/webhooks/(\d+)", url.strip())
    return m.group(1) if m else ""

try:
    from .logger import setup_logging, get_logger
    from .message_parser import MessageParser, BossKillMessage
    from .boss_database import BossDatabase
    from .discord_notifier import DiscordNotifier
    from .sound_player import SoundPlayer
    from .log_monitor import LogMonitor
    from .system_tray import SystemTray
    from .options_window import OptionsWindow
    from .message_editor import MessageEditor
    from .theme_manager import ThemeManager
    from .timestamp_formatter import TimestampFormatter
    from .activity_database import ActivityDatabase
    from .main_window import MainWindow
    from .new_boss_dialog import NewBossDialog
    from .security import SecurityManager
    # Discord checker is optional (requires discord.py)
    try:
        from .discord_checker import DiscordChecker, DISCORD_AVAILABLE
    except ImportError:
        DiscordChecker = None
        DISCORD_AVAILABLE = False
except ImportError:
    # For running as script or frozen executable
    # When frozen, PyInstaller includes modules but they may need different import paths
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - try src.* imports first
        try:
            from src.logger import setup_logging, get_logger
            from src.message_parser import MessageParser, BossKillMessage
            from src.boss_database import BossDatabase
            from src.discord_notifier import DiscordNotifier
            from src.sound_player import SoundPlayer
            from src.log_monitor import LogMonitor
            from src.system_tray import SystemTray
            from src.options_window import OptionsWindow
            from src.message_editor import MessageEditor
            from src.theme_manager import ThemeManager
            from src.timestamp_formatter import TimestampFormatter
            from src.activity_database import ActivityDatabase
            from src.main_window import MainWindow
            from src.new_boss_dialog import NewBossDialog
            from src.security import SecurityManager
            try:
                from src.discord_checker import DiscordChecker, DISCORD_AVAILABLE
            except ImportError:
                DiscordChecker = None
                DISCORD_AVAILABLE = False
        except ImportError:
            # Fallback to direct imports (PyInstaller should have collected them)
            from logger import setup_logging, get_logger
            from message_parser import MessageParser, BossKillMessage
            from boss_database import BossDatabase
            from discord_notifier import DiscordNotifier
            from sound_player import SoundPlayer
            from log_monitor import LogMonitor
            from system_tray import SystemTray
            from options_window import OptionsWindow
            from message_editor import MessageEditor
            from theme_manager import ThemeManager
            from timestamp_formatter import TimestampFormatter
            from activity_database import ActivityDatabase
            from main_window import MainWindow
            from new_boss_dialog import NewBossDialog
            try:
                from security import SecurityManager
            except ImportError:
                SecurityManager = None
            try:
                from discord_checker import DiscordChecker, DISCORD_AVAILABLE
            except ImportError:
                DiscordChecker = None
                DISCORD_AVAILABLE = False
    else:
        # Running as script - add src to path
        src_path = Path(__file__).parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        from logger import setup_logging, get_logger
        from message_parser import MessageParser, BossKillMessage
        from boss_database import BossDatabase
        from discord_notifier import DiscordNotifier
        from sound_player import SoundPlayer
        from log_monitor import LogMonitor
        from system_tray import SystemTray
        from options_window import OptionsWindow
        from message_editor import MessageEditor
        from theme_manager import ThemeManager
        from timestamp_formatter import TimestampFormatter
        from activity_database import ActivityDatabase
        from main_window import MainWindow
        from new_boss_dialog import NewBossDialog
        try:
            from security import SecurityManager
        except ImportError:
            SecurityManager = None
        # Discord checker is optional (requires discord.py)
        try:
            from discord_checker import DiscordChecker, DISCORD_AVAILABLE
        except ImportError:
            DiscordChecker = None
            DISCORD_AVAILABLE = False

logger = get_logger(__name__)
_app_log = logging.getLogger('eq_boss_tracker')


class BossTrackerApp(QObject):
    """Main application class."""
    
    def __init__(self, app: QApplication, debug_mode: bool = False):
        """Initialize the application."""
        super().__init__()
        
        self.app = app
        self.debug_mode = debug_mode
        
        # Thread-safe queue for log lines from monitor thread
        self.log_line_queue = Queue()
        
        # Timer to process queued log lines on main thread
        self.log_processor_timer = QTimer()
        self.log_processor_timer.timeout.connect(self._process_queued_log_lines)
        self.log_processor_timer.start(100)  # Process every 100ms
        
        # Timer for automatic Discord sync (interval from settings, applied after _load_settings)
        self.discord_sync_timer = QTimer()
        self.discord_sync_timer.timeout.connect(self._check_and_sync_discord)
        
        # Paths
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            self.app_dir = Path(sys.executable).parent
        else:
            # Running as script
            self.app_dir = Path(__file__).parent.parent
        
        # Use user data directory for settings/data files
        self.data_dir = self._get_user_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings_path = self.data_dir / "settings.json"
        self.bosses_path = self.data_dir / "bosses.json"
        self.activity_path = self.data_dir / "activity.json"
        
        logger.info(f"Application directory: {self.app_dir}")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Settings file (load/save): {self.settings_path!s}")
        # Load settings
        self.settings, settings_migrated = self._load_settings()
        # Normalize so we never have None or stale value; always string (possibly empty)
        self.settings['default_webhook_url'] = (self.settings.get('default_webhook_url') or '').strip()
        _app_log.info(
            "STARTUP: Settings file: %s | default_webhook_url: %s (len=%d)",
            self.settings_path,
            "EMPTY" if not self.settings['default_webhook_url'] else _mask_webhook(self.settings['default_webhook_url']),
            len(self.settings['default_webhook_url'])
        )
        _app_log.info(
            "STARTUP: THIS IS THE ONLY SETTINGS FILE THE APP USES: %s (any other settings.json is IGNORED)",
            self.settings_path.resolve()
        )
        if self.settings['default_webhook_url']:
            _app_log.info("STARTUP: Webhook ID in use: %s", _webhook_id_from_url(self.settings['default_webhook_url']))
        if settings_migrated:
            self._save_settings()
        
        # Start Discord sync timer only when Discord is configured (webhook + bot token)
        if self._has_discord_sync_config():
            interval_hours = max(1, min(168, int(self.settings.get('discord_sync_interval_hours', 12))))
            self.discord_sync_timer.start(interval_hours * 3600 * 1000)
            logger.debug(f"Discord sync timer started: every {interval_hours} hour(s)")
        else:
            self.discord_sync_timer.stop()
            logger.debug("Discord sync timer not started: webhook or bot token not configured")
        
        # Set application icon (for all windows) - done after settings are loaded
        # #region agent log
        debug_log("main.py:158", "Loading application icon", {}, hypothesis_id="C", run_id="initial")
        # #endregion
        icon_path = self._set_application_icon()
        
        # #region agent log
        if icon_path and icon_path.exists():
            icon_size = icon_path.stat().st_size
            debug_log("main.py:158", "Icon file loaded", {
                "icon_path": str(icon_path),
                "file_size_bytes": icon_size,
                "file_size_mb": icon_size / 1024 / 1024
            }, hypothesis_id="C", run_id="initial")
        # #endregion
        
        # Initialize timestamp formatter
        timezone = self.settings.get('timezone', '')
        self.timestamp_formatter = TimestampFormatter(timezone if timezone else None)
        
        # Initialize databases
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:164", "Memory before database loading", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="B", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        self.boss_db = BossDatabase(str(self.bosses_path), self.app_dir)
        self.activity_db = ActivityDatabase(str(self.activity_path))
        
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:166", "Memory after database loading", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="B", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        # Track active new boss dialogs to prevent duplicates
        self.active_new_boss_dialogs: dict = {}  # boss_name -> dialog
        
        # Track active duplicate boss selection dialogs to prevent multiple dialogs for same kill
        self._active_duplicate_dialogs: dict = {}  # dialog_key -> True
        
        # Store pending boss kills (for new bosses that need to be posted after enabling)
        self.pending_boss_kills: dict = {}  # boss_name -> BossKillMessage
        
        # Track recently processed boss kills to prevent duplicate processing
        # Key: hash of log line content (most reliable) + (timestamp, monster_name) as backup
        # This prevents the same log line from being processed multiple times
        self.recently_processed_kills: set = set()  # Set of (timestamp, monster_name) tuples
        self.recently_processed_lines: set = set()  # Set of log line hashes
        # Track recent kills by monster name and timestamp for time-window duplicate detection
        # Format: {monster_name_lower: [(timestamp_datetime, location), ...]}
        self.recent_kills_by_monster: dict = {}  # For detecting same boss within time window
        # Wall-clock last Discord post time per monster (monster_key -> time.time()) - prevents 2x/3x posts
        self._last_discord_post_time_by_monster: dict = {}
        
        # Message buffering system: buffer messages for 3 seconds to prioritize guild messages over lockout messages
        # Format: {monster_name_lower: {'messages': [BossKillMessage, ...], 'timer': QTimer, 'processed': bool}}
        self.message_buffer: dict = {}  # Buffer messages for 3 seconds before processing
        
        # Cache for channel IDs (webhook_url -> channel_id)
        self._channel_id_cache: dict = {}
        
        # Boss Simulation (debug): replay capture to simulated log file
        self._simulation_state: Optional[dict] = None  # timer, batches, batch_index, log_path, interval_seconds
        
        # Initialize Discord components
        # Check for mock mode (for testing without Discord)
        use_mock_discord = os.getenv('EQ_BOSS_TRACKER_MOCK_DISCORD', 'false').lower() == 'true'
        
        if use_mock_discord:
            logger.info("MOCK MODE: Using mock Discord notifier (messages will be logged, not posted)")
            try:
                from test_utilities.mock_discord import MockDiscordNotifier, MockDiscordChecker
                self.discord_notifier = MockDiscordNotifier(
                    self.settings.get('default_webhook_url', ''),
                    self.timestamp_formatter
                )
                self.discord_checker = MockDiscordChecker()
            except ImportError:
                logger.warning("Mock Discord not available, using real Discord notifier")
                self.discord_notifier = DiscordNotifier(
                    self.settings.get('default_webhook_url', ''),
                    self.timestamp_formatter
                )
                self.discord_checker = None
        else:
            # Read webhook from same file we use for posting (Roaming settings) so default is never stale
            _webhook_path = self._get_user_data_dir() / "settings.json"
            _initial_webhook = ""
            if _webhook_path.exists():
                try:
                    with open(_webhook_path, "r", encoding="utf-8") as f:
                        _data = json.load(f)
                    _initial_webhook = (_data.get("default_webhook_url") or "").strip()
                except (json.JSONDecodeError, IOError):
                    pass
            self.discord_notifier = DiscordNotifier(_initial_webhook, self.timestamp_formatter)
            logger.debug(f"[DISCORD] Notifier created with default_webhook_url from file: {_mask_webhook(_initial_webhook)} (all posts use settings webhook)")
            # Initialize Discord checker (for duplicate detection)
            bot_token = self.settings.get('discord_bot_token', '')
            if DiscordChecker and bot_token:
                try:
                    # #region agent log
                    debug_log("main.py:204", "Creating Discord checker", {
                        "has_bot_token": bool(bot_token),
                        "token_length": len(bot_token) if bot_token else 0
                    }, hypothesis_id="D", run_id="initial")
                    # #endregion
                    
                    self.discord_checker = DiscordChecker(bot_token)
                    # Initialize the Discord client in a background thread
                    import asyncio
                    import threading
                    def init_checker():
                        try:
                            # #region agent log
                            debug_log("main.py:212", "Discord checker initializing", {}, hypothesis_id="D", run_id="initial")
                            # #endregion
                            asyncio.run(self.discord_checker.initialize())
                            # #region agent log
                            try:
                                import psutil
                                process = psutil.Process()
                                mem_info = process.memory_info()
                                debug_log("main.py:212", "Memory after Discord checker init", {
                                    "rss_mb": mem_info.rss / 1024 / 1024,
                                    "vms_mb": mem_info.vms / 1024 / 1024
                                }, hypothesis_id="D", run_id="initial")
                            except ImportError:
                                pass
                            # #endregion
                        except Exception as e:
                            logger.error(f"Error initializing Discord checker: {e}")
                    
                    init_thread = threading.Thread(target=init_checker, daemon=True)
                    init_thread.start()
                    logger.info("Discord checker created (initializing in background)")
                except Exception as e:
                    logger.warning(f"Failed to create Discord checker: {e}")
                    self.discord_checker = None
            else:
                self.discord_checker = None
                if not DiscordChecker:
                    logger.info("Discord checker not available (discord.py not installed)")
                else:
                    logger.info("Discord checker not available (no bot token)")
        
        self.discord_notifier.start()
        
        # Initialize sound player
        sound_path = self.settings.get('sound_file_path', 'fanfare.mp3')
        if not Path(sound_path).is_absolute():
            # Relative path - look in assets folder
            sound_path = self.app_dir / "assets" / sound_path
        else:
            # Absolute path - use as-is
            sound_path = Path(sound_path)
        
        # #region agent log
        if sound_path.exists():
            sound_size = sound_path.stat().st_size
            debug_log("main.py:232", "Sound file found", {
                "sound_path": str(sound_path),
                "file_size_bytes": sound_size,
                "file_size_mb": sound_size / 1024 / 1024
            }, hypothesis_id="E", run_id="initial")
        # #endregion
        
        self.sound_player = SoundPlayer(str(sound_path))
        self.sound_player.set_enabled(self.settings.get('sound_enabled', True))
        logger.debug(f"Sound player initialized with path: {sound_path}")
        
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:240", "Memory after sound player init", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="E", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        # Initialize log monitor
        log_dir = self.settings.get('log_directory', '')
        if log_dir:
            # #region agent log
            debug_log("main.py:264", "Initializing LogMonitor", {
                "log_directory": log_dir
            }, hypothesis_id="G", run_id="initial")
            # #endregion
            
            self.log_monitor = LogMonitor(log_dir, self._on_new_log_line)
            self.log_monitor.start()
            
            # #region agent log
            try:
                import psutil
                process = psutil.Process()
                mem_info = process.memory_info()
                debug_log("main.py:268", "Memory after LogMonitor start", {
                    "rss_mb": mem_info.rss / 1024 / 1024,
                    "vms_mb": mem_info.vms / 1024 / 1024
                }, hypothesis_id="G", run_id="initial")
            except ImportError:
                pass
            # #endregion
        else:
            self.log_monitor = None
            logger.warning("Log directory not configured, log monitoring disabled")
        
        # Initialize UI components
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:252", "Memory before MainWindow creation", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="C", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        self.main_window = MainWindow(debug_mode=self.debug_mode)
        
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:252", "Memory after MainWindow creation", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="C", run_id="initial")
        except ImportError:
            pass
        # #endregion
        self.main_window.boss_enabled_changed.connect(self._on_boss_enabled_changed)
        self.main_window.zone_enabled_changed.connect(self._on_zone_enabled_changed)
        self.main_window.all_bosses_enabled_changed.connect(self._on_all_bosses_enabled_changed)
        self.main_window.add_boss_requested.connect(self._on_add_boss_requested)
        self.main_window.remove_boss_requested.connect(self._on_remove_boss_requested)
        self.main_window.settings_requested.connect(self._show_options)
        self.main_window.message_format_requested.connect(self._show_message_editor)
        self.main_window.edit_respawn_times_requested.connect(self._show_respawn_time_editor)
        self.main_window.edit_boss_requested.connect(self._show_respawn_time_editor_for_boss)
        # Refresh button: Updates the UI display of bosses and activity log
        # This is useful if you've manually edited the database files or want to see latest changes
        self.main_window.refresh_requested.connect(self._on_refresh_requested)
        self.main_window.theme_switch_requested.connect(self._switch_theme)
        self.main_window.scan_requested.connect(self._on_scan_requested)
        # Manual sync from menu should force sync regardless of 12-hour check
        self.main_window.discord_sync_requested.connect(lambda: self._check_and_sync_discord(force=True))
        if self.debug_mode:
            self.main_window.boss_capture_requested.connect(self._on_boss_capture_requested)
            self.main_window.boss_simulation_requested.connect(self._on_boss_simulation_requested)
            self.main_window.activity_log.start_simulation_requested.connect(self._on_start_simulation_requested)
            self.main_window.activity_log.stop_simulation_requested.connect(self._on_stop_simulation_requested)
        
        # Set boss database reference in zone widget for respawn calculations
        self.main_window.zone_widget.set_boss_database(self.boss_db)
        
        # Set time format preference in zone widget
        use_military_time = self.settings.get('use_military_time', False)
        self.main_window.zone_widget.set_time_format(use_military_time)
        self.main_window.on_save_window_state = self._save_window_state
        
        # Set up callbacks (only for add/remove boss, which don't use signals)
        self.main_window.on_add_boss = self._handle_add_boss
        self.main_window.on_remove_boss = self._handle_remove_boss
        
        # Apply theme with accent color from settings (after main window is created)
        current_theme = self.settings.get('theme', 'dark')
        self._apply_theme(current_theme)
        
        # Restore window geometry, splitter state, and Targets by Zone scroll position
        window_geometry = self.settings.get('window_geometry')
        splitter_sizes = self.settings.get('splitter_sizes')
        zone_scroll_position = self.settings.get('zone_scroll_position', 0)
        if window_geometry or splitter_sizes or zone_scroll_position is not None:
            # Decode geometry if it's a string (base64)
            geometry_bytes = None
            if window_geometry:
                if isinstance(window_geometry, str):
                    import base64
                    try:
                        geometry_bytes = base64.b64decode(window_geometry)
                    except Exception as e:
                        logger.warning(f"Could not decode window geometry: {e}")
                elif isinstance(window_geometry, list):
                    # It's already bytes encoded as list
                    geometry_bytes = bytes(window_geometry)
            
            # Defer restoration until window is shown
            scroll_val = max(0, int(zone_scroll_position)) if zone_scroll_position is not None else None
            QTimer.singleShot(100, lambda: self.main_window.restore_window_state(geometry_bytes, splitter_sizes, scroll_val))
        
        # Initialize system tray with icon (icon_path already set above)
        tray_icon_path = str(icon_path) if icon_path else None
        self.tray = SystemTray(tray_icon_path)
        self.tray.show_window_clicked.connect(self._show_main_window)
        self.tray.options_clicked.connect(self._show_options)
        self.tray.refresh_clicked.connect(self._on_refresh_requested)
        self.tray.discord_sync_clicked.connect(lambda: self._check_and_sync_discord(force=True))
        self.tray.exit_clicked.connect(self._exit_app)
        self.tray.show()
        
        # Defer UI updates until after event loop starts
        # Use QTimer.singleShot to schedule updates after app.exec() starts
        QTimer.singleShot(0, self._initialize_ui)
        
        # Check if Discord sync is needed on startup (only when Discord is configured)
        # Wait 10 seconds to give Discord client time to connect and be ready
        if self._has_discord_sync_config():
            QTimer.singleShot(10000, self._check_and_sync_discord)  # 10 second delay
        
        # Timer to update active character display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_active_character)
        self.update_timer.start(5000)  # Update every 5 seconds
        
        logger.info("BossTrackerApp initialized successfully")
    
    def _set_application_icon(self) -> Optional[Path]:
        """Set the application icon for all windows and system tray."""
        from PyQt6.QtGui import QIcon
        
        # Look for icon in common locations
        icon_paths = [
            self.app_dir / "icons" / "tray_icon.ico",
            self.app_dir / "icons" / "app_icon.ico",
            self.app_dir / "assets" / "icon.ico",
            self.app_dir / "icon.ico",
        ]
        
        icon_path = None
        for path in icon_paths:
            if path.exists():
                icon_path = path
                logger.debug(f"Found icon file: {icon_path}")
                break
        
        if icon_path:
            try:
                icon = QIcon(str(icon_path))
                # Verify icon is valid (not null)
                if icon.isNull():
                    logger.warning(f"Icon file found but QIcon is null: {icon_path}")
                    return None
                
                # Set for application (affects all windows)
                self.app.setWindowIcon(icon)
                logger.info(f"Application icon set from: {icon_path}")
                return icon_path
            except Exception as e:
                logger.error(f"Error loading icon from {icon_path}: {e}", exc_info=True)
                return None
        else:
            logger.debug("No custom icon found, using default")
            return None
    
    def _get_user_data_dir(self) -> Path:
        """
        Get the user data directory for storing settings and data files.
        Uses OS-specific application data directories.
        
        Returns:
            Path to user data directory
        """
        app_name = "boss tracker"
        
        if sys.platform == 'win32':
            # Windows: %APPDATA%/boss tracker
            appdata = os.getenv('APPDATA')
            if appdata:
                return Path(appdata) / app_name
            else:
                # Fallback to user home
                return Path.home() / "AppData" / "Roaming" / app_name
        elif sys.platform == 'darwin':
            # macOS: ~/Library/Application Support/boss tracker
            return Path.home() / "Library" / "Application Support" / app_name
        else:
            # Linux: ~/.config/boss tracker
            xdg_config = os.getenv('XDG_CONFIG_HOME')
            if xdg_config:
                return Path(xdg_config) / app_name
            else:
                return Path.home() / ".config" / app_name
    
    def _initialize_ui(self) -> None:
        """Initialize UI components after event loop starts."""
        try:
            logger.debug("Initializing UI components")
            # Update UI with current data
            self._refresh_bosses()
            self._update_activity_log()
            self._update_active_character()
            logger.debug("UI components initialized")
        except Exception as e:
            logger.error(f"Error initializing UI: {e}", exc_info=True)
    
    def _load_settings(self) -> tuple:
        """Load settings from JSON file and decrypt sensitive fields. Returns (settings_dict, migrated)."""
        # Detect OS theme on first run
        is_first_run = not self.settings_path.exists()
        migrated = False
        default_theme = "dark"
        
        if is_first_run:
            try:
                from .os_theme_detector import detect_os_theme
                default_theme = detect_os_theme()
                logger.info(f"First run - detected OS theme: {default_theme}")
            except ImportError:
                try:
                    from os_theme_detector import detect_os_theme
                    default_theme = detect_os_theme()
                    logger.info(f"First run - detected OS theme: {default_theme}")
                except ImportError:
                    logger.debug("OS theme detector not available, using default dark theme")
            except Exception as e:
                logger.warning(f"Error detecting OS theme on first run: {e}")
        
        default_settings = {
            "log_directory": "",
            "default_webhook_url": "",
            "discord_bot_token": "",
            "timezone": "",
            "use_military_time": False,  # False = 12-hour format (AM/PM), True = 24-hour format (military)
            "message_template": "{discord_timestamp} {monster} ({note}) was killed in {location}!",
            "lockout_message_template": "{discord_timestamp} {monster} ({note}) lockout detected!",
            "sound_enabled": True,
            "sound_file_path": "fanfare.mp3",
            "window_popup_on_new_boss": True,
            "windows_notification": False,  # Note: Actually cross-platform, name kept for backward compatibility
            "auto_detect_active_file": True,
            "new_boss_default_action": "enable",  # "enable" or "disable" - default action for new targets
            "accent_color": "#007acc",  # Default blue accent color
            "theme": default_theme,  # Use detected OS theme on first run
            "window_geometry": None,  # Base64 encoded window geometry
            "splitter_sizes": None,  # [left_size, right_size]
            "zone_scroll_position": 0,  # Targets by Zone vertical scroll position
            "debug_simulation_interval_seconds": 30,
            "discord_sync_interval_hours": 12,  # How often to auto-sync kill times from Discord (min 1h; 1h is fine for testing)
        }
        
        logger.debug(f"[SETTINGS] Load: path={self.settings_path!s}, exists={self.settings_path.exists()}")
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                logger.debug(f"[SETTINGS] Load: file read OK, keys in file: default_webhook_url={('default_webhook_url' in loaded)}, raw value length={len(loaded.get('default_webhook_url') or '')}")
                # Merge with defaults
                default_settings.update(loaded)
                # Decrypt sensitive fields (webhook may be plaintext or legacy encrypted)
                if SecurityManager:
                    SecurityManager.decrypt_dict_value(default_settings, 'default_webhook_url')
                    SecurityManager.decrypt_dict_value(default_settings, 'discord_bot_token')
                default_webhook = default_settings.get('default_webhook_url', '') or ''
                logger.info(f"[SETTINGS] Loaded from {self.settings_path!s} | default_webhook_url: {_mask_webhook(default_webhook)} (len={len(default_webhook)})")
                # Migration: Add {note} to templates if missing (ensures Vex Thal notes appear in Discord)
                template = default_settings.get('message_template', '')
                if template and '{note}' not in template and '{monster}' in template:
                    default_settings['message_template'] = template.replace('{monster}', '{monster} ({note})')
                    logger.info("Migrated message_template to include {note} for Discord note support")
                    migrated = True
                lockout_template = default_settings.get('lockout_message_template', '')
                if lockout_template and '{note}' not in lockout_template and '{monster}' in lockout_template:
                    default_settings['lockout_message_template'] = lockout_template.replace('{monster}', '{monster} ({note})')
                    logger.info("Migrated lockout_message_template to include {note} for Discord note support")
                    migrated = True
                logger.debug(f"[SETTINGS] Load: accent_color={default_settings.get('accent_color', 'NOT FOUND')!r}, log_directory={default_settings.get('log_directory', '')!r}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"[SETTINGS] Error loading settings from {self.settings_path!s}: {e}", exc_info=True)
        else:
            logger.info(f"[SETTINGS] File not found: {self.settings_path!s}, using defaults")
        
        return (default_settings, migrated)
    
    def _save_settings(self) -> None:
        """Save settings to JSON file. Uses same resolved path as _get_webhook_url_for_post and flushes to disk."""
        try:
            path = self.settings_path.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            webhook_value = (self.settings.get('default_webhook_url') or '').strip()
            logger.info(f"[SETTINGS] Saving to {path!s} | default_webhook_url: {_mask_webhook(webhook_value)} (len={len(webhook_value)})")
            settings_to_save = self.settings.copy()
            settings_to_save['default_webhook_url'] = webhook_value
            if SecurityManager:
                SecurityManager.encrypt_dict_value(settings_to_save, 'discord_bot_token')
                logger.debug("[SETTINGS] Encrypted discord_bot_token for save")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            logger.debug(f"[SETTINGS] Write completed and synced for {path!s}")
            logger.info("Settings saved successfully")
        except IOError as e:
            logger.error(f"[SETTINGS] Error saving to {self.settings_path!s}: {e}", exc_info=True)
    
    def _save_window_state(self, geometry: bytes, splitter_sizes: list, zone_scroll_position: int = 0) -> None:
        """Save window geometry, splitter state, and Targets by Zone scroll position. Does not overwrite webhook – re-read from file first."""
        try:
            # Re-read webhook from file so we never overwrite it with stale in-memory value (e.g. from before Options Save)
            path = self.settings_path.resolve()
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.settings['default_webhook_url'] = (data.get('default_webhook_url') or '').strip()
                except (json.JSONDecodeError, IOError):
                    pass
            import base64
            geometry_str = base64.b64encode(geometry).decode('utf-8')
            self.settings['window_geometry'] = geometry_str
            self.settings['splitter_sizes'] = splitter_sizes
            self.settings['zone_scroll_position'] = max(0, int(zone_scroll_position))
            self._save_settings()
            logger.debug(f"Window state saved (splitter sizes: {splitter_sizes}, zone_scroll: {zone_scroll_position})")
        except Exception as e:
            logger.error(f"Error saving window state: {e}", exc_info=True)
    
    def _on_new_log_line(self, line: str) -> None:
        """Handle a new line from the log file (called from log monitor thread)."""
        # Early duplicate check: hash the line content before queuing
        # This prevents the same line from being queued multiple times
        line_hash = hashlib.md5(line.encode('utf-8', errors='ignore')).hexdigest()
        if line_hash in self.recently_processed_lines:
            # Only log boss kill related duplicates to reduce noise
            if "has killed" in line.lower() or "incurred a lockout" in line.lower():
                logger.warning(f"[DUPLICATE DEBUG] SKIPPING at queue level - Duplicate log line (hash match): {line[:150]}... | Hash: {line_hash[:16]}...")
                # #region agent log
                debug_log("main._on_new_log_line", "skip duplicate", {"line_preview": line[:120], "hash": line_hash[:12]}, hypothesis_id="H_skip_dup", run_id="initial")
                # #endregion
            return
        
        # Log boss kill related lines for debugging
        if "has killed" in line.lower() or "incurred a lockout" in line.lower():
            logger.info(f"[DUPLICATE DEBUG] NEW LOG LINE QUEUED: {line[:250]} | Hash: {line_hash[:16]}...")
            # #region agent log
            debug_log("main._on_new_log_line", "queued", {"line_preview": line[:120], "hash": line_hash[:12]}, hypothesis_id="H_queued", run_id="initial")
            # #endregion
        
        # Mark as processed immediately to prevent race conditions
        # (We'll verify it's actually a boss kill in _process_log_line)
        self.recently_processed_lines.add(line_hash)
        
        # Queue the line for processing on the main thread
        self.log_line_queue.put(line)
    
    def _process_queued_log_lines(self) -> None:
        """Process queued log lines on the main thread."""
        try:
            # Process all queued lines (up to 10 at a time to avoid blocking)
            processed = 0
            while processed < 10 and not self.log_line_queue.empty():
                try:
                    line = self.log_line_queue.get_nowait()
                    self._process_log_line(line)
                    processed += 1
                except:
                    break
        except Exception as e:
            logger.error(f"Error processing queued log lines: {e}", exc_info=True)
    
    def _process_log_line(self, line: str) -> None:
        """Process a log line on the main thread."""
        try:
            # Log all lines that might be boss kills for debugging
            if "tells the guild" in line.lower() and "has killed" in line.lower():
                logger.info(f"[DUPLICATE DEBUG] Processing potential guild message kill line: {line[:200]}")
            elif "incurred a lockout" in line.lower():
                logger.info(f"[DUPLICATE DEBUG] Processing potential lockout line: {line[:200]}")
            
            # Try normal guild message parsing first
            parsed = MessageParser.parse_line(line)
            parse_method = "guild_message"
            
            # If normal parsing fails, try lockout message as fallback
            if not parsed:
                parsed = MessageParser.parse_lockout_line(line)
                if parsed:
                    parse_method = "lockout"
                    logger.info(f"[DUPLICATE DEBUG] Parsed lockout boss kill: {parsed.monster} at {parsed.timestamp} (location: {parsed.location})")
            else:
                logger.info(f"[DUPLICATE DEBUG] Parsed guild message boss kill: {parsed.monster} at {parsed.timestamp} (location: {parsed.location}, player: {parsed.player})")
            
            if not parsed:
                return
            
            # Create a hash of the log line content for reliable duplicate detection
            line_hash = hashlib.md5(line.encode('utf-8', errors='ignore')).hexdigest()
            # Do NOT skip here when line_hash is in recently_processed_lines: that set is populated
            # in _on_new_log_line when we *queue* the line (to prevent double-queueing). Queued lines
            # are meant to be processed here; duplicate *posts* are prevented by kill_key and time-window.

            # Also check the parsed kill key (in case same kill was already processed from another line)
            kill_key = (parsed.timestamp, parsed.monster.lower())
            if kill_key in self.recently_processed_kills:
                logger.warning(f"[DUPLICATE DEBUG] SKIPPING - Duplicate kill (exact timestamp match): {parsed.monster} at {parsed.timestamp} | "
                             f"Parse method: {parse_method} | Location: {parsed.location} | Already processed")
                # Still add to activity log for tracking, but don't post
                # This ensures activity log shows all detected kills, even duplicates
                try:
                    self._add_activity_entry(parsed, "Duplicate detected (exact timestamp match)", posted=False)
                except Exception as e:
                    logger.error(f"[ACTIVITY] Error adding duplicate activity entry: {e}", exc_info=True)
                return
            
            # CRITICAL: For duplicate bosses, check for duplicates FIRST before any other checks
            # This ensures the dialog is shown and prevents creating new entries or using wrong boss
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            all_bosses = self.boss_db.get_bosses_by_name(parsed.monster)
            
            # If this is a known duplicate boss, handle it specially BEFORE location check
            if parsed.monster in duplicate_boss_names and len(all_bosses) > 0:
                logger.info(f"[EARLY DUPLICATE CHECK] Known duplicate boss '{parsed.monster}' detected - found {len(all_bosses)} existing entries")
                for i, db_boss in enumerate(all_bosses):
                    note = db_boss.get('note', '').strip()
                    location = db_boss.get('location', 'Unknown')
                    logger.info(f"[EARLY DUPLICATE CHECK]   Existing entry {i+1}: note='{note}', location={location}")
                
                # Skip early location check - let the duplicate handler deal with it after buffering
                # This prevents using get_boss() which only returns the first match
                logger.info(f"[EARLY DUPLICATE CHECK] Skipping early location check - will handle in duplicate selection after buffering")
            # Match by name: one boss in UI = accept both lockout and zone messages (same boss).
            # Only require location-type match when multiple entries exist (e.g. North/South variants).
            elif self.boss_db.exists(parsed.monster):
                all_bosses_for_type = self.boss_db.get_bosses_by_name(parsed.monster)
                parsed_is_lockout = parsed.location == "Lockouts"
                has_matching_location_type = any(
                    (b.get('location') == "Lockouts") == parsed_is_lockout for b in all_bosses_for_type
                )
                # Skip only when we have multiple entries and none match message type
                if len(all_bosses_for_type) > 1 and not has_matching_location_type:
                    first_boss = all_bosses_for_type[0] if all_bosses_for_type else None
                    logger.info(f"[DUPLICATE DEBUG] SKIPPING - Location mismatch (early check): {parsed.monster} | "
                              f"Multiple entries, none match message type | "
                              f"Parsed message: {parsed.location} ({'lockout' if parsed_is_lockout else 'zone'}) | "
                              f"Parse method: {parse_method}")
                    if first_boss and first_boss.get('enabled', False):
                        self._add_activity_entry(parsed, f"Location mismatch (no {parsed.location} entry for this boss)", posted=False)
                    return
            
            # Mark this line as processed (line_hash already added in _on_new_log_line)
            self.recently_processed_lines.add(line_hash)  # Ensure it's in set (idempotent)
            
            # Clean up old entries (keep only last 2000 to prevent memory growth)
            if len(self.recently_processed_lines) > 2000:
                # Remove half the entries (simple approach - order doesn't matter for deduplication)
                entries_list = list(self.recently_processed_lines)
                self.recently_processed_lines = set(entries_list[len(entries_list)//2:])
                logger.debug(f"Cleaned up recently processed lines set, kept {len(self.recently_processed_lines)} entries")
            
            if len(self.recently_processed_kills) > 1000:
                # Remove half the entries
                entries_list = list(self.recently_processed_kills)
                self.recently_processed_kills = set(entries_list[len(entries_list)//2:])
                logger.debug(f"Cleaned up recently processed kills set, kept {len(self.recently_processed_kills)} entries")
            
            logger.info(f"[DUPLICATE DEBUG] PROCESSING - Boss kill passed all duplicate checks: {parsed.monster} at {parsed.timestamp} | "
                       f"Parse method: {parse_method} | Location: {parsed.location} | Player: {parsed.player if parsed.player else 'N/A'}")
            
            # Buffer messages for 3 seconds to prioritize guild (zone) messages over lockout messages.
            # Read BOTH types; after the window, post exactly one message: zone if any, else lockout.
            # Do NOT mark kill_key as processed here—only when we flush the buffer and post one message.
            monster_key = parsed.monster.lower()
            buffer_window_seconds = 3.0  # 3 second window as requested
            
            if monster_key not in self.message_buffer:
                # CRITICAL: Before creating a new buffer, check if we recently posted this kill
                # (Late messages arrive after we processed and deleted the buffer - prevent re-posting)
                try:
                    kill_time = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
                    if monster_key in self.recent_kills_by_monster:
                        for prev_time, _ in self.recent_kills_by_monster[monster_key]:
                            time_diff = abs((kill_time - prev_time).total_seconds())
                            if time_diff <= SAME_KILL_WINDOW_SECONDS:
                                logger.warning(f"[BUFFER] Late message for {parsed.monster} - kill already posted {time_diff:.1f}s ago, skipping (no new buffer)")
                                self._add_activity_entry(parsed, f"Late duplicate (posted {time_diff:.1f}s ago)", posted=False)
                                return
                except ValueError:
                    pass
                # First message for this boss - start buffering
                self.message_buffer[monster_key] = {
                    'messages': [parsed],
                    'timer': QTimer(),
                    'processed': False
                }
                
                # Set up timer to process after buffer window
                # CRITICAL: Use lambda with monster_key to ensure correct key is used
                # Also ensure timer can only fire once
                def process_buffered_messages():
                    # Double-check buffer still exists and isn't processed (defense in depth)
                    if monster_key in self.message_buffer and not self.message_buffer[monster_key]['processed']:
                        self._process_buffered_messages(monster_key)
                    else:
                        logger.warning(f"[BUFFER] Timer fired but buffer already processed or doesn't exist for {monster_key}")
                
                self.message_buffer[monster_key]['timer'].timeout.connect(process_buffered_messages)
                self.message_buffer[monster_key]['timer'].setSingleShot(True)  # Ensure it only fires once
                self.message_buffer[monster_key]['timer'].start(int(buffer_window_seconds * 1000))
                logger.info(f"[BUFFER] Started {buffer_window_seconds}s timer for {parsed.monster} (monster_key: {monster_key})")
                # #region agent log
                debug_log("main._process_log_line", "buffer started", {"monster": parsed.monster, "monster_key": monster_key, "location": parsed.location}, hypothesis_id="H_parsed_buffering", run_id="initial")
                # #endregion
                logger.info(f"[BUFFER] Buffering message for {parsed.monster} (first message, waiting {buffer_window_seconds}s for more)")
                logger.info(f"[BUFFER] Message details: location={parsed.location}, timestamp={parsed.timestamp}")
            else:
                # Additional message for same boss within buffer window - check if it's a duplicate first
                # CRITICAL: Even though it's a different log line, if it has the same timestamp, it's the same kill
                kill_key_check = (parsed.timestamp, parsed.monster.lower())
                if kill_key_check in self.recently_processed_kills:
                    logger.warning(f"[BUFFER] Additional message has same kill_key as already processed - skipping: {parsed.monster} at {parsed.timestamp}")
                    self._add_activity_entry(parsed, "Duplicate detected (same timestamp already in buffer)", posted=False)
                    return
                
                # Additional message for same boss within buffer window - add to buffer
                buffer_data = self.message_buffer[monster_key]
                if not buffer_data['processed']:
                    buffer_data['messages'].append(parsed)
                    logger.info(f"[BUFFER] Added message to buffer for {parsed.monster} (now {len(buffer_data['messages'])} messages buffered)")
                    logger.info(f"[BUFFER] New message: location={parsed.location}, timestamp={parsed.timestamp}")
                    logger.info(f"[BUFFER] All buffered messages: {[(m.location, m.timestamp) for m in buffer_data['messages']]}")
                else:
                    # Buffer already processed, this is a late message - check if it's a duplicate
                    logger.warning(f"[BUFFER] Late message received for {parsed.monster} after buffer processed - checking for duplicate")
                    
                    # CRITICAL: Check BOTH exact match and time window before processing late messages
                    kill_key = (parsed.timestamp, parsed.monster.lower())
                    if kill_key in self.recently_processed_kills:
                        logger.warning(f"[BUFFER] Late message is duplicate (exact timestamp match) - skipping")
                        self._add_activity_entry(parsed, "Late duplicate (exact timestamp match)", posted=False)
                        return
                    
                    # Check recent kills to see if this is a duplicate
                    try:
                        kill_time = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
                        if monster_key in self.recent_kills_by_monster:
                            for prev_time, prev_location in self.recent_kills_by_monster[monster_key]:
                                time_diff = abs((kill_time - prev_time).total_seconds())
                                if time_diff <= SAME_KILL_WINDOW_SECONDS:
                                    logger.warning(f"[BUFFER] Late message is duplicate (within {time_diff:.1f}s of previous kill) - skipping")
                                    self._add_activity_entry(parsed, f"Late duplicate (within {time_diff:.1f}s)", posted=False)
                                    return
                    except ValueError:
                        pass
                    # Not a duplicate, continue to normal processing below
                    logger.info(f"[BUFFER] Late message passed duplicate checks - will process")
            
            # Don't process immediately - wait for buffer timer (unless this is a late message)
            if monster_key in self.message_buffer and not self.message_buffer[monster_key]['processed']:
                logger.info(f"[BUFFER] Returning early - waiting for buffer timer for {parsed.monster} (buffer has {len(self.message_buffer[monster_key]['messages'])} messages)")
                return
            
            # Continue with normal processing (for late messages only - should be rare)
            logger.warning(f"[BUFFER] Processing late message immediately (buffer already processed or not buffered): {parsed.monster}")
            logger.warning(f"[BUFFER] This should be rare - message arrived after buffer window closed")
            
            # CRITICAL: Check for duplicate bosses FIRST before checking if boss exists
            # This prevents creating new generic entries when noted variants already exist
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            all_bosses = self.boss_db.get_bosses_by_name(parsed.monster)
            
            if parsed.monster in duplicate_boss_names and len(all_bosses) > 0:
                logger.info(f"[LATE PROCESS] Known duplicate boss '{parsed.monster}' detected - found {len(all_bosses)} existing entries")
                for i, db_boss in enumerate(all_bosses):
                    note = db_boss.get('note', '').strip()
                    location = db_boss.get('location', 'Unknown')
                    logger.info(f"[LATE PROCESS]   Existing entry {i+1}: note='{note}', location={location}")
                
                # If multiple entries exist, show dialog
                if len(all_bosses) > 1:
                    logger.info(f"[LATE PROCESS] Multiple entries found - showing selection dialog")
                    boss = self._handle_duplicate_boss_selection(parsed.monster, all_bosses, parsed)
                    if not boss:
                        logger.warning(f"[LATE PROCESS] User cancelled duplicate boss selection for '{parsed.monster}' - kill will not be posted")
                        self._add_activity_entry(parsed, "Kill detected but cancelled (duplicate name selection)", posted=False)
                        return
                    else:
                        selected_note = boss.get('note', '').strip()
                        logger.info(f"[LATE PROCESS] User selected boss with note: '{selected_note}' - will use this entry")
                        # Verify location match
                        boss_location = boss.get('location', '')
                        parsed_is_lockout = parsed.location == "Lockouts"
                        boss_is_lockout = boss_location == "Lockouts"
                        if parsed_is_lockout != boss_is_lockout:
                            logger.info(f"[LATE PROCESS] Location mismatch: boss={boss_location}, message={parsed.location}")
                            self._add_activity_entry(parsed, f"Location mismatch (selected boss is {boss_location}, message is {parsed.location})", posted=False)
                            return
                        # Location matches, process with selected boss
                        if boss.get('enabled', False):
                            self._process_boss_kill(parsed, boss)
                        else:
                            self._add_activity_entry(parsed, "Boss kill detected (disabled - not posted)", posted=False)
                        return
                else:
                    # Only one entry exists - use it
                    boss = all_bosses[0]
                    logger.info(f"[LATE PROCESS] Single entry found - using it (note: '{boss.get('note', '')}')")
                    # Verify location match
                    boss_location = boss.get('location', '')
                    parsed_is_lockout = parsed.location == "Lockouts"
                    boss_is_lockout = boss_location == "Lockouts"
                    if parsed_is_lockout != boss_is_lockout:
                        logger.info(f"[LATE PROCESS] Location mismatch: boss={boss_location}, message={parsed.location}")
                        self._add_activity_entry(parsed, f"Location mismatch (boss is {boss_location}, message is {parsed.location})", posted=False)
                        return
                    # Location matches, process
                    if boss.get('enabled', False):
                        self._process_boss_kill(parsed, boss)
                    else:
                        self._add_activity_entry(parsed, "Boss kill detected (disabled - not posted)", posted=False)
                    return
            
            # Normal boss processing (not a known duplicate)
            if not self.boss_db.exists(parsed.monster):
                # New boss detected - show dialog
                logger.info(f"New boss detected: {parsed.monster} in {parsed.location}")
                # Store the parsed message so we can post it if user enables posting
                self.pending_boss_kills[parsed.monster.lower()] = parsed
                # Add activity log entry for new boss detection
                self.activity_db.add_activity(
                    timestamp=parsed.timestamp,
                    monster=parsed.monster,
                    location=parsed.location,
                    player=parsed.player,
                    guild=parsed.guild,
                    posted_to_discord=False,
                    discord_message=None,
                    status="New boss detected (not in database)"
                )
                self.main_window.add_activity(parsed.timestamp, parsed.monster, parsed.location, "New boss detected (not in database)")
                self._handle_new_boss(parsed)
            else:
                # Boss exists - check for duplicate names
                duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
                all_bosses = self.boss_db.get_bosses_by_name(parsed.monster)
                
                if len(all_bosses) > 1:
                    # Multiple bosses with same name - handle based on type
                    logger.info(f"[PROCESS] Found {len(all_bosses)} bosses with name '{parsed.monster}'")
                    for i, db_boss in enumerate(all_bosses):
                        note = db_boss.get('note', '').strip()
                        location = db_boss.get('location', 'Unknown')
                        logger.info(f"[PROCESS]   Entry {i+1}: note='{note}', location={location}")
                    
                    if parsed.monster in duplicate_boss_names:
                        # Hardcoded duplicates - show selection dialog
                        logger.info(f"[PROCESS] Hardcoded duplicate boss '{parsed.monster}' - showing selection dialog")
                        boss = self._handle_duplicate_boss_selection(parsed.monster, all_bosses, parsed)
                        if not boss:
                            # User cancelled or no selection
                            logger.warning(f"[PROCESS] User cancelled duplicate boss selection for '{parsed.monster}' - kill will not be posted")
                            self._add_activity_entry(parsed, "Kill detected but cancelled (duplicate name selection)", posted=False)
                            return
                        else:
                            selected_note = boss.get('note', '').strip()
                            logger.info(f"[PROCESS] User selected boss with note: '{selected_note}' - will include in Discord message")
                    else:
                        # Other duplicates (e.g., lockout + zone) - match by location
                        logger.info(f"[PROCESS] Multiple entries found - matching by location: {parsed.location}")
                        matching_boss = None
                        for b in all_bosses:
                            boss_loc = b.get('location', '')
                            msg_is_lockout = parsed.location == "Lockouts"
                            boss_is_lockout = boss_loc == "Lockouts"
                            if msg_is_lockout == boss_is_lockout:
                                matching_boss = b
                                logger.info(f"[PROCESS] Matched boss by location: '{parsed.monster}' in '{boss_loc}' (message: {parsed.location})")
                                break
                        
                        if matching_boss:
                            boss = matching_boss
                        else:
                            # No location match - this shouldn't happen, but log and use first
                            logger.warning(f"[PROCESS] WARNING: No location match found for '{parsed.monster}' (message: {parsed.location})")
                            logger.warning(f"[PROCESS] Available bosses: {[(b.get('location'), b.get('note')) for b in all_bosses]}")
                            boss = all_bosses[0]
                            logger.warning(f"[PROCESS] Using first boss as fallback: {boss.get('location')}")
                else:
                    # Single boss - use standard lookup
                    boss = self.boss_db.get_boss(parsed.monster)
                
                if boss:
                    boss_location = boss.get('location', '')
                    parsed_is_lockout = parsed.location == "Lockouts"
                    boss_is_lockout = boss_location == "Lockouts"
                    # Only enforce location-type match when multiple entries exist (pick the right one)
                    # Single boss in UI = match by name only; accept both lockout and zone messages
                    if len(all_bosses) > 1 and parsed_is_lockout != boss_is_lockout:
                        logger.info(f"[DUPLICATE DEBUG] SKIPPING - Location mismatch (late check): {parsed.monster} | "
                                  f"Boss configured as: {boss_location} ({'lockout' if boss_is_lockout else 'zone'}) | "
                                  f"Parsed message: {parsed.location} ({'lockout' if parsed_is_lockout else 'zone'}) | "
                                  f"Parse method: {parse_method}")
                        if boss.get('enabled', False):
                            self._add_activity_entry(parsed, f"Location mismatch (boss is {boss_location}, message is {parsed.location})", posted=False)
                        return
                    
                    # Single boss or location matches, check if enabled
                    if boss.get('enabled', False):
                        # Process boss kill (will add/update activity log entry)
                        logger.info(f"[DUPLICATE DEBUG] PROCESSING - Enabled boss kill: {parsed.monster} in {parsed.location} | "
                                  f"Parse method: {parse_method} | Boss location: {boss_location} | Will post to Discord")
                        self._process_boss_kill(parsed, boss)
                    else:
                        logger.debug(f"Boss '{parsed.monster}' exists but is disabled (location: {parsed.location})")
                        # Add activity log entry for disabled boss
                        self._add_activity_entry(parsed, "Boss kill detected (disabled - not posted)", posted=False)
                else:
                    logger.warning(f"Boss '{parsed.monster}' was found to exist but get_boss returned None")
        except Exception as e:
            logger.error(f"Error processing log line: {e}", exc_info=True)
            logger.debug(f"Problematic line was: {line[:200]}")
    
    def _process_buffered_messages(self, monster_key: str) -> None:
        """
        Process buffered messages for a monster, selecting the best one to process.
        Prioritizes guild messages (Druzzil Ro) over lockout messages.
        
        Args:
            monster_key: Lowercase monster name key
        """
        # #region agent log
        debug_log("main._process_buffered_messages", "entry", {"monster_key": monster_key}, hypothesis_id="H_buffer_flush", run_id="initial")
        # #endregion
        if monster_key not in self.message_buffer:
            logger.warning(f"[BUFFER] No buffer found for {monster_key}")
            return
        
        buffer_data = self.message_buffer[monster_key]
        if buffer_data['processed']:
            logger.warning(f"[BUFFER] Buffer for {monster_key} already processed - skipping (this should not happen)")
            return
        
        # CRITICAL: Mark as processed IMMEDIATELY at the very start to prevent any race conditions
        # This must happen before any other processing
        buffer_data['processed'] = True
        buffer_data['timer'].stop()  # Stop timer immediately
        logger.info(f"[BUFFER] Marked buffer as processed and stopped timer for {monster_key} at start of processing")
        
        messages = buffer_data['messages']
        if not messages:
            logger.warning(f"[BUFFER] No messages in buffer for {monster_key}")
            # Clean up
            buffer_data['timer'].stop()
            del self.message_buffer[monster_key]
            return
        
        # Buffer already marked as processed at start of function - this is redundant but kept for clarity
        # Timer already stopped at start of function
        
        # Prioritize guild messages over lockout messages
        # Guild messages have location != "Lockouts" and usually have player/guild info
        guild_messages = [msg for msg in messages if msg.location != "Lockouts"]
        lockout_messages = [msg for msg in messages if msg.location == "Lockouts"]
        
        logger.info(f"[BUFFER] Processing buffer for {monster_key}: {len(messages)} total messages ({len(guild_messages)} guild, {len(lockout_messages)} lockout)")
        for i, msg in enumerate(messages):
            logger.info(f"[BUFFER]   Message {i+1}: location={msg.location}, timestamp={msg.timestamp}, player={msg.player or 'N/A'}")
        
        selected_message = None
        if guild_messages:
            # Prefer guild messages - they parse boss and zone better
            # If multiple guild messages, use the first one (they should be identical)
            selected_message = guild_messages[0]
            logger.info(f"[BUFFER] Selected guild message for {selected_message.monster} (from {len(messages)} total messages: {len(guild_messages)} guild, {len(lockout_messages)} lockout)")
        elif lockout_messages:
            # Fallback to lockout message if no guild message
            # CRITICAL: Only select the FIRST lockout message, even if there are multiple
            selected_message = lockout_messages[0]
            logger.info(f"[BUFFER] Selected FIRST lockout message for {selected_message.monster} (skipping {len(lockout_messages)-1} other lockout message(s), {len(messages)} total messages)")
        else:
            # Shouldn't happen, but handle gracefully
            logger.error(f"[BUFFER] No valid messages found in buffer for {monster_key}")
            del self.message_buffer[monster_key]
            return
        
        # Log skipped messages to activity log
        skipped_messages = [msg for msg in messages if msg != selected_message]
        if skipped_messages:
            logger.info(f"[BUFFER] Skipping {len(skipped_messages)} duplicate message(s) for {selected_message.monster}")
            for skipped in skipped_messages:
                logger.info(f"[BUFFER]   - Skipped: {skipped.location} at {skipped.timestamp} (buffer selected {selected_message.location} message)")
                # Add to activity log so user can see what was skipped
                skip_reason = f"Duplicate message skipped (buffer selected {selected_message.location} message instead)"
                self._add_activity_entry(skipped, skip_reason, posted=False)
        
        # CRITICAL: Clean up buffer IMMEDIATELY to prevent any other code paths from processing these messages
        # Timer already stopped above, but ensure buffer is deleted
        if monster_key in self.message_buffer:
            del self.message_buffer[monster_key]
            logger.info(f"[BUFFER] Buffer cleaned up for {monster_key} - only processing 1 selected message")
        
        # Do NOT add kill_key here: _process_boss_kill adds it after its duplicate checks so we don't skip the post.
        # Process the selected message through normal flow (same logic as _process_log_line)
        logger.info(f"[BUFFER] Processing selected message: {selected_message.monster} at {selected_message.timestamp} | Location: {selected_message.location}")
        logger.info(f"[BUFFER] Skipped {len(skipped_messages)} duplicate message(s), processing 1 selected message")
        
        # Use the same processing logic as _process_log_line, but skip buffering
        if not self.boss_db.exists(selected_message.monster):
            # New boss detected - show dialog
            logger.info(f"New boss detected: {selected_message.monster} in {selected_message.location}")
            self.pending_boss_kills[selected_message.monster.lower()] = selected_message
            # Add activity log entry for new boss detection
            self.activity_db.add_activity(
                timestamp=selected_message.timestamp,
                monster=selected_message.monster,
                location=selected_message.location,
                player=selected_message.player,
                guild=selected_message.guild,
                posted_to_discord=False,
                discord_message=None,
                status="New boss detected (not in database)"
            )
            self.main_window.add_activity(selected_message.timestamp, selected_message.monster, selected_message.location, "New boss detected (not in database)")
            self._handle_new_boss(selected_message)
        else:
            # Boss exists - ALWAYS check for duplicate names (bosses with same name but different notes)
            # This ensures the dialog is shown for any boss with multiple variants
            all_bosses = self.boss_db.get_bosses_by_name(selected_message.monster)
            logger.info(f"[DUPLICATE CHECK] Checking for duplicate bosses: '{selected_message.monster}' - found {len(all_bosses)} entries")
            for i, db_boss in enumerate(all_bosses):
                note = db_boss.get('note', '').strip()
                location = db_boss.get('location', 'Unknown')
                logger.info(f"[DUPLICATE CHECK]   Entry {i+1}: note='{note}', location={location}")
            
            # Check if multiple bosses have different notes (indicating North/South variants)
            bosses_with_notes = [b for b in all_bosses if b.get('note', '').strip()]
            has_multiple_variants = len(bosses_with_notes) > 1
            
            # Known duplicate bosses that should always show dialog if multiple entries exist
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            is_known_duplicate = selected_message.monster in duplicate_boss_names
            
            if len(all_bosses) > 1 and (has_multiple_variants or is_known_duplicate):
                # Multiple bosses with same name - show selection dialog
                # #region agent log
                debug_log("main.py:_process_buffered", "Duplicate boss dialog condition MET", {
                    "monster": selected_message.monster, "all_bosses_count": len(all_bosses),
                    "has_multiple_variants": has_multiple_variants, "is_known_duplicate": is_known_duplicate,
                    "notes": [b.get("note", "") for b in all_bosses]
                }, hypothesis_id="DUP_BOSS", run_id="initial")
                # #endregion
                logger.info(f"[DUPLICATE CHECK] Found {len(all_bosses)} bosses with name '{selected_message.monster}' "
                          f"(has_multiple_variants={has_multiple_variants}, is_known_duplicate={is_known_duplicate}) - showing selection dialog")
                
                # Prevent multiple dialogs for the same boss at the same time (one dialog per monster name)
                dialog_key = selected_message.monster.lower()
                if hasattr(self, '_active_duplicate_dialogs'):
                    if dialog_key in self._active_duplicate_dialogs:
                        logger.warning(f"[DUPLICATE CHECK] Dialog already active for {dialog_key} - waiting for it to complete")
                        # Wait a bit and check again (simple approach - in production might want a better mechanism)
                        return
                    self._active_duplicate_dialogs[dialog_key] = True
                else:
                    self._active_duplicate_dialogs = {dialog_key: True}
                
                try:
                    # #region agent log
                    debug_log("main.py:_process_buffered", "Showing duplicate boss dialog", {
                        "monster": selected_message.monster, "options": [b.get("note", "") for b in all_bosses],
                        "buffered_count": len(messages)
                    }, hypothesis_id="DUP_BOSS", run_id="initial")
                    # #endregion
                    boss = self._handle_duplicate_boss_selection(selected_message.monster, all_bosses, selected_message)
                    if not boss:
                        # User cancelled or no selection
                        logger.warning(f"[DUPLICATE CHECK] User cancelled duplicate boss selection for '{selected_message.monster}' - kill will not be posted")
                        self._add_activity_entry(selected_message, "Kill detected but cancelled (duplicate name selection)", posted=False)
                        return
                    else:
                        selected_note = boss.get('note', '').strip()
                        logger.info(f"[DUPLICATE CHECK] User selected boss with note: '{selected_note}' - will include in Discord message")
                        # #region agent log
                        debug_log("main.py:_process_buffered", "User selected duplicate boss, will post to Discord", {
                            "monster": selected_message.monster, "selected_note": selected_note
                        }, hypothesis_id="DUP_BOSS", run_id="initial")
                        # #endregion
                        # CRITICAL: Set boss variable so it's used below - don't fall through to other logic
                        # The boss is now set, continue to processing below
                finally:
                    # Clean up dialog tracking
                    if hasattr(self, '_active_duplicate_dialogs') and dialog_key in self._active_duplicate_dialogs:
                        del self._active_duplicate_dialogs[dialog_key]
            elif len(all_bosses) == 1:
                # Single boss - use it directly (no dialog needed)
                boss = all_bosses[0]
                logger.info(f"[DUPLICATE CHECK] Single boss found for '{selected_message.monster}' - using it directly (note: '{boss.get('note', '')}')")
                # #region agent log
                debug_log("main.py:_process_buffered", "No duplicate dialog - only 1 boss entry", {
                    "monster": selected_message.monster, "note": boss.get("note", "")
                }, hypothesis_id="DUP_BOSS", run_id="initial")
                # #endregion
            else:
                # No bosses found (shouldn't happen since we checked exists() above)
                logger.error(f"[DUPLICATE CHECK] No bosses found for '{selected_message.monster}' despite exists() returning True")
                boss = None
            
            # CRITICAL: Ensure boss is set before processing
            # If boss wasn't set above (e.g., duplicate dialog path), we need to handle it
            if not boss:
                logger.error(f"[BUFFER] ERROR: boss is None for '{selected_message.monster}' - cannot process kill")
                self._add_activity_entry(selected_message, "Error: Boss not found or selection cancelled", posted=False)
                return
            
            boss_location = boss.get('location', '')
            parsed_is_lockout = selected_message.location == "Lockouts"
            boss_is_lockout = boss_location == "Lockouts"
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            is_known_dup = selected_message.monster in duplicate_boss_names
            # Only enforce location-type match when multiple entries exist (same name, different locations)
            # Single boss in UI = match by name only; accept both lockout and zone messages
            if len(all_bosses) > 1 and parsed_is_lockout != boss_is_lockout and not is_known_dup:
                logger.info(f"[DUPLICATE DEBUG] SKIPPING - Location mismatch (late check): {selected_message.monster} | "
                          f"Boss configured as: {boss_location} ({'lockout' if boss_is_lockout else 'zone'}) | "
                          f"Parsed message: {selected_message.location} ({'lockout' if parsed_is_lockout else 'zone'})")
                if boss.get('enabled', False):
                    self._add_activity_entry(selected_message, f"Location mismatch (boss is {boss_location}, message is {selected_message.location})", posted=False)
                return
            
            # Single boss or location matches (or known duplicate), check if enabled
            boss_enabled = boss.get('enabled', False)
            # #region agent log
            debug_log("main._process_buffered_messages", "before enabled check", {"monster": selected_message.monster, "enabled": boss_enabled, "kill_key_in_recent": (selected_message.timestamp, selected_message.monster.lower()) in self.recently_processed_kills}, hypothesis_id="H_enabled", run_id="initial")
            # #endregion
            if boss_enabled:
                # Do NOT check kill_key here: we already added it at the start of this function to prevent
                # other code paths from processing the same kill; that would make us skip our own post.
                # Process boss kill (will add/update activity log entry)
                logger.info(f"[BUFFER] PROCESSING - Enabled boss kill: {selected_message.monster} in {selected_message.location} | "
                          f"Boss location: {boss_location} | Note: '{boss.get('note', '')}' | Will post to Discord")
                try:
                    self._process_boss_kill(selected_message, boss)
                    logger.info(f"[BUFFER] Successfully processed boss kill for {selected_message.monster}")
                except Exception as e:
                    logger.error(f"[BUFFER] ERROR processing boss kill: {e}", exc_info=True)
                    # Still try to add activity entry even if processing failed
                    try:
                        self._add_activity_entry(selected_message, f"Error processing kill: {str(e)[:50]}", posted=False)
                    except:
                        pass
            else:
                logger.debug(f"[BUFFER] Boss '{selected_message.monster}' exists but is disabled (location: {selected_message.location})")
                # Add activity log entry for disabled boss
                try:
                    self._add_activity_entry(selected_message, "Boss kill detected (disabled - not posted)", posted=False)
                except Exception as e:
                    logger.error(f"[BUFFER] Error adding activity entry for disabled boss: {e}", exc_info=True)
    
    def _handle_duplicate_boss_selection(self, boss_name: str, duplicate_bosses: List[Dict], parsed: BossKillMessage) -> Optional[Dict]:
        """
        Handle selection when multiple bosses have the same name.
        
        Args:
            boss_name: Name of the boss that was killed
            duplicate_bosses: List of boss dictionaries with the same name
            parsed: The parsed kill message
            
        Returns:
            Selected boss dictionary, or None if cancelled
        """
        try:
            try:
                from .duplicate_boss_dialog import DuplicateBossDialog
            except ImportError:
                from duplicate_boss_dialog import DuplicateBossDialog

            logger.info(f"[DUPLICATE DIALOG] Showing selection dialog for '{boss_name}' with {len(duplicate_bosses)} options")
            for i, boss in enumerate(duplicate_bosses):
                note = boss.get('note', '').strip()
                location = boss.get('location', 'Unknown')
                logger.info(f"[DUPLICATE DIALOG]   Option {i+1}: {boss_name} (note: '{note}', location: {location})")
            
            # CRITICAL: Restore window from tray and bring to front BEFORE showing dialog
            # This ensures the dialog is always visible
            if self.main_window.isMinimized():
                self.main_window.showNormal()
                logger.info("[DUPLICATE DIALOG] Restored window from minimized state")
            if not self.main_window.isVisible():
                self.main_window.show()
                logger.info("[DUPLICATE DIALOG] Made window visible (was hidden)")
            
            # Bring window to front and activate
            self.main_window.raise_()
            self.main_window.activateWindow()
            # Remove minimized state if present
            if self.main_window.windowState() & Qt.WindowState.WindowMinimized:
                self.main_window.setWindowState(self.main_window.windowState() & ~Qt.WindowState.WindowMinimized)
            logger.info("[DUPLICATE DIALOG] Brought window to front and activated")
            
            # Show dialog to select which boss
            dialog = DuplicateBossDialog(boss_name, duplicate_bosses, self.main_window)
            
            # Ensure dialog is on top and modal
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dialog.setModal(True)
            
            logger.info(f"[DUPLICATE DIALOG] Executing dialog for '{boss_name}'...")
            result = dialog.exec()
            logger.info(f"[DUPLICATE DIALOG] Dialog closed with result: {result} (Accepted={QDialog.DialogCode.Accepted})")
            
            if result == QDialog.DialogCode.Accepted:
                selected_boss = dialog.get_selected_boss()
                if selected_boss:
                    selected_note = selected_boss.get('note', '').strip()
                    logger.info(f"[DUPLICATE DIALOG] User selected boss: {selected_boss.get('name')} "
                               f"(note: '{selected_note}') in {selected_boss.get('location', 'Unknown')}")
                    return selected_boss
                else:
                    logger.warning("[DUPLICATE DIALOG] Dialog accepted but no boss selected")
            else:
                logger.warning(f"[DUPLICATE DIALOG] Dialog cancelled or rejected (result: {result})")
            return None
        except ImportError as e:
            logger.error(f"Error importing duplicate boss dialog: {e}", exc_info=True)
            # Fallback: use first boss if dialog can't be shown
            logger.warning(f"Could not show duplicate boss dialog, using first boss: {duplicate_bosses[0].get('name')}")
            return duplicate_bosses[0] if duplicate_bosses else None
        except Exception as e:
            logger.error(f"Error showing duplicate boss dialog: {e}", exc_info=True)
            # Fallback: use first boss if dialog fails
            logger.warning(f"Error showing duplicate boss dialog, using first boss: {duplicate_bosses[0].get('name')}")
            return duplicate_bosses[0] if duplicate_bosses else None
    
    def _handle_new_boss(self, parsed: BossKillMessage) -> None:
        """Handle discovery of a new boss (must be called from main thread)."""
        try:
            boss_key = parsed.monster.lower()
            
            # Check again if boss was added while we were processing (race condition)
            if self.boss_db.exists(parsed.monster):
                logger.debug(f"Boss '{parsed.monster}' was already added, skipping")
                return
            
            # Check if we should use default action (skip dialog)
            new_boss_default = self.settings.get('new_boss_default_action', 'disable')
            use_default_action = new_boss_default in ('enable', 'disable')
            
            if use_default_action:
                # Use default action - skip dialog
                enabled = (new_boss_default == 'enable')
                logger.info(f"New boss '{parsed.monster}' detected - using default action: {'enable' if enabled else 'disable'}")
                
                # Add boss with default enabled state (this will also post to Discord if enabled)
                self._add_new_boss(parsed.monster, parsed.location, enabled)
                
                # Show system notification if enabled
                if self.settings.get('windows_notification', False):
                    self.tray.show_notification(
                        "Target has been slain!",
                        f"{parsed.monster} in {parsed.location} ({'Enabled' if enabled else 'Disabled'})"
                    )
                
                # Pop up window if setting enabled
                if self.settings.get('window_popup_on_new_boss', True):
                    self._show_main_window()
                
                return
            
            # Otherwise, show dialog (original behavior)
            # Prevent duplicate dialogs for the same boss
            if boss_key in self.active_new_boss_dialogs:
                logger.debug(f"Dialog already exists for boss '{parsed.monster}', skipping duplicate")
                return
            
            # Show non-modal dialog
            dialog = NewBossDialog(parsed.monster, parsed.location, self.main_window)
            # Connect signal - this will be called when user clicks Yes or No
            dialog.enabled_selected.connect(
                lambda name, location, enabled: self._add_new_boss(name, location, enabled)
            )
            
            # Track this dialog
            self.active_new_boss_dialogs[boss_key] = dialog
            
            # Clean up dialog reference when it closes
            def cleanup_dialog():
                if boss_key in self.active_new_boss_dialogs:
                    del self.active_new_boss_dialogs[boss_key]
            
            dialog.finished.connect(cleanup_dialog)
            
            # Show dialog
            dialog.show()
            
            # Handle window pop-up setting
            if self.settings.get('window_popup_on_new_boss', True):
                self._show_main_window()
            # Show notification when enabled (in addition to or instead of popup)
            if self.settings.get('windows_notification', False):
                self.tray.show_notification(
                    "Target has been slain!",
                    f"{parsed.monster} in {parsed.location}"
                )
        except Exception as e:
            logger.error(f"Error handling new boss: {e}", exc_info=True)
    
    def _add_new_boss(self, name: str, location: str, enabled: bool) -> None:
        """Add a new boss to the database."""
        try:
            logger.info(f"Adding new boss: {name} in {location} (enabled: {enabled})")
            boss = self.boss_db.add_boss(name, location, enabled)
            
            # Defer UI refresh to avoid issues during signal processing
            QTimer.singleShot(0, self._refresh_bosses)
            
            # If enabled and we have a pending kill for this boss, post it now
            if enabled:
                boss_key = name.lower()
                if boss_key in self.pending_boss_kills:
                    parsed = self.pending_boss_kills[boss_key]
                    logger.info(f"Boss '{name}' was enabled - posting the current kill message")
                    # Defer processing to avoid blocking
                    QTimer.singleShot(0, lambda: self._process_boss_kill(parsed, boss))
                    # Remove from pending
                    del self.pending_boss_kills[boss_key]
                else:
                    logger.info(f"Boss '{name}' was enabled - will post future kills")
        except Exception as e:
            logger.error(f"Error adding new boss: {e}", exc_info=True)
    
    def _has_discord_sync_config(self) -> bool:
        """
        Return True if Discord is configured enough for sync (webhook + bot token).
        When False, we should not start the sync timer or run sync checks.
        Uses in-memory settings (loaded from same file as _get_webhook_url_for_post at startup/save).
        """
        webhook = (self.settings.get('default_webhook_url') or '').strip()
        token = (self.settings.get('discord_bot_token') or '').strip()
        return bool(webhook and token)

    def _get_webhook_url_for_post(self) -> str:
        """
        Return the webhook URL to use for Discord posts. Reads ONLY from the settings file.
        No in-memory fallback – so if the file is missing or unreadable, we return '' and do not post.
        Uses the same Roaming path as load/save so we never read a different settings file.
        """
        # Use explicit user data path (same as _get_user_data_dir) so we always read Roaming/boss tracker/settings.json
        path = self._get_user_data_dir() / "settings.json"
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                url = (data.get('default_webhook_url') or '').strip()
                wid = _webhook_id_from_url(url)
                # #region agent log
                debug_log("main._get_webhook_url_for_post", "returning url from file", {"path": str(path), "webhook_id": wid, "len_url": len(url)}, hypothesis_id="H2")
                # #endregion
                _app_log.info("[DISCORD] Webhook from file %s: %s (len=%d) | Webhook ID: %s", path, "EMPTY" if not url else _mask_webhook(url), len(url), wid or "none")
                logger.info(f"[DISCORD] Webhook from file {path!s}: {_mask_webhook(url)} (len={len(url)})")
                return url
            else:
                _app_log.warning("[DISCORD] Settings file missing: %s – not posting (no fallback)", path)
                logger.warning(f"[DISCORD] Settings file missing: {path!s} – returning empty, no post")
                return ''
        except (json.JSONDecodeError, IOError) as e:
            _app_log.warning("[DISCORD] Could not read settings file %s: %s – not posting (no fallback)", path, e)
            logger.warning(f"[DISCORD] Could not read webhook from {path!s}: {e} – returning empty, no post")
            return ''

    def _get_channel_id(self, webhook_url: str) -> Optional[int]:
        """
        Get channel ID for a webhook URL, using cache if available.

        Args:
            webhook_url: Discord webhook URL

        Returns:
            Channel ID if found, None otherwise
        """
        if not webhook_url:
            return None
        
        # Check cache first
        if webhook_url in self._channel_id_cache:
            return self._channel_id_cache[webhook_url]
        
        # Try to fetch from Discord API if checker is available
        channel_id = None
        if self.discord_checker and DISCORD_AVAILABLE:
            try:
                import asyncio
                channel_id = asyncio.run(self.discord_checker.get_channel_id_from_webhook(webhook_url))
                if channel_id:
                    self._channel_id_cache[webhook_url] = channel_id
                    logger.info(f"Cached channel ID {channel_id} for webhook")
            except Exception as e:
                logger.warning(f"Could not fetch channel ID from webhook: {e}")
        
        return channel_id
    
    def _add_activity_entry(self, parsed: BossKillMessage, status: str, posted: bool, message: Optional[str] = None) -> None:
        """Helper method to add activity log entry."""
        try:
            logger.info(f"[ACTIVITY] Adding entry: {parsed.monster} in {parsed.location} | Status: {status} | Posted: {posted}")
            self.activity_db.add_activity(
                timestamp=parsed.timestamp,
                monster=parsed.monster,
                location=parsed.location,
                player=parsed.player,
                guild=parsed.guild,
                posted_to_discord=posted,
                discord_message=message,
                status=status
            )
            logger.info(f"[ACTIVITY] Database entry added successfully")
            self.main_window.add_activity(parsed.timestamp, parsed.monster, parsed.location, status)
            logger.info(f"[ACTIVITY] UI entry added successfully")
        except Exception as e:
            logger.error(f"[ACTIVITY] ERROR in _add_activity_entry: {e}", exc_info=True)
            raise
    
    def _process_boss_kill(self, parsed: BossKillMessage, boss: dict) -> None:
        """Process a boss kill - check for duplicates and post to Discord."""
        # #region agent log
        debug_log("main._process_boss_kill", "entry", {"monster": parsed.monster}, hypothesis_id="H0")
        # #endregion
        logger.info(f"[DUPLICATE DEBUG] _process_boss_kill called: {parsed.monster} at {parsed.timestamp} | "
                   f"Location: {parsed.location} | Template will be: {'lockout' if parsed.location == 'Lockouts' else 'guild message'}")
        
        # CRITICAL: Create kill key for duplicate checking
        kill_key = (parsed.timestamp, parsed.monster.lower())
        
        # Check if already processed (exact timestamp match)
        if kill_key in self.recently_processed_kills:
            logger.warning(f"[DUPLICATE DEBUG] SKIPPING in _process_boss_kill - Duplicate detected (exact match): {parsed.monster} at {parsed.timestamp} - skipping")
            # Still add to activity log for tracking
            self._add_activity_entry(parsed, "Duplicate detected (exact match), skipped", posted=False)
            return
        
        # Additional time-window check here as final safeguard
        # Check if ANY recent kill of this monster exists (guild OR lockout) - if so, skip
        monster_key = parsed.monster.lower()
        try:
            kill_time = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
            if monster_key in self.recent_kills_by_monster:
                for prev_time, prev_location in self.recent_kills_by_monster[monster_key]:
                    time_diff = abs((kill_time - prev_time).total_seconds())
                    if time_diff <= SAME_KILL_WINDOW_SECONDS:
                        logger.warning(f"[DUPLICATE DEBUG] SKIPPING in _process_boss_kill - Duplicate detected (time window): "
                                     f"{parsed.monster} at {parsed.timestamp} (previous kill at {prev_time.strftime('%H:%M:%S')} in {prev_location}, diff: {time_diff:.1f}s)")
                        self._add_activity_entry(parsed, f"Duplicate (within {time_diff:.1f}s of previous kill)", posted=False)
                        return
        except ValueError:
            pass  # If timestamp parsing fails, continue with normal processing
        
        # CRITICAL: Mark as processed IMMEDIATELY after all duplicate checks pass
        # This prevents concurrent processing of the same kill
        # Must happen before any async operations or delays
        self.recently_processed_kills.add(kill_key)
        try:
            kill_time = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
            if monster_key not in self.recent_kills_by_monster:
                self.recent_kills_by_monster[monster_key] = []
            self.recent_kills_by_monster[monster_key].append((kill_time, parsed.location))
            cutoff_time = kill_time - timedelta(minutes=1)
            self.recent_kills_by_monster[monster_key] = [
                (t, loc) for t, loc in self.recent_kills_by_monster[monster_key]
                if t > cutoff_time
            ][-3:]
        except ValueError:
            pass
        logger.info(f"[DUPLICATE DEBUG] All duplicate checks passed - marked kill as processed: {parsed.monster} at {parsed.timestamp} | Kill key: {kill_key}")
        
        # Check for duplicate if Discord checker is available
        is_duplicate = False
        # Webhook comes only from the settings file (one webhook for everything)
        webhook_url = self._get_webhook_url_for_post()
        logger.info(f"[DISCORD] Post will use webhook: {_mask_webhook(webhook_url)} (empty={not webhook_url})")
        
        if self.discord_checker and self.discord_checker.ready and webhook_url:
            try:
                # Get channel ID (from cache or fetch from API)
                channel_id = self._get_channel_id(webhook_url)
                
                if channel_id:
                    # Check for duplicate messages
                    is_duplicate = self.discord_checker.check_duplicate_sync(
                        channel_id=channel_id,
                        target_name=parsed.monster,
                        log_timestamp=parsed.timestamp,
                        tolerance_minutes=3
                    )
                    if is_duplicate:
                        logger.info(f"Duplicate detected for {parsed.monster}, skipping Discord post")
                else:
                    logger.debug(f"Could not get channel ID for duplicate check, proceeding with post")
            except Exception as e:
                logger.warning(f"Error checking for duplicate: {e}, proceeding with post")
        
        # Wall-clock dedup: if we posted for this monster within same-kill window, do not post again (handles multi-file / late messages)
        if monster_key in self._last_discord_post_time_by_monster:
            elapsed = time.time() - self._last_discord_post_time_by_monster[monster_key]
            if elapsed < SAME_KILL_WINDOW_SECONDS:
                logger.warning(f"[DISCORD] Skipping post - already posted for {parsed.monster} {elapsed:.1f}s ago (cooldown {SAME_KILL_WINDOW_SECONDS}s)")
                self._add_activity_entry(parsed, f"Duplicate (posted {elapsed:.0f}s ago), skipped", posted=False)
                return
        
        if is_duplicate:
            logger.info(f"Duplicate detected for {parsed.monster}, skipping Discord post")
            status = "Duplicate detected, skipped"
            posted = False
            message = None
        else:
            if parsed.location == "Lockouts":
                template = self.settings.get('lockout_message_template', '{discord_timestamp} {monster} lockout detected!')
            else:
                template = self.settings.get('message_template', '{discord_timestamp} {monster} was killed in {location}!')
            boss_note = boss.get('note', '').strip()
            logger.debug(f"Using {'lockout' if parsed.location == 'Lockouts' else 'kill'} template for {parsed.monster}")
            logger.info(f"[DISCORD MESSAGE] Formatting message for {parsed.monster} | Note: '{boss_note}' | Template: {template[:80]}...")
            # #region agent log
            debug_log("main.py:_process_boss_kill", "Discord message pre-format", {
                "monster": parsed.monster, "note": boss_note, "template_has_note": "{note}" in template,
                "location": parsed.location
            }, hypothesis_id="DISCORD_NOTE", run_id="initial")
            # #endregion

            message = self.discord_notifier.format_message(
                template,
                timestamp=parsed.timestamp,
                monster=parsed.monster,
                player=parsed.player,
                guild=parsed.guild,
                location=parsed.location,
                server=parsed.server,
                note=boss_note
            )
            logger.info(f"[DISCORD MESSAGE] Formatted message: {message}")
            # #region agent log
            debug_log("main.py:_process_boss_kill", "Discord message queued for post", {
                "monster": parsed.monster, "note_in_message": boss_note in message if boss_note else False,
                "message_preview": message[:120]
            }, hypothesis_id="DISCORD_NOTE", run_id="initial")
            # #endregion

            # Webhook from file only (same for real logs and simulation)
            webhook_url = self._get_webhook_url_for_post()
            if not webhook_url:
                _app_log.info("[DISCORD] SKIP: no webhook in settings (len=0) - not posting for %s", parsed.monster)
                logger.info(f"[DISCORD] Skipping post for {parsed.monster}: no webhook URL in settings (simulation/test safe)")
                status = "Not posted (no webhook URL in settings)"
                posted = False
                message = None
            else:
                # Re-read from file so we never post a stale URL
                webhook_again = self._get_webhook_url_for_post()
                if not webhook_again:
                    _app_log.info("[DISCORD] SKIP: re-check before notify found empty - not posting for %s", parsed.monster)
                    logger.info(f"[DISCORD] Skipping post for {parsed.monster}: webhook empty on re-check (safety)")
                    status = "Not posted (no webhook URL in settings)"
                    posted = False
                    message = None
                else:
                    _app_log.info("[DISCORD] POST: webhook from file (len=%d) - posting for %s", len(webhook_url), parsed.monster)
                    logger.info(f"[DISCORD] POSTING: {parsed.monster} | webhook={_mask_webhook(webhook_url)} | url_len={len(webhook_url)}")
                    logger.debug(f"[DISCORD] Calling discord_notifier.notify(message, webhook={_mask_webhook(webhook_url)})")
                    # #region agent log
                    debug_log("main._process_boss_kill", "about to call notify", {"webhook_id_passed": _webhook_id_from_url(webhook_again), "monster": parsed.monster}, hypothesis_id="H1")
                    # #endregion
                    self._last_discord_post_time_by_monster[monster_key] = time.time()
                    self.discord_notifier.notify(message, webhook_again)
                    status = "Posted to Discord"
                    posted = True

            # Play sound if enabled
            sound_enabled = self.settings.get('sound_enabled', True)
            logger.info(f"[SOUND] Sound check: enabled={sound_enabled}, sound_player.enabled={self.sound_player.enabled}")
            if sound_enabled and self.sound_player.enabled:
                logger.info(f"[SOUND] Playing sound for {parsed.monster}")
                self.sound_player.play()
            else:
                logger.info(f"[SOUND] Sound disabled - skipping playback (settings: {sound_enabled}, player: {self.sound_player.enabled})")
            
            # Show system notification when enabled (always, regardless of window state)
            # Simple on/off: when enabled, show notification on every boss kill
            windows_notification_enabled = self.settings.get('windows_notification', False)
            
            if windows_notification_enabled:
                boss_note = boss.get('note', '').strip()
                formatted_notification = self._format_message_for_notification(
                    template,
                    timestamp=parsed.timestamp,
                    monster=parsed.monster,
                    note=boss_note,
                    player=parsed.player,
                    guild=parsed.guild,
                    location=parsed.location,
                    server=parsed.server
                )
                logger.info(f"[NOTIFICATION] Showing notification for {parsed.monster}: {formatted_notification[:100]}...")
                try:
                    self.tray.show_notification(
                        "Target has been slain!",
                        formatted_notification
                    )
                    logger.info(f"[NOTIFICATION] Notification shown for {parsed.monster}")
                except Exception as e:
                    logger.error(f"[NOTIFICATION] Error showing notification: {e}", exc_info=True)
            
            logger.info(f"[DUPLICATE DEBUG] Successfully queued Discord post for: {parsed.monster}")

        # Increment kill count and store the actual log timestamp FIRST
        # This ensures kill time/respawn time updates even if activity log fails
        # Only increment once per unique kill (not for duplicates)
        # Pass boss dict directly to handle duplicate names correctly
        if posted:
            try:
                logger.info(f"[KILL] Incrementing kill count for {parsed.monster} | Timestamp: {parsed.timestamp}")
                self.boss_db.increment_kill_count(parsed.monster, kill_timestamp=parsed.timestamp, boss=boss)
                logger.info(f"[KILL] Kill count incremented successfully - kill time and respawn time updated")
                # Refresh boss info in UI to show updated last kill time
                # Use boss name from the boss dict (in case of duplicates, this ensures correct refresh)
                self.main_window.zone_widget.refresh_boss_info(boss['name'])
                logger.info(f"[KILL] UI refreshed for {boss['name']}")
            except Exception as e:
                logger.error(f"[KILL] ERROR incrementing kill count: {e}", exc_info=True)
                # Continue anyway - activity log should still be added
        
        # Always add activity log entry (even for duplicates) for tracking purposes
        # This ensures activity log is always updated
        # NOTE: This happens AFTER kill count increment so kill time updates even if activity log fails
        # CRITICAL: Activity log entry MUST be added, even if it fails multiple times
        activity_logged = False
        try:
            logger.info(f"[ACTIVITY] Adding activity log entry: {parsed.monster} | Status: {status} | Posted: {posted}")
            self._add_activity_entry(parsed, status, posted, message)
            logger.info(f"[ACTIVITY] Activity log entry added successfully")
            activity_logged = True
        except Exception as e:
            logger.error(f"[ACTIVITY] ERROR adding activity entry (attempt 1): {e}", exc_info=True)
            # Try to add a basic entry without message
            try:
                logger.info(f"[ACTIVITY] Attempting fallback activity entry...")
                self.activity_db.add_activity(
                    timestamp=parsed.timestamp,
                    monster=parsed.monster,
                    location=parsed.location,
                    player=parsed.player,
                    guild=parsed.guild,
                    posted_to_discord=posted,
                    discord_message=None,
                    status=f"{status} (error logging message)"
                )
                self.main_window.add_activity(parsed.timestamp, parsed.monster, parsed.location, status)
                logger.info(f"[ACTIVITY] Added fallback activity entry successfully")
                activity_logged = True
            except Exception as e2:
                logger.error(f"[ACTIVITY] CRITICAL: Fallback activity entry also failed: {e2}", exc_info=True)
                # Last resort: try direct UI update only
                try:
                    logger.warning(f"[ACTIVITY] Attempting last resort: UI update only...")
                    self.main_window.add_activity(parsed.timestamp, parsed.monster, parsed.location, f"{status} (log error)")
                    logger.info(f"[ACTIVITY] UI update succeeded (database may be missing entry)")
                    activity_logged = True
                except Exception as e3:
                    logger.error(f"[ACTIVITY] CRITICAL: Even UI update failed: {e3}", exc_info=True)
        
        if not activity_logged:
            logger.error(f"[ACTIVITY] CRITICAL: Failed to add activity log entry after all attempts for {parsed.monster}")
            logger.error(f"[ACTIVITY] This is a serious issue - activity log may be incomplete")
    
    def _on_refresh_requested(self) -> None:
        """Handle refresh button click - refreshes both bosses and activity log."""
        logger.info("Refresh button clicked - refreshing UI")
        self._refresh_bosses()
        self._update_activity_log()
        self._update_active_character()
    
    def _on_scan_requested(self) -> None:
        """Handle scan request from UI - scan a log file for boss kills."""
        try:
            from .scan_dialog import ScanDialog
        except ImportError:
            from scan_dialog import ScanDialog
        
        logger.info("Scan requested")
        
        # Open scan dialog
        dialog = ScanDialog(self.main_window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            file_path = dialog.get_file_path()
            if file_path:
                logger.info(f"Scan dialog accepted, file selected: {file_path}")
                # Use QTimer to defer scanning so UI stays responsive
                # This allows the dialog to close before we start the heavy work
                QTimer.singleShot(100, lambda: self._perform_scan(file_path))
            else:
                logger.debug("Scan cancelled - no file selected")
        else:
            logger.debug("Scan cancelled - dialog rejected")
    
    def _on_boss_capture_requested(self) -> None:
        """Handle Debug → Boss Capture: open dialog and run capture."""
        try:
            from .boss_capture_dialog import BossCaptureDialog
        except ImportError:
            from boss_capture_dialog import BossCaptureDialog
        captures_dir = self.data_dir / "captures"
        dialog = BossCaptureDialog(self.main_window, default_capture_dir=captures_dir)
        dialog.exec()
    
    def _on_boss_simulation_requested(self) -> None:
        """Handle Debug → Boss Simulation: open simulation dialog."""
        try:
            from .boss_simulation_dialog import BossSimulationDialog
        except ImportError:
            from boss_simulation_dialog import BossSimulationDialog
        dialog = BossSimulationDialog(self.main_window, app_controller=self)
        dialog.exec()
    
    def _build_simulation_batches(self, lines: list) -> list:
        """
        Group capture lines into batches so one kill = one batch (one post).
        Lines with the same monster and timestamps within 5s are one batch; each batch
        is written with a single timestamp so the app sees one buffer and posts once.
        """
        import re
        ts_pattern = re.compile(r"^\[(.+?)\]")
        same_kill_seconds = 5
        batches = []
        current_batch = []
        current_ts = None
        current_monster = None
        current_ts_dt = None
        for line in lines:
            parsed = MessageParser.parse_line(line)
            if not parsed:
                parsed = MessageParser.parse_lockout_line(line)
            ts = parsed.timestamp if parsed else None
            if ts is None:
                match = ts_pattern.match(line)
                ts = match.group(1).strip() if match else ""
            monster = parsed.monster.lower() if parsed else ""
            try:
                ts_dt = datetime.strptime(ts.strip(), "%a %b %d %H:%M:%S %Y") if ts else None
            except ValueError:
                ts_dt = None
            # Same batch if same monster and timestamp within same_kill_seconds of current batch start
            if current_batch and monster and ts_dt and current_ts_dt and current_monster == monster:
                if abs((ts_dt - current_ts_dt).total_seconds()) <= same_kill_seconds:
                    current_batch.append(line)
                    continue
            if current_batch:
                batches.append(current_batch)
            current_batch = [line]
            current_ts = ts
            current_monster = monster
            current_ts_dt = ts_dt
        if current_batch:
            batches.append(current_batch)
        return batches
    
    def start_simulation(self, capture_path: str, character_name: str, interval_seconds: int) -> bool:
        """Create simulated log file and start replay timer. Returns True if started."""
        if self._simulation_state:
            self.stop_simulation()
        log_dir = self.settings.get("log_directory", "").strip()
        if not log_dir or not Path(log_dir).exists():
            logger.warning("Simulation requires log directory to be set and exist")
            return False
        try:
            with open(capture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load capture for simulation: {e}")
            return False
        lines = data.get("lines", [])
        if not lines:
            logger.warning("Capture has no lines")
            return False
        batches = self._build_simulation_batches(lines)
        char_name = (character_name or "SimTest").strip() or "SimTest"
        server = "pq.proj"
        log_path = Path(log_dir) / f"eqlog_{char_name}_{server}.txt"
        log_path.touch()
        interval_ms = max(1000, interval_seconds * 1000)
        timer = QTimer()
        state = {
            "timer": timer,
            "batches": batches,
            "batch_index": 0,
            "log_path": log_path,
            "interval_seconds": interval_seconds,
        }
        self._simulation_state = state
        # So simulated lines are not skipped as "duplicate" (same content may exist from a previous run)
        self.recently_processed_lines.clear()
        logger.info("[SIMULATION] Cleared recently_processed_lines so simulated lines will be processed")
        # #region agent log
        debug_log("main.start_simulation", "recently_processed_lines cleared", {"log_path": str(log_path), "batches": len(batches)}, hypothesis_id="H_sim_start", run_id="initial")
        # #endregion
        def tick():
            self._simulation_tick()
        timer.timeout.connect(tick)
        timer.start(interval_ms)
        logger.info(f"Simulation started: {len(batches)} batches, interval {interval_seconds}s, log {log_path}")
        self.main_window.add_activity(
            datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
            "Simulation", "", f"Started ({len(batches)} batches, interval {interval_seconds}s)"
        )
        return True
    
    def stop_simulation(self) -> None:
        """Stop the replay timer and clear simulation state."""
        if self._simulation_state:
            state = self._simulation_state
            state["timer"].stop()
            state["timer"].deleteLater()
            self._simulation_state = None
            logger.info("Simulation stopped")
    
    def _simulation_tick(self) -> None:
        """Write next batch to simulated log file (same timestamp for whole batch)."""
        if not self._simulation_state:
            return
        state = self._simulation_state
        batches = state["batches"]
        idx = state["batch_index"]
        if idx >= len(batches):
            self.stop_simulation()
            return
        now_str = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
        import re
        ts_pattern = re.compile(r"^\[.+?\]")
        batch_lines = batches[idx]
        try:
            with open(state["log_path"], "a", encoding="utf-8") as f:
                for line in batch_lines:
                    new_line = ts_pattern.sub(f"[{now_str}]", line, count=1)
                    f.write(new_line + "\n")
        except OSError as e:
            logger.warning(f"Simulation write failed: {e}")
        state["batch_index"] = idx + 1
    
    def is_simulation_running(self) -> bool:
        """Return True if simulation replay is active."""
        return self._simulation_state is not None
    
    def _on_start_simulation_requested(self) -> None:
        """Activity Log context menu: Start Simulation -> open Boss Simulation dialog."""
        if self.is_simulation_running():
            return
        try:
            from .boss_simulation_dialog import BossSimulationDialog
        except ImportError:
            from boss_simulation_dialog import BossSimulationDialog
        dialog = BossSimulationDialog(self.main_window, app_controller=self)
        dialog.exec()
    
    def _on_stop_simulation_requested(self) -> None:
        """Activity Log context menu: Stop Simulation."""
        self.stop_simulation()
    
    def _check_and_sync_discord(self, force: bool = False) -> None:
        """
        Check if configured interval has passed since last Discord sync, and sync if needed.

        Args:
            force: If True, skip the interval check and sync immediately
        """
        from datetime import datetime, timedelta

        # Don't run sync at all until user has configured Discord (webhook + bot token)
        if not force and not self._has_discord_sync_config():
            return

        interval_hours = max(1, min(168, int(self.settings.get('discord_sync_interval_hours', 12))))
        
        if not force:
            # Get last sync time from settings
            last_sync_str = self.settings.get('last_discord_sync_time', None)
            
            if last_sync_str:
                try:
                    last_sync = datetime.fromisoformat(last_sync_str)
                    hours_since_sync = (datetime.now() - last_sync).total_seconds() / 3600
                    
                    if hours_since_sync < interval_hours:
                        next_in = interval_hours - hours_since_sync
                        logger.debug(f"Discord sync skipped: Only {hours_since_sync:.1f}h since last sync (interval {interval_hours}h, next in {next_in:.1f}h)")
                        # Show in activity log so user sees sync was checked (e.g. at startup)
                        self.main_window.add_activity(
                            datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                            "Discord Sync",
                            "",
                            f"Sync skipped: {hours_since_sync:.1f}h since last sync (interval: {interval_hours}h, next in ~{next_in:.0f}h)"
                        )
                        return
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse last Discord sync time '{last_sync_str}': {e}")
                    # Continue with sync if parsing fails
        
        # Interval has passed (or no previous sync, or forced), proceed with sync
        if force:
            logger.info("Discord sync forced (manual trigger), starting sync...")
        else:
            logger.info(f"Discord sync interval ({interval_hours}h) reached (or no previous sync), starting sync...")
        self._sync_kill_times_from_discord()
    
    def _sync_kill_times_from_discord(self) -> None:
        """Sync last kill times from Discord channel messages."""
        from datetime import datetime

        if not self.discord_checker or not self.discord_checker.ready:
            logger.warning("Discord checker not available or not ready, cannot sync from Discord")
            self.main_window.add_activity(
                datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                "Discord Sync",
                "",
                "Discord sync failed: Bot not available or not ready"
            )
            return
        
        # Get webhook URL from settings file (same source as post)
        webhook_url = self._get_webhook_url_for_post()
        if not webhook_url:
            logger.warning("No webhook URL configured, cannot sync from Discord")
            self.main_window.add_activity(
                datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                "Discord Sync",
                "",
                "Discord sync failed: No webhook URL configured"
            )
            return
        
        # Get channel ID from webhook
        channel_id = self._get_channel_id(webhook_url)
        if not channel_id:
            logger.warning("Could not get channel ID from webhook, cannot sync from Discord")
            self.main_window.add_activity(
                datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                "Discord Sync",
                "",
                "Discord sync failed: Could not determine channel ID"
            )
            return
        
        try:
            logger.info("Starting Discord sync to update kill times")
            sync_start_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            
            self.main_window.add_activity(
                sync_start_time,
                "Discord Sync",
                "",
                "Starting Discord sync..."
            )
            
            # Get all unique boss names from database (same source as rest of app)
            all_bosses = self.boss_db.get_all_bosses()
            boss_names = list(set(boss['name'] for boss in all_bosses))
            
            # Include all bosses in scan (including duplicates)
            # Discord messages with notes like "Thall Va Xakra (South)" will be handled specially
            boss_names_to_scan = boss_names
            
            if not boss_names_to_scan:
                logger.warning("Discord sync: no bosses in tracker; skipping scan and not updating last sync time")
                self.main_window.add_activity(
                    datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                    "Discord Sync",
                    "",
                    "No bosses in tracker; add bosses to sync kill times from Discord. Last sync time not updated."
                )
                return
            
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            duplicate_count = sum(1 for name in boss_names if name in duplicate_boss_names)
            logger.info(f"Scanning Discord for {len(boss_names_to_scan)} bosses ({duplicate_count} duplicate bosses will only update if note is in message)")
            
            # Scan Discord channel
            found_kills = self.discord_checker.scan_channel_for_kills_sync(
                channel_id, 
                boss_names_to_scan,
                limit=500  # Scan up to 500 messages
            )
            
            # Update kill times in database
            updated_count = 0
            updated_bosses = []  # Track which bosses were updated
            now = datetime.now()
            
            for kill_key, kill_info in found_kills.items():
                boss_name = kill_info['monster_name']
                kill_dt = kill_info['timestamp']  # This is timezone-aware (EST)
                kill_timestamp_str = kill_info['timestamp_str']
                note_from_message = kill_info.get('note')  # Note extracted from Discord message
                
                # Find all bosses with this name (handles duplicates)
                existing_bosses = self.boss_db.get_bosses_by_name(boss_name)
                
                # Check if this is a duplicate boss name
                duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
                is_duplicate_boss = boss_name in duplicate_boss_names
                
                if existing_bosses:
                    # For duplicate bosses, only update if note matches
                    # For regular bosses, update all matching entries
                    bosses_to_update = []
                    
                    if is_duplicate_boss:
                        if note_from_message:
                            # Find the specific boss entry with matching note
                            for boss in existing_bosses:
                                boss_note = boss.get('note', '').strip()
                                if boss_note.lower() == note_from_message.lower():
                                    bosses_to_update.append(boss)
                                    logger.debug(f"Matched duplicate boss '{boss_name}' with note '{note_from_message}'")
                                    break
                            if not bosses_to_update:
                                logger.warning(f"Found kill for duplicate boss '{boss_name}' with note '{note_from_message}' but no matching boss entry found")
                        else:
                            # No note in message, skip this duplicate boss
                            logger.debug(f"Skipping duplicate boss '{boss_name}' - no note in Discord message to identify specific entry")
                    else:
                        # Regular boss - update all matching entries
                        bosses_to_update = existing_bosses
                    
                    for boss in bosses_to_update:
                        # Check if this kill is more recent than existing
                        existing_kill_time = None
                        if boss.get('last_killed'):
                            try:
                                existing_kill_time = datetime.fromisoformat(boss['last_killed'])
                                # Ensure existing_kill_time is timezone-aware for comparison
                                # If it's naive, assume it's in the same timezone as kill_dt
                                if existing_kill_time.tzinfo is None:
                                    # Make it timezone-aware by localizing to EST (same as kill_dt)
                                    import pytz
                                    est = pytz.timezone('US/Eastern')
                                    existing_kill_time = est.localize(existing_kill_time)
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not parse existing kill time for '{boss['name']}': {e}")
                                pass
                        
                        # Update if this kill is more recent (or if no existing kill time)
                        # Both datetimes are now timezone-aware, so comparison should work
                        if existing_kill_time is None or kill_dt > existing_kill_time:
                            # Store as ISO format (timezone-aware)
                            boss['last_killed'] = kill_dt.isoformat()
                            boss['last_killed_timestamp'] = kill_timestamp_str
                            updated_count += 1
                            # Convert to naive datetime for days calculation (both in same timezone)
                            kill_dt_naive = kill_dt.replace(tzinfo=None)
                            now_naive = now.replace(tzinfo=None) if hasattr(now, 'tzinfo') and now.tzinfo else now
                            age_days = (now_naive - kill_dt_naive).days if kill_dt_naive <= now_naive else 0
                            
                            # Build boss identifier (name + note if available)
                            boss_identifier = boss['name']
                            if boss.get('note'):
                                boss_identifier = f"{boss['name']} ({boss['note']})"
                            
                            updated_bosses.append({
                                'name': boss_identifier,
                                'timestamp': kill_timestamp_str,
                                'age_days': age_days
                            })
                            
                            logger.info(f"Updated kill time from Discord for '{boss_identifier}': {kill_timestamp_str} ({age_days} days ago)")
            
            # Save database after all updates
            if updated_count > 0:
                self.boss_db.save()
                logger.info(f"Updated {updated_count} boss kill times from Discord")
            
            # Save sync time only when we actually performed a meaningful sync (had bosses to scan).
            # If we had 0 bosses to scan, do not update last sync so the next run is not skipped for 12h.
            if boss_names_to_scan:
                self.settings['last_discord_sync_time'] = datetime.now().isoformat()
                self._save_settings()
                logger.debug("Saved Discord sync time to settings")
            else:
                logger.debug("Discord sync: no bosses to scan; not updating last sync time")
            
            # Refresh UI
            self._refresh_bosses()
            
            # Post summary
            sync_end_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            
            # Build summary with updated boss details
            summary_parts = [
                f"Discord sync complete! | ",
                f"Bosses scanned: {len(boss_names_to_scan)} | ",
                f"Kills found: {len(found_kills)} | ",
                f"Updated: {updated_count}"
            ]
            
            # Add details about which bosses were updated
            if updated_bosses:
                summary_parts.append(" | Updated bosses: ")
                boss_details = []
                for boss_info in updated_bosses[:5]:  # Show up to 5 bosses
                    boss_details.append(f"{boss_info['name']} ({boss_info['age_days']}d ago)")
                summary_parts.append(", ".join(boss_details))
                if len(updated_bosses) > 5:
                    summary_parts.append(f" + {len(updated_bosses) - 5} more")
            
            summary = "".join(summary_parts)
            
            self.main_window.add_activity(
                sync_end_time,
                "Discord Sync",
                "",
                summary
            )
            
            # Also log detailed info about all updated bosses
            if updated_bosses:
                logger.info(f"Discord sync complete: {updated_count} kill times updated:")
                for boss_info in updated_bosses:
                    logger.info(f"  - {boss_info['name']}: {boss_info['timestamp']} ({boss_info['age_days']} days ago)")
            else:
                logger.info(f"Discord sync complete: {updated_count} kill times updated")
            
        except Exception as e:
            logger.error(f"Error syncing kill times from Discord: {e}", exc_info=True)
            self.main_window.add_activity(
                datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
                "Discord Sync",
                "",
                f"Discord sync failed: {str(e)}"
            )
    
    def _perform_scan(self, file_path: str) -> None:
        """Perform the actual file scanning with progress updates."""
        from datetime import datetime, timedelta
        
        try:
            logger.info(f"Scanning log file: {file_path}")
            file_name = Path(file_path).name
            scan_start_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            
            # Post initial scan start message
            self.main_window.add_activity(
                scan_start_time,
                "Scan",
                file_name,
                f"Starting scan of {file_name}..."
            )
            
            # First pass: count total lines for progress tracking
            logger.debug("Counting lines in file...")
            total_lines = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for _ in f:
                    total_lines += 1
            
            logger.debug(f"File has {total_lines:,} total lines")
            
            # Calculate progress thresholds (every 20%)
            progress_thresholds = [0.2, 0.4, 0.6, 0.8, 1.0]
            next_threshold_idx = 0
            
            # Read and parse the entire file
            bosses_found = {}  # (monster, location) -> count
            # Track most recent kill timestamp for each boss
            # Key: monster name (lowercase), Value: {'timestamp': datetime, 'timestamp_str': str, 'location': str}
            boss_kill_times = {}  # monster_name_lower -> {'timestamp': datetime, 'timestamp_str': str, 'location': str}
            lines_processed = 0
            parsed_count = 0
            # Use timezone-aware datetime for consistency with kill_dt (EST)
            import pytz
            est = pytz.timezone('US/Eastern')
            now = est.localize(datetime.now())
            one_week_ago = now - timedelta(days=7)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    lines_processed += 1
                    
                    # Check if we've reached a progress threshold
                    if total_lines > 0:
                        progress = lines_processed / total_lines
                        if next_threshold_idx < len(progress_thresholds):
                            threshold = progress_thresholds[next_threshold_idx]
                            if progress >= threshold:
                                percent = int(threshold * 100)
                                self.main_window.add_activity(
                                    scan_start_time,
                                    "Scan",
                                    file_name,
                                    f"Scan progress: {percent}% ({lines_processed:,}/{total_lines:,} lines)"
                                )
                                logger.debug(f"Scan progress: {percent}%")
                                next_threshold_idx += 1
                                # Process events to update UI
                                self.app.processEvents()
                    
                    # Try normal guild message parsing first
                    parsed = MessageParser.parse_line(line)
                    is_lockout = False
                    
                    # If normal parsing fails, try lockout message as fallback
                    if not parsed:
                        parsed = MessageParser.parse_lockout_line(line)
                        if parsed:
                            is_lockout = True
                            logger.debug(f"Found lockout message during scan: {parsed.monster}")
                    
                    if parsed:
                        parsed_count += 1
                        monster = parsed.monster
                        location = parsed.location
                        
                        logger.debug(f"Parsed kill: {monster} in {location} at {parsed.timestamp}")
                        
                        # Track unique bosses (monster + location combination)
                        key = (monster, location)
                        if key not in bosses_found:
                            bosses_found[key] = {'monster': monster, 'location': location, 'count': 0}
                        bosses_found[key]['count'] += 1
                        
                        # Track most recent kill timestamp for this boss
                        # Skip duplicate boss names - we can't tell which specific entry was killed
                        duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
                        if monster not in duplicate_boss_names:
                            # Parse the timestamp from the log line
                            try:
                                kill_dt = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
                                monster_lower = monster.lower()
                                
                                # Track ALL kills (regardless of age) and find the most recent one
                                # Bosses older than 1 week will show as "available" via respawn calculation
                                if monster_lower not in boss_kill_times:
                                    boss_kill_times[monster_lower] = {
                                        'timestamp': kill_dt,
                                        'timestamp_str': parsed.timestamp,
                                        'location': location,
                                        'monster_name': monster  # Store original name for lookup
                                    }
                                elif kill_dt > boss_kill_times[monster_lower]['timestamp']:
                                    # This kill is more recent, update it
                                    boss_kill_times[monster_lower] = {
                                        'timestamp': kill_dt,
                                        'timestamp_str': parsed.timestamp,
                                        'location': location,
                                        'monster_name': monster  # Store original name for lookup
                                    }
                            except ValueError as e:
                                logger.warning(f"Could not parse timestamp '{parsed.timestamp}' for boss '{monster}': {e}")
                        else:
                            logger.debug(f"Skipping kill time tracking for duplicate boss '{monster}' - cannot determine specific entry")
            
            # Add all found bosses to database (disabled by default)
            added_count = 0
            skipped_count = 0
            updated_kill_times = 0
            
            for key, info in bosses_found.items():
                monster = info['monster']
                location = info['location']
                
                # Check if boss already exists (handle duplicates)
                existing_bosses = self.boss_db.get_bosses_by_name(monster)
                
                if existing_bosses:
                    # Update location if not set for any of the duplicates
                    for boss in existing_bosses:
                        if location and not boss.get('location'):
                            boss['location'] = location
                            logger.debug(f"Updated location for existing boss '{monster}': {location}")
                    skipped_count += len(existing_bosses)
                else:
                    # Add new boss (disabled by default)
                    self.boss_db.add_boss(monster, location, enabled=False)
                    added_count += 1
                    logger.info(f"Added boss from scan: {monster} in {location}")
            
            # Special-case: when scan finds duplicate-name bosses we can't tell which variant was killed
            # Clear last killed | respawn for all entries with that name so UI shows "Respawn: Unknown"
            duplicate_boss_names = ["Thall Va Xakra", "Kaas Thox Xi Aten Ha Ra"]
            found_monster_names = {info['monster'] for info in bosses_found.values()}
            cleared_duplicate_count = 0
            for dup_name in duplicate_boss_names:
                if dup_name not in found_monster_names:
                    continue
                existing_bosses = self.boss_db.get_bosses_by_name(dup_name)
                for boss in existing_bosses:
                    boss.pop('last_killed', None)
                    boss.pop('last_killed_timestamp', None)
                    boss['respawn_hours_is_default'] = True
                    cleared_duplicate_count += 1
                    logger.info(f"Cleared last kill/respawn for duplicate boss '{boss['name']}' ({boss.get('note', 'no note')}) - scan cannot determine which variant was killed")
            
            # Update last kill times for existing bosses
            for monster_lower, kill_info in boss_kill_times.items():
                # Find all bosses with this name (handles duplicates)
                # Use original monster name for lookup (method handles case-insensitive matching)
                existing_bosses = self.boss_db.get_bosses_by_name(kill_info['monster_name'])
                
                if existing_bosses:
                    # Update all matching bosses with the most recent kill time from log (log = truth)
                    for boss in existing_bosses:
                        kill_dt = kill_info['timestamp']
                        kill_timestamp_str = kill_info['timestamp_str']
                        if kill_dt.tzinfo is None:
                            import pytz
                            est = pytz.timezone('US/Eastern')
                            kill_dt = est.localize(kill_dt)
                        
                        # Log file is truth: always replace with scan result (overwrites simulation/false times)
                        boss['last_killed'] = kill_dt.isoformat()
                        boss['last_killed_timestamp'] = kill_timestamp_str
                        updated_kill_times += 1
                        age_days = (now - kill_dt).days
                        logger.debug(f"Calculated age: {age_days} days (now: {now}, kill_dt: {kill_dt})")
                        logger.info(f"Updated last kill time for '{boss['name']}' ({boss.get('note', 'no note')}): {kill_timestamp_str} ({age_days} days ago)")
                else:
                    logger.debug(f"No existing boss found for '{kill_info['monster_name']}' - kill time not updated (boss may need to be added first)")
            
            # Save database after all updates (including cleared duplicate bosses)
            if updated_kill_times > 0 or cleared_duplicate_count > 0:
                self.boss_db.save()
                if updated_kill_times > 0:
                    logger.info(f"Updated {updated_kill_times} boss kill times from scan")
                if cleared_duplicate_count > 0:
                    logger.info(f"Cleared last kill/respawn for {cleared_duplicate_count} duplicate boss entries (respawn unknown)")
            
            # Refresh UI to show new bosses and updated kill times
            self._refresh_bosses()
            
            # Count lockout-detected bosses for summary
            lockout_bosses = sum(1 for info in bosses_found.values() if info['location'] == 'Lockouts')
            
            # Post summary to activity log
            scan_end_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            summary_parts_scan = [
                f"Scan complete! File: {file_name} | ",
                f"Lines: {total_lines:,} | ",
                f"Kills found: {parsed_count:,} | ",
                f"Unique bosses: {len(bosses_found)} | ",
                f"Lockout-detected: {lockout_bosses} | ",
                f"Added: {added_count} | ",
                f"Skipped: {skipped_count} | ",
                f"Kill times updated: {updated_kill_times} | ",
            ]
            if cleared_duplicate_count > 0:
                summary_parts_scan.append(f"Cleared (respawn unknown): {cleared_duplicate_count} | ")
            summary_parts_scan.append("All new bosses disabled by default")
            summary = "".join(summary_parts_scan)
            
            self.main_window.add_activity(
                scan_end_time,
                "Scan",
                file_name,
                summary
            )
            
            logger.info(f"Scan complete: {added_count} new bosses added, {skipped_count} skipped, {updated_kill_times} kill times updated")
            
        except Exception as e:
            logger.error(f"Error scanning log file: {e}", exc_info=True)
            error_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            self.main_window.add_activity(
                error_time,
                "Scan",
                Path(file_path).name,
                f"Error: {str(e)}"
            )
    
    def _switch_theme(self) -> None:
        """Switch between light and dark themes."""
        current_theme = self.settings.get('theme', 'dark')
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        
        logger.info(f"Switching theme from {current_theme} to {new_theme}")
        
        # Update settings
        self.settings['theme'] = new_theme
        self._save_settings()
        
        # Apply new theme
        self._apply_theme(new_theme)
    
    def _apply_theme(self, theme: str) -> None:
        """Apply theme to the application."""
        try:
            # Get accent color from settings (default to blue)
            accent_color = self.settings.get('accent_color', '#007acc')
            # Update stylesheet
            self.app.setStyleSheet(_get_theme(theme, accent_color))
            
            # Update palette with accent color
            accent_qcolor = QColor(accent_color)
            if not accent_qcolor.isValid():
                accent_qcolor = QColor('#007acc')  # Fallback to default blue
            
            if theme == "dark":
                palette = QPalette()
                palette.setColor(QPalette.ColorRole.Window, QColor(13, 13, 13))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
                palette.setColor(QPalette.ColorRole.Base, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor(21, 21, 21))
                palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(13, 13, 13))
                palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
                palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
                palette.setColor(QPalette.ColorRole.Button, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
                palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.Link, accent_qcolor)
                # Use a darker version for highlight
                h, s, l, a = accent_qcolor.getHslF()
                darker_accent = QColor()
                darker_accent.setHslF(h, s, max(0.0, l - 0.3), a)
                palette.setColor(QPalette.ColorRole.Highlight, darker_accent)
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
                self.app.setPalette(palette)
            else:
                palette = QPalette()
                palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor(249, 249, 249))
                palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.ToolTipText, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.Text, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(26, 26, 26))
                palette.setColor(QPalette.ColorRole.BrightText, QColor(0, 0, 0))
                palette.setColor(QPalette.ColorRole.Link, accent_qcolor)
                palette.setColor(QPalette.ColorRole.Highlight, accent_qcolor)
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
                self.app.setPalette(palette)
            
            # Update menu text
            self.main_window.update_theme_menu(theme)
            
            logger.info(f"Theme switched to {theme}")
        except Exception as e:
            logger.error(f"Error applying theme: {e}", exc_info=True)
    
    def _refresh_bosses(self) -> None:
        """Refresh boss list in main window."""
        try:
            bosses = self.boss_db.get_all_bosses()
            self.main_window.set_bosses(bosses)
            # Refresh all boss info labels (last kill time, respawn time)
            # This recalculates respawn times based on current time
            QTimer.singleShot(100, lambda: self._update_all_boss_info_labels())
            logger.debug(f"Refreshed boss list: {len(bosses)} bosses")
        except Exception as e:
            logger.error(f"Error refreshing bosses: {e}", exc_info=True)
    
    def _update_all_boss_info_labels(self) -> None:
        """Update all boss info labels (called after UI is ready)."""
        try:
            bosses = self.boss_db.get_all_bosses()
            for boss in bosses:
                self.main_window.zone_widget.refresh_boss_info(boss['name'])
        except Exception as e:
            logger.error(f"Error updating boss info labels: {e}", exc_info=True)
    
    def _update_activity_log(self) -> None:
        """Update activity log in main window."""
        try:
            today_activities = self.activity_db.get_today_activities()
            # Activity log widget will handle setting activities
            logger.debug(f"Updating activity log with {len(today_activities)} entries")
            # Use QTimer to ensure UI update happens on main thread
            QTimer.singleShot(0, lambda: self.main_window.activity_log.set_activities(today_activities))
        except Exception as e:
            logger.error(f"Error updating activity log: {e}", exc_info=True)
    
    def _update_active_character(self) -> None:
        """Update active character display."""
        try:
            if self.log_monitor:
                character = self.log_monitor.get_active_character()
                self.main_window.set_active_character(character)
                self.tray.set_tooltip(
                    f"Project Quarm Boss Tracker - Monitoring: {character}" if character
                    else "Project Quarm Boss Tracker - No active character"
                )
        except Exception as e:
            logger.error(f"Error updating active character: {e}", exc_info=True)
    
    def _show_main_window(self) -> None:
        """Show the main window."""
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        logger.debug("Main window shown")
    
    def _on_boss_enabled_changed(self, boss: Dict, enabled: bool) -> None:
        """Handle boss enable/disable change from UI."""
        self._handle_boss_enable_change(boss, enabled)
    
    def _handle_boss_enable_change(self, boss: Dict, enabled: bool) -> None:
        """Handle boss enable/disable change."""
        boss_name = boss.get('name', 'Unknown')
        note = boss.get('note', '').strip()
        
        # Use boss dict directly for proper duplicate handling
        if enabled:
            self.boss_db.enable_boss(boss_name, note=note, boss=boss)
        else:
            self.boss_db.disable_boss(boss_name, note=note, boss=boss)
    
    def _on_zone_enabled_changed(self, zone_name: str, enabled: bool) -> None:
        """Handle zone enable/disable change from UI."""
        self._handle_zone_enable_change(zone_name, enabled)
    
    def _handle_zone_enable_change(self, zone_name: str, enabled: bool) -> None:
        """Handle zone enable/disable change."""
        try:
            # Get all bosses in this zone
            bosses_by_zone = self.boss_db.get_bosses_by_location()
            zone_bosses = bosses_by_zone.get(zone_name, [])
            
            for boss in zone_bosses:
                try:
                    boss_name = boss.get('name')
                    note = boss.get('note', '').strip()
                    # Use boss dict for proper duplicate handling
                    if enabled:
                        self.boss_db.enable_boss(boss_name, note=note, boss=boss)
                    else:
                        self.boss_db.disable_boss(boss_name, note=note, boss=boss)
                except Exception as e:
                    logger.error(f"Error {'enabling' if enabled else 'disabling'} boss {boss.get('name', 'unknown')}: {e}", exc_info=True)
            
            # Use QTimer to defer refresh to avoid issues during signal processing
            QTimer.singleShot(0, self._refresh_bosses)
        except Exception as e:
            logger.error(f"Error handling zone enable change: {e}", exc_info=True)
    
    def _on_all_bosses_enabled_changed(self, enabled: bool) -> None:
        """Handle enable/disable all bosses across all zones."""
        try:
            all_bosses = self.boss_db.get_all_bosses()
            logger.info(f"{'Enabling' if enabled else 'Disabling'} all {len(all_bosses)} targets across all zones")
            
            for boss in all_bosses:
                try:
                    boss_name = boss.get('name')
                    note = boss.get('note', '').strip()
                    # Use boss dict for proper duplicate handling
                    if enabled:
                        self.boss_db.enable_boss(boss_name, note=note, boss=boss)
                    else:
                        self.boss_db.disable_boss(boss_name, note=note, boss=boss)
                except Exception as e:
                    logger.error(f"Error {'enabling' if enabled else 'disabling'} boss {boss.get('name', 'unknown')}: {e}", exc_info=True)
            
            # Use QTimer to defer refresh to avoid issues during signal processing
            QTimer.singleShot(0, self._refresh_bosses)
        except Exception as e:
            logger.error(f"Error handling all bosses enable change: {e}", exc_info=True)
    
    def _on_add_boss_requested(self) -> None:
        """Handle add boss request from UI."""
        try:
            try:
                from .add_boss_dialog import AddBossDialog
            except ImportError:
                from add_boss_dialog import AddBossDialog

            dialog = AddBossDialog(self.main_window)
            if dialog.exec():
                name, location, note = dialog.get_boss_data()
                if name:
                    self._handle_add_boss(name, location or '', note)
        except ImportError as e:
            logger.error(f"Error importing add boss dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self.main_window,
                "Error",
                f"Could not open add target dialog: {e}"
            )
        except Exception as e:
            logger.error(f"Error showing add boss dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self.main_window,
                "Error",
                f"Could not open add target dialog: {e}"
            )
    
    def _handle_add_boss(self, name: str, location: str = '', note: Optional[str] = None) -> None:
        """Handle adding a boss manually."""
        self.boss_db.add_boss(name, location, enabled=False, note=note)
        self._refresh_bosses()
    
    def _on_remove_boss_requested(self, boss_name: str) -> None:
        """Handle remove boss request from UI."""
        # This is called with just the name, but we should handle boss dict instead
        # The main_window will pass the boss dict via on_remove_boss callback
        pass
    
    def _handle_remove_boss(self, boss: Dict) -> None:
        """Handle removing a boss."""
        boss_name = boss.get('name')
        note = boss.get('note')
        # Remove using boss dict for proper duplicate handling
        success = self.boss_db.remove_boss(boss_name, note=note, boss=boss)
        if success:
            logger.info(f"Successfully removed boss: {boss_name} ({note or 'no note'})")
        else:
            logger.warning(f"Failed to remove boss: {boss_name}")
        self._refresh_bosses()
    
    def _show_options(self) -> None:
        """Show the options window."""
        window = OptionsWindow(self.main_window)
        window.set_settings(self.settings)
        window.set_bosses_json_path(self.bosses_path)
        
        if self.log_monitor:
            window.set_active_character(self.log_monitor.get_active_character())
        
        window.on_settings_save = self._save_options
        window.on_test_notification = self._test_windows_notification
        
        # Set callback for manual backup creation
        def create_backup():
            """Create a manual backup of bosses.json."""
            try:
                backup_path = self.boss_db.create_manual_backup()
                return backup_path
            except Exception as e:
                logger.error(f"Error creating manual backup: {e}", exc_info=True)
                return None
        
        window.on_create_backup = create_backup
        
        if window.exec():
            logger.info("Options window closed with Save")
        else:
            logger.debug("Options window closed with Cancel")
    
    def _format_message_for_notification(self, template: str, timestamp: Optional[str] = None, **kwargs) -> str:
        """
        Format a message for system notifications, using regular timestamps instead of Discord timestamps.
        Handles {note} variable - removes it if note is empty.
        
        Args:
            template: Message template with {variable} placeholders
            timestamp: Timestamp string from log
            **kwargs: Variables to substitute in template
            
        Returns:
            Formatted message string with regular timestamps (not Discord format)
        """
        # Replace Discord timestamp variables with regular timestamp variable
        # This ensures Windows notifications show readable timestamps
        notification_template = template.replace('{discord_timestamp}', '{timestamp}')
        notification_template = notification_template.replace('{discord_timestamp_relative}', '{timestamp}')
        
        # Handle {note} variable - remove it if note is empty (same as Discord formatting)
        note = kwargs.get('note', '').strip()
        if not note:
            import re
            # Remove {note} and any surrounding parentheses and spaces
            notification_template = re.sub(r'\s*\(?\s*\{note\}\s*\)?\s*', ' ', notification_template)
            # Clean up multiple spaces
            notification_template = re.sub(r'\s+', ' ', notification_template).strip()
            # Remove note from kwargs so format() doesn't try to use it
            kwargs = {k: v for k, v in kwargs.items() if k != 'note'}
        
        # Ensure timestamp variable exists
        if 'timestamp' not in kwargs and timestamp:
            kwargs['timestamp'] = timestamp
        
        try:
            result = notification_template.format(**kwargs)
            logger.debug(f"Formatted notification message: {result[:100]}...")
            return result
        except KeyError as e:
            logger.error(f"Missing template variable in notification: {e}")
            return template
    
    def _test_windows_notification(self) -> None:
        """Test system notification functionality using the message format preview."""
        logger.info("Testing system notification")
        
        # Get the current message template from settings
        template = self.settings.get(
            'message_template',
            '{discord_timestamp} {monster} was killed in {location}!'
        )
        
        # Use the same sample data as the message format preview
        sample_timestamp = 'Sat Nov 22 23:02:42 2025'
        sample_data = {
            'monster': 'Severilous',
            'note': '',  # No note for first test
            'player': 'Saelilya',
            'guild': 'Former Glory',
            'location': 'The Emerald Jungle',
            'server': 'Druzzil Ro'
        }
        
        # Format the message for system notification (uses regular timestamp, not Discord format)
        formatted_message = self._format_message_for_notification(
            template,
            timestamp=sample_timestamp,
            **sample_data
        )
        
        # Show notification with formatted message
        self.tray.show_notification(
            "Target has been slain!",
            formatted_message
        )
        
        # Also test with a note to show how it works
        sample_data_with_note = {
            'monster': 'Thall Va Xakra',
            'note': 'F1 North',  # Example note
            'player': 'Saelilya',
            'guild': 'Former Glory',
            'location': 'Vex Thal',
            'server': 'Druzzil Ro'
        }
        
        formatted_message_with_note = self._format_message_for_notification(
            template,
            timestamp=sample_timestamp,
            **sample_data_with_note
        )
        
        # Show second notification with note example
        self.tray.show_notification(
            "Target has been slain! (with note)",
            formatted_message_with_note
        )
    
    def _save_options(self, new_settings: dict) -> None:
        """Save options from the options window."""
        keys_updated = list(new_settings.keys())
        new_webhook = new_settings.get('default_webhook_url', '') or ''
        old_webhook = self.settings.get('default_webhook_url', '') or ''
        webhook_changed = old_webhook != new_webhook

        _app_log.info("=" * 60)
        _app_log.info("SETTINGS: _save_options called (Options dialog saved)")
        _app_log.info("SETTINGS: Keys being saved: %s", keys_updated)
        _app_log.info("SETTINGS: default_webhook_url: %s (len=%d)", "EMPTY" if not new_webhook else _mask_webhook(new_webhook), len(new_webhook))
        _app_log.info("SETTINGS: webhook_changed=%s | Writing to file: %s", webhook_changed, self.settings_path)
        # Check if accent color changed
        old_accent = self.settings.get('accent_color', '#007acc')
        new_accent = new_settings.get('accent_color', '#007acc')
        accent_changed = old_accent != new_accent
        logger.debug(f"[OPTIONS] accent_color changed={accent_changed}")
        # Update settings
        self.settings.update(new_settings)
        if 'accent_color' not in self.settings:
            self.settings['accent_color'] = '#007acc'
            logger.warning("accent_color was missing from settings, using default")
        _app_log.info("SETTINGS: Calling _save_settings() -> %s", self.settings_path)
        self._save_settings()
        _app_log.info("SETTINGS: Save completed. default_webhook_url in file is now: %s", "EMPTY" if not (self.settings.get('default_webhook_url') or '').strip() else _mask_webhook(self.settings.get('default_webhook_url', '')))
        _app_log.info("=" * 60)

        # Reapply theme if accent color changed
        if accent_changed:
            current_theme = self.settings.get('theme', 'dark')
            self._apply_theme(current_theme)

        # Update components
        self.discord_notifier.default_webhook_url = self.settings.get('default_webhook_url', '')
        logger.debug(f"Options: discord_notifier.default_webhook_url synced to settings: {_mask_webhook(self.discord_notifier.default_webhook_url)}")
        
        # Update timezone (empty = auto-detect; formatter supports any IANA name including EU/AUS)
        timezone = self.settings.get('timezone', '')
        self.timestamp_formatter.set_timezone(timezone)
        
        # Update time format in zone widget
        use_military_time = self.settings.get('use_military_time', False)
        self.main_window.zone_widget.set_time_format(use_military_time)
        
        # Start/stop Discord sync timer based on whether Discord is configured
        if self._has_discord_sync_config():
            interval_hours = max(1, min(168, int(self.settings.get('discord_sync_interval_hours', 12))))
            self.discord_sync_timer.stop()
            self.discord_sync_timer.start(interval_hours * 3600 * 1000)
            logger.info(f"Discord sync timer started: every {interval_hours} hour(s)")
        else:
            self.discord_sync_timer.stop()
            logger.debug("Discord sync timer stopped: webhook or bot token not configured")
        
        # Update sound
        self.sound_player.set_enabled(self.settings.get('sound_enabled', True))
        
        # Update sound file path if changed
        new_sound_path = self.settings.get('sound_file_path', 'fanfare.mp3')
        if not Path(new_sound_path).is_absolute():
            new_sound_path = self.app_dir / "assets" / new_sound_path
        else:
            new_sound_path = Path(new_sound_path)
        
        # Only update if path changed
        if str(new_sound_path) != str(self.sound_player.sound_file_path):
            self.sound_player.set_sound_file(str(new_sound_path))
        
        # Update Discord checker: use token from new_settings (form) so we have the value just saved
        bot_token = (new_settings.get('discord_bot_token') or '').strip()
        if not bot_token:
            bot_token = (self.settings.get('discord_bot_token') or '').strip()
        if bot_token and not self.discord_checker:
            if DiscordChecker:
                try:
                    import asyncio
                    import threading
                    logger.info("Creating Discord checker from saved credentials (token length=%d)", len(bot_token))
                    self.discord_checker = DiscordChecker(bot_token)

                    def _init_discord_checker():
                        try:
                            asyncio.run(self.discord_checker.initialize())
                            logger.info("Discord checker initialized after settings save")
                        except Exception as e:
                            logger.error(f"Error initializing Discord checker: {e}")

                    init_thread = threading.Thread(target=_init_discord_checker, daemon=True)
                    init_thread.start()
                    logger.info("Discord checker created from settings (initializing in background)")
                except Exception as e:
                    logger.warning(f"Failed to create Discord checker: {e}")
                    self.discord_checker = None
            else:
                logger.warning("Discord checker not available (discord.py not installed)")
        elif bot_token and self.discord_checker:
            self.discord_checker.bot_token = bot_token
            logger.info("Discord checker bot token updated")
        
        # Update log monitor if directory changed
        new_log_dir = self.settings.get('log_directory', '')
        if new_log_dir and (not self.log_monitor or self.log_monitor.log_directory != Path(new_log_dir)):
            if self.log_monitor:
                self.log_monitor.stop()
            self.log_monitor = LogMonitor(new_log_dir, self._on_new_log_line)
            self.log_monitor.start()
            logger.info(f"Log monitor updated with new directory: {new_log_dir}")
    
    def _show_respawn_time_editor(self) -> None:
        """Show the respawn time editor dialog (Tools → Edit Bosses)."""
        self._show_respawn_time_editor_for_boss(None)

    def _show_respawn_time_editor_for_boss(self, initial_boss) -> None:
        """Show the respawn time editor dialog, optionally with a specific boss preselected."""
        try:
            try:
                from .respawn_time_editor import RespawnTimeEditor
            except ImportError:
                from respawn_time_editor import RespawnTimeEditor

            bosses = self.boss_db.get_all_bosses()
            if not bosses:
                QMessageBox.information(
                    self.main_window,
                    "No Targets",
                    "No targets found. Please add targets first."
                )
                return

            dialog = RespawnTimeEditor(bosses, self.main_window, initial_boss=initial_boss)
            if dialog.exec():
                boss_dict, respawn_hours, note = dialog.get_selected_boss_and_respawn()
                if boss_dict:
                    boss_name = boss_dict['name']
                    original_note = boss_dict.get('note', '').strip()
                    
                    # Find the actual boss in the database list (by name and original note)
                    # This ensures we're updating the correct entry, not a copy
                    actual_boss = None
                    if original_note:
                        actual_boss = next(
                            (b for b in self.boss_db.bosses 
                             if b['name'].lower() == boss_name.lower() 
                             and b.get('note', '').strip() == original_note),
                            None
                        )
                    else:
                        # For non-duplicate bosses, find by name (first match)
                        actual_boss = next(
                            (b for b in self.boss_db.bosses 
                             if b['name'].lower() == boss_name.lower() 
                             and not b.get('note', '').strip()),
                            None
                        )
                    
                    if not actual_boss:
                        logger.warning(f"Could not find boss '{boss_name}' (note: '{original_note}') in database")
                        QMessageBox.warning(
                            self.main_window,
                            "Update Failed",
                            f"Could not find the selected boss in the database."
                        )
                        return
                    
                    boss_identifier = boss_name
                    if note:
                        boss_identifier = f"{boss_name} ({note})"
                    
                    # Track what was changed
                    changes = []
                    
                    # Set respawn time - use the actual boss dict from database
                    old_respawn = actual_boss.get('respawn_hours')
                    self.boss_db.set_respawn_time(boss_name, respawn_hours, note=original_note, boss=actual_boss)
                    if respawn_hours != old_respawn:
                        if respawn_hours:
                            days = int(respawn_hours // 24)
                            hours = int(respawn_hours % 24)
                            changes.append(f"Respawn time: {days} day(s), {hours} hour(s)")
                        else:
                            changes.append("Respawn time: Removed")
                        if respawn_hours:
                            logger.info(f"Set respawn time for '{boss_identifier}': {respawn_hours} hours")
                        else:
                            logger.info(f"Removed respawn time for '{boss_identifier}'")
                    
                    # Set note - use the actual boss dict from database
                    old_note = actual_boss.get('note', '').strip()
                    self.boss_db.set_note(boss_name, note, boss=actual_boss)
                    new_note = note.strip() if note else ''
                    if old_note != new_note:
                        if new_note:
                            changes.append(f"Note: '{new_note}'")
                        else:
                            changes.append("Note: Removed")
                        if note:
                            logger.info(f"Set note for '{boss_identifier}': {note}")
                        else:
                            logger.info(f"Removed note for '{boss_identifier}'")
                    
                    # Refresh UI to show updated respawn times and notes
                    self._refresh_bosses()
                    
                    # Show success message with what was changed
                    if changes:
                        message_parts = [f"Boss '{boss_identifier}' updated:"]
                        message_parts.extend(changes)
                        message = "\n".join(message_parts)
                        
                        QMessageBox.information(
                            self.main_window,
                            "Boss Updated",
                            message
                        )
                    else:
                        # No changes detected (user clicked save without changing anything)
                        QMessageBox.information(
                            self.main_window,
                            "No Changes",
                            f"No changes were made to '{boss_identifier}'."
                        )
        except ImportError as e:
            logger.error(f"Error importing respawn time editor: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not open respawn time editor: {e}"
            )
        except Exception as e:
            logger.error(f"Error showing respawn time editor: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred: {e}"
            )
    
    def _show_message_editor(self) -> None:
        """Show the message format editor."""
        window = MessageEditor(self.main_window)
        window.set_template(
            self.settings.get('message_template', '{discord_timestamp} {monster} was killed in {location}!'),
            self.settings.get('lockout_message_template', '{discord_timestamp} {monster} lockout detected!')
        )
        window.on_save = self._save_message_template
        
        if window.exec():
            logger.info("Message editor closed with Save")
        else:
            logger.debug("Message editor closed with Cancel")
    
    def _save_message_template(self, template: str, lockout_template: str) -> None:
        """Save the message templates."""
        logger.info(f"Saving message templates: regular={template[:50]}..., lockout={lockout_template[:50]}...")
        self.settings['message_template'] = template
        self.settings['lockout_message_template'] = lockout_template
        self._save_settings()
    
    def _exit_app(self) -> None:
        """Exit the application."""
        logger.info("Exiting application")
        
        # Stop log monitor
        if self.log_monitor:
            try:
                self.log_monitor.stop()
                logger.debug("Log monitor stopped")
            except Exception as e:
                logger.warning(f"Error stopping log monitor: {e}")
        
        # Stop Discord notifier
        try:
            self.discord_notifier.stop()
            logger.debug("Discord notifier stopped")
        except Exception as e:
            logger.warning(f"Error stopping Discord notifier: {e}")
        
        # Close Discord checker
        if self.discord_checker:
            try:
                # Discord checker cleanup (async, but we'll just log for now)
                logger.info("Discord checker will be closed on exit")
            except Exception as e:
                logger.warning(f"Error closing Discord checker: {e}")
        
        # Close all windows
        try:
            if self.main_window:
                self.main_window.close()
            if hasattr(self, 'options_window') and self.options_window:
                self.options_window.close()
        except Exception as e:
            logger.warning(f"Error closing windows: {e}")
        
        # Quit application
        logger.info("Application exit complete")
        QApplication.quit()


def main():
    """Application entry point."""
    # Check for debug logging flag (command line or environment variable)
    import argparse
    parser = argparse.ArgumentParser(description='Project Quarm Boss Tracker')
    parser.add_argument('--debug', '-d', action='store_true', 
                       help='Enable debug logging (verbose)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='Set logging level (DEBUG, INFO, WARNING, ERROR)')
    args, unknown = parser.parse_known_args()  # Use parse_known_args to avoid Qt argument conflicts
    
    # Determine log level
    log_level = logging.INFO  # Default
    if args.debug or os.getenv('EQ_BOSS_TRACKER_DEBUG', '').lower() in ('1', 'true', 'yes'):
        log_level = logging.DEBUG
        print("=" * 80)
        print("DEBUG LOGGING ENABLED - Verbose logging active")
        print("=" * 80)
    elif args.log_level:
        log_level = getattr(logging, args.log_level)
        print(f"Log level set to: {args.log_level}")
    elif os.getenv('EQ_BOSS_TRACKER_LOG_LEVEL'):
        level_str = os.getenv('EQ_BOSS_TRACKER_LOG_LEVEL').upper()
        if hasattr(logging, level_str):
            log_level = getattr(logging, level_str)
            print(f"Log level from environment: {level_str}")
    
    # #region agent log
    # Check if running as onefile or onedir
    # Note: _MEIPASS exists in both modes, but in --onedir it points to _internal folder
    # In --onefile it points to a temp directory (usually in AppData\Local\Temp)
    is_onefile = False
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            meipass = sys._MEIPASS
            # Check if _MEIPASS is a temp directory (indicates --onefile)
            # Temp directories typically contain "_MEI" in the path
            import tempfile
            temp_dir = tempfile.gettempdir()
            is_onefile = temp_dir.lower() in meipass.lower() or '_MEI' in Path(meipass).name
    
    debug_log("main.py:1366", "Application startup", {
        "frozen": getattr(sys, 'frozen', False),
        "is_onefile": is_onefile,
        "is_onedir": getattr(sys, 'frozen', False) and not is_onefile,
        "executable": sys.executable if getattr(sys, 'frozen', False) else None,
        "meipass": getattr(sys, '_MEIPASS', None) if hasattr(sys, '_MEIPASS') else None,
        "argv": sys.argv
    }, hypothesis_id="A", run_id="initial")
    
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        debug_log("main.py:1366", "Memory at startup", {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024
        }, hypothesis_id="A", run_id="initial")
    except ImportError:
        pass
    # #endregion
    
    # Check for single instance (prevent multiple instances)
    if sys.platform == 'win32':
        try:
            import win32event
            import win32api
            import winerror
            
            # Create a named mutex to ensure only one instance
            mutex_name = "BossTrackerSingleInstanceMutex"
            mutex = win32event.CreateMutex(None, False, mutex_name)
            last_error = win32api.GetLastError()
            
            if last_error == winerror.ERROR_ALREADY_EXISTS:
                # Another instance is already running
                print("Another instance of Boss Tracker is already running.")
                print("Please close the existing instance or check the system tray.")
                sys.exit(1)
        except ImportError:
            # pywin32 not available, skip single-instance check
            pass
        except Exception as e:
            # If mutex creation fails for any reason, log but continue
            print(f"Warning: Could not create single-instance mutex: {e}")
    
    # Set up logging first
    # Determine app directory for finding default files
    app_dir = Path(__file__).parent.parent if not getattr(sys, 'frozen', False) else Path(sys.executable).parent
    
    # #region agent log
    debug_log("main.py:1394", "App directory determined", {
        "app_dir": str(app_dir),
        "frozen": getattr(sys, 'frozen', False),
        "executable_parent": str(Path(sys.executable).parent) if getattr(sys, 'frozen', False) else None
    }, hypothesis_id="A", run_id="initial")
    # #endregion
    
    # Use user data directory for logs
    app_name = "boss tracker"
    if sys.platform == 'win32':
        appdata = os.getenv('APPDATA')
        if appdata:
            log_dir = Path(appdata) / app_name / "logs"
        else:
            log_dir = Path.home() / "AppData" / "Roaming" / app_name / "logs"
    elif sys.platform == 'darwin':
        log_dir = Path.home() / "Library" / "Application Support" / app_name / "logs"
    else:
        xdg_config = os.getenv('XDG_CONFIG_HOME')
        if xdg_config:
            log_dir = Path(xdg_config) / app_name / "logs"
        else:
            log_dir = Path.home() / ".config" / app_name / "logs"
    
    logger = setup_logging(log_dir, log_level=log_level)
    
    # Log startup information
    log_filename = f'boss_tracker_{datetime.now().strftime("%Y%m%d")}.log'
    log_file_path = log_dir / log_filename
    
    logger.info("=" * 80)
    logger.info("Project Quarm Boss Tracker - Starting")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    logger.info(f"Log file: {log_file_path}")
    if log_level == logging.DEBUG:
        logger.info("DEBUG MODE: Verbose logging enabled")
        logger.debug("Debug logging is active - all operations will be logged in detail")
    logger.info("=" * 80)
    
    # #region agent log
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        debug_log("main.py:1413", "Memory after logging setup", {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024
        }, hypothesis_id="F", run_id="initial")
    except ImportError:
        debug_log("main.py:1413", "Memory check skipped (psutil not available)", {}, hypothesis_id="F", run_id="initial")
    # #endregion
    
    # Install exception handler to catch unhandled exceptions and prevent console windows
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Handle unhandled exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = exception_handler
    
    app = QApplication(sys.argv)
    app.setApplicationName("Project Quarm Boss Tracker")
    app.setApplicationDisplayName("Project Quarm Boss Tracker")
    app.setQuitOnLastWindowClosed(False)  # Keep running when windows are closed
    
    # #region agent log
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        debug_log("main.py:1429", "Memory after QApplication creation", {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024
        }, hypothesis_id="C", run_id="initial")
    except ImportError:
        pass
    # #endregion
    
    # Note: PyQt6 handles high DPI scaling automatically, no need to set attributes
    
    # Determine app directory (for finding default files like bosses.json)
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent.parent
    
    # Get user data directory for settings
    app_name = "boss tracker"
    if sys.platform == 'win32':
        appdata = os.getenv('APPDATA')
        if appdata:
            user_data_dir = Path(appdata) / app_name
        else:
            user_data_dir = Path.home() / "AppData" / "Roaming" / app_name
    elif sys.platform == 'darwin':
        user_data_dir = Path.home() / "Library" / "Application Support" / app_name
    else:
        xdg_config = os.getenv('XDG_CONFIG_HOME')
        if xdg_config:
            user_data_dir = Path(xdg_config) / app_name
        else:
            user_data_dir = Path.home() / ".config" / app_name
    
    # Load settings to get theme preference
    settings_path = user_data_dir / "settings.json"
    theme = "dark"  # Default
    
    # Detect OS theme on first run (if settings don't exist)
    is_first_run = not settings_path.exists()
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                theme = settings.get('theme', 'dark')
        except Exception as e:
            logger.warning(f"Could not load theme from settings: {e}")
    elif is_first_run:
        # First run - detect OS theme
        try:
            from .os_theme_detector import detect_os_theme
            detected_theme = detect_os_theme()
            theme = detected_theme
            logger.info(f"First run detected - using OS theme: {theme}")
        except ImportError:
            try:
                from os_theme_detector import detect_os_theme
                detected_theme = detect_os_theme()
                theme = detected_theme
                logger.info(f"First run detected - using OS theme: {theme}")
            except ImportError:
                logger.warning("Could not import OS theme detector, using default dark theme")
        except Exception as e:
            logger.warning(f"Error detecting OS theme: {e}, using default dark theme")
    
    # Apply palette based on theme
    if theme == "dark":
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(13, 13, 13))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Base, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(21, 21, 21))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(13, 13, 13))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Button, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 122, 204))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(10, 74, 106))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)
        
        # Force dark mode on Windows to prevent theme overlays
        if sys.platform == 'win32':
            try:
                import ctypes
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        ctypes.windll.user32.GetForegroundWindow(),
                        20,  # DWMWA_USE_IMMERSIVE_DARK_MODE
                        ctypes.byref(ctypes.c_int(1)),
                        ctypes.sizeof(ctypes.c_int)
                    )
                except:
                    pass
            except:
                pass
    else:
        # Light theme palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(249, 249, 249))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.Text, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(26, 26, 26))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)
    
    # Load and apply theme stylesheet
    try:
        # Get accent color from settings (default to blue)
        accent_color = '#007acc'  # Default
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    temp_settings = json.load(f)
                    accent_color = temp_settings.get('accent_color', '#007acc')
            except Exception:
                pass
        
        app.setStyleSheet(_get_theme(theme, accent_color))
        logger.info(f"Using {theme} theme with accent color {accent_color}")
    except Exception as e:
        logger.error(f"Error loading theme: {e}")
        # Fallback to dark theme
        app.setStyleSheet(_get_theme("dark", '#007acc'))
    
    # Check if system tray is available
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("System tray is not available!")
        QMessageBox.critical(
            None,
            "System Tray",
            "System tray is not available on this system."
        )
        sys.exit(1)
    
    # Create and run application
    try:
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:1517", "Memory before BossTrackerApp creation", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="F", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        debug_mode = args.debug or os.getenv('EQ_BOSS_TRACKER_DEBUG', '').lower() in ('1', 'true', 'yes')
        tracker = BossTrackerApp(app, debug_mode=debug_mode)
        
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:1517", "Memory after BossTrackerApp creation", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="F", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        # Theme is already applied in BossTrackerApp.__init__ with accent color
        # Just update the menu to reflect current theme
        current_theme = tracker.settings.get('theme', 'dark')
        tracker.main_window.update_theme_menu(current_theme)
        
        # Show main window on startup (defer to ensure UI is ready)
        QTimer.singleShot(100, tracker._show_main_window)
        
        logger.info("Application started successfully")
        
        # #region agent log
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            debug_log("main.py:1529", "Memory before app.exec()", {
                "rss_mb": mem_info.rss / 1024 / 1024,
                "vms_mb": mem_info.vms / 1024 / 1024
            }, hypothesis_id="F", run_id="initial")
        except ImportError:
            pass
        # #endregion
        
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Error",
            f"Failed to start application:\n{e}"
        )
        sys.exit(1)


def _lighten_color(hex_color: str, factor: float = 0.2) -> str:
    """Lighten a hex color by a factor (0.0 to 1.0)."""
    color = QColor(hex_color)
    if not color.isValid():
        return hex_color
    
    # Convert to HSL, lighten, convert back
    h, s, l, a = color.getHslF()
    l = min(1.0, l + factor)
    color.setHslF(h, s, l, a)
    return color.name()

def _darken_color(hex_color: str, factor: float = 0.2) -> str:
    """Darken a hex color by a factor (0.0 to 1.0)."""
    color = QColor(hex_color)
    if not color.isValid():
        return hex_color
    
    # Convert to HSL, darken, convert back
    h, s, l, a = color.getHslF()
    l = max(0.0, l - factor)
    color.setHslF(h, s, l, a)
    return color.name()

def _get_theme(theme_name: str = "dark", accent_color: str = "#007acc") -> str:
    """Get theme QSS by name with optional accent color."""
    if theme_name == "light":
        return _get_light_theme(accent_color)
    else:
        return _get_dark_theme(accent_color)

def _get_dark_theme(accent_color: str = "#007acc") -> str:
    """Get a default dark theme with custom accent color."""
    # Generate color variations
    base_color = accent_color
    hover_color = _lighten_color(base_color, 0.15)
    pressed_color = _darken_color(base_color, 0.25)
    border_color = _lighten_color(base_color, 0.1)
    status_bar_color = base_color
    status_bar_border = _darken_color(base_color, 0.3)
    focus_color = _lighten_color(base_color, 0.1)
    selection_color = _darken_color(base_color, 0.4)
    
    return """
/* Dark Theme - Deep, Rich Dark Colors - No White Sheen */
QWidget {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
}}

QMainWindow {{
    background-color: #0d0d0d;
}}

QDialog {{
    background-color: #0d0d0d;
    color: #f0f0f0;
}}

QPushButton {{
    background-color: {base_color};
    color: #ffffff;
    border: 1px solid {border_color};
    border-radius: 4px;
    padding: 6px 14px;
    min-width: 80px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: 500;
    font-size: 9pt;
}}

QPushButton:hover {{
    background-color: {hover_color};
    border-color: {focus_color};
}}

QPushButton:pressed {{
    background-color: {pressed_color};
    border-color: {pressed_color};
}}

QPushButton:disabled {{
    background-color: #1a1a1a;
    color: #666666;
    border-color: #1a1a1a;
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: #1a1a1a;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    selection-background-color: {selection_color};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {focus_color};
    background-color: #1f1f1f;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #151515;
    color: #666666;
    border-color: #1a1a1a;
}}

QCheckBox {{
    color: #f0f0f0;
    spacing: 8px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid #2a2a2a;
    border-radius: 4px;
    background-color: #1a1a1a;
}}

QCheckBox::indicator:hover {{
    border-color: {focus_color};
    background-color: #1f1f1f;
}}

QCheckBox::indicator:checked {{
    background-color: {base_color};
    border-color: {border_color};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzLjMzMzMgNEw2IDEyTDIuNjY2NjcgOC42NjY2NyIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
}}

QCheckBox::indicator:disabled {{
    background-color: #151515;
    border-color: #1a1a1a;
}}

QListWidget {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    alternate-background-color: #151515;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid #2a2a2a;
    color: #f0f0f0;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QListWidget::item:hover {{
    background-color: #1a1a1a;
    color: #ffffff;
}}

QListWidget::item:selected {{
    background-color: {selection_color};
    color: #ffffff;
}}

QGroupBox {{
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
    color: #f0f0f0;
    font-size: 10pt;
    background-color: #0d0d0d;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
}}

QGroupBox QLabel {{
    color: #f0f0f0;
}}

QGroupBox QLabel[class="zone-title"] {{
    color: #f0f0f0;
    font-weight: bold;
}}

QGroupBox QLabel[class="zone-count"] {{
    color: #999999;
}}

QLabel {{
    color: #f0f0f0;
    background-color: transparent;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QLabel[class="heading"] {{
    color: #ffffff;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
    font-size: 11pt;
}}

QMenuBar {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    border-bottom: 1px solid #2a2a2a;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

QMenuBar::item:selected {{
    background-color: #1a1a1a;
    color: #ffffff;
}}

QMenu {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMenu::item {{
    padding: 6px 24px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    color: #f0f0f0;
}}

QMenu::item:selected {{
    background-color: {selection_color};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: #2a2a2a;
    margin: 4px 0;
}}

QStatusBar {{
    background-color: {status_bar_color};
    color: #ffffff;
    border-top: 1px solid {status_bar_border};
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QScrollBar:vertical {{
    background-color: #0d0d0d;
    width: 14px;
    border-radius: 7px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #2a2a2a;
    border-radius: 7px;
    min-height: 30px;
    border: 2px solid #0d0d0d;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #3a3a3a;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: #0d0d0d;
    height: 14px;
    border-radius: 7px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #2a2a2a;
    border-radius: 7px;
    min-width: 30px;
    border: 2px solid #0d0d0d;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #3a3a3a;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QComboBox {{
    background-color: #1a1a1a;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QComboBox:hover {{
    border-color: {focus_color};
    background-color: #1f1f1f;
}}

QComboBox:focus {{
    border: 2px solid {focus_color};
    background-color: #1f1f1f;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iI2Q0ZDRkNCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
    width: 12px;
    height: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    selection-background-color: {selection_color};
    selection-color: #ffffff;
}}

QSplitter::handle {{
    background-color: #1a1a1a;
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Message Boxes and Dialogs */
QMessageBox {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMessageBox QLabel {{
    color: #f0f0f0;
    min-width: 300px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

/* Tooltips */
QToolTip {{
    background-color: #0d0d0d;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
    padding: 4px 8px;
    border-radius: 4px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

""".format(
        base_color=base_color,
        border_color=border_color,
        hover_color=hover_color,
        focus_color=focus_color,
        pressed_color=pressed_color,
        selection_color=selection_color,
        status_bar_color=status_bar_color,
        status_bar_border=status_bar_border
    )

def _get_light_theme(accent_color: str = "#0078d4") -> str:
    """Get a default light theme with custom accent color."""
    # Generate color variations
    base_color = accent_color
    hover_color = _lighten_color(base_color, 0.1)
    pressed_color = _darken_color(base_color, 0.2)
    border_color = _darken_color(base_color, 0.2)
    status_bar_color = base_color
    status_bar_border = _darken_color(base_color, 0.3)
    focus_color = base_color
    selection_color = base_color
    
    return """
/* Light Theme - Clean, Bright Colors */
QWidget {{
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
}}

QMainWindow {{
    background-color: #ffffff;
}}

QDialog {{
    background-color: #ffffff;
    color: #1a1a1a;
}}

QPushButton {{
    background-color: {base_color};
    color: #ffffff;
    border: 1px solid {border_color};
    border-radius: 4px;
    padding: 6px 14px;
    min-width: 80px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: 500;
    font-size: 9pt;
}}

QPushButton:hover {{
    background-color: {hover_color};
    border-color: {border_color};
}}

QPushButton:pressed {{
    background-color: {pressed_color};
    border-color: {pressed_color};
}}

QPushButton:disabled {{
    background-color: #e5e5e5;
    color: #999999;
    border-color: #cccccc;
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    selection-background-color: {selection_color};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {focus_color};
    background-color: #ffffff;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #f5f5f5;
    color: #999999;
    border-color: #e5e5e5;
}}

QCheckBox {{
    color: #1a1a1a;
    spacing: 8px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid #cccccc;
    border-radius: 4px;
    background-color: #ffffff;
}}

QCheckBox::indicator:hover {{
    border-color: {focus_color};
    background-color: #f5f5f5;
}}

QCheckBox::indicator:checked {{
    background-color: {base_color};
    border-color: {base_color};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzLjMzMzMgNEw2IDEyTDIuNjY2NjcgOC42NjY2NyIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
}}

QCheckBox::indicator:disabled {{
    background-color: #f5f5f5;
    border-color: #e5e5e5;
}}

QListWidget {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 4px;
    alternate-background-color: #f9f9f9;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid #e5e5e5;
    color: #1a1a1a;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QListWidget::item:hover {{
    background-color: #f5f5f5;
    color: #000000;
}}

QListWidget::item:selected {{
    background-color: {selection_color};
    color: #ffffff;
}}

QGroupBox {{
    border: 1px solid #cccccc;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
    color: #1a1a1a;
    font-size: 10pt;
    background-color: #ffffff;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
}}

QGroupBox QLabel {{
    color: #1a1a1a;
}}

QGroupBox QLabel[class="zone-title"] {{
    color: #000000;
    font-weight: bold;
}}

QGroupBox QLabel[class="zone-count"] {{
    color: #666666;
}}

QLabel {{
    color: #1a1a1a;
    background-color: transparent;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QLabel[class="heading"] {{
    color: #000000;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
    font-weight: bold;
    font-size: 11pt;
}}

QMenuBar {{
    background-color: #ffffff;
    color: #1a1a1a;
    border-bottom: 1px solid #e5e5e5;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

QMenuBar::item:selected {{
    background-color: #f5f5f5;
    color: #000000;
}}

QMenu {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 4px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMenu::item {{
    padding: 6px 24px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
    color: #1a1a1a;
}}

QMenu::item:selected {{
    background-color: {selection_color};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: #e5e5e5;
    margin: 4px 0;
}}

QStatusBar {{
    background-color: {status_bar_color};
    color: #ffffff;
    border-top: 1px solid {status_bar_border};
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QScrollBar:vertical {{
    background-color: #ffffff;
    width: 14px;
    border-radius: 7px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #cccccc;
    border-radius: 7px;
    min-height: 30px;
    border: 2px solid #ffffff;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #999999;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: #ffffff;
    height: 14px;
    border-radius: 7px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #cccccc;
    border-radius: 7px;
    min-width: 30px;
    border: 2px solid #ffffff;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #999999;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QComboBox {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QComboBox:hover {{
    border-color: {focus_color};
    background-color: #ffffff;
}}

QComboBox:focus {{
    border: 2px solid {focus_color};
    background-color: #ffffff;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iIzFhMWExYSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
    width: 12px;
    height: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    selection-background-color: {selection_color};
    selection-color: #ffffff;
}}

QSplitter::handle {{
    background-color: #e5e5e5;
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Message Boxes and Dialogs */
QMessageBox {{
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMessageBox QLabel {{
    color: #1a1a1a;
    min-width: 300px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    font-family: "Segoe UI", "Fira Sans", Arial, sans-serif;
}}

/* Tooltips */
QToolTip {{
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    padding: 4px 8px;
    border-radius: 4px;
    font-family: "Fira Sans", "Segoe UI", Arial, sans-serif;
}}

""".format(
        base_color=base_color,
        border_color=border_color,
        hover_color=hover_color,
        focus_color=focus_color,
        pressed_color=pressed_color,
        selection_color=selection_color,
        status_bar_color=status_bar_color,
        status_bar_border=status_bar_border
    )


if __name__ == "__main__":
    main()
