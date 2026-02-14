"""Play sound notifications."""
import os
from pathlib import Path
import pygame
import threading

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class SoundPlayer:
    """Handles playing sound notifications."""
    
    def __init__(self, sound_file_path: str = "fanfare.mp3"):
        """
        Initialize the sound player.
        
        Args:
            sound_file_path: Path to the sound file to play
        """
        self.sound_file_path = Path(sound_file_path)
        self.enabled = True
        pygame.mixer.init()
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sound playback."""
        self.enabled = enabled
        logger.info(f"Sound playback {'enabled' if enabled else 'disabled'}")
    
    def set_sound_file(self, sound_file_path: str) -> None:
        """Set the sound file path."""
        self.sound_file_path = Path(sound_file_path)
        logger.debug(f"Sound file path set to: {sound_file_path}")
    
    def play(self) -> None:
        """Play the sound file in a separate thread."""
        if not self.enabled:
            logger.info("[SOUND] Sound playback disabled, skipping")
            return
        
        if not self.sound_file_path.exists():
            logger.warning(f"Sound file not found: {self.sound_file_path}")
            return
        
        def _play():
            try:
                logger.info(f"[SOUND] Playing sound: {self.sound_file_path}")
                pygame.mixer.music.load(str(self.sound_file_path))
                pygame.mixer.music.play()
                logger.info("[SOUND] Sound played successfully")
            except pygame.error as e:
                logger.error(f"[SOUND] Error playing sound: {e}")
        
        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

