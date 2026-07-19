import paramiko

def check_time_format():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.82"
    print(f"Connecting to older-floater at {ip}...")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        stdin, stdout, stderr = client.exec_command("cat /mnt/us/koreader/settings.reader.lua | grep -i time")
        print(stdout.read().decode('utf-8', errors='ignore').strip())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_time_format()
