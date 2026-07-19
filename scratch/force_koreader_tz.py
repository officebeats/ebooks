import paramiko
import json
import time

HOSTS_FILE = "kindle_hosts.json"
TZ_EXPORT = "export TZ=CST6CDT"

def force_koreader_timezone():
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
            
            # 1. Read current koreader.sh
            stdin, stdout, stderr = client.exec_command("cat /mnt/us/koreader/koreader.sh")
            content = stdout.read().decode('utf-8')
            
            if not content:
                print(f"  [ERROR] Empty or missing koreader.sh on {nickname}")
                continue
                
            # 2. Inject TZ export if not present
            if "export TZ=" not in content:
                new_content = content.replace("#!/bin/sh", f"#!/bin/sh\n{TZ_EXPORT}")
                
                # Write back
                sftp = client.open_sftp()
                with sftp.file('/mnt/us/koreader/koreader.sh', 'w') as f:
                    f.write(new_content)
                sftp.close()
                print(f"  [SUCCESS] Injected TZ into koreader.sh on {nickname}")
            else:
                print(f"  [INFO] TZ already exported on {nickname}")
                
            # 3. Ensure hardware clock matches correct UTC time by forcing NTP sync now
            client.exec_command("ntpd -q -p pool.ntp.org > /dev/null 2>&1")
            
            # 4. Restart KOReader
            client.exec_command("lipc-set-prop com.lab126.appmgrd start app://com.lab126.blanket")

        except Exception as e:
            print(f"  [ERROR] Failed to fix timezone on {nickname}: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    force_koreader_timezone()
