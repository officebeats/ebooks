import os
import paramiko
import shutil

WHITE_IP = "192.168.68.93"
PORT = 2222
USER = "root"
PASSWORD = ""

LOCAL_LAUNCHER_DIR = r"C:\Users\admin-beats\Documents\antigravity\hopeful-bose\koreader_home_launcher"

def pull_launcher():
    os.makedirs(LOCAL_LAUNCHER_DIR, exist_ok=True)
    os.makedirs(os.path.join(LOCAL_LAUNCHER_DIR, "koreader.sh.sdr"), exist_ok=True)
    os.makedirs(os.path.join(LOCAL_LAUNCHER_DIR, "koreader.sdr"), exist_ok=True)
    
    print(f"Connecting to White Bedroom ({WHITE_IP}) to pull launcher files...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(WHITE_IP, port=PORT, username=USER, password=PASSWORD)
    
    sftp = client.open_sftp()
    
    try:
        # Pull koreader.sh
        sftp.get("/mnt/us/documents/koreader.sh", os.path.join(LOCAL_LAUNCHER_DIR, "koreader.sh"))
        print("Pulled koreader.sh")
        
        # Pull icon.png
        sftp.get("/mnt/us/documents/koreader.sh.sdr/icon.png", os.path.join(LOCAL_LAUNCHER_DIR, "koreader.sh.sdr", "icon.png"))
        print("Pulled icon.png")
        
        # Pull metadata.sh.lua
        sftp.get("/mnt/us/documents/koreader.sdr/metadata.sh.lua", os.path.join(LOCAL_LAUNCHER_DIR, "koreader.sdr", "metadata.sh.lua"))
        print("Pulled metadata.sh.lua")
        
    except Exception as e:
        print(f"Error pulling files: {e}")
    finally:
        sftp.close()
        client.close()

if __name__ == "__main__":
    pull_launcher()
