"""Test theme rendering to debug UI appearance issues."""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QGroupBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.main import _get_default_theme


def test_theme():
    """Test theme rendering in isolation."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # Set dark palette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(13, 13, 13))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 232, 232))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(26, 26, 26))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(232, 232, 232))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(26, 26, 26))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(232, 232, 232))
    app.setPalette(dark_palette)
    
    # Apply theme
    theme = _get_default_theme()
    app.setStyleSheet(theme)
    
    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Theme Test - Should be Deep Dark")
    window.setMinimumSize(600, 400)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Heading
    heading = QLabel("Theme Test Window")
    heading.setProperty("class", "heading")
    layout.addWidget(heading)
    
    # Regular label
    label = QLabel("This is regular text using Fira Sans")
    layout.addWidget(label)
    
    # Input field
    input_field = QLineEdit()
    input_field.setPlaceholderText("Test input field")
    layout.addWidget(input_field)
    
    # Checkbox
    checkbox = QCheckBox("Test checkbox")
    layout.addWidget(checkbox)
    
    # Group box
    group = QGroupBox("Test Group Box")
    group_layout = QVBoxLayout()
    group_layout.addWidget(QLabel("Content inside group box"))
    group.setLayout(group_layout)
    layout.addWidget(group)
    
    # Buttons
    button1 = QPushButton("Test Button (Segoe UI)")
    layout.addWidget(button1)
    
    button2 = QPushButton("Another Button")
    layout.addWidget(button2)
    
    layout.addStretch()
    
    window.setCentralWidget(central)
    window.show()
    
    print("Theme test window opened.")
    print("Check if:")
    print("1. Background is deep dark (#0d0d0d) - near black")
    print("2. Text is bright (#e8e8e8) - light gray/white")
    print("3. No white sheen or light gray overlay")
    print("4. Input fields are dark (#1a1a1a)")
    print("5. Buttons are blue (#0e639c)")
    print("\nIf it still looks wrong, it may be a Windows display/HDR issue.")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_theme()
