"""Generate test log files for testing."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Import module
import message_parser
MessageParser = message_parser.MessageParser


def generate_test_log_line(timestamp: datetime, server: str, player: str, 
                           guild: str, monster: str, location: str) -> str:
    """Generate a test log line in EverQuest format."""
    timestamp_str = timestamp.strftime("%a %b %d %H:%M:%S %Y")
    return f"[{timestamp_str}] {server} tells the guild, '{player} of <{guild}> has killed {monster} in {location}!'"


def generate_test_log_file(output_path: Path, num_entries: int = 20):
    """Generate a test log file with various boss kills."""
    
    # Sample data
    servers = ["Druzzil Ro", "Project Quarm"]
    players = ["TestPlayer1", "TestPlayer2", "TestPlayer3"]
    guilds = ["Test Guild", "Another Guild"]
    
    # Sample bosses and zones
    bosses_zones = [
        ("Severilous", "The Emerald Jungle"),
        ("Aten Ha Ra", "Vex Thal"),
        ("Rhag`Zhezum", "Ssraeshza Temple"),
        ("Thought Horror Overfiend", "The Deep"),
        ("Lord Inquisitor Seru", "Sanctus Seru"),
        ("Phara Dar", "Vex Thal"),
        ("Master Yael", "The Emerald Jungle"),
    ]
    
    # Generate entries
    lines = []
    base_time = datetime.now() - timedelta(hours=1)
    
    for i in range(num_entries):
        # Random time within last hour
        entry_time = base_time + timedelta(minutes=random.randint(0, 60))
        
        # Random selection
        server = random.choice(servers)
        player = random.choice(players)
        guild = random.choice(guilds)
        monster, location = random.choice(bosses_zones)
        
        line = generate_test_log_line(entry_time, server, player, guild, monster, location)
        lines.append(line)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Generated test log file: {output_path}")
    print(f"Entries: {num_entries}")
    
    # Verify parsing
    parser = MessageParser()
    parsed_count = 0
    for line in lines:
        if parser.parse_line(line):
            parsed_count += 1
    
    print(f"Successfully parsed: {parsed_count}/{num_entries}")
    
    return output_path


def generate_recent_entry(output_path: Path, monster: str, location: str):
    """Append a recent entry to test log file (simulates new kill)."""
    timestamp = datetime.now()
    server = "Druzzil Ro"
    player = "TestPlayer"
    guild = "Test Guild"
    
    line = generate_test_log_line(timestamp, server, player, guild, monster, location)
    
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write('\n' + line)
    
    print(f"Appended new entry: {monster} in {location}")
    return line


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test log files")
    parser.add_argument("--output", "-o", default="test_logs/eqlog_TestChar_pq.proj.txt",
                       help="Output log file path")
    parser.add_argument("--entries", "-n", type=int, default=20,
                       help="Number of entries to generate")
    parser.add_argument("--append", "-a", action="store_true",
                       help="Append a new recent entry")
    parser.add_argument("--monster", "-m", default="TestBoss",
                       help="Monster name for append")
    parser.add_argument("--location", "-l", default="Test Zone",
                       help="Location for append")
    
    args = parser.parse_args()
    
    output_path = Path(args.output)
    
    if args.append:
        generate_recent_entry(output_path, args.monster, args.location)
    else:
        generate_test_log_file(output_path, args.entries)
