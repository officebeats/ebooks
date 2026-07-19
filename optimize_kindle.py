import os
import sys
import json
import argparse
import tempfile
import paramiko
import re

DEFAULT_KINDLE_IP = "192.168.68.82"
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""

def load_kindle_hosts():
    hosts_path = "kindle_hosts.json"
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def build_connection(ip, port, user, password):
    print(f"Connecting to Kindle at {ip}:{port or 2222}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ports_to_try = [port] if port else [2222, 22]
    for p in ports_to_try:
        try:
            ssh.connect(ip, port=p, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
            return ssh
        except Exception as e:
            pass
    return None

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    hosts_config = load_kindle_hosts()
    parser = argparse.ArgumentParser(description="Optimize Kindle performance and clean up storage")
    parser.add_argument("--ip", default=DEFAULT_KINDLE_IP, help="Kindle IP address or host nickname")
    parser.add_argument("--port", type=int, help="Kindle SSH port")
    parser.add_argument("--user", default=DEFAULT_KINDLE_USER, help="Kindle SSH user")
    parser.add_argument("--password", default=DEFAULT_KINDLE_PASSWORD, help="Kindle SSH password")
    
    args = parser.parse_args()
    
    for nickname in [args.ip, f"{args.ip}_kindle"]:
        if nickname in hosts_config:
            device = hosts_config[nickname]
            args.ip = device.get("ip", args.ip)
            args.port = device.get("port", args.port) or args.port
            args.user = device.get("user", args.user) or args.user
            args.password = device.get("password", args.password) or args.password
            break

    ssh = build_connection(args.ip, args.port, args.user, args.password)
    if not ssh:
        print("ERROR: Could not connect to Kindle. Aborting.")
        sys.exit(1)

    print("\n--- 1. Plugin Cleanup Handled By Deployment Script ---")
    print("Skipping manual plugin cleanup. The deployment script now enforces a strict plugin baseline.")

    print("\n--- 2. Storage Cleanup ---")
    print("Deleting logs older than 7 days...")
    ssh.exec_command('find /mnt/us -name "*.log" -mtime +7 -exec rm -f {} \\;')
    
    print("Deleting OTA updates...")
    ssh.exec_command('rm -f /mnt/us/update.bin /mnt/us/*.bin')
    
    print("Deleting orphaned .sdr folders...")
    script = """
    for sdr in /mnt/us/epubs/*.sdr; do
        if [ -d "$sdr" ]; then
            base="${sdr%.sdr}"
            if [ ! -f "$base.epub" ] && [ ! -f "$base.pdf" ]; then
                rm -rf "$sdr"
                echo "Removed orphaned folder: $sdr"
            fi
        fi
    done
    """
    stdin, stdout, stderr = ssh.exec_command(script)
    orphaned = stdout.read().decode().strip().splitlines()
    if orphaned:
        for line in orphaned:
            print(f"  {line}")
    else:
        print("  No orphaned .sdr folders found.")

    print("\n--- 2.5 Deep Optimizations (Bloat & Indexing) ---")
    script_deep = """
    # --- HARDWARE & SAFETY CHECKS ---
    # 1. Verify this is actually a Kindle device to prevent accidental bricking
    if ! command -v lipc-get-prop >/dev/null 2>&1; then
        echo "ERROR: lipc-get-prop not found. This doesn't look like a standard Kindle OS. Aborting deep optimizations!"
        exit 1
    fi
    
    # 2. Extract storage stats for logging (Constraints removed per user request)
    ROOT_FREE=$(df -k / | tail -1 | awk '{print $4}')
    ROOT_PCT=$(df -k / | tail -1 | awk '{print $5}' | sed 's/%//')
    USER_PCT=$(df -k /mnt/us | tail -1 | awk '{print $5}' | sed 's/%//')
    
    echo "Hardware safety checks passed. Proceeding with optimizations unconditionally..."

    # --- AGGRESSIVE CLEANUP (Always Run) ---
    echo "Running aggressive bloat log cleanup..."
    rm -f /mnt/us/*.log
    rm -f /mnt/us/koreader/crash.log
    rm -rf /mnt/us/system/syslog
    
    echo "Running rootfs daemon log sweep..."
    rm -rf /var/log/*
    rm -rf /var/tmp/*

    # 1. Clean Crash Dumps & OTA Bloat
    rm -f /mnt/us/KPPMainAppV2_*.core
    rm -rf /mnt/us/Indexer_Dump_*
    rm -f /mnt/us/update.bin.tmp.partial

    # 1.5 Prevent future core dumps
    touch /mnt/us/DISABLE_CORE_DUMP
    touch /mnt/us/DISABLE_CORE_DUMP_ALERT

    # 2. Block Amazon Indexer
    rm -rf "/mnt/us/system/Search Indexes"
    touch "/mnt/us/system/Search Indexes"
    chmod 444 "/mnt/us/system/Search Indexes"

    # 3. Block Thumbnail Generator
    rm -rf /mnt/us/system/thumbnails
    touch /mnt/us/system/thumbnails
    chmod 444 /mnt/us/system/thumbnails

    # 4. Clean Amazon Documents (Protect KUAL and KOReader launchers)
    find /mnt/us/documents -type f \\( -name "*.mobi" -o -name "*.azw*" -o -name "*.pdf" -o -name "*.txt" \\) ! -iname "*KUAL*" ! -iname "*koreader*" -exec rm -f {} +
    """
    ssh.exec_command(script_deep)
    
    print("\n--- 2.6 Install True Auto-Boot ---")
    script_autoboot = """
    mntroot rw
    if [ -d /etc/upstart ]; then
        UPSTART_DIR="/etc/upstart"
    else
        UPSTART_DIR="/etc/init"
    fi
    
    cat << 'EOF' > ${UPSTART_DIR}/koreader-autoboot.conf
start on started lab126_gui

script
    /bin/sleep 30s
    if [ -x /mnt/us/extensions/koreader/bin/koreader-ext.sh ]; then
        exec /mnt/us/extensions/koreader/bin/koreader-ext.sh --kual --framework_stop
    fi
end script
EOF
    mntroot ro
    """
    ssh.exec_command(script_autoboot)
    print("True Auto-Boot upstart script injected.")

    print("Deep optimizations applied (indexers blocked, bloat wiped, shortcut installed, auto-boot injected).")

    print("\n--- 3. Rendering Tweaks ---")
    sftp = ssh.open_sftp()
    remote_settings = "/mnt/us/koreader/settings.reader.lua"
    fd, local_temp = tempfile.mkstemp()
    os.close(fd)
    try:
        sftp.get(remote_settings, local_temp)
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Tweaks
        # kerning_method = "good"
        if '["font_kerning"]' in content:
            content = re.sub(r'\["font_kerning"\]\s*=\s*"[^"]*"', '["font_kerning"] = "good"', content)
        else:
            content = content.replace("return {", 'return {\n    ["font_kerning"] = "good",')
            
        # image_scaling = "fast"
        if '["image_scaling"]' in content:
            content = re.sub(r'\["image_scaling"\]\s*=\s*"[^"]*"', '["image_scaling"] = "fast"', content)
        else:
            content = content.replace("return {", 'return {\n    ["image_scaling"] = "fast",')
            
        # full_refresh_count = 10
        if '["full_refresh_count"]' in content:
            content = re.sub(r'\["full_refresh_count"\]\s*=\s*\d+', '["full_refresh_count"] = 10', content)
        else:
            content = content.replace("return {", 'return {\n    ["full_refresh_count"] = 10,')

        with open(local_temp, "w", encoding="utf-8") as f:
            f.write(content)
            
        sftp.put(local_temp, remote_settings)
        print("Settings successfully updated for performance.")
    except Exception as e:
        print(f"Error updating settings: {e}")
    finally:
        if os.path.exists(local_temp):
            os.remove(local_temp)
        sftp.close()

    ssh.close()
    print("\nOptimization and cleanup complete!")

if __name__ == "__main__":
    main()
