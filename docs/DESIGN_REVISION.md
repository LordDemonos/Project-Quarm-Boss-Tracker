# EverQuest Boss Tracker - Revised Design

## Updated Requirements

### Core Functionality
- Monitor EverQuest (TAKP) log files in real-time
- Parse guild messages about boss kills
- Post notifications to Discord via webhook
- **Discord deduplication** - Check channel for duplicate posts within 3 minutes to prevent spam
- Support customizable message templates
- Sound notification on boss kill (optional)
- Auto-discover new targets from log messages

### UI Requirements (REVISED)

#### Main Window (Primary Interface)
- **Always visible or accessible** - Main application window, not just system tray
- **Target List View** - Shows all tracked bosses/targets
- **Grouped by Zone** - Targets organized by location/zone (e.g., "Vex Thal", "The Emerald Jungle")
- **Checkboxes** - Each target has a checkbox to enable/disable Discord posting
- **Zone-level Controls** - Checkbox or button to enable/disable all targets in a zone at once
- **Activity Log** - Shows recent activity: when targets were found and posted to Discord
- **Add/Remove Targets** - UI controls to manually add or remove targets

#### System Tray (Secondary)
- **Minimize to tray** - Option to minimize main window to system tray
- **Quick access** - Double-click tray icon to show main window
- **Context menu** - Options, Exit (no balloon notifications needed)

### Data Structure Changes

#### Boss Database Schema
```json
{
  "bosses": [
    {
      "name": "Aten Ha Ra",
      "location": "Vex Thal",
      "enabled": true,
      "webhook_url": null,
      "first_seen": "2025-11-22T23:02:42",
      "kill_count": 0,
      "last_killed": null
    }
  ]
}
```

**Message Format**: `[timestamp] Server tells the guild, 'Person of <Guild> has killed Target in Zone!'`
- Target name: Between "killed" and "in"
- Zone name: Between "in" and "!"

#### Activity Log Schema
```json
{
  "activity": [
    {
      "timestamp": "2025-11-22T23:02:42",
      "date": "2025-11-22",
      "monster": "Aten Ha Ra",
      "location": "Vex Thal",
      "player": "Saelilya",
      "guild": "Former Glory",
      "posted_to_discord": true,
      "discord_message": "[Sat Nov 22 23:02:42 2025] Aten Ha Ra",
      "discord_message_id": "1234567890"
    }
  ]
}
```

**Note**: Activity log filtered to show only today's entries in UI, but all entries stored for history.

## UI Layout Design

### Main Window Structure

```
┌─────────────────────────────────────────────────────────┐
│ EverQuest Boss Tracker                    [Settings] [X]   │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Targets (Grouped by Zone)                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ▼ Vex Thal                          [Enable All]  │  │
│  │   ☑ Aten Ha Ra                                      │  │
│  │   ☑ Phara Dar                                       │  │
│  │   ☐ Vex Thal Boss 3                                 │  │
│  │   ☑ Vex Thal Boss 4                                 │  │
│  │                                                      │  │
│  │ ▼ The Emerald Jungle                 [Enable All]  │  │
│  │   ☑ Severilous                                      │  │
│  │   ☐ Other Boss                                      │  │
│  │                                                      │  │
│  │ ▼ Other Zone                         [Enable All]  │  │
│  │   ☐ Boss 1                                          │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  [Add Target]  [Remove Selected]  [Refresh]              │
│                                                           │
├─────────────────────────────────────────────────────────┤
│  Activity Log                                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │ [23:02:42] Aten Ha Ra (Vex Thal) - Posted to Discord│  │
│  │ [23:15:30] Severilous (Emerald Jungle) - Posted    │  │
│  │ [23:45:12] Phara Dar (Vex Thal) - Posted           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  Status: Monitoring Xanax (pq.proj)                      │
└─────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. Main Window (`main_window.py`) - NEW
- **QMainWindow** with menu bar
- **Left Panel**: Target list grouped by zone (QTreeWidget or custom widget)
- **Right Panel**: Activity log (QTextEdit or QListWidget)
- **Status Bar**: Shows active character being monitored
- **Menu**: File (Settings, Exit), View (Refresh)

#### 2. Zone Group Widget (`zone_group_widget.py`) - NEW
- **QGroupBox** or custom widget for each zone
- **Header**: Zone name + "Enable All" checkbox/button
- **List**: Individual target checkboxes
- **Collapsible**: Can expand/collapse zones

#### 3. Activity Log (`activity_log.py`) - NEW
- **QListWidget** or **QTextEdit** showing recent activity
- **Auto-scroll** to newest entries
- **Format**: `[timestamp] Target Name (Zone) - Status`
- **Color coding**: Success (green), Error (red)

#### 4. Options Window (REVISED)
- **Simplified** - Just settings (log directory, webhook URL, sound)
- **Remove** boss management from here (moved to main window)

#### 5. System Tray (SIMPLIFIED)
- **Remove** balloon notifications for new boss discovery
- **Keep** context menu (Show Window, Options, Exit)
- **Double-click** to show main window

## Implementation Changes

### Files to Create
1. `src/main_window.py` - Main application window
2. `src/zone_group_widget.py` - Zone grouping widget
3. `src/activity_log.py` - Activity log component
4. `src/activity_database.py` - Activity log persistence
5. `src/discord_checker.py` - Check Discord channel for duplicate messages
6. `src/new_boss_dialog.py` - Dialog to prompt user when new boss discovered
7. `src/timestamp_formatter.py` - Handle timezone conversion and Discord timestamp formatting

### Files to Modify
1. `src/main.py` - Change to show main window instead of just tray
2. `src/options_window.py` - Remove boss management, add timezone selection
3. `src/boss_database.py` - Add location/zone field support
4. `src/system_tray.py` - Remove balloon notification code
5. `src/discord_notifier.py` - Add deduplication check, Discord timestamp formatting
6. `src/message_parser.py` - Ensure proper parsing of target and zone
7. `src/message_editor.py` - Add Discord timestamp variable hints

### Files to Keep (Unchanged)
- `src/message_parser.py`
- `src/discord_notifier.py`
- `src/sound_player.py`
- `src/log_monitor.py`
- `src/message_editor.py` (can be accessed from main window menu)

## User Workflow

1. **Start Application**
   - Main window opens automatically (can minimize to tray)
   - Shows all discovered targets grouped by zone
   - Activity log shows today's entries only

2. **Auto-Discovery**
   - When new target detected in logs:
     - Dialog appears: "New target discovered: [Target] in [Zone]. Enable Discord posting?"
     - User chooses Yes (enabled) or No (disabled)
     - Target added to appropriate zone group
     - Zone auto-created if it doesn't exist

3. **Configure Targets**
   - Targets listed by zone with checkboxes
   - User checks boxes to enable Discord posting
   - Can enable entire zone with one click ("Enable All" button)
   - Targets persist across sessions

4. **Monitor Activity**
   - When target is killed and enabled:
     - Check Discord for duplicates (within 3 minutes)
     - If no duplicate: Post to Discord, show in activity log
     - If duplicate: Skip posting, log "Duplicate detected"
   - Activity log shows: `[timestamp] Target (Zone) - Posted to Discord`
   - Sound plays (if enabled)

5. **Manage Targets**
   - Add target manually: Click "Add Target", enter name and zone
   - Remove target: Select and click "Remove Selected"
   - Enable/disable: Use checkboxes

## Key Features

### Zone Grouping
- Targets automatically grouped by `location` field from log messages
- Zones auto-created when new zone detected in logs
- Zones can be collapsed/expanded
- Zone header shows count: "Vex Thal (4 targets, 3 enabled)"
- "Enable All" button per zone to toggle all targets in that zone

### Activity Log
- **Shows only today's entries** (filtered view)
- All entries stored in database for history
- Persists to file (activity.json)
- Auto-scrolls to newest
- Shows: timestamp, target name, zone, status
- Status: "Posted to Discord" or "Duplicate detected, skipped"

### Discord Timestamp Formatting
- **Discord's timezone-aware timestamps**: Use Discord's special timestamp format `<t:unix_timestamp:format>`
  - Automatically displays in each viewer's local timezone
  - Formats: `<t:1234567890>` (default), `<t:1234567890:F>` (long date/time), `<t:1234567890:R>` (relative)
- **Timezone detection**: Auto-detect from system timezone, allow manual override
- **Conversion process**:
  1. Parse log timestamp (EST/server time)
  2. Convert to user's timezone (from settings)
  3. Convert to Unix timestamp
  4. Format as Discord timestamp: `<t:unix_timestamp:F>`
- **Message template**: Supports Discord timestamp placeholders
  - `{discord_timestamp}` - Full date/time format
  - `{discord_timestamp_relative}` - Relative format ("2 minutes ago")
  - `{timestamp}` - Original log timestamp (for fallback)

### Discord Deduplication
- Before posting, fetch recent messages from Discord channel
- Check for same target name within last 3 minutes
- **Timezone handling**: Server time is EST, but account for user timezones (CST, PST, etc.)
  - Check timestamps within 3-minute window, accounting for up to +/- 3 hour timezone differences
  - Compare target name and approximate timestamp (within tolerance)
  - When comparing, convert Discord message timestamps to EST for comparison
- Requires Discord bot token (webhooks can't read messages)
- Logs when duplicate detected (doesn't post)
- Configurable: 3 minutes default, can be adjusted in settings

### Real-time Updates
- When boss kill detected and posted, immediately add to activity log
- Update target's last_killed timestamp
- Increment kill count
- UI updates instantly

### Auto-Discovery Dialog
- **Non-modal dialog** when new target detected (doesn't block app)
- Shows: Target name, Zone name
- Options: "Yes, enable posting" / "No, disable posting"
- Target added to database with user's choice
- **Window pop-up behavior**: Configurable setting
  - If enabled: Window pops up and becomes visible when new boss detected
  - If disabled: Window stays minimized, optional Windows notification shown
- **Windows notification**: Optional system tray notification when window is minimized

## Data Flow (Revised)

1. Log monitor detects new line
2. Parser extracts boss kill info (monster, location, etc.)
   - Format: `Person of <Guild> has killed Target in Zone!`
   - Target: Between "killed" and "in"
   - Zone: Between "in" and "!"
3. Check if monster exists in database
   - **If new**: 
     - Show dialog: "New target discovered: [Target] in [Zone]. Enable Discord posting?"
     - Add to database with user's choice (enabled=true/false)
     - Auto-create zone group if zone doesn't exist
     - Update UI
   - **If exists**: Check if enabled
4. If enabled:
   - **Check Discord channel** for duplicate posts within last 3 minutes
     - Fetch recent messages from webhook's channel
     - Compare target name and timestamp
     - **Account for timezone differences**: Server time is EST, but users may be in CST/PST/etc (up to +/- 3 hours)
     - Convert Discord message timestamps to EST for comparison
     - Check if timestamp is within 3 minutes, accounting for timezone offset
     - If duplicate found: Skip posting, log "Duplicate detected, skipped"
   - If no duplicate:
     - **Format Discord timestamp**: Convert log timestamp to user's timezone, then to Unix timestamp
     - Format message with Discord timestamp: `<t:unix_timestamp:F>` (or user's preferred format)
     - Post to Discord
     - Add entry to activity log (with message ID)
     - Update UI (activity log, last_killed)
     - Play sound
5. UI updates in real-time
6. Activity log shows only today's entries (filtered view)

## Settings (Simplified)

- Log directory
- Discord webhook URL
- **Discord bot token** (for reading channel messages for deduplication)
- **Timezone** (auto-detected from system, can be manually overridden)
- Sound enabled/disabled
- Sound file path
- Message template (accessed via menu)
- Deduplication window (default 3 minutes, configurable)
- **Window pop-up on new boss** (enable/disable)
- **Windows notification on new boss** (enable/disable, only when window minimized)

## Implementation Notes

### Discord Deduplication Implementation

**Discord Bot Token (Required)**
- User provides bot token in settings
- Bot can read channel messages via Discord API
- Fetch last N messages (enough to cover 3 minutes + timezone buffer)
- Check for duplicates:
  - Match target name (exact match)
  - Check timestamp within 3-minute window
  - Account for timezone differences (server time EST, users may be CST/PST/etc)
  - Compare timestamps with tolerance for timezone offset

**Timezone Handling**:
- **Server time**: EST (from log timestamps)
- **User timezone**: Auto-detected from system, can be manually set
- **Discord timestamps**: Use Discord's `<t:unix_timestamp:format>` for timezone-aware display
- **Conversion**:
  1. Parse log timestamp (EST/server time)
  2. Convert to user's timezone (from settings)
  3. Convert to Unix timestamp
  4. Format as Discord timestamp in message
- **Duplicate checking**:
  1. Parse Discord message timestamp (UTC from Discord API)
  2. Convert to EST for comparison
  3. Compare with log timestamp (already EST)
  4. Check if within 3-minute window

**Bot Setup Instructions** (for README):
1. Go to Discord Developer Portal (https://discord.com/developers/applications)
2. Create new application or select existing
3. Go to "Bot" section
4. Click "Add Bot"
5. Under "Token", click "Reset Token" and copy the token
6. Enable "Message Content Intent" under "Privileged Gateway Intents"
7. Invite bot to server with "Read Message History" permission
8. Paste token into application settings

### Message Parsing

Regex pattern: `\[(.+?)\] (.+?) tells the guild, '(.+?) of <(.+?)> has killed (.+?) in (.+?)!'`

Groups:
1. Timestamp
2. Server
3. Player
4. Guild
5. **Target** (monster name)
6. **Zone** (location)

Target extraction: Group 5 (between "killed" and "in")
Zone extraction: Group 6 (between "in" and "!")

### Activity Log Filtering

- Store all entries with date field
- UI filter: `date == today` (shows only today's entries)
- Database keeps full history (all entries stored)
- Can add "Show All" toggle in future

### Window Behavior Settings

- **Pop-up on new boss**: Toggle to show/hide window when new target detected
  - Enabled: Window pops up and becomes visible
  - Disabled: Window stays minimized
- **Windows notification**: Optional system tray notification
  - Only shown when window is minimized
  - Shows: "New target: [Target] in [Zone]"
  - Can be enabled/disabled independently

## Phase 2 Features (Future)

- Per-boss webhook URLs
- Multiple Discord channels
- Statistics view (kill counts, most active zones)
- Export activity log
- Filter activity log by zone/target
- Historical activity view (beyond today)
