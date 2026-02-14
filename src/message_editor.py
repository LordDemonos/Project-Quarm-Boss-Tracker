"""Message format editor window."""
import re
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class MessageEditor(QDialog):
    """Window for editing Discord message format."""
    
    def __init__(self, parent=None):
        """Initialize the message editor."""
        super().__init__(parent)
        self.setWindowTitle("Message Format Editor")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.template = ""
        self.lockout_template = ""
        self.on_save: Optional[Callable] = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Info label with Discord timestamp variables
        info_text = (
            "Available variables:\n"
            "• {timestamp} - Original log timestamp\n"
            "• {discord_timestamp} - Discord timestamp (full date/time, auto-adjusts to viewer timezone)\n"
            "• {discord_timestamp_relative} - Discord relative timestamp (e.g., '2 minutes ago')\n"
            "• {monster} - Boss/target name\n"
            "• {note} - Boss note/nickname (only shown if note exists, e.g., 'F1 North')\n"
            "• {player} - Player name\n"
            "• {guild} - Guild name\n"
            "• {location} - Zone/location\n"
            "• {server} - Server name"
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Regular message template editor (smaller)
        editor_group = QGroupBox("Message Template")
        editor_layout = QVBoxLayout()
        
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText(
            "Example: {discord_timestamp} {monster} ({note}) was killed by {player} of <{guild}> in {location}!"
        )
        self.template_edit.setMaximumHeight(80)  # Reduced height
        editor_layout.addWidget(self.template_edit)
        
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)
        
        # Lockout message template editor
        lockout_group = QGroupBox("Lockout Message Template")
        lockout_layout = QVBoxLayout()
        
        lockout_info = QLabel("Used for bosses detected via lockout messages (no location available)")
        lockout_info.setWordWrap(True)
        lockout_info.setStyleSheet("color: #999999; font-style: italic;")
        lockout_layout.addWidget(lockout_info)
        
        self.lockout_template_edit = QTextEdit()
        self.lockout_template_edit.setPlaceholderText(
            "Example: {discord_timestamp} {monster} lockout detected!"
        )
        self.lockout_template_edit.setMaximumHeight(80)  # Same reduced height
        lockout_layout.addWidget(self.lockout_template_edit)
        
        lockout_group.setLayout(lockout_layout)
        layout.addWidget(lockout_group)
        
        # Preview group
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.preview_label)
        
        self.lockout_preview_label = QLabel()
        self.lockout_preview_label.setWordWrap(True)
        self.lockout_preview_label.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.lockout_preview_label)
        
        preview_btn = QPushButton("Update Preview")
        preview_btn.clicked.connect(self._update_preview)
        preview_layout.addWidget(preview_btn)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def set_template(self, template: str, lockout_template: Optional[str] = None) -> None:
        """Set the message templates."""
        self.template = template
        self.template_edit.setPlainText(template)
        if lockout_template is not None:
            self.lockout_template = lockout_template
            self.lockout_template_edit.setPlainText(lockout_template)
        self._update_preview()
    
    def _update_preview(self) -> None:
        """Update the preview with sample data. Always reads current editor content."""
        template = self.template_edit.toPlainText().strip()
        lockout_template = self.lockout_template_edit.toPlainText().strip()
        
        # Regular message sample data
        sample_data = {
            'timestamp': 'Sat Nov 22 23:02:42 2025',
            'discord_timestamp': '<t:1732312962:F>',  # Example Discord timestamp
            'discord_timestamp_relative': '<t:1732312962:R>',
            'monster': 'Severilous',
            'note': '',  # No note for this example
            'player': 'Saelilya',
            'guild': 'Former Glory',
            'location': 'The Emerald Jungle',
            'server': 'Druzzil Ro'
        }
        
        # Also show example with note
        sample_data_with_note = {
            'timestamp': 'Sat Nov 22 23:02:42 2025',
            'discord_timestamp': '<t:1732312962:F>',
            'discord_timestamp_relative': '<t:1732312962:R>',
            'monster': 'Thall Va Xakra',
            'note': 'F1 North',  # Example note
            'player': 'Saelilya',
            'guild': 'Former Glory',
            'location': 'Vex Thal',
            'server': 'Druzzil Ro'
        }
        
        # Lockout message sample data (no location, player, guild)
        lockout_sample_data = {
            'timestamp': 'Mon Jan 12 22:01:42 2026',
            'discord_timestamp': '<t:1732312962:F>',
            'discord_timestamp_relative': '<t:1732312962:R>',
            'monster': 'Emperor Ssraeshza',
            'note': '',  # No note for lockout example
            'player': '',
            'guild': '',
            'location': '',
            'server': ''
        }
        lockout_sample_data_with_note = {
            'timestamp': 'Mon Jan 12 22:01:42 2026',
            'discord_timestamp': '<t:1732312962:F>',
            'discord_timestamp_relative': '<t:1732312962:R>',
            'monster': 'Kaas Thox Xi Aten Ha Ra',
            'note': 'South Blob',  # So template ({note}) shows parentheses in preview
            'player': '',
            'guild': '',
            'location': '',
            'server': ''
        }
        
        # Update regular preview
        try:
            if template:
                # Show two previews: one without note, one with note
                preview_no_note = self._format_template_with_note(template, sample_data)
                preview_with_note = self._format_template_with_note(template, sample_data_with_note)
                
                preview_text = f"Regular (no note): {preview_no_note}\nRegular (with note): {preview_with_note}"
                self.preview_label.setText(preview_text)
            else:
                self.preview_label.setText("Regular: (empty)")
            logger.debug("Regular preview updated successfully")
        except KeyError as e:
            error_msg = f"Regular Error: Unknown variable {e}"
            self.preview_label.setText(error_msg)
            logger.warning(f"Regular preview error - unknown variable: {e}")
        except Exception as e:
            error_msg = f"Regular Error: {e}"
            self.preview_label.setText(error_msg)
            logger.error(f"Regular preview error: {e}")
        
        # Update lockout preview (with and without note so ({note}) is visible when used)
        try:
            if lockout_template:
                preview_no_note = self._format_template_with_note(lockout_template, lockout_sample_data)
                preview_with_note = self._format_template_with_note(lockout_template, lockout_sample_data_with_note)
                self.lockout_preview_label.setText(f"Lockout (no note): {preview_no_note}\nLockout (with note): {preview_with_note}")
            else:
                self.lockout_preview_label.setText("Lockout: (empty)")
            logger.debug("Lockout preview updated successfully")
        except KeyError as e:
            error_msg = f"Lockout Error: Unknown variable {e}"
            self.lockout_preview_label.setText(error_msg)
            logger.warning(f"Lockout preview error - unknown variable: {e}")
        except Exception as e:
            error_msg = f"Lockout Error: {e}"
            self.lockout_preview_label.setText(error_msg)
            logger.error(f"Lockout preview error: {e}")
        # Force UI to refresh so preview reflects current template text immediately
        self.preview_label.update()
        self.lockout_preview_label.update()
        QApplication.processEvents()
    
    def _format_template_with_note(self, template: str, data: dict) -> str:
        """
        Format template, handling {note} variable - removes it if note is empty.
        
        Args:
            template: Message template string
            data: Dictionary with template variables including 'note'
            
        Returns:
            Formatted message string
        """
        note = data.get('note', '').strip()
        
        if not note:
            # Remove {note} and clean up surrounding spaces/punctuation
            # Handle patterns like " ({note})", " {note}", "{note} ", etc.
            # Remove {note} and any surrounding parentheses and spaces
            template = re.sub(r'\s*\(?\s*\{note\}\s*\)?\s*', ' ', template)
            # Clean up multiple spaces
            template = re.sub(r'\s+', ' ', template).strip()
            # Remove note from data so format() doesn't try to use it
            data = {k: v for k, v in data.items() if k != 'note'}
        
        return template.format(**data)
    
    def _save(self) -> None:
        """Save the templates."""
        template = self.template_edit.toPlainText().strip()
        lockout_template = self.lockout_template_edit.toPlainText().strip()
        
        if not template:
            logger.warning("Attempted to save empty template")
            QMessageBox.warning(self, "Empty Template", "Regular message template cannot be empty.")
            return
        
        if not lockout_template:
            logger.warning("Attempted to save empty lockout template")
            QMessageBox.warning(self, "Empty Template", "Lockout message template cannot be empty.")
            return
        
        # Validate regular template with sample data
        sample_data = {
            'timestamp': 'test',
            'discord_timestamp': '<t:1234567890:F>',
            'discord_timestamp_relative': '<t:1234567890:R>',
            'monster': 'test',
            'note': '',  # Empty note for validation
            'player': 'test',
            'guild': 'test',
            'location': 'test',
            'server': 'test'
        }
        
        try:
            # Use the note-aware formatter for validation
            self._format_template_with_note(template, sample_data)
            logger.debug("Regular template validation successful")
        except KeyError as e:
            logger.error(f"Regular template validation failed - unknown variable: {e}")
            QMessageBox.warning(
                self,
                "Invalid Template",
                f"Unknown variable in regular template: {e}"
            )
            return
        except Exception as e:
            logger.error(f"Regular template validation failed: {e}")
            QMessageBox.warning(self, "Invalid Template", f"Regular template error: {e}")
            return
        
        # Validate lockout template (no location, player, guild)
        lockout_sample_data = {
            'timestamp': 'test',
            'discord_timestamp': '<t:1234567890:F>',
            'discord_timestamp_relative': '<t:1234567890:R>',
            'monster': 'test',
            'note': '',  # Empty note for validation
            'player': '',
            'guild': '',
            'location': '',
            'server': ''
        }
        
        try:
            # Use the note-aware formatter for validation
            self._format_template_with_note(lockout_template, lockout_sample_data)
            logger.debug("Lockout template validation successful")
        except KeyError as e:
            logger.error(f"Lockout template validation failed - unknown variable: {e}")
            QMessageBox.warning(
                self,
                "Invalid Template",
                f"Unknown variable in lockout template: {e}"
            )
            return
        except Exception as e:
            logger.error(f"Lockout template validation failed: {e}")
            QMessageBox.warning(self, "Invalid Template", f"Lockout template error: {e}")
            return
        
        logger.info("Saving message templates")
        if self.on_save:
            self.on_save(template, lockout_template)
        
        self.accept()

