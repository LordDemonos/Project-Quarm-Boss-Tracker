"""Non-modal dialog for new boss discovery."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional, Callable

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class NewBossDialog(QDialog):
    """Non-modal dialog shown when a new boss is discovered."""
    
    # Signals
    enabled_selected = pyqtSignal(str, str, bool)  # boss_name, location, enabled
    
    def __init__(self, boss_name: str, location: str, parent=None):
        """
        Initialize the new boss dialog.
        
        Args:
            boss_name: Name of the discovered boss
            location: Zone/location where boss was found
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("New Target Discovered")
        self.setModal(False)  # Non-modal
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self.boss_name = boss_name
        self.location = location
        
        self.on_enabled: Optional[Callable] = None
        self.on_disabled: Optional[Callable] = None
        
        logger.info(f"Showing new boss dialog: {boss_name} in {location}")
        self._setup_ui()
        
        # Ensure dialog inherits dark theme from parent application
        # The theme should be applied automatically via QSS, but we ensure it's visible
        self.setStyleSheet("")  # Clear any local styles to inherit from app stylesheet
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Message label
        message = QLabel(
            f"New target discovered:\n\n"
            f"<b>{self.boss_name}</b>\n"
            f"Location: {self.location}\n\n"
            f"Enable Discord posting for this target?"
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        yes_btn = QPushButton("Yes, Enable Posting")
        yes_btn.setDefault(True)
        yes_btn.clicked.connect(self._on_yes)
        buttons_layout.addWidget(yes_btn)
        
        no_btn = QPushButton("No, Disable Posting")
        no_btn.clicked.connect(self._on_no)
        buttons_layout.addWidget(no_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Set minimum size
        self.setMinimumWidth(400)
    
    def _on_yes(self) -> None:
        """Handle Yes button click."""
        logger.info(f"User enabled Discord posting for new boss: {self.boss_name}")
        # Only emit signal - don't call callback directly to avoid double-calling
        self.enabled_selected.emit(self.boss_name, self.location, True)
        self.accept()
    
    def _on_no(self) -> None:
        """Handle No button click."""
        logger.info(f"User disabled Discord posting for new boss: {self.boss_name}")
        # Only emit signal - don't call callback directly to avoid double-calling
        self.enabled_selected.emit(self.boss_name, self.location, False)
        self.accept()
    
    def closeEvent(self, event) -> None:
        """Handle close event - treat as No."""
        logger.debug(f"New boss dialog closed (treated as No): {self.boss_name}")
        self._on_no()
        super().closeEvent(event)
