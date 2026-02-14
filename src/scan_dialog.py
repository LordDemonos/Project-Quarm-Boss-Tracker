"""Dialog for selecting a log file to scan."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from pathlib import Path

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class ScanDialog(QDialog):
    """Dialog for selecting a log file to scan for boss kills."""
    
    def __init__(self, parent=None):
        """
        Initialize the scan dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Scan Log File")
        self.setModal(True)
        self.setMinimumWidth(600)
        
        self.selected_file_path: str = ""
        
        logger.info("Opening scan dialog")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Description
        info_label = QLabel(
            "Scan a log file to find boss kills and update kill times. "
            "The scan will:\n"
            "• Find all boss kills in the log file\n"
            "• Add any new bosses found (disabled by default)\n"
            "• Update last kill times for existing bosses (most recent kill within the last week)\n"
            "• Scan the entire file to discover old bosses to add"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # File selection group
        file_group_layout = QVBoxLayout()
        file_group_layout.setSpacing(10)
        
        file_label = QLabel("Log File:")
        file_group_layout.addWidget(file_label)
        
        # File path display and browse button
        file_path_layout = QHBoxLayout()
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("No file selected")
        file_path_layout.addWidget(self.file_path_edit)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_file)
        file_path_layout.addWidget(browse_button)
        
        file_group_layout.addLayout(file_path_layout)
        layout.addLayout(file_group_layout)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self._on_ok)
        self.ok_button.setEnabled(False)  # Disabled until file is selected
        button_layout.addWidget(self.ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _browse_file(self) -> None:
        """Open file dialog to select log file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File to Scan",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            self.selected_file_path = file_path
            self.ok_button.setEnabled(True)
            logger.debug(f"Selected log file: {file_path}")
    
    def _on_ok(self) -> None:
        """Handle OK button click."""
        if not self.selected_file_path:
            QMessageBox.warning(
                self,
                "No File Selected",
                "Please select a log file to scan."
            )
            return
        
        # Verify file exists
        if not Path(self.selected_file_path).exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The selected file does not exist:\n{self.selected_file_path}"
            )
            return
        
        self.accept()
    
    def get_file_path(self) -> str:
        """
        Get the selected file path.
        
        Returns:
            Selected file path, or empty string if cancelled
        """
        return self.selected_file_path
