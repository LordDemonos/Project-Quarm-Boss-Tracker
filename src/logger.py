"""Centralized logging configuration for the application."""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_dir: Path = None, log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up application-wide logging.
    
    Args:
        log_dir: Directory for log files (defaults to data/logs)
        log_level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('eq_boss_tracker')
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log file with date
    log_file = log_dir / f"boss_tracker_{datetime.now().strftime('%Y%m%d')}.log"
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler (flush after each message so output appears immediately when not a TTY)
    class FlushingStreamHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            self.flush()
    console_handler = FlushingStreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info("=" * 80)
    logger.info("Project Quarm Boss Tracker - Logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    Uses eq_boss_tracker.<name> so all loggers are children of the app root
    and propagate to its handlers (file + console).
    """
    # Keep full hierarchy under eq_boss_tracker so propagation to console works
    if name.startswith('eq_boss_tracker'):
        logger_name = name
    else:
        logger_name = f'eq_boss_tracker.{name}'
    logger = logging.getLogger(logger_name)
    
    # If no handlers exist, add a simple console handler (for testing)
    if not logger.handlers and logging.getLogger('eq_boss_tracker').level == logging.NOTSET:
        # This is likely a test environment, use simple handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.WARNING)  # Only show warnings/errors in tests
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
    
    return logger
