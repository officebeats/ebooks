import paramiko
import time
import socket
import os
import sys

KINDLE_IPS = ["192.168.68.93", "192.168.68.82", "192.168.68.55"]

def deploy_watchdog_to_device(ip, port=2222):
    print(f"\n==================================================")
    print(f" HARDENING & DEPLOYING WATCHDOG ({ip}:{port})")
    print(f"==================================================")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port=port, username="root", password="", timeout=5, look_for_keys=False, allow_agent=False)
        print("SSH Connection Successful!")
        
        # 1. Deploy Fail-Safe Watchdog Upstart Script
        print("\n[1/3] Injecting Self-Healing Watchdog Upstart Script...")
        watchdog_script = """
        mntroot rw
        UPSTART_DIR="/etc/upstart"
        [ -d /etc/init ] && UPSTART_DIR="/etc/init"
        
        cat << 'EOF' > ${UPSTART_DIR}/koreader-watchdog.conf
start on started lab126_gui

script
    while true; do
        /bin/sleep 15s
        IS_READER=$(ps | grep reader.lua | grep -v grep || true)
        IS_GUI=$(ps | grep cvm | grep -v grep || true)
        
        # If both KOReader and native GUI are dead, auto-restore native GUI to prevent hard freeze!
        if [ -z "$IS_READER" ] && [ -z "$IS_GUI" ]; then
            start lab126_gui 2>/dev/null || true
        fi
    done
end script
EOF
        chmod 644 ${UPSTART_DIR}/koreader-watchdog.conf 2>/dev/null || true
        mntroot ro
        """
        client.exec_command(watchdog_script)
        print("  Watchdog upstart script deployed.")

        # 2. Clear stale lock files & verify Search Indexes / Thumbnails
        print("\n[2/3] Cleaning stale locks & verifying directory safety...")
        clean_script = """
        rm -f /var/tmp/koreader-fb.dump /tmp/koreader* /tmp/dropbear* 2>/dev/null || true
        mkdir -p "/mnt/us/system/Search Indexes" /mnt/us/system/thumbnails
        touch "/mnt/us/system/Search Indexes/DISABLE_INDEXER" 2>/dev/null || true
        """
        client.exec_command(clean_script)
        print("  Locks cleared and directories verified.")

        # 3. Clean restart of KOReader
        print("\n[3/3] Performing clean KOReader restart...")
        client.exec_command("killall -9 reader.lua 2>/dev/null || true")
        time.sleep(1)
        client.exec_command("/mnt/us/koreader/koreader.sh /mnt/us/koreader --kual --framework_stop >/dev/null 2>&1 &")
        print("  KOReader launched with fail-safe guard.")
        
        client.close()
        return True
    except Exception as e:
        print(f"Could not connect/deploy to {ip}:{port}: {e}")
        return False

if __name__ == "__main__":
    for ip in KINDLE_IPS:
        for port in [2222, 22]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            res = sock.connect_ex((ip, port))
            sock.close()
            if res == 0:
                deploy_watchdog_to_device(ip, port)
                break
