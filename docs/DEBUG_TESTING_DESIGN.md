# Debug Testing Tool – Design Document

Design for the Debug menu (Boss Capture, Boss Simulation, Advanced Settings). Full plan lives in Cursor plans; this doc captures the design and **test-scenario clarifications**.

---

## What we're simulating

We're simulating the **last week** of boss kills from the user's log: same lines, same grouping by timestamp, but with **current timestamps** and a **shortened delay** between batches so we don't have to wait a week. The simulation replays whatever the logs actually had—no fixed pattern.

- **Lockout bosses** (e.g. those in the Lockouts list) often have **only two messages** in the log: the game double-posts the lockout line but does **not** post a zone message for those. So a batch might be 2 lockout lines, or 2 lockout + 1 zone, or 1 zone only, etc., depending on what happened that week.
- **Duration between simulated postings** is configurable **in the Boss Simulation window** (e.g. "Replay interval (seconds)" spinbox, default 30). That way users can shorten the gap between batches for faster testing.

---

## Test-scenario priorities and two-sided verification

**Priority:** Duplicate posts, duplicate-boss popup, and notes in Discord are the most important to test.

**Two-sided verification:**

1. **Simulation side (replay fidelity)**  
   The simulation must replay exactly what was in the logs. Whatever lines shared the same original timestamp (e.g. 2 lockout only, or 2 lockout + 1 zone) are written together in one batch with the same (current) timestamp. Verify by checking the simulated log file or a short "replay summary" (batch N = X lines at time T).

2. **Program side (single post per kill)**  
   When the main program receives that batch (e.g. 2 or 3 lines for one logical kill), it must post **at most one message** to Discord. So: simulation posted N lines for one kill → app posts 1 Discord message (and 1 Activity Log "Posted"). Buffer and cooldown should ensure no double/triple post.

**Duplicate posts (single post per kill) – refined**

- Capture a log that has both guild and/or lockout messages for the same kill (e.g. Thall Va Xakra, Kaas Thox Xi Aten Ha Ra, or lockout-only bosses with two lockout lines). Include whatever pattern your logs actually had (2 lockout, or 2 lockout + 1 zone, etc.).
- **Simulation:** Replay so all lines that shared the same original timestamp are written together in one batch (same current timestamp). Verify the simulated log file contains exactly those lines for that batch.
- **Program:** Expect one Discord post (and one Activity Log "Posted") for that kill. Buffer should collapse to one message; cooldown should prevent a second post.
- Optional: Replay the same kill again in a later batch and confirm the second is treated as duplicate (no second post or "Duplicate detected" in Activity Log).

So: we verify the simulation is posting what actually happened (whatever that was—2 lockout, 2 lockout + 1 zone, etc.), and we verify the main program is not posting more than one message to Discord for that batch.

---

## Reverting after simulation (restore real kill times)

When you run Boss Simulation, the main program records kill times (e.g. `last_killed`, `last_killed_timestamp`) in the boss database as it processes each replayed line. Those times are **today’s** timestamps. When you’re done testing and go back to playing for real, you want your **real** kill times back.

**Use Restore from Backup.** The app already has **File → Settings → Backup & Restore** with “Create Backup Now” and “Restore from Backup…”. That is the intended way to revert:

1. **Before testing:** Create a backup (see below for optional auto-backup when starting simulation), or use **Create Backup Now** in Settings so you have a snapshot with your real times.
2. **Run your simulation** (kill times in the DB will be updated to simulation timestamps).
3. **After testing:** **File → Settings → Restore from Backup…** → pick the backup you made *before* you started the simulation. After restore, the app should reload; you’ll be back to your real kill times and notes.

**Why scanning the real log won’t fix it.** Scan only updates a boss’s last kill time when the kill found in the log is **more recent** than the one already stored. Simulation wrote **today’s** timestamps, so they are always “more recent” than your real kills from last week. So scanning your original character file after testing will **not** overwrite the simulation times. Restore from backup is the correct way to go back.

**Pre-simulation backup (recommended in implementation).** When the user clicks **Save & Start Simulation**, the program should **automatically create a backup** of `bosses.json` (using the existing backup mechanism). Then show a short message, e.g.: “A backup was created so you can restore your data after testing. When done, use File → Settings → Restore from Backup and select the backup from just now.” That way you don’t have to remember to create a backup manually before starting. Optionally the backup could be named so it’s easy to spot (e.g. `bosses_pre_simulation_YYYYMMDD_HHMMSS.json`), but the existing timestamped name is usually enough if the backup is created at start-simulation time.

---

## Agent-run tests (for the AI assistant to troubleshoot)

Once the Debug tools (Boss Capture, Simulation, Advanced Settings) exist, **adding a script or test suite the agent can run** will make it much easier to troubleshoot issues you report (e.g. "duplicate posts when I simulate 2 lockout + 1 zone").

**Why:** You can say "simulation is posting twice for one kill"; the agent can run an automated test that replays a canned capture through the same logic the app uses, see the failure, change code, re-run, and confirm the fix—without you having to run the GUI and reproduce by hand every time.

**Recommended approach:**

- **Test suite (e.g. pytest)** that:
  - Uses **canned capture JSONs** (e.g. under `tests/fixtures/` or `assets/`: one file with "2 lockout + 1 zone same timestamp", one with "2 lockout only") so runs don't depend on your real log.
  - Replays those lines through the **same processing path** the main app uses (parsing, buffering, dedupe, decision to post). That may require a small refactor so the "process line / process buffer / post" logic can be called from tests without starting the full PyQt app.
  - **Mocks Discord** (no real webhook calls); asserts e.g. "exactly 1 post (one `notify` call) for this batch."
  - The agent runs `pytest tests/test_simulation_dedup.py` (or similar) and gets pass/fail and any logs.

- **Alternative: CLI runner script** (e.g. `python -m src.run_simulation_test path/to/capture.json`) that replays the capture through the same logic and prints a summary (e.g. "Batches: 3, Discord post count: 3, Expected: 3"). The agent runs it and reads stdout to verify behavior.

**What to test (aligned with your priorities):**

- Single post per batch: replay a canned "2 lockout + 1 zone same timestamp" capture → assert 1 Discord post for that batch.
- Duplicate-boss popup path: replay lockout line(s) for Thall Va Xakra / Kaas Thox → assert the correct note is used when posting (if we can simulate or mock the dialog choice).
- Notes in Discord: replay a kill for a boss with a note → assert the message content includes the note.

**Where it lives:** Under `tests/` (and optionally `tests/fixtures/` for canned JSONs) in the target tracker repo. The design doesn't require this for v1 of the Debug tools, but it's the natural next step so the agent can run tests and help you troubleshoot reliably.
