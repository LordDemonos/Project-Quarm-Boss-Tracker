# EverQuest Boss Tracker - Testing Plan

## Testing Phases

### Phase 1: Core Functionality (No Discord)
Test all core components without Discord integration.

### Phase 2: UI Testing
Test all UI components and user interactions.

### Phase 3: Log File Simulation
Test with simulated log files and generated log lines.

### Phase 4: Live Log Monitoring
Test with actual EverQuest log files (monitoring mode).

### Phase 5: Discord Integration
Test Discord webhook posting and duplicate detection.

---

## Phase 1: Core Functionality Testing

### 1.1 Message Parser
**Goal**: Verify parsing of log messages

**Test Cases**:
- [ ] Parse valid boss kill message
- [ ] Parse message with special characters in boss name
- [ ] Parse message with multi-word zone names
- [ ] Reject non-matching log lines
- [ ] Handle edge cases (empty fields, malformed messages)

**How to Test**:
```python
# Use test_log_generator.py to create test messages
python test_utilities/test_log_generator.py --test-parser
```

### 1.2 Boss Database
**Goal**: Verify database operations

**Test Cases**:
- [ ] Add new boss
- [ ] Add boss with location
- [ ] Enable/disable boss
- [ ] Remove boss
- [ ] Get bosses by location
- [ ] Increment kill count
- [ ] Persistence (save/load)

**How to Test**:
```python
# Use test_utilities/test_database.py
python test_utilities/test_database.py
```

### 1.3 Timestamp Formatter
**Goal**: Verify timezone conversion and Discord timestamp formatting

**Test Cases**:
- [ ] Parse log timestamp (EST)
- [ ] Convert to user timezone
- [ ] Format Discord timestamp (full)
- [ ] Format Discord timestamp (relative)
- [ ] Handle timezone changes
- [ ] Compare timestamps for duplicates

**How to Test**:
```python
# Use test_utilities/test_timestamp.py
python test_utilities/test_timestamp.py
```

### 1.4 Activity Database
**Goal**: Verify activity log storage and filtering

**Test Cases**:
- [ ] Add activity entry
- [ ] Filter today's activities
- [ ] Store full history
- [ ] Clear old activities
- [ ] Persistence

**How to Test**:
```python
# Use test_utilities/test_activity.py
python test_utilities/test_activity.py
```

---

## Phase 2: UI Testing

### 2.1 Main Window
**Goal**: Verify main window displays and functions

**Test Cases**:
- [ ] Window opens on startup
- [ ] Window minimizes to tray
- [ ] Window restores from tray
- [ ] Menu bar functions
- [ ] Status bar updates

**How to Test**:
- Run application: `python run.py`
- Check window appears
- Test minimize/restore
- Test menu items

### 2.2 Zone Group Widget
**Goal**: Verify zone grouping and controls

**Test Cases**:
- [ ] Bosses grouped by zone
- [ ] Individual boss checkboxes work
- [ ] "Enable All" button works
- [ ] "Disable All" button works
- [ ] Zone groups display correctly
- [ ] Empty zones handled

**How to Test**:
- Add test bosses via database
- Verify grouping in UI
- Test enable/disable controls

### 2.3 Activity Log Widget
**Goal**: Verify activity log display

**Test Cases**:
- [ ] Shows today's entries only
- [ ] Auto-scrolls to newest
- [ ] Color coding works
- [ ] Handles many entries
- [ ] Updates in real-time

**How to Test**:
- Add test activities
- Verify display
- Test scrolling

### 2.4 Options Window
**Goal**: Verify settings management

**Test Cases**:
- [ ] All settings display correctly
- [ ] Timezone selection works
- [ ] Settings save/load
- [ ] Log directory browser works
- [ ] Active character displays

**How to Test**:
- Open Options from menu
- Change settings
- Save and verify persistence

### 2.5 New Boss Dialog
**Goal**: Verify new boss discovery dialog

**Test Cases**:
- [ ] Dialog appears (non-modal)
- [ ] "Yes" enables boss
- [ ] "No" disables boss
- [ ] Window pop-up setting respected
- [ ] Windows notification setting respected

**How to Test**:
- Simulate new boss discovery
- Test dialog behavior

### 2.6 Message Editor
**Goal**: Verify message template editing

**Test Cases**:
- [ ] Template loads correctly
- [ ] Preview updates
- [ ] Discord timestamp variables work
- [ ] Validation works
- [ ] Save works

**How to Test**:
- Open Message Format editor
- Edit template
- Test preview
- Save and verify

---

## Phase 3: Log File Simulation

### 3.1 Test Log Generator
**Goal**: Create test log files with various scenarios

**Test Cases**:
- [ ] Generate log file with multiple boss kills
- [ ] Generate log file with different zones
- [ ] Generate log file with various timestamps
- [ ] Simulate active file switching

**How to Test**:
```python
# Generate test log file
python test_utilities/test_log_generator.py --output test_logs/eqlog_TestChar_pq.proj.txt

# Point application to test_logs directory
# Watch application detect and process entries
```

### 3.2 Log Monitor
**Goal**: Verify log file monitoring

**Test Cases**:
- [ ] Detects log files
- [ ] Identifies active file
- [ ] Extracts character name
- [ ] Tails file for new lines
- [ ] Handles file switching
- [ ] Handles file locking

**How to Test**:
- Use test log generator
- Monitor with application
- Verify detection and parsing

---

## Phase 4: Live Log Monitoring

### 4.1 Real Log File Monitoring
**Goal**: Test with actual EverQuest log files

**Test Cases**:
- [ ] Application detects real log files
- [ ] Identifies active character
- [ ] Parses real guild messages
- [ ] Handles real log file format
- [ ] Updates UI in real-time

**How to Test**:
1. Configure log directory to actual EQ logs
2. Start application
3. Play EverQuest and trigger guild messages
4. Watch application detect and process

**Expected Behavior**:
- Application shows active character
- New bosses trigger dialog
- Activity log updates
- No Discord posting (simulated)

---

## Phase 5: Discord Integration

### 5.1 Mock Discord (Initial Testing)
**Goal**: Test Discord posting without real webhook

**Test Cases**:
- [ ] Message formatting works
- [ ] Discord timestamp formatting works
- [ ] Posting logic executes
- [ ] Error handling works

**How to Test**:
- Use mock Discord notifier
- Verify message format
- Check logs for posting attempts

### 5.2 Real Discord Webhook
**Goal**: Test actual Discord posting

**Test Cases**:
- [ ] Webhook URL validation
- [ ] Message posts successfully
- [ ] Message format correct
- [ ] Timestamps display correctly
- [ ] Error handling for invalid webhook

**How to Test**:
1. Set up Discord webhook
2. Configure in application
3. Trigger test boss kill
4. Verify message in Discord

### 5.3 Duplicate Detection
**Goal**: Test duplicate detection with Discord bot

**Test Cases**:
- [ ] Bot token validation
- [ ] Channel message reading
- [ ] Duplicate detection logic
- [ ] Timezone handling in duplicates
- [ ] Skips posting when duplicate found

**How to Test**:
1. Set up Discord bot
2. Configure bot token
3. Post message manually to Discord
4. Trigger same boss kill within 3 minutes
5. Verify duplicate detected and skipped

---

## Test Utilities

### test_log_generator.py
Generates test log files with various scenarios.

### test_database.py
Tests database operations.

### test_timestamp.py
Tests timestamp formatting.

### test_activity.py
Tests activity log.

### mock_discord.py
Mocks Discord webhook for testing without real Discord.

---

## Testing Checklist

### Pre-Testing Setup
- [ ] Install all dependencies
- [ ] Create test directories
- [ ] Backup any existing data files

### Phase 1: Core Functionality
- [ ] Message parser works
- [ ] Boss database works
- [ ] Timestamp formatter works
- [ ] Activity database works

### Phase 2: UI Testing
- [ ] Main window displays
- [ ] Zone grouping works
- [ ] Activity log displays
- [ ] Options window works
- [ ] New boss dialog works
- [ ] Message editor works

### Phase 3: Log Simulation
- [ ] Test log generator works
- [ ] Log monitor detects files
- [ ] Parsing works with test logs

### Phase 4: Live Monitoring
- [ ] Real log files detected
- [ ] Real messages parsed
- [ ] UI updates correctly

### Phase 5: Discord Integration
- [ ] Mock Discord works
- [ ] Real webhook works
- [ ] Duplicate detection works

---

## Known Issues to Watch For

1. **Discord Checker Async**: May need adjustment for Qt event loop
2. **File Locking**: Log files may be locked by EverQuest
3. **Timezone Detection**: May need manual timezone selection
4. **Character Name Extraction**: Edge cases with special characters
5. **Window Pop-up**: May interfere with gameplay

---

## Success Criteria

- [ ] All core functionality works without Discord
- [ ] UI displays and functions correctly
- [ ] Log monitoring works with real files
- [ ] Discord posting works correctly
- [ ] Duplicate detection prevents spam
- [ ] No crashes or errors in logs
- [ ] Performance is acceptable
