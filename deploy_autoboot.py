import paramiko
import time

KINDLES = [
    {"name": "older-floater", "ip": "192.168.68.82"},
    {"name": "newer-backroom", "ip": "192.168.68.55"},
    {"name": "white-bedroom", "ip": "192.168.68.93"}
]

UPSTART_SCRIPT = """start on started lab126_gui

script
    # Wait for framework and UI to settle before hijacking
    /bin/sleep 30s
    if [ -x /mnt/us/extensions/koreader/bin/koreader-ext.sh ]; then
        exec /mnt/us/extensions/koreader/bin/koreader-ext.sh --kual --framework_stop
    fi
end script
"""

def deploy_autoboot():
    for kindle in KINDLES:
        name = kindle["name"]
        ip = kindle["ip"]
        print(f"Deploying to {name} ({ip})...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            client.connect(ip, port=2222, username="root", password="", timeout=10)
            
            # Remove crash dumps and bloat first
            print("  -> Cleaning up bloat and crash dumps...")
            client.exec_command("rm -f /mnt/us/KPPMainAppV2_*.core")
            client.exec_command("rm -f /mnt/us/update.bin.tmp.partial")
            
            # Check upstart directory path
            stdin, stdout, stderr = client.exec_command("if [ -d /etc/upstart ]; then echo '/etc/upstart'; else echo '/etc/init'; fi")
            upstart_dir = stdout.read().decode('utf-8').strip()
            
            # Remount root as read-write
            print(f"  -> Remounting root rw and writing to {upstart_dir}/koreader-autoboot.conf...")
            client.exec_command("mntroot rw")
            time.sleep(1)
            
            # Write the file
            sftp = client.open_sftp()
            with sftp.file(f"{upstart_dir}/koreader-autoboot.conf", 'w') as f:
                f.write(UPSTART_SCRIPT)
            sftp.close()
            
            # Remount read-only
            client.exec_command("mntroot ro")
            print("  -> Done.")
            
        except Exception as e:
            print(f"  -> Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    deploy_autoboot()
