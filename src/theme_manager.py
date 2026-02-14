"""Manage application themes - convert CSS to PyQt6 QSS."""
import json
import re
from pathlib import Path
from typing import Dict, Optional

try:
    from colorspacious import cspace_convert
    HAS_COLORSPACIOUS = True
except ImportError:
    HAS_COLORSPACIOUS = False
    print("Warning: colorspacious not available, using fallback color conversion")


class ThemeManager:
    """Manages application themes by converting CSS to PyQt6 QSS."""
    
    def __init__(self, theme_dir: str = "themes"):
        """
        Initialize the theme manager.
        
        Args:
            theme_dir: Directory containing theme files
        """
        self.theme_dir = Path(theme_dir)
        self.theme_dir.mkdir(parents=True, exist_ok=True)
        self.current_theme: Optional[str] = None
        self.light_qss: Optional[str] = None
        self.dark_qss: Optional[str] = None
    
    def oklch_to_rgb(self, oklch_str: str) -> str:
        """
        Convert oklch color string to RGB hex.
        
        Args:
            oklch_str: oklch color string like "oklch(0.9754 0.0084 325.6414)"
            
        Returns:
            RGB hex color string like "#f9f9f9"
        """
        try:
            # Parse oklch string: oklch(L C H)
            match = re.match(r"oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)", oklch_str)
            if not match:
                return "#ffffff"
            
            L, C, H = float(match.group(1)), float(match.group(2)), float(match.group(3))
            
            if HAS_COLORSPACIOUS:
                try:
                    # Convert oklch to RGB using colorspacious
                    # OKLCH -> CIELAB -> XYZ -> sRGB255
                    oklch_color = [L * 100, C * 100, H]  # L in 0-100, C in 0-100, H in degrees
                    # Try via CIELAB as intermediate
                    lab = cspace_convert(oklch_color, "OKLCH", "CIELAB")
                    xyz = cspace_convert(lab, "CIELAB", "XYZ100")
                    rgb = cspace_convert(xyz, "XYZ100", "sRGB255")
                    
                    # Clamp values and convert to hex
                    r = max(0, min(255, int(rgb[0])))
                    g = max(0, min(255, int(rgb[1])))
                    b = max(0, min(255, int(rgb[2])))
                    
                    return f"#{r:02x}{g:02x}{b:02x}"
                except Exception as e:
                    # Try direct conversion if intermediate fails
                    try:
                        oklch_color = [L * 100, C * 100, H]
                        rgb = cspace_convert(oklch_color, "OKLCH", "sRGB1")
                        # Convert from 0-1 range to 0-255
                        r = max(0, min(255, int(rgb[0] * 255)))
                        g = max(0, min(255, int(rgb[1] * 255)))
                        b = max(0, min(255, int(rgb[2] * 255)))
                        return f"#{r:02x}{g:02x}{b:02x}"
                    except Exception as e2:
                        pass  # Fall through to manual conversion
            
            # Manual OKLCH to RGB conversion (simplified approximation)
            # This is a basic approximation - for better results, use colorspacious
            import math
            
            # Convert OKLCH to OKLab
            a = C * math.cos(math.radians(H))
            b = C * math.sin(math.radians(H))
            
            # OKLab to linear RGB (simplified)
            # This is a rough approximation
            l_linear = L + 0.3963377774 * a + 0.2158037573 * b
            m_linear = L - 0.1055613458 * a - 0.0638541728 * b
            s_linear = L - 0.0894841775 * a - 1.2914855480 * b
            
            # Apply gamma correction (simplified)
            def linear_to_srgb(c):
                if c <= 0.0031308:
                    return 12.92 * c
                else:
                    return 1.055 * (c ** (1.0 / 2.4)) - 0.055
            
            r_linear = +1.2270138511 * l_linear - 0.5577999807 * m_linear + 0.2812561490 * s_linear
            g_linear = -0.0405801784 * l_linear + 1.1122568696 * m_linear - 0.0716766787 * s_linear
            b_linear = -0.0763812849 * l_linear - 0.4214819784 * m_linear + 1.5861632204 * s_linear
            
            r = max(0, min(255, int(linear_to_srgb(r_linear) * 255)))
            g = max(0, min(255, int(linear_to_srgb(g_linear) * 255)))
            b = max(0, min(255, int(linear_to_srgb(b_linear) * 255)))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception as e:
            print(f"Error converting oklch to RGB: {e}")
            return "#ffffff"
    
    def convert_css_to_qss(self, css_vars: Dict[str, str], is_dark: bool = False) -> str:
        """
        Convert CSS custom properties to PyQt6 QSS.
        
        Args:
            css_vars: Dictionary of CSS variable names to oklch values
            is_dark: Whether this is the dark theme
            
        Returns:
            QSS stylesheet string
        """
        # Convert colors
        colors = {}
        for key, value in css_vars.items():
            if value.startswith("oklch("):
                colors[key] = self.oklch_to_rgb(value)
            else:
                colors[key] = value
        
        # Extract radius value
        radius = css_vars.get("--radius", "0.5rem")
        radius_px = self._rem_to_px(radius)
        
        # Build QSS stylesheet
        qss = f"""
/* {'Dark' if is_dark else 'Light'} Theme */

QWidget {{
    background-color: {colors.get('--background', '#ffffff')};
    color: {colors.get('--foreground', '#000000')};
    font-family: {css_vars.get('--font-sans', 'Segoe UI')};
}}

QPushButton {{
    background-color: {colors.get('--primary', '#0078d4')};
    color: {colors.get('--primary-foreground', '#ffffff')};
    border: 1px solid {colors.get('--border', '#cccccc')};
    border-radius: {radius_px}px;
    padding: 8px 16px;
}}

QPushButton:hover {{
    background-color: {colors.get('--accent', '#005a9e')};
}}

QPushButton:pressed {{
    background-color: {colors.get('--primary', '#0078d4')};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {colors.get('--input', '#ffffff')};
    color: {colors.get('--foreground', '#000000')};
    border: 1px solid {colors.get('--border', '#cccccc')};
    border-radius: {radius_px}px;
    padding: 4px 8px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {colors.get('--ring', '#0078d4')};
}}

QCheckBox {{
    color: {colors.get('--foreground', '#000000')};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {colors.get('--border', '#cccccc')};
    border-radius: 4px;
    background-color: {colors.get('--input', '#ffffff')};
}}

QCheckBox::indicator:checked {{
    background-color: {colors.get('--primary', '#0078d4')};
    border-color: {colors.get('--primary', '#0078d4')};
}}

QListWidget {{
    background-color: {colors.get('--card', '#ffffff')};
    color: {colors.get('--foreground', '#000000')};
    border: 1px solid {colors.get('--border', '#cccccc')};
    border-radius: {radius_px}px;
}}

QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {colors.get('--border', '#cccccc')};
}}

QListWidget::item:hover {{
    background-color: {colors.get('--accent', '#f0f0f0')};
}}

QListWidget::item:selected {{
    background-color: {colors.get('--primary', '#0078d4')};
    color: {colors.get('--primary-foreground', '#ffffff')};
}}

QMenuBar {{
    background-color: {colors.get('--background', '#ffffff')};
    color: {colors.get('--foreground', '#000000')};
}}

QMenu {{
    background-color: {colors.get('--popover', '#ffffff')};
    color: {colors.get('--popover-foreground', '#000000')};
    border: 1px solid {colors.get('--border', '#cccccc')};
    border-radius: {radius_px}px;
}}

QMenu::item {{
    padding: 8px 24px;
}}

QMenu::item:selected {{
    background-color: {colors.get('--accent', '#f0f0f0')};
}}

QScrollBar:vertical {{
    background-color: {colors.get('--muted', '#f5f5f5')};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.get('--border', '#cccccc')};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.get('--accent', '#e0e0e0')};
}}

QScrollBar:horizontal {{
    background-color: {colors.get('--muted', '#f5f5f5')};
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {colors.get('--border', '#cccccc')};
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {colors.get('--accent', '#e0e0e0')};
}}

QLabel {{
    color: {colors.get('--foreground', '#000000')};
}}

QGroupBox {{
    border: 1px solid {colors.get('--border', '#cccccc')};
    border-radius: {radius_px}px;
    margin-top: 12px;
    padding-top: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {colors.get('--foreground', '#000000')};
}}
"""
        return qss.strip()
    
    def _rem_to_px(self, rem_str: str) -> int:
        """Convert rem string to pixels (assuming 1rem = 16px)."""
        try:
            rem_value = float(rem_str.replace("rem", "").strip())
            return int(rem_value * 16)
        except:
            return 8
    
    def load_theme_from_css(self, css_file: str) -> None:
        """
        Load theme from CSS file and convert to QSS.
        
        Args:
            css_file: Path to CSS file with theme variables
        """
        css_path = Path(css_file)
        if not css_path.exists():
            print(f"CSS file not found: {css_file}")
            return
        
        # Parse CSS to extract variables
        light_vars = {}
        dark_vars = {}
        
        with open(css_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract :root variables (light theme)
        root_match = re.search(r':root\s*\{([^}]+)\}', content, re.DOTALL)
        if root_match:
            vars_text = root_match.group(1)
            for match in re.finditer(r'--([^:]+):\s*([^;]+);', vars_text):
                key = f"--{match.group(1).strip()}"
                value = match.group(2).strip()
                light_vars[key] = value
        
        # Extract .dark variables
        dark_match = re.search(r'\.dark\s*\{([^}]+)\}', content, re.DOTALL)
        if dark_match:
            vars_text = dark_match.group(1)
            for match in re.finditer(r'--([^:]+):\s*([^;]+);', vars_text):
                key = f"--{match.group(1).strip()}"
                value = match.group(2).strip()
                dark_vars[key] = value
        
        # Convert to QSS
        self.light_qss = self.convert_css_to_qss(light_vars, is_dark=False)
        self.dark_qss = self.convert_css_to_qss(dark_vars, is_dark=True)
        
        # Save QSS files
        light_qss_path = self.theme_dir / "light.qss"
        dark_qss_path = self.theme_dir / "dark.qss"
        
        light_qss_path.write_text(self.light_qss, encoding='utf-8')
        dark_qss_path.write_text(self.dark_qss, encoding='utf-8')
    
    def get_qss(self, theme: str = "light") -> str:
        """
        Get QSS stylesheet for the specified theme.
        
        Args:
            theme: "light" or "dark"
            
        Returns:
            QSS stylesheet string
        """
        if theme == "dark":
            if self.dark_qss:
                return self.dark_qss
            # Try to load from file
            dark_path = self.theme_dir / "dark.qss"
            if dark_path.exists():
                return dark_path.read_text(encoding='utf-8')
        else:
            if self.light_qss:
                return self.light_qss
            # Try to load from file
            light_path = self.theme_dir / "light.qss"
            if light_path.exists():
                return light_path.read_text(encoding='utf-8')
        
        return ""  # Return empty if no theme available
    
    def apply_theme(self, app, theme: str = "light") -> None:
        """
        Apply theme to a QApplication.
        
        Args:
            app: QApplication instance
            theme: "light" or "dark"
        """
        qss = self.get_qss(theme)
        if qss:
            app.setStyleSheet(qss)
            self.current_theme = theme

