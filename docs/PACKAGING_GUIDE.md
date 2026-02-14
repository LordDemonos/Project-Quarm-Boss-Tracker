# Packaging Guide

## Pre-populating Boss Database

To include your collected bosses in the packaged application:

1. **Copy your current bosses.json** to one of these locations (checked in order):
   - `data/bosses.json` (preferred)
   - `assets/bosses.json`
   - `bosses.json` (root directory)

2. **When packaging**, ensure the bosses.json file is included in the package:
   - For PyInstaller: Add `--add-data "data/bosses.json;data"` or similar
   - For other packagers: Include the file in the application directory

3. **On first run**, the application will:
   - Check if user's `data/bosses.json` exists
   - If not, copy the default `bosses.json` from the app directory
   - User's data directory will be created automatically

## Security Features

Sensitive data is encrypted before saving:

- **Encrypted fields:**
  - `default_webhook_url` in settings.json
  - `discord_bot_token` in settings.json
  - `webhook_url` in individual boss entries (bosses.json)

- **Encryption method:** XOR cipher with base64 encoding (obfuscation, not true security)
- **Note:** This prevents casual viewing but determined users can still decrypt. For production, consider stronger encryption.

## File Structure

```
Application Directory/
├── bosses.json (default, will be copied to user data on first run)
├── data/
│   └── bosses.json (alternative location)
├── assets/
│   └── bosses.json (alternative location)
└── [executable]

User Data Directory (created on first run)/
├── data/
│   ├── bosses.json (user's boss database)
│   ├── settings.json (encrypted sensitive fields)
│   └── activity.json
└── logs/
```

## Testing

Before packaging:
1. Copy your `data/bosses.json` to the app directory
2. Delete user's `data/bosses.json` (or rename it)
3. Run the application
4. Verify that bosses are loaded from the default file
5. Verify that new bosses are saved to user's data directory
