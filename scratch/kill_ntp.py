import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def kill_ntp():
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
            
            # Disable native NTP binaries
            client.exec_command("mntroot rw")
            client.exec_command("if [ -f /usr/sbin/ntpd ]; then mv /usr/sbin/ntpd /usr/sbin/ntpd.bak; fi")
            client.exec_command("if [ -f /usr/bin/ntpdate ]; then mv /usr/bin/ntpdate /usr/bin/ntpdate.bak; fi")
            client.exec_command("killall ntpd ntpdate 2>/dev/null")
            client.exec_command("mntroot ro")
            
            print(f"[{nickname}] Native NTP killed and disabled.")
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    kill_ntp()
