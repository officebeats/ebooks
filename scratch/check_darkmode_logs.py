import paramiko

def check_logs():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect("192.168.68.82", port=2222, username="root", password="", timeout=10)
        
        stdin, stdout, stderr = client.exec_command("curl -s http://worldtimeapi.org/api/timezone/America/Chicago")
        out = stdout.read().decode('utf-8').strip()
        print("API Response:")
        print(out)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_logs()
