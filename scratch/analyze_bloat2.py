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
        
        print("\n--- ROOT DIRECTORY SIZES (/mnt/us) ---")
        stdin, stdout, stderr = client.exec_command("du -s /mnt/us/* | sort -nr | head -n 15")
        print(stdout.read().decode('utf-8').strip())
        
    except Exception as e:
        print(f"Error connecting/analyzing: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    for name, ip in KINDLES.items():
        analyze_device(name, ip)
