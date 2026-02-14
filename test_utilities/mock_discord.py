"""Mock Discord webhook for testing without real Discord."""
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

# Add src to path for logger
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class MockDiscordNotifier:
    """Mock Discord notifier that logs messages instead of posting."""

    def __init__(self, default_webhook_url: Optional[str] = None,
                 timestamp_formatter=None):
        """Initialize the mock Discord notifier."""
        self.default_webhook_url = default_webhook_url
        self.timestamp_formatter = timestamp_formatter
        self.posted_messages: List[Dict] = []
        logger.info("Mock Discord notifier initialized (messages will be logged, not posted)")
    
    def start(self) -> None:
        """Start the mock notifier (no-op)."""
        logger.debug("Mock Discord notifier started")
    
    def stop(self) -> None:
        """Stop the mock notifier (no-op)."""
        logger.debug("Mock Discord notifier stopped")
    
    def format_message(self, template: str, timestamp: Optional[str] = None, **kwargs) -> str:
        """Format a message using template variables."""
        # Add Discord timestamp variables if timestamp formatter available
        if self.timestamp_formatter and timestamp:
            kwargs['discord_timestamp'] = self.timestamp_formatter.format_discord_timestamp_full(timestamp)
            kwargs['discord_timestamp_relative'] = self.timestamp_formatter.format_discord_timestamp_relative(timestamp)
        
        # Ensure timestamp variable exists
        if 'timestamp' not in kwargs and timestamp:
            kwargs['timestamp'] = timestamp
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return template
    
    def notify(self, message: str, webhook_url: Optional[str] = None) -> None:
        """
        Log a notification instead of posting to Discord.

        Args:
            message: Message content
            webhook_url: Webhook URL (for logging purposes)
        """
        url = webhook_url or self.default_webhook_url

        entry = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'webhook_url': url
        }
        
        self.posted_messages.append(entry)
        
        logger.info("=" * 80)
        logger.info("MOCK DISCORD POST (not actually posted):")
        logger.info(f"Webhook: {url[:50]}..." if url else "Webhook: None")
        logger.info(f"Message: {message}")
        logger.info("=" * 80)
        
        print("\n" + "=" * 80)
        print("MOCK DISCORD POST (not actually posted):")
        print(f"Message: {message}")
        print("=" * 80 + "\n")
    
    def get_posted_messages(self) -> List[Dict]:
        """Get all posted messages."""
        return self.posted_messages.copy()
    
    def clear_messages(self) -> None:
        """Clear posted messages list."""
        self.posted_messages.clear()
        logger.debug("Mock Discord message history cleared")


class MockDiscordChecker:
    """Mock Discord checker for testing duplicate detection."""
    
    def __init__(self, bot_token: Optional[str] = None):
        """Initialize the mock Discord checker."""
        self.bot_token = bot_token
        self.ready = True  # Always ready for mock
        self.duplicate_messages: List[Dict] = []
        logger.info("Mock Discord checker initialized")
    
    async def initialize(self) -> bool:
        """Initialize (always succeeds for mock)."""
        self.ready = True
        logger.info("Mock Discord checker initialized")
        return True
    
    async def check_duplicate(self, channel_id: int, target_name: str,
                             log_timestamp: str, tolerance_minutes: int = 3) -> bool:
        """
        Check for duplicates in mock posted messages.
        
        Args:
            channel_id: Channel ID (ignored in mock)
            target_name: Target name to check
            log_timestamp: Log timestamp
            tolerance_minutes: Tolerance window
            
        Returns:
            True if duplicate found in mock messages, False otherwise
        """
        # This would check against posted_messages from MockDiscordNotifier
        # For now, return False (no duplicates in mock)
        logger.debug(f"Mock duplicate check for {target_name}: No duplicate (mock)")
        return False
    
    async def close(self) -> None:
        """Close mock checker (no-op)."""
        logger.debug("Mock Discord checker closed")
