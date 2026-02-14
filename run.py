"""Run script for EverQuest Boss Tracker."""
import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# Import and run main
from src.main import main

if __name__ == "__main__":
    main()

