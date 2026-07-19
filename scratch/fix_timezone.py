import paramiko
import json
import time

HOSTS_FILE = "kindle_hosts.json"
TARGET_TIMEZONE = "America/Chicago"

def fix_timezone_on_kindles():
    with open(HOSTS_FILE, 'r') as f:
        hosts = json.load(f)

    for nickname, info in hosts.items():
        ip = info.get("ip")
        if not ip:
            continue
            
        print(f"Connecting to {nickname} at {ip}...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            client.connect(ip, port=2222, username="root", password="", timeout=10)
            print(f"  Connected to {nickname}. Applying timezone fixes...")
            
            # Method 1: The LIPC method (most reliable for Amazon UI persistence)
            cmd1 = f"lipc-set-prop com.lab126.wan timezone {TARGET_TIMEZONE}"
            client.exec_command(cmd1)
            
            # Method 2: The standard Linux symlink method (for underlying libs and KOReader)
            cmd2 = f"mntroot rw && rm -f /etc/localtime && ln -s /usr/share/zoneinfo/{TARGET_TIMEZONE} /etc/localtime && mntroot ro"
            client.exec_command(cmd2)
            
            # Method 3: Restart KOReader if it is running to pick up the new timezone
            cmd3 = "lipc-set-prop com.lab126.appmgrd start app://com.lab126.blanket"
            client.exec_command(cmd3)

            print(f"  [SUCCESS] Timezone set to {TARGET_TIMEZONE} on {nickname}")
        except Exception as e:
            print(f"  [ERROR] Failed to connect or fix timezone on {nickname}: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    fix_timezone_on_kindles()
