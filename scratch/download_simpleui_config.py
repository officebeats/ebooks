import paramiko
import os
import stat

def download_simpleui_config():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.55"
    print(f"Connecting to newer-backroom at {ip}...")
    
    local_dir = r"C:\Users\admin-beats\Documents\antigravity\hopeful-bose\simpleui_config_backup"
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        sftp = client.open_sftp()
        
        remote_dir = "/mnt/us/koreader/settings/simpleui"
        
        def download_recursive(r_dir, l_dir):
            if not os.path.exists(l_dir):
                os.makedirs(l_dir)
            
            for item in sftp.listdir_attr(r_dir):
                r_path = r_dir + "/" + item.filename
                l_path = os.path.join(l_dir, item.filename)
                
                if stat.S_ISDIR(item.st_mode):
                    download_recursive(r_path, l_path)
                else:
                    if item.filename.endswith(".lua"):
                        print(f"Downloading {r_path}...")
                        sftp.get(r_path, l_path)
                        
        download_recursive(remote_dir, local_dir)
        print("Download complete!")
        sftp.close()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    download_simpleui_config()
