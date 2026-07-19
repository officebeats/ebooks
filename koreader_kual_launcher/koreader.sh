#!/bin/sh

# Install autoboot script silently on first launch
if [ ! -f /etc/upstart/koreader-autoboot.conf ] && [ ! -f /etc/init/koreader-autoboot.conf ]; then
    mntroot rw
    if [ -d /etc/upstart ]; then
        UPSTART_DIR="/etc/upstart"
    else
        UPSTART_DIR="/etc/init"
    fi
    
    cat << 'EOF' > ${UPSTART_DIR}/koreader-autoboot.conf
start on started lab126_gui

script
    # Wait for framework and UI to settle before hijacking
    /bin/sleep 30s
    if [ -x /mnt/us/extensions/koreader/bin/koreader.sh ]; then
        exec /mnt/us/extensions/koreader/bin/koreader.sh --kual --framework_stop
    fi
end script
EOF
    mntroot ro
fi

# Relocate and rotate KPPMainAppV2 crash logs to hidden folder to hide from documents/home library
mkdir -p /mnt/us/system/crash_logs
for f in /mnt/us/documents/KPPMainAppV2_*; do
    [ -e "$f" ] || continue
    mv "$f" /mnt/us/system/crash_logs/ 2>/dev/null
done
rm -f /mnt/us/system/crash_logs/*.core 2>/dev/null

tgz_files=$(ls -1tr /mnt/us/system/crash_logs/KPPMainAppV2_*.tgz 2>/dev/null)
count=$(echo "$tgz_files" | grep -c "KPPMainAppV2_")
if [ "$count" -gt 1 ]; then
    oldest_files=$(echo "$tgz_files" | head -n -1)
    for f in $oldest_files; do
        rm -f "$f"
        rm -rf "${f%.tgz}.sdr"
    done
fi

exec /mnt/us/koreader/koreader.sh "$@"
