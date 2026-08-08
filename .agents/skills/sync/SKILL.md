---
name: sync
description: Automatically run the /sync command to deduplicate and sync the ebook library to all Kindles.
---

# Sync Skill Workflow

When the user types `/sync` or requests to sync their ebooks, you MUST follow this strict 4-step workflow. This applies to Antigravity, Claude Code, Codex, or any compatible AI agent.

## Step 0: Maintenance, Clean Baseline & Launcher Enforcement
Before syncing, ensure all active Kindles have the latest plugins, patches, launchers, and configurations.
For each Kindle in `kindle_hosts.json`, you MUST run the deployment script (`python deploy_beats_kindle_config.py --ip <kindle_nickname>`).
**MANDATORY BASELINE ENFORCEMENTS:**
1. **Home Screen Document Isolation & Launcher Self-Healing**: Moves ONLY recognized ebook files (`.epub`, `.mobi`, `.azw3`, `.pdf`, `.txt`, `.docx`, `.cbz`, `.cbr`, `.fb2`) out of `/mnt/us/documents/` into `/mnt/us/epubs/`, explicitly protecting all KUAL booklets, KOReader booklets, `.sh` scripts, dictionaries, and system folders. Runs automated self-healing to verify and restore KUAL/KOReader launchers on the native Kindle home screen.
2. **Default No-Framework Mode (`--framework_stop`)**: Enforces `--framework_stop` by default across all launchers (Booklet, KUAL, auto-boot) so KOReader always stops native `lab126_gui`, freeing 45MB-60MB of RAM for performance and battery life.
3. **2D Cover Grid/List Support & Fast E-Ink Scaling**: Preserves 2D cover rendering (`list_image_meta`/`mosaic`) with hardware fast-scaling (`image_scaling = "fast"`), folder cover patches (`2-browser-folder-cover.lua`), non-ebook image guards (`2-disable-image-docs.lua`), and pre-launch memory flushes (`echo 3 > /proc/sys/vm/drop_caches`).
4. **Persistent Cloud Popup Suppression**: Injects `/etc/upstart/suppress-cloud-popup.conf` and `/etc/hosts` loopbacks so the native "Cloud not available" popup is permanently suppressed on boot.
5. **Smart Power & SSH Keep-Alive (`3-keep-ssh-alive-charging.lua`)**: When plugged in (charging), prevents screen saver (`preventScreenSaver = 1`) so the device stays awake for SSH sync tool operations. When unplugged (battery mode), operates normally to maximize battery life.
6. **Automated Background Modifications**: Deploys `4-auto-timesync.lua` (NTP time sync on wake) and `4-auto-dedupe.lua` (storage deduplication on wake).
7. **Strict Plugin Baseline**: Automatically purges unauthorized bloat plugins.
**Command:** `python deploy_beats_kindle_config.py --ip <kindle_nickname>`

## Step 1: Sync Kindle Time & Settings
Execute the `sync_kindle_time_and_settings.py` script. This script connects to all active Kindles, syncs their system time to match the host PC, sets the timezone to Chicago, and modifies KOReader's configuration to use location-based Auto Night Mode.
**Command:** `python sync_kindle_time_and_settings.py`

## Step 2: Hardware Scan, Adaptive Resolution, RAM Tuning & Crash Diagnostics
Execute the `optimize_kindle.py` script for each Kindle. This script performs the following core actions every time `/sync` runs:
1. **Hardware Spec Scan & Adaptive Resolution/RAM Profiling**: Scans device CPU, board, OS version, and total RAM capacity. Automatically applies hardware-tailored profiles:
   - **Low-RAM (<= 384MB RAM)**: Applies aggressive Linux kernel VM cache reclamation (`sysctl vm.vfs_cache_pressure=150`), limits cover cache bloat, and optimizes font kerning (`font_kerning="fast"`).
   - **High-RAM (>= 512MB RAM)**: Applies balanced page cache retention (`sysctl vm.vfs_cache_pressure=100`) for instantaneous page flips and high-quality typography (`font_kerning="good"`).
   - **Hardware Resolution**: Resets KOReader resolution/scaling (`screen_dpi`, `ui_scale`, `font_scaling`) to align strictly with the e-ink hardware's native DPI.
2. **Amazon Bloat Daemon Sweep**: Suppresses unnecessary Amazon telemetry and phone-home background daemons (`phd`, `tod`, `otav3`, `scanlogd`) while KOReader runs, freeing 20MB–40MB of RAM and eliminating CPU spikes.
3. **Maximum Storage Optimization**: Maximizes available storage space for EPUB books by disabling the Amazon search indexer (`DISABLE_INDEXER`), purging Amazon search index databases (`/mnt/us/system/Search Indexes/*`), clearing Amazon thumbnail cache (`/mnt/us/system/thumbnails/*`), clearing KOReader cover image cache (`/mnt/us/koreader/cache/*`), blocking OTA firmware updates (`/mnt/us/update.bin.tmp.partial`), and deleting logs and orphaned `.sdr` folders.
4. **Crash Diagnostics & Prevention**: Verifies KOReader process health (`reader.lua`), inspects crash logs (`/mnt/us/koreader/crash.log` and `/var/log/messages`), clears stale locks, disables core dumps, and enforces Unix LF line endings on launcher scripts.
**CRASH PREVENTION MANDATE:** Optimization scripts MUST preserve active `reader.lua` sessions and MUST NOT issue native GUI framework restarts (`stop lab126_gui`) while KOReader is running.
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
