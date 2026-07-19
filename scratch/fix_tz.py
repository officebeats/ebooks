import paramiko

def fix_timezone():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect("192.168.68.82", port=2222, username="root", password="", timeout=10)
        
        # Restore NTP
        client.exec_command("mntroot rw; mv /usr/sbin/ntpd.bak /usr/sbin/ntpd; mv /usr/bin/ntpdate.bak /usr/bin/ntpdate; mntroot ro")
        
        # Set LIPC timezone
        client.exec_command("lipc-set-prop com.lab126.wan timezone America/Chicago")
        
        # Inject TZ into koreader.sh
        client.exec_command("sed -i '/export LC_ALL/a export TZ=CST6CDT' /mnt/us/koreader/koreader.sh")
        
        print("Timezone fixed.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_timezone()
