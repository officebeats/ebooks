---
name: sync
description: Automatically run the /sync command to deduplicate and sync the ebook library to all Kindles.
---

# Sync Skill Workflow

When the user types `/sync` or requests to sync their ebooks, you MUST follow this strict 4-step workflow. This applies to Antigravity, Claude Code, Codex, or any compatible AI agent.

## Step 0: Maintenance & Updates (Plugins and Patches)
Before syncing, ensure all active Kindles have the latest plugins, patches, and configurations.
For each Kindle in `kindle_hosts.json`, you MUST run the deployment script to fetch the latest GitHub releases, deploy them, and enforce a strict plugin baseline (automatically deleting unauthorized bloat plugins).
**IMPORTANT CHECK:** As an agent, if you are running this kit, you MUST ensure that the following core modifications are present or installed via the deployment script:
1. `4-auto-timesync.lua` (for automated NTP time sync on wake)
2. `4-auto-dedupe.lua` (for automated storage deduplication on wake)
3. The custom KUAL `menu.json` config that forces "No Framework" 1-Tap Launch.
**Command:** `python deploy_beats_kindle_config.py --ip <kindle_nickname>`

## Step 1: Sync Kindle Time & Settings
Execute the `sync_kindle_time_and_settings.py` script. This script connects to all active Kindles, syncs their system time to match the host PC, sets the timezone to Chicago, and modifies KOReader's configuration to use location-based Auto Night Mode.
**Command:** `python sync_kindle_time_and_settings.py`

## Step 2: Optimize Storage, Normalize Resolution & Diagnose Crashes
Execute the `optimize_kindle.py` script for each Kindle. This script maximizes available storage space for EPUB books (disabling Amazon indexer, purging Amazon search indexes, clearing Amazon thumbnail cache & KOReader image cache, blocking OTA updates, deleting logs and orphaned `.sdr` folders), resets KOReader resolution/scaling (`screen_dpi`, `ui_scale`, `font_scaling`) to default hardware native resolution, checks for recent KOReader crashes on that specific device, clears stale lock files, enforces Unix LF line endings on launcher scripts, and applies crash-prevention safeguards.
**Command:** `python optimize_kindle.py --ip <kindle_nickname>`

## Step 3: Deduplicate Libraries
Execute the deduplication script IMMEDIATELY across the local library and all Kindles. Do not ask for permission for this step.
**Command:** `python dedupe_all_libraries.py`

*Note: This script automatically handles both the local folder and the remote Kindles based on its internal configuration.*

## Step 4: Calculate Deltas (Dry-Run)
Read `kindle_hosts.json` to get the list of active Kindles (by their nickname keys, e.g. `older-floater (192.168.68.82)`, `newer-backroom (192.168.68.55)`, `white-bedroom (192.168.68.93)`).
For **each** Kindle, run the local-to-Kindle sync script in dry-run mode to see what is missing on that device.
**Command:** `python sync_local_to_kindle.py --ip <kindle_nickname> --dry-run`

## Step 5: Ask For User Permission
Aggregate the output from the dry runs.
Respond to the user with a summary of the differences:
- Tell them exactly how many and which books are missing from each Kindle.
- **IMPORTANT:** Ask the user if they would like to proceed with transferring the missing books to the respective devices.

## Step 6: Execute Final Sync
Wait for the user's approval.
If they say "yes" or approve the transfer, run the actual sync scripts for the affected Kindles without the dry-run flag.
**Command:** `python sync_local_to_kindle.py --ip <kindle_nickname>`

After the transfers complete, confirm success with the user.
