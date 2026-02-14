"""Monitor EverQuest log files for new entries."""
import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)

# Debug instrumentation - import from main if available
try:
    import sys
    if 'main' in sys.modules:
        from main import debug_log
    else:
        # Fallback if main not imported yet
        def _get_debug_log_path():
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent.parent
            debug_path = base_dir / ".cursor" / "debug.log"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            return debug_path
        def debug_log(location, message, data=None, hypothesis_id=None, run_id="initial"):
            try:
                import json as json_lib
                import time
                log_entry = {"location": location, "message": message, "timestamp": time.time() * 1000, "runId": run_id}
                if data: log_entry["data"] = data
                if hypothesis_id: log_entry["hypothesisId"] = hypothesis_id
                with open(_get_debug_log_path(), "a", encoding="utf-8") as f:
                    f.write(json_lib.dumps(log_entry) + "\n")
            except: pass
except:
    def debug_log(*args, **kwargs): pass


class LogMonitor:
    """Monitors EverQuest log files for new lines."""
    
    def __init__(self, log_directory: str, on_new_line: Callable[[str], None]):
        """
        Initialize the log monitor.
        
        Args:
            log_directory: Directory containing log files
            on_new_line: Callback function called with each new line
        """
        self.log_directory = Path(log_directory)
        self.on_new_line = on_new_line
        self.active_file: Optional[Path] = None
        self.file_handles: dict = {}
        self.file_positions: dict = {}
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start monitoring log files."""
        if self.running:
            return
        
        # #region agent log
        debug_log("log_monitor.py:36", "LogMonitor starting", {
            "log_directory": str(self.log_directory),
            "directory_exists": self.log_directory.exists()
        }, hypothesis_id="G", run_id="initial")
        
        # Check how many files will be scanned
        if self.log_directory.exists():
            log_files = list(self.log_directory.glob("eqlog_*_*.txt"))
            debug_log("log_monitor.py:36", "Initial log file scan", {
                "file_count": len(log_files),
                "total_size_mb": sum(f.stat().st_size for f in log_files) / 1024 / 1024 if log_files else 0
            }, hypothesis_id="G", run_id="initial")
        # #endregion
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Log monitor started for directory: {self.log_directory}")
    
    def stop(self) -> None:
        """Stop monitoring log files."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            logger.info("Log monitor stopped")
        
        # Close all file handles
        for handle in self.file_handles.values():
            try:
                handle.close()
            except Exception as e:
                logger.warning(f"Error closing file handle: {e}")
        self.file_handles.clear()
        self.file_positions.clear()
    
    def _get_log_files(self) -> List[Path]:
        """Get all log files matching the pattern eqlog_*_*.txt"""
        if not self.log_directory.exists():
            return []
        
        # #region agent log
        log_files = list(self.log_directory.glob("eqlog_*_*.txt"))
        debug_log("log_monitor.py:67", "Scanning log files", {
            "log_directory": str(self.log_directory),
            "file_count": len(log_files),
            "files": [str(f.name) for f in log_files[:10]]  # First 10 filenames
        }, hypothesis_id="G", run_id="initial")
        # #endregion
        
        return log_files
    
    def _get_active_file(self) -> Optional[Path]:
        """Determine which log file is currently active (most recently modified)."""
        log_files = self._get_log_files()
        if not log_files:
            return None
        
        # #region agent log
        debug_log("log_monitor.py:69", "Finding active file", {
            "file_count": len(log_files)
        }, hypothesis_id="G", run_id="initial")
        # #endregion
        
        # Find the file with the most recent modification time
        # This calls stat() on every file - could be expensive with many files
        most_recent = max(log_files, key=lambda f: f.stat().st_mtime)
        
        # #region agent log
        if most_recent:
            try:
                file_size = most_recent.stat().st_size
                debug_log("log_monitor.py:76", "Active file determined", {
                    "active_file": str(most_recent.name),
                    "file_size_bytes": file_size,
                    "file_size_mb": file_size / 1024 / 1024,
                    "mtime": most_recent.stat().st_mtime
                }, hypothesis_id="G", run_id="initial")
            except Exception:
                pass
        # #endregion
        
        return most_recent
    
    def _extract_character_name(self, filepath: Path) -> Optional[str]:
        """
        Extract character name from log filename.
        
        Format: eqlog_{CharacterName}_{ServerName}.txt
        Example: eqlog_Xanax_pq.proj.txt -> "Xanax"
        """
        try:
            # Remove extension and split by underscore
            name_parts = filepath.stem.split('_')
            if len(name_parts) >= 2:
                # Character name is the second part (index 1)
                return name_parts[1]
        except:
            pass
        return None
    
    def get_active_character(self) -> Optional[str]:
        """Get the name of the character whose log is currently active."""
        if self.active_file:
            return self._extract_character_name(self.active_file)
        return None
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        active_file_check_counter = 0
        while self.running:
            try:
                # Check for active file every 10 seconds (not every second)
                # This reduces filesystem overhead significantly
                active_file_check_counter += 1
                if active_file_check_counter >= 10 or self.active_file is None:
                    active_file_check_counter = 0
                    active_file = self._get_active_file()
                    
                    if active_file != self.active_file:
                        # Active file changed
                        old_file = self.active_file
                        self.active_file = active_file
                        if active_file:
                            # Start reading from END of file to avoid processing old entries
                            # Only process new entries that appear after the program starts
                            try:
                                with open(active_file, 'rb') as f:
                                    f.seek(0, 2)  # Seek to end of file
                                    end_pos = f.tell()
                                self.file_positions[active_file] = end_pos
                                character = self._extract_character_name(active_file)
                                logger.info(f"Active log file changed: {old_file} -> {active_file} (Character: {character})")
                                logger.info(f"Starting to monitor from end of file (position {end_pos}) - will only process new entries")
                            except Exception as e:
                                logger.error(f"Error determining file size for {active_file}: {e}")
                                # Fallback to 0 if we can't determine size
                                self.file_positions[active_file] = 0
                
                if self.active_file and self.active_file.exists():
                    self._read_new_lines(self.active_file)
                
                time.sleep(1)  # Check every second for new lines (but only check active file every 10 seconds)
            except Exception as e:
                logger.error(f"Error in log monitor loop: {e}")
                time.sleep(5)
    
    def _read_new_lines(self, filepath: Path) -> None:
        """Read new lines from a log file."""
        try:
            # Get current position for this file
            current_pos = self.file_positions.get(filepath, 0)
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last known position
                f.seek(current_pos)
                
                # Read new lines
                lines_read = 0
                while True:
                    line = f.readline()
                    if not line:
                        break
                    
                    line = line.rstrip('\n\r')
                    if line:
                        lines_read += 1
                        self.on_new_line(line)
                
                # Update position
                new_pos = f.tell()
                if lines_read > 0:
                    logger.debug(f"Read {lines_read} new lines from {filepath.name} (position {current_pos} -> {new_pos})")
                    # #region agent log
                    try:
                        debug_log("log_monitor._read_new_lines", "delivered lines", {"lines_read": lines_read, "file": str(filepath.name), "pos": current_pos, "new_pos": new_pos}, hypothesis_id="H_monitor_deliver", run_id="initial")
                    except Exception:
                        pass
                    # #endregion
                self.file_positions[filepath] = new_pos
        except (IOError, PermissionError) as e:
            # File might be locked or inaccessible, skip this iteration
            logger.debug(f"Log file temporarily inaccessible: {filepath} - {e}")
            pass
        except Exception as e:
            logger.error(f"Unexpected error reading log file {filepath}: {e}", exc_info=True)

