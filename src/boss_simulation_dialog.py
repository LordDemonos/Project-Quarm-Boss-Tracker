"""Debug → Boss Simulation: replay a capture JSON to a simulated character log file."""
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QMessageBox
)
from PyQt6.QtCore import QTimer

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)

SERVER_NAME = "pq.proj"


class BossSimulationDialog(QDialog):
    """Configure and run boss kill simulation from a capture JSON."""
    
    def __init__(self, parent=None, app_controller=None):
        super().__init__(parent)
        self.setWindowTitle("Boss Simulation (Debug)")
        self.setModal(False)
        self.setMinimumWidth(500)
        self.app_controller = app_controller
        self.captures_dir = getattr(app_controller, "data_dir", Path()) / "captures"
        self._setup_ui()
        self._refresh_capture_list()
        self._update_stop_button()
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._update_stop_button)
        self._poll_timer.start(1000)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        info = QLabel(
            "Replay a Boss Capture JSON into a simulated character log so the app processes kills as live. "
            "Log file is created under the configured log directory."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QHBoxLayout()
        form.addWidget(QLabel("Character name:"))
        self.char_edit = QLineEdit()
        self.char_edit.setPlaceholderText("e.g. SimTest")
        self.char_edit.setText("SimTest")
        form.addWidget(self.char_edit)
        layout.addLayout(form)
        cap_layout = QHBoxLayout()
        cap_layout.addWidget(QLabel("Capture file:"))
        self.capture_combo = QComboBox()
        self.capture_combo.setMinimumWidth(280)
        cap_layout.addWidget(self.capture_combo)
        layout.addLayout(cap_layout)
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Replay interval (seconds):"))
        self.interval_spin = QSpinBox()
        # Minimum 10s so replay interval is always > SAME_KILL_WINDOW_SECONDS (9s); North/South back-to-back both get dialog/post
        self.interval_spin.setMinimum(10)
        self.interval_spin.setMaximum(3600)
        self.interval_spin.setSuffix(" s")
        interval_sec = 30
        if self.app_controller and hasattr(self.app_controller, "settings"):
            interval_sec = self.app_controller.settings.get("debug_simulation_interval_seconds", 30)
        self.interval_spin.setValue(interval_sec)
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        self.save_start_btn = QPushButton("Save & Start Simulation")
        self.save_start_btn.setDefault(True)
        self.save_start_btn.clicked.connect(self._on_save_and_start)
        btn_layout.addWidget(self.save_start_btn)
        self.stop_btn = QPushButton("Stop Simulation")
        self.stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)
    
    def _persist_interval(self) -> None:
        """Save replay interval to app settings and persist to disk."""
        if not self.app_controller:
            return
        val = max(10, min(3600, self.interval_spin.value()))
        self.app_controller.settings["debug_simulation_interval_seconds"] = val
        if hasattr(self.app_controller, "_save_settings"):
            self.app_controller._save_settings()
            logger.debug(f"Saved replay interval: {val} s")

    def _refresh_capture_list(self) -> None:
        self.capture_combo.clear()
        if not self.captures_dir.exists():
            return
        files = sorted(self.captures_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files:
            self.capture_combo.addItem(p.name, str(p))
    
    def _update_stop_button(self) -> None:
        running = self.app_controller and self.app_controller.is_simulation_running()
        self.stop_btn.setEnabled(running)
        if running:
            self.status_label.setText("Simulation is running.")
        else:
            self.status_label.setText("")
    
    def _on_save(self) -> None:
        if not self.app_controller:
            return
        self._persist_interval()
        log_dir = self.app_controller.settings.get("log_directory", "").strip()
        if not log_dir or not Path(log_dir).exists():
            QMessageBox.warning(
                self, "Boss Simulation",
                "Log directory is not set or does not exist. Set it in Settings first."
            )
            return
        char_name = (self.char_edit.text() or "SimTest").strip() or "SimTest"
        log_path = Path(log_dir) / f"eqlog_{char_name}_{SERVER_NAME}.txt"
        try:
            log_path.touch()
            logger.info(f"Simulation log file created/updated: {log_path}")
            QMessageBox.information(self, "Boss Simulation", f"Log file ready:\n{log_path}")
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not create log file: {e}")
    
    def _on_save_and_start(self) -> None:
        if not self.app_controller:
            return
        self._persist_interval()
        capture_path = self.capture_combo.currentData()
        if not capture_path or not Path(capture_path).exists():
            QMessageBox.warning(self, "Boss Simulation", "Select a valid capture file.")
            return
        log_dir = self.app_controller.settings.get("log_directory", "").strip()
        if not log_dir or not Path(log_dir).exists():
            QMessageBox.warning(
                self, "Boss Simulation",
                "Log directory is not set or does not exist. Set it in Settings first."
            )
            return
        char_name = (self.char_edit.text() or "SimTest").strip() or "SimTest"
        interval = self.interval_spin.value()
        if self.app_controller.start_simulation(capture_path, char_name, interval):
            self._update_stop_button()  # Keep window open so user can click Stop Simulation
        else:
            QMessageBox.warning(self, "Boss Simulation", "Could not start simulation (check log).")
    
    def _on_stop(self) -> None:
        if self.app_controller:
            self.app_controller.stop_simulation()
            self.status_label.setText("")
    
    def closeEvent(self, event) -> None:
        self._poll_timer.stop()
        super().closeEvent(event)
