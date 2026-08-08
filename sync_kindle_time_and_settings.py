import paramiko
import json
import time
import os
import tempfile
import re

def load_kindle_hosts():
    hosts_path = "kindle_hosts.json"
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {hosts_path}: {e}")
    return {}

def run_cmd(ssh, cmd):
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
        return stdout.read().decode('utf-8', errors='ignore').strip()
    except Exception as e:
        print(f"  Command failed: {cmd} - Error: {e}")
        return ""

def harvest_kosync_credentials(hosts):
    print("\n--- Harvesting Kosync Credentials ---")
    creds = {}
    for nickname, device in hosts.items():
        ip = device.get("ip")
        port = device.get("port", 2222)
        user = device.get("user", "root")
        password = device.get("password", "")
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(ip, port=port, username=user, password=password, timeout=3, look_for_keys=False, allow_agent=False)
            sftp = client.open_sftp()
            fd, local_temp = tempfile.mkstemp()
            os.close(fd)
            try:
                sftp.get("/mnt/us/koreader/settings.reader.lua", local_temp)
                with open(local_temp, "r", encoding="utf-8") as f:
                    content = f.read()
                
                uname_match = re.search(r'\["kosync_username"\]\s*=\s*"([^"]+)",?', content)
                hash_match = re.search(r'\["kosync_password_hash"\]\s*=\s*"([^"]+)",?', content)
                endpoint_match = re.search(r'\["kosync_endpoint"\]\s*=\s*"([^"]+)",?', content)
                
                if uname_match and hash_match:
                    creds['username'] = uname_match.group(1)
                    creds['hash'] = hash_match.group(1)
                    if endpoint_match:
                        creds['endpoint'] = endpoint_match.group(1)
                    print(f"  Found Kosync credentials on {nickname}!")
                    sftp.close()
                    client.close()
                    os.remove(local_temp)
                    return creds
            except Exception:
                pass
            finally:
                if os.path.exists(local_temp):
                    os.remove(local_temp)
            sftp.close()
        except Exception:
            pass
        finally:
            client.close()
    
    print("  No active Kosync credentials found on any device.")
    return None

def update_koreader_settings(sftp, kosync_creds):
    remote_path = "/mnt/us/koreader/settings.reader.lua"
    print(f"  Updating KOReader settings at {remote_path}...")
    fd, local_temp = tempfile.mkstemp()
    os.close(fd)
    try:
        sftp.get(remote_path, local_temp)
    except Exception:
        print("  Could not download settings.reader.lua. Skipping KOReader settings.")
        return

    try:
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()

        # Update autowarmth settings
        if '["autowarmth_activate"]' in content:
            content = re.sub(r'\["autowarmth_activate"\]\s*=\s*[0-9]+,?', '["autowarmth_activate"] = 2,', content)
        else:
            content = content.replace("return {", 'return {\n    ["autowarmth_activate"] = 2,')
            
        if '["autowarmth_control_nightmode"]' in content:
            content = re.sub(r'\["autowarmth_control_nightmode"\]\s*=\s*(true|false),?', '["autowarmth_control_nightmode"] = true,', content)
        else:
            content = content.replace("return {", 'return {\n    ["autowarmth_control_nightmode"] = true,')
            
        if '["autowarmth_location"]' in content:
            content = re.sub(r'\["autowarmth_location"\]\s*=\s*.*?,', '["autowarmth_location"] = {\n        [1] = 41.8781,\n        [2] = -87.6298,\n    },', content, flags=re.DOTALL)
        else:
            content = content.replace("return {", 'return {\n    ["autowarmth_location"] = {\n        [1] = 41.8781,\n        [2] = -87.6298,\n    },')
            
        if '["twelve_hour_clock"]' in content:
            content = re.sub(r'\["twelve_hour_clock"\]\s*=\s*(true|false),?', '["twelve_hour_clock"] = true,', content)
        else:
            content = content.replace("return {", 'return {\n    ["twelve_hour_clock"] = true,')

        # Wi-Fi & Power keep-alive settings
        wifi_tweaks = {
            '["prevent_standby_while_charging"]': '["prevent_standby_while_charging"] = true,',
            '["wifi_auto_turn_off"]': '["wifi_auto_turn_off"] = false,',
            '["wifi_timeout_seconds"]': '["wifi_timeout_seconds"] = 0,',
            '["auto_suspend"]': '["auto_suspend"] = false,',
        }
        for key, value in wifi_tweaks.items():
            if key in content:
                content = re.sub(re.escape(key) + r'\s*=\s*[^,\n]+,?', value, content)
            else:
                content = content.replace("return {", f'return {{\n    {value}')

        # Inject Kosync credentials
        if kosync_creds:
            uname = kosync_creds['username']
            phash = kosync_creds['hash']
            endpoint = kosync_creds.get('endpoint', 'https://sync.koreader.rocks')
            
            if '["kosync_username"]' in content:
                content = re.sub(r'\["kosync_username"\]\s*=\s*"[^"]*",?', f'["kosync_username"] = "{uname}",', content)
            else:
                content = content.replace("return {", f'return {{\n    ["kosync_username"] = "{uname}",')
                
            if '["kosync_password_hash"]' in content:
                content = re.sub(r'\["kosync_password_hash"\]\s*=\s*"[^"]*",?', f'["kosync_password_hash"] = "{phash}",', content)
            else:
                content = content.replace("return {", f'return {{\n    ["kosync_password_hash"] = "{phash}",')
                
            if '["kosync_endpoint"]' in content:
                content = re.sub(r'\["kosync_endpoint"\]\s*=\s*"[^"]*",?', f'["kosync_endpoint"] = "{endpoint}",', content)
            else:
                content = content.replace("return {", f'return {{\n    ["kosync_endpoint"] = "{endpoint}",')

        with open(local_temp, "w", encoding="utf-8") as f:
            f.write(content)
            
        sftp.put(local_temp, remote_path)
        print("  KOReader settings updated successfully!")
        if kosync_creds:
            print("  Kosync credentials cloned to this device.")
    except Exception as e:
        print(f"  Error modifying settings.reader.lua: {e}")
    finally:
        if os.path.exists(local_temp):
            os.remove(local_temp)

def main():
    hosts = load_kindle_hosts()
    if not hosts:
        print("No Kindles found in kindle_hosts.json")
        return

    now = int(time.time())
    
    # Harvest kosync credentials before starting sync loop
    kosync_creds = harvest_kosync_credentials(hosts)
    
    for nickname, device in hosts.items():
        ip = device.get("ip")
        port = device.get("port", 2222)
        user = device.get("user", "root")
        password = device.get("password", "")
        
        print(f"\n--- Syncing time and settings on '{nickname}' ({ip}) ---")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, port=port, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
            
            print("  Setting Kindle system time to host time...")
            run_cmd(ssh, f"date -u -s '@{now}'")
            run_cmd(ssh, "hwclock -w")
            
            print("  Setting Kindle OS Timezone to America/Chicago...")
            run_cmd(ssh, "lipc-set-prop com.lab126.wan timezone America/Chicago")
            # Create timezone symlink just in case (needs rw)
            run_cmd(ssh, "mntroot rw && ln -sf /usr/share/zoneinfo/America/Chicago /etc/localtime && mntroot ro")
            
            print("  Configuring Wi-Fi persistent keep-alive daemon...")
            run_cmd(ssh, "lipc-set-prop com.lab126.wifid enable 1")
            
            autoboot_wifi = """
            mntroot rw
            UPSTART_DIR="/etc/upstart"
            [ -d /etc/init ] && UPSTART_DIR="/etc/init"
            cat << 'EOF' > ${UPSTART_DIR}/keep-wifi-alive.conf
start on started lab126_gui

script
    while true; do
        is_charging=$(lipc-get-prop com.lab126.powerd isCharging 2>/dev/null || echo 0)
        if [ "$is_charging" = "1" ]; then
            lipc-set-prop com.lab126.wifid enable 1 2>/dev/null || true
            lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null || true
        fi
        sleep 60
    done
end script
EOF
            mntroot ro
            """
            run_cmd(ssh, autoboot_wifi)
            
            sftp = ssh.open_sftp()
            update_koreader_settings(sftp, kosync_creds)
            sftp.close()
            
            print("  Sync complete for this device.")
            
        except Exception as e:
            print(f"  Could not connect to {nickname}: {e}")
        finally:
            ssh.close()

if __name__ == "__main__":
    main()
