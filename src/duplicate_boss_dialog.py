"""Dialog for selecting which duplicate boss was killed."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QGroupBox
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Optional

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class DuplicateBossDialog(QDialog):
    """Dialog shown when multiple bosses with the same name exist."""
    
    def __init__(self, boss_name: str, duplicate_bosses: List[Dict], parent=None):
        """
        Initialize the duplicate boss selection dialog.
        
        Args:
            boss_name: Name of the boss that was killed (appears in multiple entries)
            duplicate_bosses: List of boss dictionaries with the same name
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Target")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)
        
        self.boss_name = boss_name
        self.duplicate_bosses = duplicate_bosses
        self.selected_boss: Optional[Dict] = None
        
        logger.info(f"Showing duplicate boss dialog for '{boss_name}' with {len(duplicate_bosses)} options")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Message label
        message = QLabel(
            f"Multiple targets found with the name <b>{self.boss_name}</b>.\n\n"
            f"Please select which target was killed:"
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Radio button group for boss selection
        self.button_group = QButtonGroup(self)
        boss_group = QGroupBox("Select Target")
        boss_layout = QVBoxLayout()
        
        for i, boss in enumerate(self.duplicate_bosses):
            location = boss.get('location', 'Unknown')
            note = boss.get('note', '').strip()
            
            # Build display text
            if note:
                display_text = f"{self.boss_name} ({note}) - {location}"
            else:
                display_text = f"{self.boss_name} - {location}"
            
            radio = QRadioButton(display_text)
            radio.setChecked(i == 0)  # Select first by default
            self.button_group.addButton(radio, i)
            boss_layout.addWidget(radio)
            
            # Store boss reference
            radio.boss = boss
        
        boss_group.setLayout(boss_layout)
        layout.addWidget(boss_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)
        buttons_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def _on_ok(self) -> None:
        """Handle OK button click."""
        checked_button = self.button_group.checkedButton()
        if checked_button:
            self.selected_boss = checked_button.boss
            logger.info(f"User selected duplicate boss: {self.selected_boss.get('name')} "
                       f"({self.selected_boss.get('note', 'no note')}) in {self.selected_boss.get('location', 'Unknown')}")
            self.accept()
        else:
            logger.warning("No boss selected in duplicate boss dialog")
            self.reject()
    
    def get_selected_boss(self) -> Optional[Dict]:
        """Get the selected boss after dialog closes."""
        if self.result() == QDialog.DialogCode.Accepted and self.selected_boss:
            return self.selected_boss
        return None
