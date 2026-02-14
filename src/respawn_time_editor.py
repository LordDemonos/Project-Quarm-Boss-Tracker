"""Dialog for editing respawn times for bosses."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QMessageBox, QGroupBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import List, Dict, Optional

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class RespawnTimeEditor(QDialog):
    """Dialog for editing respawn times for bosses."""
    
    def __init__(self, bosses: List[Dict], parent=None, initial_boss: Optional[Dict] = None):
        """
        Initialize the respawn time editor dialog.

        Args:
            bosses: List of boss dictionaries
            parent: Parent widget
            initial_boss: If set, preselect this boss in the dropdown (match by name, location, note)
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Bosses")
        self.setModal(True)
        self.setMinimumWidth(500)

        self.bosses = bosses
        self.initial_boss = initial_boss
        self.selected_boss: Optional[Dict] = None  # Store full boss dict, not just name

        logger.info(f"Opening respawn time editor with {len(bosses)} bosses")
        self._setup_ui()

        if initial_boss:
            self._select_boss(initial_boss)
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Instructions
        info_label = QLabel(
            "Select a target and set its respawn time and note. Leave days/hours at 0 to remove respawn time."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Boss selection group
        boss_group = QGroupBox("Select Target")
        boss_layout = QVBoxLayout()
        
        boss_label = QLabel("Target:")
        boss_layout.addWidget(boss_label)
        
        self.boss_combo = QComboBox()
        # Sort bosses alphabetically, then by note if duplicates exist
        sorted_bosses = sorted(self.bosses, key=lambda b: (b['name'].lower(), b.get('note', '').lower()))
        for boss in sorted_bosses:
            boss_name = boss['name']
            location = boss.get('location', 'Unknown')
            note = boss.get('note', '').strip()
            
            # Build display text: include note if present to distinguish duplicates
            if note:
                display_text = f"{boss_name} ({note}) - {location}"
            else:
                display_text = f"{boss_name} ({location})"
            
            # Store the full boss dict as itemData so we can identify the specific entry
            self.boss_combo.addItem(display_text, boss)
        
        self.boss_combo.currentIndexChanged.connect(self._on_boss_selected)
        boss_layout.addWidget(self.boss_combo)
        
        boss_group.setLayout(boss_layout)
        layout.addWidget(boss_group)
        
        # Respawn time group
        respawn_group = QGroupBox("Respawn Time")
        respawn_layout = QVBoxLayout()
        
        # Days
        days_layout = QHBoxLayout()
        days_label = QLabel("Days:")
        days_label.setMinimumWidth(80)
        days_layout.addWidget(days_label)
        
        self.days_spin = QSpinBox()
        self.days_spin.setMinimum(0)
        self.days_spin.setMaximum(365)
        self.days_spin.setSingleStep(2)  # Increment by 2 days at a time
        self.days_spin.setValue(0)
        days_layout.addWidget(self.days_spin)
        days_layout.addStretch()
        respawn_layout.addLayout(days_layout)
        
        # Hours
        hours_layout = QHBoxLayout()
        hours_label = QLabel("Hours:")
        hours_label.setMinimumWidth(80)
        hours_layout.addWidget(hours_label)
        
        self.hours_spin = QSpinBox()
        self.hours_spin.setMinimum(0)
        self.hours_spin.setMaximum(23)
        self.hours_spin.setSingleStep(6)  # Increment by 6 hours at a time
        self.hours_spin.setValue(0)
        hours_layout.addWidget(self.hours_spin)
        hours_layout.addStretch()
        respawn_layout.addLayout(hours_layout)
        
        # Current respawn time display
        self.current_time_label = QLabel("Current respawn time: Not set")
        self.current_time_label.setStyleSheet("color: #999999; font-style: italic;")
        respawn_layout.addWidget(self.current_time_label)
        
        respawn_group.setLayout(respawn_layout)
        layout.addWidget(respawn_group)
        
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
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        buttons_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # Load initial boss data if available
        if self.boss_combo.count() > 0:
            self._on_boss_selected(0)

    def _select_boss(self, boss: Dict) -> None:
        """Select the given boss in the combo (match by name, location, note)."""
        name = (boss.get('name') or '').lower()
        location = (boss.get('location') or '').lower()
        note = (boss.get('note') or '').strip().lower()
        for i in range(self.boss_combo.count()):
            b = self.boss_combo.itemData(i)
            if not isinstance(b, dict):
                continue
            if (b.get('name') or '').lower() == name and (b.get('location') or '').lower() == location and (b.get('note') or '').strip().lower() == note:
                self.boss_combo.setCurrentIndex(i)
                return

    def _on_boss_selected(self, index: int) -> None:
        """Handle boss selection change."""
        if index < 0:
            return
        
        # Get the boss dict directly from itemData
        boss = self.boss_combo.itemData(index)
        if not boss or not isinstance(boss, dict):
            return
        
        self.selected_boss = boss
        
        # Load current respawn time
        respawn_hours = boss.get('respawn_hours')
        if respawn_hours is not None:
            days = int(respawn_hours // 24)
            hours = int(respawn_hours % 24)
            self.days_spin.setValue(days)
            self.hours_spin.setValue(hours)
            self.current_time_label.setText(f"Current respawn time: {days} day(s), {hours} hour(s)")
        else:
            self.days_spin.setValue(0)
            self.hours_spin.setValue(0)
            self.current_time_label.setText("Current respawn time: Not set")
        
        # Load current note
        note = boss.get('note', '')
        self.note_input.setText(note)
    
    def _on_save(self) -> None:
        """Handle save button click."""
        if not self.selected_boss:
            QMessageBox.warning(self, "No Target Selected", "Please select a target.")
            return
        
        days = self.days_spin.value()
        hours = self.hours_spin.value()
        
        # Calculate total hours
        total_hours = (days * 24) + hours
        
        # If both are 0, remove respawn time
        if total_hours == 0:
            respawn_hours = None
        else:
            respawn_hours = float(total_hours)
        
        # Emit signal with the data (parent will handle saving)
        self.accept()
    
    def get_selected_boss_and_respawn(self):
        """Get the selected boss dict, respawn time, and note after dialog closes."""
        if self.result() == QDialog.DialogCode.Accepted:
            days = self.days_spin.value()
            hours = self.hours_spin.value()
            total_hours = (days * 24) + hours
            respawn_hours = None if total_hours == 0 else float(total_hours)
            note = self.note_input.text().strip()
            return self.selected_boss, respawn_hours, note if note else None
        return None, None, None
