"""Run all unit tests."""
import sys
import io
import importlib
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    # Only wrap if not already wrapped
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add test_utilities to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("EverQuest Boss Tracker - Test Suite")
print("=" * 80)
print()

# Run tests
tests = [
    ("Message Parser", "test_parser", "test_message_parser"),
    ("Boss Database", "test_database", "test_boss_database"),
    ("Timestamp Formatter", "test_timestamp", "test_timestamp_formatter"),
    ("Activity Database", "test_activity", "test_activity_database"),
]

passed = 0
failed = 0

for test_name, test_module, test_func_name in tests:
    print(f"\nRunning {test_name} tests...")
    print("-" * 80)
    try:
        module = importlib.import_module(test_module)
        if hasattr(module, test_func_name):
            test_func = getattr(module, test_func_name)
            test_func()
            passed += 1
            print(f"[PASS] {test_name} tests PASSED")
        else:
            print(f"[FAIL] {test_name} tests FAILED - test function '{test_func_name}' not found")
            print(f"Available functions: {[x for x in dir(module) if x.startswith('test_')]}")
            failed += 1
    except Exception as e:
        print(f"[FAIL] {test_name} tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

print("\n" + "=" * 80)
print(f"Test Results: {passed} passed, {failed} failed")
print("=" * 80)

if failed > 0:
    sys.exit(1)
