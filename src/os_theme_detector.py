"""Detect OS theme (light/dark mode) for initial app setup."""
import sys
import logging

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


def detect_os_theme() -> str:
    """
    Detect the operating system's theme preference.
    
    Returns:
        "light" or "dark" based on OS theme, defaults to "dark" if detection fails
    """
    if sys.platform == 'win32':
        return _detect_windows_theme()
    elif sys.platform == 'darwin':
        return _detect_macos_theme()
    elif sys.platform.startswith('linux'):
        return _detect_linux_theme()
    else:
        logger.debug(f"OS theme detection not implemented for platform: {sys.platform}")
        return "dark"  # Default to dark


def _detect_windows_theme() -> str:
    """Detect Windows 10/11 theme preference."""
    try:
        import winreg
        
        # Windows 10/11 registry key for theme preference
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        value_name = "AppsUseLightTheme"
        
        try:
            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_READ
            )
            
            # Read the value
            value, _ = winreg.QueryValueEx(key, value_name)
            winreg.CloseKey(key)
            
            # 0 = dark mode, 1 = light mode
            theme = "light" if value == 1 else "dark"
            logger.info(f"Detected Windows theme: {theme} (registry value: {value})")
            return theme
            
        except FileNotFoundError:
            logger.debug("Windows theme registry key not found, using default dark theme")
            return "dark"
        except Exception as e:
            logger.warning(f"Error reading Windows theme from registry: {e}")
            return "dark"
            
    except ImportError:
        # winreg not available (shouldn't happen on Windows, but handle gracefully)
        logger.warning("winreg module not available, cannot detect Windows theme")
        return "dark"


def _detect_macos_theme() -> str:
    """Detect macOS theme preference."""
    try:
        import subprocess
        
        # Use defaults command to read macOS appearance
        result = subprocess.run(
            ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0:
            theme = result.stdout.strip().lower()
            if 'dark' in theme:
                logger.info("Detected macOS theme: dark")
                return "dark"
            else:
                logger.info("Detected macOS theme: light")
                return "light"
        else:
            # Command failed or returned non-zero (usually means light mode)
            logger.info("Detected macOS theme: light (default)")
            return "light"
            
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"Error detecting macOS theme: {e}")
        return "dark"  # Default to dark


def _detect_linux_theme() -> str:
    """Detect Linux desktop environment theme preference."""
    try:
        import subprocess
        import os
        
        # Try different desktop environments
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        
        # GNOME
        if 'gnome' in desktop:
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                scheme = result.stdout.strip().lower()
                if 'dark' in scheme:
                    logger.info("Detected GNOME theme: dark")
                    return "dark"
                else:
                    logger.info("Detected GNOME theme: light")
                    return "light"
        
        # KDE Plasma
        elif 'kde' in desktop or 'plasma' in desktop:
            result = subprocess.run(
                ['kreadconfig5', '--file', 'kdeglobals', '--group', 'Colors:Window', '--key', 'BackgroundNormal'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # KDE detection is more complex, default to dark for now
                logger.info("Detected KDE desktop, defaulting to dark theme")
                return "dark"
        
        # Fallback: check GTK theme
        gtk_theme = os.environ.get('GTK_THEME', '').lower()
        if 'dark' in gtk_theme:
            logger.info("Detected dark GTK theme")
            return "dark"
        
        logger.info("Linux theme detection inconclusive, defaulting to dark")
        return "dark"
        
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"Error detecting Linux theme: {e}")
        return "dark"  # Default to dark
