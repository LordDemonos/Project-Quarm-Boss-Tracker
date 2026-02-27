"""Check Discord channel for duplicate messages to prevent spam."""
try:
    import discord
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import re
import pytz
import asyncio

# Discord timestamp in messages: <t:unix_seconds:F> (or other format letters)
DISCORD_TIMESTAMP_RE = re.compile(r"<t:(\d+):[RFdDfTt]>")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class DiscordChecker:
    """Checks Discord channel for duplicate messages."""

    EST = pytz.timezone('US/Eastern')
    CST = pytz.timezone('US/Central')
    PST = pytz.timezone('US/Pacific')

    # Users who post with CST timestamps (match if author name/display_name contains any, case-insensitive)
    CST_POSTER_SUBSTRINGS = frozenset({"velde", "wool", "cukazi", "barakkas"})
    # Users who post with PST timestamps
    PST_POSTER_SUBSTRINGS = frozenset({"synth"})
    
    def __init__(self, bot_token: Optional[str] = None):
        if not DISCORD_AVAILABLE:
            raise ImportError("discord.py is not installed. Install it with: pip install discord.py")
        """
        Initialize the Discord checker.
        
        Args:
            bot_token: Discord bot token for reading messages
        """
        self.bot_token = bot_token
        self.client: Optional[discord.Client] = None
        self.ready = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None  # Store client's event loop
    
    async def initialize(self) -> bool:
        """
        Initialize Discord client.
        
        Returns:
            True if initialized successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Cannot initialize Discord checker: no bot token provided")
            return False
        
        if self.client and self.ready:
            logger.debug("Discord checker already initialized")
            return True
        
        try:
            intents = discord.Intents.default()
            intents.message_content = True  # Required to read message content
            
            self.client = discord.Client(intents=intents)
            
            @self.client.event
            async def on_ready():
                self.ready = True
                logger.info("Discord checker client ready")
            
            # Start the client - this runs the event loop
            # We need to run it in a background task since start() blocks
            import threading
            def run_client():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._client_loop = loop  # Store reference to client's event loop
                    loop.run_until_complete(self.client.start(self.bot_token))
                except Exception as e:
                    logger.error(f"Error running Discord client: {e}")
                    self.ready = False
                    self._client_loop = None
            
            client_thread = threading.Thread(target=run_client, daemon=True)
            client_thread.start()
            
            # Wait a bit for connection to establish
            import time
            for _ in range(50):  # Wait up to 5 seconds (50 * 0.1)
                if self.ready:
                    break
                time.sleep(0.1)
            
            if self.ready:
                logger.info("Discord checker initialized successfully")
            else:
                logger.warning("Discord checker initialized but not ready yet (will retry on use)")
            return True
        except Exception as e:
            logger.error(f"Error initializing Discord client: {e}")
            return False
    
    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize target name for comparison.
        Replaces backticks with single quotes to handle EverQuest name variations.
        
        Args:
            name: Target name (may contain backticks or single quotes)
            
        Returns:
            Normalized name (lowercase, backticks replaced with single quotes)
        """
        # Replace backticks with single quotes and convert to lowercase
        return name.replace('`', "'").lower()
    
    @staticmethod
    def _name_matches(target_name: str, message_content: str) -> bool:
        """
        Check if target name matches message content, handling variations.
        
        Args:
            target_name: Target name from log (may have backticks)
            message_content: Message content to search
            
        Returns:
            True if name matches (accounting for backtick/single quote variations)
        """
        normalized_target = DiscordChecker._normalize_name(target_name)
        normalized_message = DiscordChecker._normalize_name(message_content)
        
        # Check if normalized target name appears in normalized message
        return normalized_target in normalized_message

    @classmethod
    def _is_cst_poster(cls, message) -> bool:
        """True if message author is known to post timestamps in CST (e.g. Velde/Wool, Cukazi/Barakkas)."""
        if not message or not getattr(message, "author", None):
            return False
        author = message.author
        name = (getattr(author, "name", "") or "").lower()
        display = (getattr(author, "display_name", "") or "").lower()
        combined = f"{name} {display}"
        return any(sub in combined for sub in cls.CST_POSTER_SUBSTRINGS)

    @classmethod
    def _is_pst_poster(cls, message) -> bool:
        """True if message author is known to post timestamps in PST (e.g. Synth)."""
        if not message or not getattr(message, "author", None):
            return False
        author = message.author
        name = (getattr(author, "name", "") or "").lower()
        display = (getattr(author, "display_name", "") or "").lower()
        combined = f"{name} {display}"
        return any(sub in combined for sub in cls.PST_POSTER_SUBSTRINGS)

    def _parse_kill_timestamp_from_discord_message(
        self, timestamp_str: str, message
    ) -> Tuple[datetime, str]:
        """
        Parse timestamp string from a Discord message into EST datetime and display string.
        Handles: (1) Discord format <t:unix:F>; (2) log format "Sun Feb 15 13:56:04 2026"
        with author-based TZ (Velde/Cukazi=CST, Synth=PST, else EST).
        Returns (kill_dt_est, timestamp_str_est). Raises ValueError if unparseable.
        """
        ts = (timestamp_str or "").strip()
        # Discord format: <t:1771125694:F> (unix seconds)
        discord_match = DISCORD_TIMESTAMP_RE.match(ts)
        if discord_match:
            unix_sec = int(discord_match.group(1))
            dt_utc = datetime.utcfromtimestamp(unix_sec).replace(tzinfo=pytz.UTC)
            kill_dt_est = dt_utc.astimezone(self.EST)
            timestamp_str_est = kill_dt_est.strftime("%a %b %d %H:%M:%S %Y")
            return kill_dt_est, timestamp_str_est
        # Log-style format: "Sun Feb 15 13:56:04 2026"
        kill_dt = datetime.strptime(ts, "%a %b %d %H:%M:%S %Y")
        if self._is_pst_poster(message):
            kill_dt_tz = self.PST.localize(kill_dt)
            kill_dt_est = kill_dt_tz.astimezone(self.EST)
            timestamp_str_est = kill_dt_est.strftime("%a %b %d %H:%M:%S %Y")
            return kill_dt_est, timestamp_str_est
        if self._is_cst_poster(message):
            kill_dt_tz = self.CST.localize(kill_dt)
            kill_dt_est = kill_dt_tz.astimezone(self.EST)
            timestamp_str_est = kill_dt_est.strftime("%a %b %d %H:%M:%S %Y")
            return kill_dt_est, timestamp_str_est
        kill_dt_est = self.EST.localize(kill_dt)
        return kill_dt_est, ts

    async def check_duplicate(self, channel_id: int, target_name: str,
                             log_timestamp: str, tolerance_minutes: int = 3) -> bool:
        """
        Check if a duplicate message exists in the channel.
        
        Args:
            channel_id: Discord channel ID
            target_name: Target/boss name to check for
            log_timestamp: Timestamp from log (EST format: "Sat Jan 31 23:30:48 2026")
            tolerance_minutes: Time window in minutes (default 3)
            
        Returns:
            True if duplicate found, False otherwise
        """
        if not self.client or not self.ready:
            logger.warning("Discord checker not ready, cannot check for duplicates")
            return False
        
        try:
            logger.debug(f"Checking for duplicate: {target_name} at {log_timestamp}")
            channel = self.client.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found")
                return False
            
            # Parse log timestamp (EST)
            try:
                dt_log = datetime.strptime(log_timestamp, "%a %b %d %H:%M:%S %Y")
                dt_log_est = self.EST.localize(dt_log)
            except ValueError as e:
                logger.error(f"Failed to parse log timestamp '{log_timestamp}': {e}")
                return False
            
            # Calculate time window (account for timezone differences)
            # People may post in different timezones, so expand window to +/- 6 hours
            # This accounts for EST, CST, MST, PST, etc.
            # Check messages from tolerance + 6 hours ago to tolerance + 6 hours in future
            window_start = dt_log_est - timedelta(minutes=tolerance_minutes + 360)
            window_end = dt_log_est + timedelta(minutes=tolerance_minutes + 360)
            
            logger.debug(f"Checking messages between {window_start} and {window_end}")
            
            # Fetch recent messages (Discord API limit is 100 messages)
            message_count = 0
            async for message in channel.history(limit=100):
                message_count += 1
                
                # Check if message contains target name (with normalization for backticks/single quotes)
                if self._name_matches(target_name, message.content):
                    # Get message timestamp (Discord messages are in UTC)
                    msg_timestamp = message.created_at
                    
                    # Convert to EST for comparison
                    msg_timestamp_est = msg_timestamp.astimezone(self.EST)
                    
                    # Check if within tolerance window
                    if window_start <= msg_timestamp_est <= window_end:
                        # Check if within actual tolerance (3 minutes)
                        # But also check if message might be in a different timezone
                        # If someone posts "9pm CST" and log shows "10pm EST", they're the same time
                        diff_seconds = abs((dt_log_est - msg_timestamp_est).total_seconds())
                        
                        # Allow up to tolerance_minutes, but also check if message content
                        # suggests a different timezone (e.g., "CST", "PST", etc.)
                        # If message is within 4 hours (max timezone difference in US), consider it
                        max_timezone_diff_hours = 4
                        if diff_seconds <= (tolerance_minutes * 60):
                            logger.info(f"Duplicate found: {target_name} posted {diff_seconds:.0f} seconds ago")
                            return True  # Duplicate found
                        elif diff_seconds <= (max_timezone_diff_hours * 3600):
                            # Check if message content suggests different timezone
                            message_lower = message.content.lower()
                            timezone_indicators = ['cst', 'cdt', 'mst', 'mdt', 'pst', 'pdt', 'est', 'edt', 'akst', 'akdt', 'hst']
                            if any(tz in message_lower for tz in timezone_indicators):
                                # Message likely in different timezone, consider it a match
                                logger.info(f"Duplicate found: {target_name} posted {diff_seconds/3600:.1f} hours ago (different timezone)")
                                return True  # Duplicate found
            
            logger.debug(f"Checked {message_count} messages, no duplicate found for {target_name}")
            return False  # No duplicate found
            
        except Exception as e:
            logger.error(f"Error checking for duplicate: {e}")
            return False
    
    async def get_channel_id_from_webhook(self, webhook_url: str) -> Optional[int]:
        """
        Get channel ID from webhook URL by fetching webhook info from Discord API.
        
        Args:
            webhook_url: Discord webhook URL (format: https://discord.com/api/webhooks/WEBHOOK_ID/TOKEN)
            
        Returns:
            Channel ID if found, None otherwise
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, cannot fetch channel ID from webhook")
            return None
        
        try:
            # Extract webhook ID and token from URL
            # Format: https://discord.com/api/webhooks/WEBHOOK_ID/TOKEN
            parts = webhook_url.rstrip('/').split('/')
            if len(parts) < 6 or parts[5] == '':
                logger.warning(f"Invalid webhook URL format: {webhook_url}")
                return None
            
            webhook_id = parts[5]
            webhook_token = parts[6] if len(parts) > 6 else None
            
            if not webhook_token:
                logger.warning(f"Could not extract token from webhook URL")
                return None
            
            # Fetch webhook info from Discord API
            url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        channel_id = data.get('channel_id')
                        if channel_id:
                            logger.debug(f"Retrieved channel ID {channel_id} from webhook")
                            return int(channel_id)
                        else:
                            logger.warning("Webhook response missing channel_id")
                    else:
                        logger.warning(f"Failed to fetch webhook info: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error getting channel ID from webhook: {e}")
        return None
    
    def check_duplicate_sync(self, channel_id: Optional[int], target_name: str,
                             log_timestamp: str, tolerance_minutes: int = 3) -> bool:
        """
        Synchronous wrapper for check_duplicate.
        
        Args:
            channel_id: Discord channel ID (or None to skip check)
            target_name: Target/boss name to check for
            log_timestamp: Timestamp from log (EST format: "Sat Jan 31 23:30:48 2026")
            tolerance_minutes: Time window in minutes (default 3)
            
        Returns:
            True if duplicate found, False otherwise
        """
        if not channel_id:
            return False
        
        if not self.client or not self.ready:
            logger.warning("Discord checker not ready, cannot check for duplicates")
            return False
        
        try:
            # Run async check in new event loop
            return asyncio.run(self.check_duplicate(channel_id, target_name, log_timestamp, tolerance_minutes))
        except Exception as e:
            logger.error(f"Error in synchronous duplicate check: {e}")
            return False
    
    async def scan_channel_for_kills(self, channel_id: int, boss_names: List[str], 
                                     limit: int = 500) -> Dict[str, Dict]:
        """
        Scan Discord channel messages to find boss kills and extract kill times.
        Stops scanning when messages are older than 1 week (since no lockout is older than a week).
        
        Args:
            channel_id: Discord channel ID to scan
            boss_names: List of boss names to search for (case-insensitive)
            limit: Maximum number of messages to scan (default 500)
            
        Returns:
            Dictionary mapping boss_name_lower -> {
                'timestamp': datetime,
                'timestamp_str': str (EST format),
                'monster_name': str (original name),
                'message_content': str
            }
        """
        if not self.client or not self.ready:
            logger.warning("Discord checker not ready, cannot scan channel")
            return {}
        
        try:
            logger.info(f"Scanning Discord channel {channel_id} for {len(boss_names)} bosses (limit: {limit} messages, stopping at 1 week old)")
            channel = self.client.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found")
                return {}
            
            # Normalize boss names for matching (lowercase, handle backticks)
            normalized_bosses = {self._normalize_name(name): name for name in boss_names}
            found_kills = {}  # normalized_name -> kill_info
            
            # Import MessageParser to parse Discord messages
            try:
                from .message_parser import MessageParser
            except ImportError:
                from message_parser import MessageParser
            
            # Calculate 1 week ago threshold (in EST)
            one_week_ago = datetime.now(self.EST) - timedelta(days=7)
            logger.debug(f"Stopping scan when messages are older than: {one_week_ago.strftime('%a %b %d %H:%M:%S %Y')}")
            
            message_count = 0
            parsed_messages = 0
            matched_messages = 0
            stopped_early = False
            
            async for message in channel.history(limit=limit):
                message_count += 1
                
                # Check if message is older than 1 week
                # Discord messages are in UTC, convert to EST for comparison
                msg_timestamp_est = message.created_at.astimezone(self.EST)
                
                if msg_timestamp_est < one_week_ago:
                    stopped_early = True
                    logger.info(f"Stopped scanning at message #{message_count}: message is older than 1 week ({msg_timestamp_est.strftime('%a %b %d %H:%M:%S %Y')})")
                    break
                
                # Log every 50 messages for progress
                if message_count % 50 == 0:
                    logger.debug(f"Scanned {message_count} messages so far...")
                
                # Try to parse message as boss kill(s). Discord messages may be multi-line with
                # guild format, lockout format, or simple "[timestamp] Boss in Zone" per line.
                parsed_results = []
                for line in message.content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parsed = (
                        MessageParser.parse_line(line)
                        or MessageParser.parse_lockout_line(line)
                        or MessageParser.parse_simple_line(line)
                    )
                    if parsed:
                        parsed_results.append(parsed)

                if parsed_results:
                    for parsed in parsed_results:
                        parsed_messages += 1
                        logger.debug(f"Parsed message #{message_count}: {parsed.monster} in {parsed.location} at {parsed.timestamp}")

                        # Check if monster name includes a note in parentheses (e.g., "Thall Va Xakra (South)")
                        monster_name = parsed.monster
                        note = None
                        import re
                        note_match = re.search(r'^(.+?)\s*\(([^)]+)\)$', monster_name)
                        if note_match:
                            monster_name = note_match.group(1).strip()
                            note = note_match.group(2).strip()
                            logger.debug(f"Extracted note '{note}' from boss name '{parsed.monster}' -> '{monster_name}'")

                        monster_normalized = self._normalize_name(monster_name)

                        if monster_normalized in normalized_bosses:
                            matched_messages += 1
                            original_name = normalized_bosses[monster_normalized]
                            logger.info(f"Found matching boss kill in Discord: {original_name}{f' ({note})' if note else ''} at {parsed.timestamp}")

                            try:
                                kill_dt_est, timestamp_str_est = self._parse_kill_timestamp_from_discord_message(
                                    parsed.timestamp, message
                                )
                                kill_key = f"{monster_normalized}|{note}" if note else monster_normalized

                                if kill_key not in found_kills:
                                    found_kills[kill_key] = {
                                        'timestamp': kill_dt_est,
                                        'timestamp_str': timestamp_str_est,
                                        'monster_name': original_name,
                                        'note': note,
                                        'message_content': message.content[:200],
                                    }
                                    logger.info(f"  -> New kill time for {original_name}{f' ({note})' if note else ''}: {timestamp_str_est}")
                                elif kill_dt_est > found_kills[kill_key]['timestamp']:
                                    old_time = found_kills[kill_key]['timestamp_str']
                                    found_kills[kill_key] = {
                                        'timestamp': kill_dt_est,
                                        'timestamp_str': timestamp_str_est,
                                        'monster_name': original_name,
                                        'note': note,
                                        'message_content': message.content[:200],
                                    }
                                    logger.info(f"  -> Updated kill time for {original_name}{f' ({note})' if note else ''}: {old_time} -> {timestamp_str_est}")
                            except ValueError as e:
                                logger.warning(f"Could not parse timestamp '{parsed.timestamp}' from Discord message: {e}")
                else:
                    # Fallback: match every boss name that appears in the message (no break)
                    message_normalized = self._normalize_name(message.content)
                    msg_timestamp_est = message.created_at.astimezone(self.EST)
                    timestamp_str = msg_timestamp_est.strftime("%a %b %d %H:%M:%S %Y")

                    for normalized_name, original_name in normalized_bosses.items():
                        if normalized_name in message_normalized:
                            matched_messages += 1
                            logger.info(f"Found boss name '{original_name}' in Discord message (unparsed format)")
                            logger.info(f"  -> Using Discord message timestamp: {timestamp_str}")

                            if normalized_name not in found_kills:
                                found_kills[normalized_name] = {
                                    'timestamp': msg_timestamp_est,
                                    'timestamp_str': timestamp_str,
                                    'monster_name': original_name,
                                    'note': None,
                                    'message_content': message.content[:200],
                                }
                            elif msg_timestamp_est > found_kills[normalized_name]['timestamp']:
                                old_time = found_kills[normalized_name]['timestamp_str']
                                found_kills[normalized_name] = {
                                    'timestamp': msg_timestamp_est,
                                    'timestamp_str': timestamp_str,
                                    'monster_name': original_name,
                                    'note': None,
                                    'message_content': message.content[:200],
                                }
                                logger.info(f"  -> Updated kill time for {original_name}: {old_time} -> {timestamp_str}")
            
            scan_summary = f"Discord scan complete: Scanned {message_count} messages"
            if stopped_early:
                scan_summary += " (stopped early at 1 week threshold)"
            scan_summary += f", parsed {parsed_messages} kill messages, matched {matched_messages} to tracked bosses, found {len(found_kills)} unique boss kills"
            logger.info(scan_summary)
            return found_kills
            
        except Exception as e:
            logger.error(f"Error scanning Discord channel: {e}", exc_info=True)
            return {}
    
    def scan_channel_for_kills_sync(self, channel_id: Optional[int], boss_names: List[str],
                                     limit: int = 500) -> Dict[str, Dict]:
        """
        Synchronous wrapper for scan_channel_for_kills.
        Uses run_coroutine_threadsafe to schedule on the Discord client's event loop.
        
        Args:
            channel_id: Discord channel ID (or None to skip)
            boss_names: List of boss names to search for
            limit: Maximum number of messages to scan
            
        Returns:
            Dictionary of found kills (same format as async version)
        """
        if not channel_id:
            return {}
        
        if not self.client or not self.ready:
            logger.warning("Discord checker not ready, cannot scan channel")
            return {}
        
        try:
            # Use run_coroutine_threadsafe to schedule on the client's event loop
            # This is the correct way to call async code from a different thread
            if self._client_loop and self._client_loop.is_running():
                import concurrent.futures
                logger.debug("Using run_coroutine_threadsafe to schedule scan on client's event loop")
                future = asyncio.run_coroutine_threadsafe(
                    self.scan_channel_for_kills(channel_id, boss_names, limit),
                    self._client_loop
                )
                try:
                    result = future.result(timeout=120)  # 120 second timeout for scanning
                    return result
                except concurrent.futures.TimeoutError:
                    logger.error("Discord scan timed out after 120 seconds")
                    return {}
            else:
                # Fallback: try to get loop from client
                if self.client and hasattr(self.client, 'loop') and self.client.loop and self.client.loop.is_running():
                    import concurrent.futures
                    logger.debug("Using client.loop for run_coroutine_threadsafe")
                    future = asyncio.run_coroutine_threadsafe(
                        self.scan_channel_for_kills(channel_id, boss_names, limit),
                        self.client.loop
                    )
                    try:
                        result = future.result(timeout=120)
                        return result
                    except concurrent.futures.TimeoutError:
                        logger.error("Discord scan timed out after 120 seconds")
                        return {}
                else:
                    # Last resort: create new event loop (may not work if Discord client is running)
                    logger.warning("No running event loop found, creating new one (may cause issues)")
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(self.scan_channel_for_kills(channel_id, boss_names, limit))
                            return result
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.error(f"Error creating new event loop for scan: {e}", exc_info=True)
                        return {}
        except Exception as e:
            logger.error(f"Error in synchronous channel scan: {e}", exc_info=True)
            return {}
    
    async def close(self) -> None:
        """Close Discord client connection."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Discord checker client closed")
            except Exception as e:
                logger.error(f"Error closing Discord client: {e}")
            self.client = None
            self.ready = False
