#!/bin/sh

# eips print helper
eips_print_bottom_centered() {
    eips 0 39 "$1" 2>/dev/null
}

eips_print_bottom_centered "Healing KOReader..."

# 1. Force kill any stuck KOReader processes
killall -9 reader.lua luajit koreader.sh 2>/dev/null

# 2. Unmount custom screensaver mount-bind if stuck
umount -l /usr/share/blanket/screensaver 2>/dev/null

# 3. Clean up lock files, temp framebuffer dumps, and redirect/rotate KPP crash logs
rm -f /var/tmp/koreader-fb.dump /var/tmp/koreader.sh /var/tmp/fbink

# Relocate KPPMainAppV2 crash logs to hidden system folder to hide from documents/home library
mkdir -p /mnt/us/system/crash_logs
for f in /mnt/us/documents/KPPMainAppV2_*; do
    [ -e "$f" ] || continue
    mv "$f" /mnt/us/system/crash_logs/ 2>/dev/null
done
rm -f /mnt/us/system/crash_logs/*.core 2>/dev/null

# Rotate TGZ crash logs in hidden folder so only the single newest is kept
tgz_files=$(ls -1tr /mnt/us/system/crash_logs/KPPMainAppV2_*.tgz 2>/dev/null)
count=$(echo "$tgz_files" | grep -c "KPPMainAppV2_")
if [ "$count" -gt 1 ]; then
    oldest_files=$(echo "$tgz_files" | head -n -1)
    for f in $oldest_files; do
        rm -f "$f"
        rm -rf "${f%.tgz}.sdr"
    done
fi

# 3b. Force Unix line endings (LF) on all core shell scripts to heal Windows CRLF corruption
eips_print_bottom_centered "Enforcing Unix line endings..."
for f in /mnt/us/koreader/koreader.sh /mnt/us/documents/koreader.sh /mnt/us/extensions/koreader/bin/koreader.sh /mnt/us/extensions/koreader/bin/heal_koreader.sh; do
    if [ -f "$f" ]; then
        sed -i 's/\r$//' "$f"
        chmod 777 "$f"
    fi
done

# 4. Resume Kindle OS UI services if left suspended
killall -CONT cvm awesome volumd 2>/dev/null

# 5. Handle full reinstallation if requested
if [ ! -f /mnt/us/koreader/reader.lua ] || [ ! -f /mnt/us/koreader/koreader.sh ]; then
    eips_print_bottom_centered "Core files missing! Forcing reinstall..."
    FORCE_REINSTALL=1
fi

if [ "$1" = "--reinstall" ] || [ "$FORCE_REINSTALL" = "1" ]; then
    eips_print_bottom_centered "Downloading stable KOReader..."
    # Download the stable v2025.10 release zip using curl (with -k/--insecure to bypass expired SSL certs on older devices)
    curl -k -L -o /mnt/us/koreader_tmp.zip "https://github.com/koreader/koreader/releases/download/v2025.10/koreader-kindle-v2025.10.zip"
    
    if [ $? -eq 0 ] && [ -f /mnt/us/koreader_tmp.zip ]; then
        eips_print_bottom_centered "Extracting KOReader files..."
        unzip -o /mnt/us/koreader_tmp.zip -d /mnt/us/
        rm -f /mnt/us/koreader_tmp.zip
        eips_print_bottom_centered "KOReader base reinstalled."
    else
        eips_print_bottom_centered "Download failed! Check Wi-Fi."
        rm -f /mnt/us/koreader_tmp.zip
        exit 1
    fi
fi

# 6. Self-heal/Restore custom patches from KUAL backup folder
if [ -d /mnt/us/extensions/koreader/patches ]; then
    eips_print_bottom_centered "Restoring user patches..."
    mkdir -p /mnt/us/koreader/patches
    cp -rf /mnt/us/extensions/koreader/patches/* /mnt/us/koreader/patches/ 2>/dev/null
fi

# 7. Ensure screensavers directory exists
mkdir -p /mnt/us/screensavers

# 8. Refresh the e-ink screen to clear ghosting/artifacts
eips -c
eips -f

eips_print_bottom_centered "KOReader healed successfully!"
