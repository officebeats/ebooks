import paramiko
import time

def check_upstart():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = "192.168.68.93"  # white-bedroom
    try:
        client.connect(ip, port=2222, username="root", password="", timeout=10)
        
        stdin, stdout, stderr = client.exec_command("ls /etc/upstart/")
        print("Upstart dir:")
        print(stdout.read().decode('utf-8', errors='ignore').strip())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_upstart()
