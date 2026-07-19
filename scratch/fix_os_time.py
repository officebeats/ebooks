import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def fix_os_time():
    with open(HOSTS_FILE, 'r') as f:
        hosts = json.load(f)

    for nickname, info in hosts.items():
        ip = info.get("ip")
        if not ip:
            continue
            
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(ip, port=2222, username="root", password="", timeout=10)
            print(f"[{nickname}] Connected.")
            
            # 1. Remove TZ from koreader.sh
            client.exec_command("sed -i '/export TZ=CST6CDT/d' /mnt/us/koreader/koreader.sh")
            
            # 2. Upload the new 4-auto-timesync.lua
            sftp = client.open_sftp()
            sftp.put("patches/4-auto-timesync.lua", "/mnt/us/koreader/patches/4-auto-timesync.lua")
            sftp.close()
            
            # 3. Fetch exact time and set it
            script = '''
JSON=$(curl -s --max-time 10 http://worldtimeapi.org/api/timezone/America/Chicago)
DATETIME=$(echo "$JSON" | grep -o '"datetime":"[^"]*' | cut -d'"' -f4)
if [ -n "$DATETIME" ]; then
    DATE_PART=$(echo "$DATETIME" | cut -dT -f1)
    TIME_PART=$(echo "$DATETIME" | cut -dT -f2 | cut -d. -f1)
    date -s "$DATE_PART $TIME_PART"
    hwclock -w 2>/dev/null
fi
'''
            client.exec_command(script)
            
            # 4. Restart KOReader to pick up the changes
            client.exec_command("lipc-set-prop com.lab126.appmgrd start app://com.lab126.blanket")
            
            print(f"[{nickname}] OS Time synced to Chicago and TZ removed from KOReader.")
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    fix_os_time()
