"""Dialog for removing a target."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Optional, Tuple

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class RemoveBossDialog(QDialog):
    """Dialog for removing a target from the database."""
    
    def __init__(self, bosses: List[Dict], parent=None):
        """
        Initialize the remove boss dialog.
        
        Args:
            bosses: List of boss dictionaries
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Remove Target")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.bosses = bosses
        self.selected_boss: Optional[Dict] = None
        
        logger.debug(f"Showing remove boss dialog with {len(bosses)} bosses")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        info_label = QLabel(
            "Select a target to remove from tracking. This action cannot be undone."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Boss selection group
        boss_group = QGroupBox("Select Target")
        boss_layout = QVBoxLayout()
        
        boss_label = QLabel("Target:")
        boss_layout.addWidget(boss_label)
        
        self.boss_combo = QComboBox()
        
        # Group bosses by zone for better organization
        bosses_by_zone: Dict[str, List[Dict]] = {}
        for boss in self.bosses:
            zone = boss.get('location', 'Unknown')
            if zone not in bosses_by_zone:
                bosses_by_zone[zone] = []
            bosses_by_zone[zone].append(boss)
        
        # Sort zones alphabetically
        for zone in sorted(bosses_by_zone.keys(), key=str.lower):
            # Sort bosses within zone by name, then by note
            zone_bosses = sorted(bosses_by_zone[zone], key=lambda b: (b['name'].lower(), b.get('note', '').lower()))
            
            for boss in zone_bosses:
                boss_name = boss['name']
                note = boss.get('note', '').strip()
                
                # Build display text
                if note:
                    display_text = f"{boss_name} ({note}) - {zone}"
                else:
                    display_text = f"{boss_name} - {zone}"
                
                self.boss_combo.addItem(display_text, boss)
        
        if self.boss_combo.count() == 0:
            # No bosses to remove
            no_bosses_label = QLabel("No targets available to remove.")
            no_bosses_label.setStyleSheet("color: #999999; font-style: italic;")
            boss_layout.addWidget(no_bosses_label)
            self.boss_combo.setEnabled(False)
        else:
            boss_layout.addWidget(self.boss_combo)
        
        boss_group.setLayout(boss_layout)
        layout.addWidget(boss_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        remove_btn = QPushButton("Remove Target")
        remove_btn.setDefault(True)
        remove_btn.clicked.connect(self._on_remove)
        remove_btn.setEnabled(self.boss_combo.count() > 0)
        buttons_layout.addWidget(remove_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def _on_remove(self) -> None:
        """Handle remove button click."""
        if self.boss_combo.count() == 0:
            QMessageBox.warning(self, "No Targets", "No targets available to remove.")
            return
        
        index = self.boss_combo.currentIndex()
        if index < 0:
            return
        
        boss = self.boss_combo.itemData(index)
        if not boss:
            return
        
        self.selected_boss = boss
        boss_name = boss.get('name', 'Unknown')
        note = boss.get('note', '').strip()
        location = boss.get('location', 'Unknown')
        
        # Build confirmation message
        if note:
            display_name = f"{boss_name} ({note})"
        else:
            display_name = boss_name
        
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{display_name}' from {location}?\n\nThis will permanently delete this target and all its tracking data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"User confirmed removal of boss: {display_name} from {location}")
            self.accept()
        else:
            logger.debug("User cancelled removal")
    
    def get_selected_boss(self) -> Optional[Dict]:
        """
        Get the selected boss after dialog closes.
        
        Returns:
            Selected boss dictionary, or None if cancelled
        """
        if self.result() == QDialog.DialogCode.Accepted and self.selected_boss:
            return self.selected_boss
        return None
