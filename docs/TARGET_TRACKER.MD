### Functional Requirements

- Monitor EverQuest log file in real-time for new lines.
- Parse lines to detect guild messages about boss kills.
- Allow user to maintain a list of tracked monster names (add/remove).
- If a boss kill line matches a monster in the list, post the timestamp and monster name to Discord (using a webhook).
- Message format should be: `[timestamp] [monster name]`

***

### Discord Webhook Setup

1. **Access Discord Server Settings:**
   - Go to your Discord server and select the channel to receive notifications.[1][2][3]

2. **Create a Webhook:**
   - Click channel settings → Integrations → Create Webhook.
   - Name the webhook and select your target channel.
   - Copy the generated webhook URL for use in your script.

***

### High-Level Architecture

**Components:**

- Log Monitor: Tails the EverQuest log file for new lines.[4][5]
- Parser/Filter: Extracts monster names from lines with boss kill messages; matches names against the tracked monster list.
- Config Management: Allows update of the monster list (console commands, simple config file, or JSON).
- Discord Notifier: Sends formatted messages to the Discord webhook.

***

### Example Data Flow

1. The script "tails" the log file for real-time reading.
2. Each new line is checked for the signature boss kill message (via regex/string match).
3. The parser extracts the monster name for comparison.
4. If the monster name is in the tracked list, the Discord notifier sends `[timestamp] [monster name]` to your webhook.

***

### Skeleton Python Implementation

**Dependencies:**
- Python 3.x
- `requests` (for posting to Discord webhook)
- Optional: `re` for regex parsing

**Example Core Functions:**

```python
import re
import time
import requests

LOG_FILE = "eqlog_<Your_Character>_server.txt"
WEBHOOK_URL = "<your_discord_webhook_url>"

# Dynamically load tracked monsters from a config file or editable list
tracked_mobs = {"Severilous", "Faydedar", "Master Yael"}

def post_to_discord(msg):
    requests.post(WEBHOOK_URL, json={"contenpythonkilled (.*?) in", line)
    if match:
        timestamp, mob = match.groups()
        return timestamp, mob
    return None, None

def tail_log():
    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
            timestamp, mob = parse_line(line)
            if mob in tracked_mobs:
                post_to_discord(f"[{timestamp}] {mob}")

# Functions to add/remove monsters from tracked_mobs could watch a config file or provide a command-line interface
```

***

### User Management of Monster List

- Store the monster list in a local config file (e.g., `tracked_mobs.json`) for persistence and editability.
- Provide a CLI or script commands to add/remove tracked monsters.
- Reload the monster list periodically or upon command (e.g., send SIGUSR1 signal, check for file changes).

***

### Notes/Enhancements

- Add error handling for webhook delivery and file access.
- Consider letting the script run as a system tray/background process for convenience.
- For advanced customization, build a Discord bot for in-guild commands to manage the monster list remotely. Webhook is simpler and sufficient for notifications.

***

This design combines file monitoring, regex parsing, list filtering, and Discord notification delivery. Edit the monster list for your targets; only tracked monsters will prompt a Discord post, enabling granular control and reducing noise.[6][7]

Let me know if you want a complete implementation or more advanced bot managementt options.

[1](https://www.svix.com/resources/guides/how-to-make-webhook-discord/)
[2](https://hookdeck.com/webhooks/platforms/how-to-get-started-with-discord-webhooks)
[3](https://www.reddit.com/r/discordapp/comments/55eug2/guide_how_to_use_and_create_webhooks/)
[4](https://stackoverflow.com/questions/24818486/get-only-new-lines-from-file)
[5](https://stackoverflow.com/questions/182197/how-do-i-watch-a-file-for-changes)
[6](https://www.geeksforgeeks.org/python/python-filter-a-list-based-on-the-given-list-of-strings/)
[7](https://www.geeksforgeeks.org/python/python-filter-list-of-strings-based-on-the-substring-list/)
[8](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)
[9](https://www.youtube.com/watch?v=fKksxz2Gdnc)
[10](https://discord.com/developers/docs/resources/webhook)