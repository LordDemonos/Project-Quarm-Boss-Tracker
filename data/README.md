# Project `data/` folder

This folder is **not** used for normal app storage at runtime and **is not included** in the installer.

## Where the app actually stores data

At runtime the app uses the **user data directory** (not this folder):

- **Windows**: `%APPDATA%\boss tracker\` (e.g. `C:\Users\<You>\AppData\Roaming\boss tracker\`)
- **macOS**: `~/Library/Application Support/boss tracker/`
- **Linux**: `~/.config/boss tracker/`

There it keeps: `settings.json`, `bosses.json`, `activity.json`, `backups/`, `captures/`, `logs/`.

## How this folder is used

- **Read-only fallback for default bosses**: When loading the boss list, the app can use `data/bosses.json` as one possible **default** source (after `default_bosses.json`, before `assets/bosses.json`) if the user has no bosses file yet. It never writes here.
- **Git**: `data/*.json` and `data/logs/` are in `.gitignore`, so local copies in this folder are not committed. You can keep optional `data/bosses.json` or example files for development; the installer does not bundle this folder.

You can leave this folder empty or use it for local dev defaults only.
