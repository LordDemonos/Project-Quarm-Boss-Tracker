"""Test message parser."""
import sys
import io
from pathlib import Path

# Fix Windows console encoding (only if not already wrapped)
if sys.platform == 'win32':
    if not isinstance(sys.stdout, io.TextIOWrapper) or (hasattr(sys.stdout, 'encoding') and sys.stdout.encoding != 'utf-8'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if not isinstance(sys.stderr, io.TextIOWrapper) or (hasattr(sys.stderr, 'encoding') and sys.stderr.encoding != 'utf-8'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Import module
import message_parser
MessageParser = message_parser.MessageParser


def test_message_parser():
    """Test message parser."""
    print("Testing Message Parser...")
    print("=" * 60)
    
    parser = MessageParser()
    
    # Test valid message
    valid_line = "[Sat Jan 31 23:30:48 2026] Druzzil Ro tells the guild, 'Orez of <Former Glory> has killed Rhag`Zhezum in Ssraeshza Temple!'"
    parsed = parser.parse_line(valid_line)
    
    assert parsed is not None, "Should parse valid message"
    assert parsed.monster == "Rhag`Zhezum", f"Monster should be 'Rhag`Zhezum', got '{parsed.monster}'"
    assert parsed.location == "Ssraeshza Temple", f"Location should be 'Ssraeshza Temple', got '{parsed.location}'"
    assert parsed.player == "Orez", f"Player should be 'Orez', got '{parsed.player}'"
    assert parsed.guild == "Former Glory", f"Guild should be 'Former Glory', got '{parsed.guild}'"
    print("[OK] Valid message parsed correctly")
    print(f"  Monster: {parsed.monster}")
    print(f"  Location: {parsed.location}")
    print(f"  Player: {parsed.player}")
    print(f"  Guild: {parsed.guild}")
    
    # Test another valid message
    valid_line2 = "[Sat Jan 31 23:12:16 2026] Druzzil Ro tells the guild, 'Chararak of <Former Glory> has killed Thought Horror Overfiend in The Deep!'"
    parsed2 = parser.parse_line(valid_line2)
    
    assert parsed2 is not None, "Should parse second valid message"
    assert parsed2.monster == "Thought Horror Overfiend", "Monster should match"
    assert parsed2.location == "The Deep", "Location should match"
    print("[OK] Second valid message parsed correctly")
    
    # Test invalid message
    invalid_line = "This is not a valid log line"
    parsed3 = parser.parse_line(invalid_line)
    assert parsed3 is None, "Should not parse invalid message"
    print("[OK] Invalid message rejected correctly")
    
    # Test edge case: special characters
    special_line = "[Sat Jan 31 23:30:48 2026] Druzzil Ro tells the guild, 'Player of <Guild> has killed Boss`Name in Zone Name!'"
    parsed4 = parser.parse_line(special_line)
    assert parsed4 is not None, "Should parse message with special characters"
    assert parsed4.monster == "Boss`Name", "Should handle backtick in name"
    assert parsed4.location == "Zone Name", "Should handle spaces in location"
    print("[OK] Special characters handled correctly")
    
    print("\n" + "=" * 60)
    print("All tests passed!")


if __name__ == "__main__":
    test_message_parser()
