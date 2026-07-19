import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def check_kindle_time():
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
            
            # Check timezone prop
            stdin, stdout, stderr = client.exec_command("lipc-get-prop com.lab126.wan timezone")
            tz = stdout.read().decode('utf-8').strip()
            print(f"[{nickname}] com.lab126.wan timezone: {tz}")
            
            # Check actual OS time
            stdin, stdout, stderr = client.exec_command("date")
            dt = stdout.read().decode('utf-8').strip()
            print(f"[{nickname}] date command output: {dt}")
            
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    check_kindle_time()
