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

exec /mnt/us/koreader/koreader.sh "$@"
