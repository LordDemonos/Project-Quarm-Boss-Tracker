"""Dialog for Boss Capture (Debug): select a log file and save boss-kill lines from last 8 days to JSON."""
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

try:
    from .logger import get_logger
    from .message_parser import MessageParser
except ImportError:
    from logger import get_logger
    from message_parser import MessageParser

logger = get_logger(__name__)

WINDOW_DAYS = 8


def run_boss_capture(log_file_path: str) -> tuple[list[str], int]:
    """
    Read a log file and collect raw zone + lockout boss-kill lines from the last 8 days.
    
    Args:
        log_file_path: Path to the EQ log file.
        
    Returns:
        (lines, total_matching): List of raw log lines (in file order) and count.
    """
    lines = []
    path = Path(log_file_path)
    if not path.exists():
        return lines, 0
    cutoff = datetime.now() - timedelta(days=WINDOW_DAYS)
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if not line:
                    continue
                parsed = MessageParser.parse_line(line)
                if not parsed:
                    parsed = MessageParser.parse_lockout_line(line)
                if not parsed:
                    continue
                try:
                    kill_dt = datetime.strptime(parsed.timestamp, "%a %b %d %H:%M:%S %Y")
                except ValueError:
                    continue
                if kill_dt >= cutoff:
                    lines.append(line)
    except OSError as e:
        logger.warning(f"Error reading log file for capture: {e}")
        return [], 0
    return lines, len(lines)


class BossCaptureDialog(QDialog):
    """Dialog to select a log file and run Boss Capture (save last 8 days of boss-kill lines to JSON)."""
    
    def __init__(self, parent=None, default_capture_dir: Path = None):
        super().__init__(parent)
        self.setWindowTitle("Boss Capture (Debug)")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.selected_file_path = ""
        self.default_capture_dir = default_capture_dir or Path()
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        info = QLabel(
            "Capture zone and lockout boss-kill lines from an EQ log file (last 8 days). "
            "Output is a JSON file of raw lines for use with Boss Simulation."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("No file selected")
        file_layout.addWidget(self.file_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("Capture")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_capture)
        self.ok_btn.setEnabled(False)
        btn_layout.addWidget(self.ok_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
    
    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select EQ Log File", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if path:
            self.file_path_edit.setText(path)
            self.selected_file_path = path
            self.ok_btn.setEnabled(True)
    
    def _on_capture(self) -> None:
        if not self.selected_file_path:
            QMessageBox.warning(self, "No File", "Please select a log file.")
            return
        if not Path(self.selected_file_path).exists():
            QMessageBox.warning(self, "Error", "The selected file no longer exists.")
            return
        lines, count = run_boss_capture(self.selected_file_path)
        if not lines:
            QMessageBox.information(
                self, "Boss Capture",
                "No zone or lockout boss-kill lines found in the last 8 days."
            )
            return
        self.default_capture_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = self.default_capture_dir / f"boss_capture_{stamp}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Capture As", str(default_path), "JSON (*.json);;All Files (*.*)"
        )
        if not path:
            return
        try:
            import json
            data = {
                "version": 1,
                "source_file": self.selected_file_path,
                "captured_at": datetime.now().isoformat(),
                "window_days": WINDOW_DAYS,
                "lines": lines,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Boss Capture: {count} lines from last {WINDOW_DAYS} days → {path}")
            QMessageBox.information(
                self, "Boss Capture",
                f"Saved {count} lines from the last {WINDOW_DAYS} days to:\n{path}"
            )
            self.accept()
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not save file: {e}")
