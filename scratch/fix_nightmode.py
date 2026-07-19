import paramiko
import tempfile
import os
import re

def fix_nightmode():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.82"
    print(f"Connecting to older-floater at {ip}...")
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        # 1. Kill KOReader so it doesn't overwrite our changes
        print("Killing KOReader...")
        client.exec_command("killall luajit")
        
        # 2. Get settings file
        remote_path = "/mnt/us/koreader/settings.reader.lua"
        sftp = client.open_sftp()
        fd, local_temp = tempfile.mkstemp()
        os.close(fd)
        sftp.get(remote_path, local_temp)
        
        # 3. Patch settings
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Remove global night_mode if it's set to true
        content = re.sub(r'\["night_mode"\]\s*=\s*true,?', '["night_mode"] = false,', content)
        
        # Fix location
        if '["autowarmth_location"]' in content:
            content = re.sub(r'\["autowarmth_location"\]\s*=\s*.*?,', '["autowarmth_location"] = {\n        [1] = 41.8781,\n        [2] = -87.6298,\n    },', content, flags=re.DOTALL)
            
        with open(local_temp, "w", encoding="utf-8") as f:
            f.write(content)
            
        # 4. Upload and restart
        sftp.put(local_temp, remote_path)
        sftp.close()
        print("Settings patched!")
        
        print("Restarting framework to trigger autoboot...")
        client.exec_command("stop lab126_gui && start lab126_gui")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(local_temp):
            os.remove(local_temp)
        client.close()

if __name__ == "__main__":
    fix_nightmode()
