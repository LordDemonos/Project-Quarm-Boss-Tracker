"""System tray icon and window management."""
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class SystemTray(QObject):
    """Manages the system tray icon and window visibility."""
    
    # Signals
    show_window_clicked = pyqtSignal()
    options_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()
    discord_sync_clicked = pyqtSignal()
    exit_clicked = pyqtSignal()
    
    def __init__(self, icon_path: Optional[str] = None):
        """
        Initialize the system tray.
        
        Args:
            icon_path: Path to tray icon file
        """
        super().__init__()
        self.tray_icon = QSystemTrayIcon()
        
        if icon_path:
            try:
                icon = QIcon(icon_path)
                # Verify icon is valid (not null)
                if icon.isNull():
                    logger.warning(f"Tray icon file found but QIcon is null: {icon_path}, using default")
                    icon = QApplication.style().standardIcon(
                        QApplication.style().StandardPixmap.SP_ComputerIcon
                    )
                else:
                    logger.debug(f"Loaded tray icon from: {icon_path}")
                self.tray_icon.setIcon(icon)
            except Exception as e:
                logger.error(f"Error loading tray icon from {icon_path}: {e}", exc_info=True)
                # Fallback to default icon
                self.tray_icon.setIcon(QApplication.style().standardIcon(
                    QApplication.style().StandardPixmap.SP_ComputerIcon
                ))
                logger.debug("Using default system tray icon due to error")
        else:
            # Use default icon
            self.tray_icon.setIcon(QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_ComputerIcon
            ))
            logger.debug("Using default system tray icon (no icon path provided)")
        
        self.tray_icon.setToolTip("Project Quarm Boss Tracker")
        
        # Create context menu
        self.menu = QMenu()
        
        show_window_action = QAction("Show Window", self)
        show_window_action.triggered.connect(self.show_window_clicked.emit)
        self.menu.addAction(show_window_action)
        
        self.menu.addSeparator()
        
        options_action = QAction("Settings", self)
        options_action.triggered.connect(self.options_clicked.emit)
        self.menu.addAction(options_action)
        
        self.menu.addSeparator()
        
        # Quick actions - commonly used operations
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_clicked.emit)
        self.menu.addAction(refresh_action)
        
        discord_sync_action = QAction("Sync from Discord", self)
        discord_sync_action.triggered.connect(self.discord_sync_clicked.emit)
        self.menu.addAction(discord_sync_action)
        
        self.menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_clicked.emit)
        self.menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        logger.info("System tray initialized")
    
    def show(self) -> None:
        """Show the system tray icon."""
        self.tray_icon.show()
        logger.debug("System tray icon shown")
    
    def hide(self) -> None:
        """Hide the system tray icon."""
        self.tray_icon.hide()
        logger.debug("System tray icon hidden")
    
    def set_tooltip(self, text: str) -> None:
        """Update the tooltip text."""
        self.tray_icon.setToolTip(text)
        logger.debug(f"Tray tooltip updated: {text}")
    
    def show_notification(self, title: str, message: str) -> None:
        """
        Show a system notification (cross-platform).
        
        On Windows: Uses Windows notification system
        On macOS: Uses macOS notification system
        On Linux: Uses desktop environment's notification system (e.g., libnotify)
        
        Args:
            title: Notification title
            message: Notification message
        """
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.error("[NOTIFICATION] System tray is not available - cannot show notification")
            return
        
        # Check if tray icon is visible
        if not self.tray_icon.isVisible():
            logger.warning("[NOTIFICATION] Tray icon is not visible - notification may not display")
        
        logger.info(f"[NOTIFICATION] Attempting to show notification: {title} - {message[:100]}...")
        
        try:
            # Use NoIcon so the notification uses our tray/app icon instead of the generic blue "i"
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.NoIcon,
                10000  # Show for 10 seconds
            )
            logger.info(f"[NOTIFICATION] Notification showMessage() called successfully")
        except Exception as e:
            logger.error(f"[NOTIFICATION] Error showing notification: {e}", exc_info=True)
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - do nothing
            pass
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double click - show window
            logger.debug("Tray icon double-clicked, showing window")
            self.show_window_clicked.emit()
