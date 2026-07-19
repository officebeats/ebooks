import paramiko

def check_crash():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.55"
    print(f"Connecting to newer-backroom at {ip}...")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        # KOReader logs crashes to crash.log in its root directory or /mnt/us/crash.log
        cmd = "tail -n 50 /mnt/us/crash.log 2>/dev/null || tail -n 50 /mnt/us/koreader/crash.log 2>/dev/null"
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        print("CRASH LOG:")
        print(out if out else "No crash log found.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_crash()
