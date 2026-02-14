"""Handle timezone conversion and Discord timestamp formatting."""
import re
from datetime import datetime
from typing import Optional
import pytz

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class TimestampFormatter:
    """Formats timestamps for Discord with timezone support."""
    
    # EST timezone (server time)
    EST = pytz.timezone('US/Eastern')
    
    def __init__(self, user_timezone: Optional[str] = None):
        """
        Initialize the timestamp formatter.

        Args:
            user_timezone: IANA timezone (e.g. 'US/Central', 'Europe/London', 'Australia/Sydney').
                          If None or empty, auto-detect from system (works for EU/AUS when system reports a known zone).
        """
        if user_timezone and user_timezone.strip():
            try:
                self.user_tz = pytz.timezone(user_timezone.strip())
            except pytz.exceptions.UnknownTimeZoneError:
                self.user_tz = pytz.timezone(self.get_system_timezone())
        else:
            # Auto-detect from system (supports EU, AUS, etc. when system TZ is detectable)
            tz_name = self.get_system_timezone()
            self.user_tz = pytz.timezone(tz_name)
    
    def set_timezone(self, timezone: str) -> None:
        """Set the user's timezone. Pass empty string to use system (auto-detect)."""
        if not timezone or not timezone.strip():
            tz_name = self.get_system_timezone()
            self.user_tz = pytz.timezone(tz_name)
            logger.info(f"Timezone set to auto-detect: {tz_name}")
            return
        try:
            self.user_tz = pytz.timezone(timezone.strip())
            logger.info(f"Timezone set to: {timezone}")
        except pytz.exceptions.UnknownTimeZoneError as e:
            logger.error(f"Unknown timezone '{timezone}': {e}")
    
    def parse_log_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse timestamp from log message.
        
        Format: "Sat Jan 31 23:30:48 2026"
        Returns datetime in EST (server time)
        
        Args:
            timestamp_str: Timestamp string from log
            
        Returns:
            datetime object in EST, or None if parsing fails
        """
        try:
            # Parse the timestamp (assumes EST/server time)
            dt = datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %Y")
            # Localize to EST
            dt_est = self.EST.localize(dt)
            logger.debug(f"Parsed timestamp: {timestamp_str} -> {dt_est}")
            return dt_est
        except ValueError as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None
    
    def to_unix_timestamp(self, dt: datetime) -> int:
        """
        Convert datetime to Unix timestamp.
        
        Args:
            dt: datetime object
            
        Returns:
            Unix timestamp (seconds since epoch)
        """
        return int(dt.timestamp())
    
    def format_discord_timestamp(self, timestamp_str: str, format_type: str = 'F') -> str:
        """
        Format log timestamp as Discord timestamp.
        
        Args:
            timestamp_str: Timestamp string from log (EST)
            format_type: Discord format type:
                        'F' - Full date/time (default)
                        'R' - Relative time
                        't' - Short time
                        'T' - Long time
                        'd' - Short date
                        'D' - Long date
                        'f' - Short date/time
                        ''  - Default format
        
        Returns:
            Discord timestamp string like "<t:1234567890:F>"
        """
        dt_est = self.parse_log_timestamp(timestamp_str)
        if not dt_est:
            logger.warning(f"Could not format Discord timestamp, returning original: {timestamp_str}")
            return timestamp_str  # Return original if parsing fails
        
        # Convert to user's timezone
        dt_user = dt_est.astimezone(self.user_tz)
        
        # Convert to Unix timestamp
        unix_ts = self.to_unix_timestamp(dt_user)
        
        # Format as Discord timestamp
        result = f"<t:{unix_ts}:{format_type}>"
        logger.debug(f"Formatted Discord timestamp: {timestamp_str} -> {result} (user_tz: {self.user_tz})")
        return result
    
    def format_discord_timestamp_relative(self, timestamp_str: str) -> str:
        """Format as relative Discord timestamp (e.g., "2 minutes ago")."""
        return self.format_discord_timestamp(timestamp_str, 'R')
    
    def format_discord_timestamp_full(self, timestamp_str: str) -> str:
        """Format as full date/time Discord timestamp."""
        return self.format_discord_timestamp(timestamp_str, 'F')
    
    def get_system_timezone(self) -> str:
        """
        Get system timezone IANA name so auto-detect works for EU, AUS, etc.

        Returns:
            IANA timezone name (e.g. 'US/Eastern', 'Europe/London', 'Australia/Sydney').
        """
        # 1) Try zoneinfo.ZoneInfo local zone (Python 3.9+, some systems set .key)
        try:
            from datetime import datetime
            now = datetime.now().astimezone()
            if now.tzinfo and getattr(now.tzinfo, "key", None):
                name = getattr(now.tzinfo, "key")
                if name and name != "localtime":
                    pytz.timezone(name)  # validate
                    return name
        except Exception:
            pass

        # 2) Map time.tzname abbreviations to IANA (US, EU, AUS, Asia)
        try:
            import time
            tzname = (time.tzname()[0] or "").upper()
            tz_map = {
                # US
                "EST": "US/Eastern",
                "EDT": "US/Eastern",
                "CST": "US/Central",
                "CDT": "US/Central",
                "MST": "US/Mountain",
                "MDT": "US/Mountain",
                "PST": "US/Pacific",
                "PDT": "US/Pacific",
                # Europe / UK
                "GMT": "Europe/London",
                "BST": "Europe/London",
                "CET": "Europe/Paris",
                "CEST": "Europe/Paris",
                "EET": "Europe/Athens",
                "EEST": "Europe/Athens",
                "WET": "Europe/London",
                "WEST": "Europe/London",
                # Australia
                "AEST": "Australia/Sydney",
                "AEDT": "Australia/Sydney",
                "ACST": "Australia/Adelaide",
                "ACDT": "Australia/Adelaide",
                "AWST": "Australia/Perth",
                # Asia
                "JST": "Asia/Tokyo",
                "SGT": "Asia/Singapore",
                "HKT": "Asia/Hong_Kong",
            }
            if tzname in tz_map:
                return tz_map[tzname]
        except Exception:
            pass

        return "US/Eastern"
    
    def compare_timestamps(self, timestamp1_str: str, timestamp2_str: str, 
                          tolerance_minutes: int = 3) -> bool:
        """
        Compare two timestamps to see if they're within tolerance.
        
        Used for duplicate detection - accounts for timezone differences.
        Both timestamps are assumed to be in EST (server time).
        
        Args:
            timestamp1_str: First timestamp string (EST)
            timestamp2_str: Second timestamp string (EST)
            tolerance_minutes: Tolerance in minutes (default 3)
            
        Returns:
            True if timestamps are within tolerance, False otherwise
        """
        dt1 = self.parse_log_timestamp(timestamp1_str)
        dt2 = self.parse_log_timestamp(timestamp2_str)
        
        if not dt1 or not dt2:
            return False
        
        # Calculate difference
        diff = abs((dt1 - dt2).total_seconds())
        tolerance_seconds = tolerance_minutes * 60
        
        return diff <= tolerance_seconds
