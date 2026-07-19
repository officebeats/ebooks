import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def check_storage():
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
            
            # Check disk space on user partition
            stdin, stdout, stderr = client.exec_command("df -h /mnt/us")
            df_output = stdout.read().decode('utf-8').strip()
            
            # Check for largest directories in user partition to give optimization recommendations
            stdin, stdout, stderr = client.exec_command("du -h -d 1 /mnt/us 2>/dev/null | sort -hr | head -n 5")
            du_output = stdout.read().decode('utf-8').strip()
            
            print(f"[{nickname}] Storage Status:")
            print(f"{df_output}")
            print(f"Top 5 largest directories:")
            print(f"{du_output}\n")
            
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    check_storage()
