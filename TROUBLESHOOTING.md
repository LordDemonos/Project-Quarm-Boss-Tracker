# Troubleshooting Guide

For first-time Discord setup (webhook URL and bot token), use **Help** → **Quick Start** in the app for a step-by-step guide.

## Enabling Debug Logging

When troubleshooting issues, enable debug logging to see detailed information about all operations.

### Method 1: Command Line Argument (Easiest)

```bash
# Windows PowerShell
python run.py --debug

# Windows CMD
python run.py --debug

# Or use short form
python run.py -d
```

### Method 2: Environment Variable

```bash
# Windows PowerShell
$env:EQ_BOSS_TRACKER_DEBUG="true"
python run.py

# Windows CMD
set EQ_BOSS_TRACKER_DEBUG=true
python run.py

# Linux/Mac
export EQ_BOSS_TRACKER_DEBUG=true
python run.py
```

### Method 3: Set Specific Log Level

```bash
# Windows PowerShell
python run.py --log-level DEBUG

# Or via environment variable
$env:EQ_BOSS_TRACKER_LOG_LEVEL="DEBUG"
python run.py
```

Available log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

## Data and log locations

All paths below use the app’s data directory. Backups live in a `backups` subfolder; logs in `logs`.

| Platform | Data directory |
|----------|----------------|
| **Windows** | `%APPDATA%\boss tracker\` (e.g. `C:\Users\<You>\AppData\Roaming\boss tracker\`) |
| **macOS** | `~/Library/Application Support/boss tracker/` |
| **Linux** | `~/.config/boss tracker/` |

### Log files

- **Path**: `<data directory>\logs\boss_tracker_YYYYMMDD.log`
- **Example (Windows)**: `C:\Users\<YourUsername>\AppData\Roaming\boss tracker\logs\boss_tracker_20260209.log`

## What Gets Logged

### INFO Level (Default)
- All save/load operations
- Boss additions/removals
- Respawn time changes
- Kill count updates
- Discord sync operations
- Errors and warnings

### DEBUG Level (Verbose)
- Everything from INFO level, plus:
- Detailed file operations
- Internal state changes
- Function entry/exit
- Data structure details
- All debug messages

## Log Tags

Look for these tags in logs to find specific operations:

- `[INIT]` - Initialization and startup
- `[LOAD]` - Loading data from files
- `[SAVE]` - Saving data to files
- `[BACKUP]` - Backup creation
- `[MERGE]` - Merging defaults with user data
- `[RESPAWN]` - Respawn time operations
- `[ADD]` - Adding new bosses
- `[KILL]` - Kill count updates
- `[NOTIFICATION]` - System notifications
- `[SOUND]` - Sound playback
- `[DISCORD]` - Discord operations
- `[ACTIVITY]` - Activity log entries
- `[SETTINGS]` - Settings load/save

## Common Issues

### Discord sync not running or kill times not updating from Discord

- **Bot token required**: Discord sync (pulling kill times from your channel) requires a Discord bot token in Settings. If you only use a webhook, the app can post but not read from the channel.
- **Sync interval**: In Settings, check **Discord Sync Interval** (1–168 hours). After changing it, click **Save**; the next sync runs at the new interval.
- **Bot permissions**: The bot must have **Read Message History** and **View Channels** in the channel where the webhook posts. See **Help** → **Quick Start** for the invite steps.

### Activity log empty or not showing today’s entries

- The Activity Log shows **today’s** entries only (by date in your configured timezone). Full history is in the database and in `activity.json` in your data directory.
- If the list is empty, ensure the log directory is set correctly and that kills have been detected today. Use **Tools** → **Scan** to backfill from an existing log file.

### Missing Respawn Times
Look for `[RESPAWN]` tags in logs to see:
- When respawn times are loaded
- When defaults are merged
- Which bosses are missing respawn times

### Data Loss
Look for `[SAVE]` and `[BACKUP]` tags:
- Check if backups were created before saves
- Verify file sizes before/after operations
- Look for errors during save operations

### Missing Kill Times
Look for `[KILL]` tags:
- See when kill counts are incremented
- Check if timestamps are being parsed correctly
- Verify Discord sync operations

## Quick Debug Session

1. **Enable debug logging:**
   ```bash
   python run.py --debug
   ```

2. **Reproduce the issue**

3. **Check the log file:**
   - Open the most recent log file in the logs directory
   - Search for relevant tags (`[SAVE]`, `[LOAD]`, `[RESPAWN]`, etc.)
   - Look for ERROR or WARNING messages

4. **Share logs:**
   - Copy relevant sections from the log file
   - Include timestamps and error messages
   - Note what operation you were performing

## Backup Recovery

### In-app restore (recommended)

1. Open **Settings** (File → Settings or tray → Options).
2. In **Backup & Restore**, click **Restore from Backup...**.
3. Choose a backup from the list (newest first) and confirm. The app will replace `bosses.json` with the selected backup and reload.

### Manual restore from backups folder

- **Windows**: `%APPDATA%\boss tracker\backups\`
- **macOS**: `~/Library/Application Support/boss tracker/backups/`
- **Linux**: `~/.config/boss tracker/backups/`

Backup files are named `bosses_backup_YYYYMMDD_HHMMSS.json`. Copy the most recent one to `bosses.json` in the parent directory (same folder that contains `backups`), then restart the app.

### Command-line restore script

From the project root you can list and restore backups without opening the app:

```bash
# List available backups
python restore_backup.py

# Restore a specific backup
python restore_backup.py "path\to\backup\bosses_backup_YYYYMMDD_HHMMSS.json"
```

The script uses the same backup and `bosses.json` locations as the app (see paths above).

## Testing duplicate detection (two instances / two users)

The app has two duplicate mechanisms:

1. **Same log / same machine (9 seconds)** – If the same boss appears twice in the log within 9 seconds (e.g. lockout + zone message), only one Discord post is sent. You already saw this in action.
2. **Discord channel check (3 minutes)** – Before every post, the app uses the **bot token** to read the Discord channel. If a message with that boss name was posted in the last 3 minutes (by this app or another instance), it skips posting. This is what prevents double posts when two people run the app.

To be confident the **channel check** works (e.g. two programs running):

### Prerequisites

- **Bot token** set in Settings (duplicate check is skipped if no bot token).
- **Message Content Intent** enabled for the bot in the Discord Developer Portal.
- Bot invited to the server with **Read Message History** and **View Channels** in the channel where the webhook posts.

### Test with two instances on one PC

1. **First instance** – Run the app normally (or from IDE). Use your usual data directory.
2. **Second instance** – Run a second copy with a **different** data directory so it has its own config but you can point it at the same webhook and bot token:
   - **Windows (PowerShell):**  
     `$env:APPDATA="C:\Temp\boss-tracker-test"; python run.py`  
     (Replace with a folder you’re happy to use; that instance will use `C:\Temp\boss-tracker-test\boss tracker\` for settings.)
   - Or copy your existing `%APPDATA%\boss tracker` to another folder and run with `APPDATA` pointing there; set the same webhook URL and bot token in both.
3. **Same log source** – Point both at the same log directory (or use Boss Simulation on one and have the other watching the same channel).
4. **Trigger a kill** – Either:
   - Use **Debug → Boss Simulation** on the first instance to post a message to Discord, then trigger the same boss from the second instance (e.g. simulate again or paste a matching log line), or  
   - Have both watching the same log; when one real kill is detected, the first instance posts and the second should see that message in the channel and skip.
5. **Check logs** – In the second instance’s log, look for:
   - `"Checking for duplicate: <BossName> at ..."` (from `discord_checker`)
   - `"Duplicate found: <BossName> posted X seconds ago"`
   - `"Duplicate detected for <BossName>, skipping Discord post"`
   - Activity log: **"Duplicate detected, skipped"** for that kill.

If the second instance does **not** have a bot token or the checker isn’t ready, you’ll see `"Discord checker not ready, cannot check for duplicates"` or no channel check, and it might post anyway (or skip for other reasons).

### Test with two PCs (or PC + VM)

- Run the app on two machines, same webhook URL and same (or different) bot tokens. When the same boss is killed and both see it (e.g. same guild log), the first to post wins; the other should see that message in the channel and skip. Use the same log lines above to confirm the second instance performed the channel check and got “Duplicate found”.

### Quick sanity check without two instances

- Post a boss kill to Discord (e.g. with Simulation or a real kill). Within 3 minutes, trigger the **same** boss again from the same instance (e.g. simulate again or paste the same line). The second time you should see “Duplicate found” and “Duplicate detected, skipped” in the log and in the Activity log, because the checker sees the first message in the channel.
