import paramiko

def check_kual_menu():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect("192.168.68.82", port=2222, username="root", password="", timeout=10)
        
        stdin, stdout, stderr = client.exec_command("cat /mnt/us/extensions/koreader/menu.json")
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        print("menu.json on older-floater:")
        print(out)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_kual_menu()
