# Test Utilities

Utilities for testing the EverQuest Boss Tracker application.

## Quick Start

### Run All Unit Tests
```bash
python test_utilities/run_all_tests.py
```

### Run Individual Tests
```bash
# Test message parser
python test_utilities/test_parser.py

# Test boss database
python test_utilities/test_database.py

# Test timestamp formatter
python test_utilities/test_timestamp.py

# Test activity database
python test_utilities/test_activity.py
```

### Generate Test Log File
```bash
# Generate test log with 20 entries
python test_utilities/test_log_generator.py --output test_logs/eqlog_TestChar_pq.proj.txt --entries 20

# Append a new recent entry (simulates new kill)
python test_utilities/test_log_generator.py --append --monster "TestBoss" --location "Test Zone" --output test_logs/eqlog_TestChar_pq.proj.txt
```

### Run Application in Mock Mode (No Real Discord)
```bash
# Windows PowerShell
$env:EQ_BOSS_TRACKER_MOCK_DISCORD="true"
python run.py

# Windows CMD
set EQ_BOSS_TRACKER_MOCK_DISCORD=true
python run.py

# Linux/Mac
export EQ_BOSS_TRACKER_MOCK_DISCORD=true
python run.py
```

In mock mode:
- Discord messages will be logged to console and log file
- No actual Discord webhook calls will be made
- Perfect for testing without Discord setup

## Testing Workflow

### Phase 1: Unit Tests
1. Run all unit tests: `python test_utilities/run_all_tests.py`
2. Verify all tests pass
3. Check logs for any warnings

### Phase 2: UI Testing
1. Run application: `python run.py`
2. Test all UI components manually
3. Verify settings save/load
4. Test boss management

### Phase 3: Log File Testing
1. Generate test log file
2. Configure application to use test_logs directory
3. Watch application detect and process entries
4. Verify parsing and UI updates

### Phase 4: Mock Discord Testing
1. Run in mock mode: `set EQ_BOSS_TRACKER_MOCK_DISCORD=true && python run.py`
2. Configure settings (webhook URL can be fake in mock mode)
3. Trigger test boss kills
4. Verify messages are logged (not posted)

### Phase 5: Live Testing
1. Configure with real log directory
2. Run application normally
3. Play EverQuest and trigger guild messages
4. Watch application detect and process

### Phase 6: Real Discord Testing
1. Set up Discord webhook and bot
2. Configure in application
3. Test actual posting
4. Test duplicate detection

## Test Files

- `test_parser.py` - Tests message parsing
- `test_database.py` - Tests boss database operations
- `test_timestamp.py` - Tests timestamp formatting
- `test_activity.py` - Tests activity log
- `test_log_generator.py` - Generates test log files
- `mock_discord.py` - Mock Discord for testing
- `run_all_tests.py` - Runs all unit tests

## Mock Discord

The mock Discord notifier:
- Logs all messages to console and log file
- Shows "MOCK DISCORD POST" banner
- Does not make actual HTTP requests
- Perfect for testing message formatting

To use mock Discord, set environment variable:
```bash
EQ_BOSS_TRACKER_MOCK_DISCORD=true
```
