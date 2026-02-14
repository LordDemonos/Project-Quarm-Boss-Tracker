# Pre-Flight Checklist for Live Testing

## ✅ Required for Discord Messages to Send

### 1. **Discord Webhook URL is Set**
   - ✅ Open Settings (File → Settings or System Tray → Options)
   - ✅ Check that "Discord Webhook URL" field has a valid URL
   - ✅ Format should be: `https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN`
   - ✅ **Test**: You can paste the webhook URL in a browser - it should show webhook info (or an error if invalid)

### 2. **Bosses Are Enabled**
   - ✅ Open the main window
   - ✅ Check that at least one boss has its checkbox **checked** (enabled)
   - ✅ The checkbox must be checked for Discord posting to work
   - ✅ You can use "Enable All" button for a zone to enable all bosses in that zone

### 3. **Log Directory is Configured**
   - ✅ Settings → "Log Directory" should point to your EverQuest log folder
   - ✅ Example: `C:\TAKP\Logs` or wherever your `eqlog_*.txt` files are
   - ✅ The application will only monitor the most recently modified log file

### 4. **Application is Running**
   - ✅ Start the application: `python run.py`
   - ✅ Check system tray - icon should be visible
   - ✅ Main window should show your configured bosses
   - ✅ Status bar should show "Monitoring: [CharacterName]"

## ⚠️ Optional (But Recommended)

### 5. **Discord Bot Token (for Duplicate Detection)**
   - ⚠️ Not required for messages to send
   - ⚠️ Only needed if you want duplicate detection (prevents spam if multiple people run it)
   - ⚠️ If not set, messages will still post, but won't check for duplicates

### 6. **Sound File (Optional)**
   - ⚠️ Only needed if you want sound notifications
   - ⚠️ Place `fanfare.mp3` in `assets/` directory
   - ⚠️ Can be enabled/disabled in settings

## 🔍 How to Verify Everything is Working

### Check Logs
- Logs are stored in: `data/logs/`
- Look for:
  - `"Discord notifier worker thread started"` - confirms Discord notifier is running
  - `"Parsed boss kill: [BossName] in [Zone]"` - confirms log parsing is working
  - `"Posted to Discord: [BossName]"` - confirms message was sent
  - `"Error sending Discord notification"` - indicates a problem

### Test Flow
1. ✅ Application is running
2. ✅ At least one boss is enabled (checkbox checked)
3. ✅ Webhook URL is set in settings
4. ✅ Log directory is configured correctly
5. ✅ When a boss kill happens in-game, check:
   - Activity Log (right pane) should show the kill
   - Discord channel should receive the message
   - Logs should show "Posted to Discord"

## 🚨 Common Issues

### Messages Not Sending?
- **Check webhook URL**: Make sure it's valid and not expired
- **Check boss is enabled**: The checkbox must be checked!
- **Check logs**: Look in `data/logs/` for error messages
- **Check network**: Make sure you have internet connection

### Wrong Channel?
- The webhook URL determines which channel messages go to
- To change channels: Create a new webhook in the desired channel and update the URL in settings

### Boss Not Detected?
- Check log file format matches: `eqlog_CharacterName_ServerName.txt`
- Check that the log line format matches: `[timestamp] Server tells the guild, 'Player of <Guild> has killed BossName in ZoneName!'`
- Check logs for parsing errors

## ✅ Ready to Test!

If all the required items above are checked, you're ready for live testing! The application will:
1. Monitor your log file for new entries
2. Parse boss kill messages
3. Post to Discord when enabled bosses are killed
4. Show activity in the Activity Log

Good luck with your raid! 🎮
