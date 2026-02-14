"""Parse EverQuest log messages to extract boss kill information."""
import re
from dataclasses import dataclass
from typing import Optional

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


@dataclass
class BossKillMessage:
    """Structured data from a parsed boss kill message."""
    timestamp: str
    server: str
    player: str
    guild: str
    monster: str
    location: str


class MessageParser:
    """Parse guild messages about boss kills from EverQuest logs."""
    
    # Pattern: [timestamp] server tells the guild, 'player of <guild> has killed monster in location!'
    PATTERN = re.compile(
        r"\[(.+?)\] (.+?) tells the guild, '(.+?) of <(.+?)> has killed (.+?) in (.+?)!'"
    )
    
    # Pattern: [timestamp] You have incurred a lockout for BossName that expires in X Days and Y Hours.
    LOCKOUT_PATTERN = re.compile(
        r"\[(.+?)\] You have incurred a lockout for (.+?) that expires in"
    )
    
    @classmethod
    def parse_line(cls, line: str) -> Optional[BossKillMessage]:
        """
        Parse a log line to extract boss kill information.
        
        Args:
            line: A line from the EverQuest log file
            
        Returns:
            BossKillMessage if the line matches the pattern, None otherwise
        """
        # Check if line contains keywords that suggest it might be a boss kill message
        if "tells the guild" in line.lower() and "has killed" in line.lower() and "in " in line.lower():
            match = cls.PATTERN.search(line)
            if not match:
                # Log potential matches that didn't parse (for debugging)
                logger.debug(f"Line contains boss kill keywords but didn't match pattern: {line[:100]}...")
                return None
            
            timestamp, server, player, guild, monster, location = match.groups()
            
            result = BossKillMessage(
                timestamp=timestamp.strip(),
                server=server.strip(),
                player=player.strip(),
                guild=guild.strip(),
                monster=monster.strip(),
                location=location.strip()
            )
            
            logger.debug(f"Parsed boss kill: {result.monster} in {result.location} by {result.player}")
            return result
        
        return None
    
    @classmethod
    def parse_lockout_line(cls, line: str) -> Optional[BossKillMessage]:
        """
        Parse a lockout message as a fallback when normal guild message isn't found.
        
        Format: [timestamp] You have incurred a lockout for BossName that expires in X Days and Y Hours.
        
        Args:
            line: A line from the EverQuest log file
            
        Returns:
            BossKillMessage if the line matches the lockout pattern, None otherwise
        """
        if "incurred a lockout" in line.lower() and "expires in" in line.lower():
            match = cls.LOCKOUT_PATTERN.search(line)
            if match:
                timestamp, monster = match.groups()
                
                result = BossKillMessage(
                    timestamp=timestamp.strip(),
                    server="",  # Not available in lockout message
                    player="",  # Not available in lockout message
                    guild="",   # Not available in lockout message
                    monster=monster.strip(),
                    location="Lockouts"  # Special category for lockout-detected bosses
                )
                
                logger.debug(f"Parsed lockout boss kill: {result.monster} (location: Lockouts)")
                return result
        
        return None

