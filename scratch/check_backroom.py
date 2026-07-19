import paramiko

def check_koreader_ext():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.55"
    print(f"Connecting to newer-backroom at {ip}...")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        print("\n--- menu.json ---")
        stdin, stdout, stderr = client.exec_command("cat /mnt/us/extensions/koreader/menu.json")
        print(stdout.read().decode('utf-8', errors='ignore').strip())
        
        print("\n--- /mnt/us/extensions/koreader/bin/ contents ---")
        stdin, stdout, stderr = client.exec_command("ls -la /mnt/us/extensions/koreader/bin/")
        print(stdout.read().decode('utf-8', errors='ignore').strip())
        
        print("\n--- /mnt/us/koreader/ contents (head) ---")
        stdin, stdout, stderr = client.exec_command("ls -la /mnt/us/koreader/ | head -n 15")
        print(stdout.read().decode('utf-8', errors='ignore').strip())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_koreader_ext()
