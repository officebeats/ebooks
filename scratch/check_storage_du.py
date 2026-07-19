import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def check_storage_details():
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
            
            print(f"--- [{nickname}] ---")
            
            # Check overall space
            stdin, stdout, stderr = client.exec_command("df -h /mnt/us")
            print(stdout.read().decode('utf-8').strip())
            
            # Check top 5 largest directories in /mnt/us (sizes in MB)
            cmd = "du -sm /mnt/us/* 2>/dev/null | sort -nr | head -n 5"
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode('utf-8').strip()
            print("\nLargest directories (MB):")
            print(out)
            print("\n")
            
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    check_storage_details()
