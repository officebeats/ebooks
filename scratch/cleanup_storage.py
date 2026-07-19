import paramiko
import json

HOSTS_FILE = "kindle_hosts.json"

def cleanup_storage():
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
            
            # Execute cleanup
            client.exec_command("rm -f /mnt/us/*.core")
            client.exec_command("rm -rf /mnt/us/mrpackages/* 2>/dev/null")
            
            # Verify new space
            stdin, stdout, stderr = client.exec_command("df -h /mnt/us")
            print(stdout.read().decode('utf-8').strip())
            print("")
            
        except Exception as e:
            print(f"[{nickname}] Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    cleanup_storage()
