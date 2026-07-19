import paramiko

def find_simpleui_settings():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.55"
    print(f"Connecting to newer-backroom at {ip}...")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        print("--- checking plugins directory ---")
        stdin, stdout, stderr = client.exec_command("ls -la /mnt/us/koreader/plugins/simpleui.koplugin/")
        print(stdout.read().decode('utf-8', errors='ignore'))
        
        print("--- checking settings directory ---")
        stdin, stdout, stderr = client.exec_command("ls -la /mnt/us/koreader/settings/ | grep -i simple")
        print(stdout.read().decode('utf-8', errors='ignore'))
        
        print("--- checking global settings.reader.lua ---")
        stdin, stdout, stderr = client.exec_command("cat /mnt/us/koreader/settings.reader.lua | grep -i simple")
        print(stdout.read().decode('utf-8', errors='ignore'))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    find_simpleui_settings()
