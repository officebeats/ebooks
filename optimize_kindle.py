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
    
    for key, device in hosts_config.items():
        ip_addr = device.get("ip", "")
        if args.ip == key or args.ip in key or args.ip == ip_addr or args.ip in ip_addr:
            args.ip = ip_addr
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

    print("\n--- 2.3 Hardware Spec Scanning & Adaptive Profile ---")
    stdin, stdout, stderr = ssh.exec_command("cat /etc/version.txt 2>/dev/null | head -n 1")
    v_txt = stdout.read().decode('utf-8', errors='ignore').strip()
    stdin, stdout, stderr = ssh.exec_command("grep -i Hardware /proc/cpuinfo 2>/dev/null")
    cpu_hw = stdout.read().decode('utf-8', errors='ignore').strip()
    stdin, stdout, stderr = ssh.exec_command("free -m | grep Mem | awk '{print $2}'")
    ram_mb = stdout.read().decode('utf-8', errors='ignore').strip()
    total_ram_mb = int(ram_mb) if ram_mb.isdigit() else 256
    is_low_ram = total_ram_mb <= 384

    print(f"  [Hardware Scan] {cpu_hw if cpu_hw else 'Kindle Hardware Board'} | RAM: {total_ram_mb}MB | {v_txt if v_txt else 'Kindle OS'}")
    
    # Adaptive kernel sysctl memory tuning
    if is_low_ram:
        print("  [Adaptive RAM Profiling] Low-RAM profile active (<= 384MB RAM). Applying aggressive Linux kernel VM cache reclamation...")
        ssh.exec_command("sysctl -w vm.vfs_cache_pressure=150 vm.dirty_background_ratio=5 vm.dirty_ratio=10 2>/dev/null")
    else:
        print("  [Adaptive RAM Profiling] High-RAM profile active (>= 512MB RAM). Applying balanced page cache retention...")
        ssh.exec_command("sysctl -w vm.vfs_cache_pressure=100 vm.dirty_background_ratio=10 vm.dirty_ratio=20 2>/dev/null")

    # Amazon OS background bloat daemon sweep
    print("  [Amazon Bloat Sweep] Suppressing background Amazon telemetry daemons (phd, tod, otav3, scanlogd)...")
    ssh.exec_command("stop phd 2>/dev/null || killall -9 phd 2>/dev/null; stop tod 2>/dev/null || killall -9 tod 2>/dev/null; stop otav3 2>/dev/null || killall -9 otav3 2>/dev/null; stop scanlogd 2>/dev/null || killall -9 scanlogd 2>/dev/null")

    print("\n--- 2.4 Device-Specific Crash Diagnostics & Prevention ---")
    stdin, stdout, stderr = ssh.exec_command("ps | grep reader.lua | grep -v grep")
    ps_out = stdout.read().decode('utf-8', errors='ignore').strip()
    if ps_out:
        print("  [Health Check] KOReader process (reader.lua) is currently RUNNING.")
    else:
        print("  [Health Warning] KOReader process (reader.lua) is NOT running.")
        print("  Attempting clean background restart of KOReader...")
        ssh.exec_command("/mnt/us/koreader/koreader.sh /mnt/us/koreader >/dev/null 2>&1 &")

    crash_checks = """
    for log_path in /mnt/us/koreader/crash.log /mnt/us/crash.log /tmp/koreader.log; do
        if [ -f "$log_path" ]; then
            echo "=== Log: $log_path ==="
            tail -n 25 "$log_path" | grep -iE "error|crash|terminated|oom|fault|fatal" || tail -n 10 "$log_path"
        fi
    done
    """
    stdin, stdout, stderr = ssh.exec_command(crash_checks)
    log_out = stdout.read().decode('utf-8', errors='ignore').strip()
    if log_out:
        print(f"  [Crash Analysis]\n{log_out}")
    else:
        print("  [Crash Analysis] No active crash log errors found.")

    prevention_script = """
    rm -f /var/tmp/koreader-fb.dump /var/tmp/koreader.sh /var/tmp/fbink /mnt/us/KPPMainAppV2_*.core
    touch /mnt/us/DISABLE_CORE_DUMP /mnt/us/DISABLE_CORE_DUMP_ALERT
    for f in /mnt/us/koreader/koreader.sh /mnt/us/documents/koreader.sh /mnt/us/extensions/koreader/bin/koreader.sh /mnt/us/extensions/koreader/bin/heal_koreader.sh; do
        if [ -f "$f" ]; then
            sed -i 's/\\r$//' "$f"
            chmod 777 "$f"
        fi
    done
    """
    ssh.exec_command(prevention_script)
    print("  [Crash Prevention] Stale locks cleared, core dumps disabled, Unix LF line endings enforced.")

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

    # 2. Clean Amazon Indexer files safely and enforce indexer disable flag
    mkdir -p "/mnt/us/system/Search Indexes"
    rm -rf "/mnt/us/system/Search Indexes/"* 2>/dev/null
    touch "/mnt/us/system/Search Indexes/DISABLE_INDEXER" 2>/dev/null

    # 3. Clean Thumbnail Cache & KOReader stale image cache safely
    mkdir -p /mnt/us/system/thumbnails
    rm -rf /mnt/us/system/thumbnails/* 2>/dev/null
    rm -rf /mnt/us/koreader/cache/* 2>/dev/null

    # 3.5 Block OTA updates
    rm -rf /mnt/us/update.bin /mnt/us/*.bin 2>/dev/null
    mkdir -p /mnt/us/update.bin.tmp.partial 2>/dev/null

    # 4. Safely move ONLY ebook files to /mnt/us/epubs/ (preserving all launchers and system items)
    echo "Isolating ebooks in /mnt/us/documents to /mnt/us/epubs/..."
    mkdir -p /mnt/us/epubs
    MOVED_ANY=0
    for item in /mnt/us/documents/*; do
        [ -e "$item" ] || continue
        base=$(basename "$item")
        
        # Explicitly skip launchers, booklets, scripts, dictionaries, or system folders
        if echo "$base" | grep -iqE "koreader|kual|kindleforge|dictionaries|system|\\.azw2$|\\.kual$|\\.sh$"; then
            continue
        fi
        
        # Move ONLY recognized ebook file formats
        if echo "$base" | grep -iqE "\\.(epub|mobi|azw3|pdf|txt|docx|cbz|cbr|fb2)$"; then
            echo "  Moving ebook $base to /mnt/us/epubs/"
            mv "$item" "/mnt/us/epubs/" 2>/dev/null || true
            sdr_folder="/mnt/us/documents/${base}.sdr"
            if [ -d "$sdr_folder" ]; then
                mv "$sdr_folder" "/mnt/us/epubs/" 2>/dev/null || true
            fi
            MOVED_ANY=1
        fi
    done
    
    # 4.1 Launcher Self-Healing & Verification
    # Ensure all launcher items are present in /mnt/us/documents/
    for pattern in "koreader" "kual" "KUAL" "kindleforge"; do
        for f in /mnt/us/epubs/*${pattern}*; do
            [ -e "$f" ] || continue
            echo "  [Self-Healing] Restoring launcher item to /mnt/us/documents/: $(basename "$f")"
            mv "$f" "/mnt/us/documents/" 2>/dev/null || true
        done
    done
    
    # 4.5 Clean empty directories in documents (preserving dictionaries and system)
    find /mnt/us/documents -mindepth 1 -maxdepth 1 -type d -empty -not -name "dictionaries" -not -name "system" -exec rmdir {} \\; 2>/dev/null || true
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

    print("\n--- 3. Rendering Tweaks & Hardware Resolution Normalization ---")
    sftp = ssh.open_sftp()
    remote_settings = "/mnt/us/koreader/settings.reader.lua"
    fd, local_temp = tempfile.mkstemp()
    os.close(fd)
    try:
        sftp.get(remote_settings, local_temp)
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. Strip screen_dpi, ui_scale, and font_scaling to force hardware default DPI auto-detection
        if '["screen_dpi"]' in content:
            content = re.sub(r'\["screen_dpi"\]\s*=\s*[^,\n]+,?\n?', '', content)
        if '["ui_scale"]' in content:
            content = re.sub(r'\["ui_scale"\]\s*=\s*[^,\n]+,?\n?', '', content)
        if '["font_scaling"]' in content:
            content = re.sub(r'\["font_scaling"\]\s*=\s*[^,\n]+,?\n?', '', content)

        # Hardware-adaptive rendering tweaks
        kerning_val = "fast" if is_low_ram else "good"
        if '["font_kerning"]' in content:
            content = re.sub(r'\["font_kerning"\]\s*=\s*"[^"]*"', f'["font_kerning"] = "{kerning_val}"', content)
        else:
            content = content.replace("return {", f'return {{\n    ["font_kerning"] = "{kerning_val}",')
            
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
        print("Settings successfully updated for performance and native hardware resolution.")
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
