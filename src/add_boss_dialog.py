"""Dialog for manually adding a new target."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Optional, Tuple

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class AddBossDialog(QDialog):
    """Dialog for manually adding a new target."""
    
    def __init__(self, parent=None):
        """Initialize the add boss dialog."""
        super().__init__(parent)
        self.setWindowTitle("Add Target")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        logger.debug("Showing add boss dialog")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        info_label = QLabel(
            "Enter the target name and zone. You can optionally add a note to help identify the target."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Target name group
        name_group = QGroupBox("Target Information")
        name_layout = QVBoxLayout()
        
        name_label = QLabel("Target Name:")
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Aten Ha Ra")
        self.name_input.setMaxLength(100)
        name_layout.addWidget(self.name_input)
        
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # Location group
        location_group = QGroupBox("Location")
        location_layout = QVBoxLayout()
        
        location_label = QLabel("Zone/Location:")
        location_layout.addWidget(location_label)
        
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("e.g., Vex Thal")
        self.location_input.setMaxLength(100)
        location_layout.addWidget(self.location_input)
        
        location_group.setLayout(location_layout)
        layout.addWidget(location_group)
        
        # Note group
        note_group = QGroupBox("Note (Optional)")
        note_layout = QVBoxLayout()
        
        note_label = QLabel("Note/Nickname:")
        note_label.setToolTip("Add a short note to help identify this target (e.g., 'F1 North', 'Spawn Point A')")
        note_layout.addWidget(note_label)
        
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("e.g., F1 North")
        self.note_input.setMaxLength(50)
        note_layout.addWidget(self.note_input)
        
        note_group.setLayout(note_layout)
        layout.addWidget(note_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        add_btn = QPushButton("Add Target")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._on_add)
        buttons_layout.addWidget(add_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # Focus on name input
        self.name_input.setFocus()
    
    def _on_add(self) -> None:
        """Handle add button click."""
        name = self.name_input.text().strip()
        location = self.location_input.text().strip()
        note = self.note_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a target name.")
            self.name_input.setFocus()
            return
        
        # Location is optional, but we'll use empty string if not provided
        # Note is optional, so we can use None or empty string
        
        logger.info(f"User adding target: {name} in {location or 'Unknown'} with note: {note or 'None'}")
        self.accept()
    
    def get_boss_data(self) -> Tuple[str, str, Optional[str]]:
        """
        Get the boss data after dialog closes.
        
        Returns:
            Tuple of (name, location, note)
        """
        if self.result() == QDialog.DialogCode.Accepted:
            name = self.name_input.text().strip()
            location = self.location_input.text().strip()
            note = self.note_input.text().strip()
            return name, location, note if note else None
        return None, None, None
