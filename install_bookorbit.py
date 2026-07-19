import os
import shutil
import paramiko

KINDLE_IP = "192.168.68.82"
KINDLE_PORT = 2222
KINDLE_USER = "root"
KINDLE_PASSWORD = ""
SOURCE_DIR = r"C:\Users\admin-beats\Documents\antigravity\hopeful-bose\bookorbit\koreader-plugin\bookorbit.koplugin"
ZIP_FILE = "bookorbit.koplugin.zip"

def main():
    print("Zipping plugin directory...")
    # This creates bookorbit.koplugin.zip containing the directory 'bookorbit.koplugin'
    shutil.make_archive("bookorbit.koplugin", 'zip', root_dir=os.path.dirname(SOURCE_DIR), base_dir="bookorbit.koplugin")
    
    print(f"Connecting to Kindle at {KINDLE_IP}:{KINDLE_PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(KINDLE_IP, port=KINDLE_PORT, username=KINDLE_USER, password=KINDLE_PASSWORD)
    
    sftp = ssh.open_sftp()
    remote_zip = "/mnt/us/bookorbit.koplugin.zip"
    
    print("Uploading zip to Kindle...")
    sftp.put(ZIP_FILE, remote_zip)
    sftp.close()
    
    print("Unzipping on Kindle...")
    # unzip on the Kindle
    stdin, stdout, stderr = ssh.exec_command(f"unzip -o {remote_zip} -d /mnt/us/koreader/plugins/")
    stdout.channel.recv_exit_status()  # Wait for command to finish
    
    print("Cleaning up zip file on Kindle...")
    ssh.exec_command(f"rm {remote_zip}")
    
    print("Restarting KOReader...")
    # Depending on the jailbreak, killing koreader might auto-restart it or we might need to use lipc-set-prop
    ssh.exec_command("killall luajit")
    
    ssh.close()
    if os.path.exists(ZIP_FILE):
        os.remove(ZIP_FILE)
    print("Done!")

if __name__ == "__main__":
    main()
