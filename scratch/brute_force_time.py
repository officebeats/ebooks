import paramiko
import json
import time
from datetime import datetime
import pytz

HOSTS_FILE = "kindle_hosts.json"

def fix_all_time():
    with open(HOSTS_FILE, 'r') as f:
        hosts = json.load(f)
        
    tz = pytz.timezone('America/Chicago')
    
    for nickname, info in hosts.items():
        ip = info.get("ip")
        if not ip:
            continue
            
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(ip, port=2222, username="root", password="", timeout=10)
            
            now = datetime.now(tz)
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            client.exec_command(f"date -s '{date_str}'; hwclock -w 2>/dev/null")
            client.exec_command("lipc-set-prop com.lab126.appmgrd start app://com.lab126.blanket")
            print(f"[{nickname}] Force set time to {date_str}")
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    fix_all_time()
