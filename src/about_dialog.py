"""About dialog showing application information."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from pathlib import Path
from datetime import datetime
import sys

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


def _get_version() -> str:
    """Get application version from version.txt."""
    try:
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_dir = Path(sys.executable).parent
        else:
            # Running as script
            base_dir = Path(__file__).parent.parent
        
        version_file = base_dir / "version.txt"
        if version_file.exists():
            version = version_file.read_text(encoding="utf-8").strip()
            return version
    except Exception as e:
        logger.warning(f"Could not read version file: {e}")
    return "Unknown"


def _get_release_date() -> str:
    """Get release date from version.txt modification time or use default."""
    try:
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent.parent
        
        version_file = base_dir / "version.txt"
        if version_file.exists():
            # Use file modification time as release date
            mtime = version_file.stat().st_mtime
            release_date = datetime.fromtimestamp(mtime)
            return release_date.strftime("%B %d, %Y")
    except Exception as e:
        logger.warning(f"Could not get release date: {e}")
    # Default fallback
    return "February 8, 2026"


class AboutDialog(QDialog):
    """About dialog showing application information."""
    
    def __init__(self, parent=None):
        """Initialize the about dialog."""
        super().__init__(parent)
        self.setWindowTitle("About Project Quarm Boss Tracker")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)
        
        logger.debug("Showing about dialog")
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Application title
        title_label = QLabel("Project Quarm Boss Tracker")
        title_label.setProperty("class", "heading")
        title_font = title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version = _get_version()
        version_label = QLabel(f"Version {version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = version_label.font()
        version_font.setPointSize(10)
        version_label.setFont(version_font)
        layout.addWidget(version_label)
        
        # Release date
        release_date = _get_release_date()
        date_label = QLabel(f"Released: {release_date}")
        date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_label)
        
        # Spacer
        layout.addSpacing(10)
        
        # Description
        description = QLabel(
            "A desktop application that monitors EverQuest (TAKP) log files\n"
            "and sends Discord notifications when tracked bosses are killed."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Spacer
        layout.addSpacing(10)
        
        # GitHub link
        github_layout = QHBoxLayout()
        github_layout.addStretch()
        github_label = QLabel("GitHub:")
        github_layout.addWidget(github_label)
        
        github_link = QLabel('<a href="https://github.com/LordDemonos/Project-Quarm-Boss-Tracker">https://github.com/LordDemonos/Project-Quarm-Boss-Tracker</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_layout.addWidget(github_link)
        github_layout.addStretch()
        layout.addLayout(github_layout)
        
        # Author
        author_label = QLabel("Author: LordDemonos")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_label)
        
        # License
        license_label = QLabel("License: MIT License")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)
        
        # Spacer
        layout.addStretch()
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(100)
        button_layout.addWidget(close_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
