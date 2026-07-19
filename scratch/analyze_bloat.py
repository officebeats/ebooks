import paramiko

KINDLES = {
    "older-floater": "192.168.68.82",
    "newer-backroom": "192.168.68.55",
    "white-bedroom": "192.168.68.93"
}

def analyze_device(name, ip):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"\n{'='*50}\nAnalyzing {name} ({ip})\n{'='*50}")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        print("\n--- RAM USAGE ---")
        stdin, stdout, stderr = client.exec_command("free -m")
        print(stdout.read().decode('utf-8').strip())
        
        print("\n--- STORAGE USAGE (df -h) ---")
        stdin, stdout, stderr = client.exec_command("df -h")
        print(stdout.read().decode('utf-8').strip())
        
        print("\n--- ROOT DIRECTORY SIZES (/mnt/us) ---")
        stdin, stdout, stderr = client.exec_command("du -sh /mnt/us/* | sort -rh | head -n 15")
        print(stdout.read().decode('utf-8').strip())
        
        print("\n--- POTENTIAL BLOAT (Logs, Updates, Caches) ---")
        # Check for large log files
        stdin, stdout, stderr = client.exec_command("find /mnt/us -name '*.log' -size +1M -exec ls -lh {} +")
        print("Large Logs:")
        print(stdout.read().decode('utf-8').strip())
        
        # Check for OTA update files
        stdin, stdout, stderr = client.exec_command("find /mnt/us -name '*.bin' -maxdepth 1 -exec ls -lh {} +")
        print("OTA Update bins:")
        print(stdout.read().decode('utf-8').strip())
        
        # Check for Amazon sidecar bloat (.sdr without matching book)
        stdin, stdout, stderr = client.exec_command("find /mnt/us/documents -name '*.sdr' | wc -l")
        print("Number of Amazon .sdr folders:", stdout.read().decode('utf-8').strip())

    except Exception as e:
        print(f"Error connecting/analyzing: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    for name, ip in KINDLES.items():
        analyze_device(name, ip)
