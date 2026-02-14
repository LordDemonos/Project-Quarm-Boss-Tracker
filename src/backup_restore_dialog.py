"""Dialog for restoring bosses.json from backup files."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
import shutil

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class BackupRestoreDialog(QDialog):
    """Dialog for selecting and restoring a backup file."""
    
    def __init__(self, bosses_json_path: Path, parent=None):
        """
        Initialize the backup restore dialog.
        
        Args:
            bosses_json_path: Path to the bosses.json file
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Restore Backup")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        self.bosses_json_path = Path(bosses_json_path)
        self.backup_dir = self.bosses_json_path.parent / "backups"
        self.selected_backup: Optional[Path] = None
        
        logger.info(f"[BACKUP RESTORE] Initializing dialog")
        logger.info(f"[BACKUP RESTORE] Bosses JSON path: {self.bosses_json_path}")
        logger.info(f"[BACKUP RESTORE] Backup directory: {self.backup_dir}")
        
        self._setup_ui()
        self._load_backups()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Select a backup file to restore. The current bosses.json will be backed up before restoration."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Backup list
        list_group = QGroupBox("Available Backups")
        list_layout = QVBoxLayout()
        
        self.backup_list = QListWidget()
        self.backup_list.itemSelectionChanged.connect(self._on_backup_selected)
        self.backup_list.itemDoubleClicked.connect(self._on_backup_double_clicked)
        list_layout.addWidget(self.backup_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # Backup details
        details_group = QGroupBox("Backup Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.restore_btn = QPushButton("Restore Selected Backup")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self._restore_backup)
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self._load_backups)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.restore_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def _load_backups(self) -> None:
        """Load and display available backups."""
        self.backup_list.clear()
        self.details_text.clear()
        self.selected_backup = None
        self.restore_btn.setEnabled(False)
        
        if not self.backup_dir.exists():
            logger.warning(f"[BACKUP RESTORE] Backup directory does not exist: {self.backup_dir}")
            item = QListWidgetItem("No backup directory found")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Disable selection
            self.backup_list.addItem(item)
            return
        
        backups = sorted(
            self.backup_dir.glob("bosses_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not backups:
            logger.info(f"[BACKUP RESTORE] No backups found in {self.backup_dir}")
            item = QListWidgetItem("No backups found")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Disable selection
            self.backup_list.addItem(item)
            return
        
        logger.info(f"[BACKUP RESTORE] Found {len(backups)} backup(s)")
        
        for backup in backups:
            try:
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                size = backup.stat().st_size
                
                # Count bosses with notes
                bosses_with_notes = 0
                total_bosses = 0
                try:
                    with open(backup, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        bosses = data.get('bosses', [])
                        total_bosses = len(bosses)
                        bosses_with_notes = sum(1 for b in bosses if b.get('note', '').strip())
                except Exception as e:
                    logger.warning(f"[BACKUP RESTORE] Error reading backup {backup.name}: {e}")
                
                # Create display text
                display_text = f"{backup.name}\n"
                display_text += f"Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')} | "
                display_text += f"Size: {size:,} bytes | "
                display_text += f"Bosses: {total_bosses} ({bosses_with_notes} with notes)"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, backup)
                self.backup_list.addItem(item)
                
            except Exception as e:
                logger.error(f"[BACKUP RESTORE] Error processing backup {backup.name}: {e}")
                item = QListWidgetItem(f"Error: {backup.name} ({str(e)})")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.backup_list.addItem(item)
    
    def _on_backup_selected(self) -> None:
        """Handle backup selection."""
        selected_items = self.backup_list.selectedItems()
        if not selected_items:
            self.selected_backup = None
            self.restore_btn.setEnabled(False)
            self.details_text.clear()
            return
        
        item = selected_items[0]
        backup_path = item.data(Qt.ItemDataRole.UserRole)
        
        if not backup_path or not isinstance(backup_path, Path):
            self.selected_backup = None
            self.restore_btn.setEnabled(False)
            return
        
        self.selected_backup = backup_path
        self.restore_btn.setEnabled(True)
        
        # Show detailed information
        self._show_backup_details(backup_path)
    
    def _on_backup_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on backup item."""
        backup_path = item.data(Qt.ItemDataRole.UserRole)
        if backup_path and isinstance(backup_path, Path):
            self.selected_backup = backup_path
            self._restore_backup()
    
    def _show_backup_details(self, backup_path: Path) -> None:
        """Show detailed information about the selected backup."""
        try:
            mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
            size = backup_path.stat().st_size
            
            details = []
            details.append(f"File: {backup_path.name}")
            details.append(f"Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            details.append(f"Size: {size:,} bytes ({size / 1024:.2f} KB)")
            details.append("")
            
            # Load and analyze backup content
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    bosses = data.get('bosses', [])
                    
                    details.append(f"Total Bosses: {len(bosses)}")
                    
                    bosses_with_notes = sum(1 for b in bosses if b.get('note', '').strip())
                    details.append(f"Bosses with Notes: {bosses_with_notes}")
                    
                    bosses_with_kills = sum(1 for b in bosses if b.get('kill_count', 0) > 0)
                    details.append(f"Bosses with Kill Data: {bosses_with_kills}")
                    
                    bosses_with_respawn = sum(1 for b in bosses if b.get('respawn_hours') is not None)
                    details.append(f"Bosses with Respawn Times: {bosses_with_respawn}")
                    
            except Exception as e:
                details.append(f"Error reading backup content: {e}")
            
            self.details_text.setText("\n".join(details))
            
        except Exception as e:
            logger.error(f"[BACKUP RESTORE] Error showing backup details: {e}")
            self.details_text.setText(f"Error loading details: {e}")
    
    def _restore_backup(self) -> None:
        """Restore the selected backup."""
        if not self.selected_backup or not self.selected_backup.exists():
            QMessageBox.warning(
                self,
                "Invalid Backup",
                "Selected backup file does not exist."
            )
            return
        
        # Confirm restoration
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Are you sure you want to restore from:\n\n{self.selected_backup.name}\n\n"
            f"The current bosses.json will be backed up before restoration.\n\n"
            f"⚠️ WARNING: This will replace your current boss data!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Create backup of current file before restoring
            if self.bosses_json_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_backup = self.bosses_json_path.parent / f"bosses_backup_BEFORE_RESTORE_{timestamp}.json"
                shutil.copy2(self.bosses_json_path, current_backup)
                logger.info(f"[BACKUP RESTORE] Created backup of current file: {current_backup.name}")
            
            # Restore from backup
            shutil.copy2(self.selected_backup, self.bosses_json_path)
            logger.info(f"[BACKUP RESTORE] Successfully restored from: {self.selected_backup.name}")
            
            # Show success message with summary
            try:
                with open(self.bosses_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    bosses = data.get('bosses', [])
                    bosses_with_notes = sum(1 for b in bosses if b.get('note', '').strip())
                    
                    QMessageBox.information(
                        self,
                        "Restore Successful",
                        f"✓ Successfully restored from backup!\n\n"
                        f"File: {self.selected_backup.name}\n"
                        f"Total bosses: {len(bosses)}\n"
                        f"Bosses with notes: {bosses_with_notes}\n\n"
                        f"⚠️ Please restart the application for changes to take effect."
                    )
            except Exception as e:
                QMessageBox.information(
                    self,
                    "Restore Successful",
                    f"✓ Successfully restored from backup!\n\n"
                    f"File: {self.selected_backup.name}\n\n"
                    f"⚠️ Please restart the application for changes to take effect.\n\n"
                    f"Note: Could not read restored file details: {e}"
                )
            
            self.accept()
            
        except Exception as e:
            logger.error(f"[BACKUP RESTORE] Error restoring backup: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"Failed to restore backup:\n\n{str(e)}\n\n"
                f"Please check the logs for more details."
            )
