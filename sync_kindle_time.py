import paramiko
import os
import json
import argparse
from datetime import datetime

DEFAULT_KINDLE_IP = "192.168.68.89"
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""

def load_kindle_hosts():
    hosts_path = "kindle_hosts.json"
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {hosts_path}: {e}")
    return {}

def main():
    hosts_config = load_kindle_hosts()
    default_ip = DEFAULT_KINDLE_IP
    if "white" in hosts_config:
        default_ip = hosts_config["white"].get("ip", DEFAULT_KINDLE_IP)

    parser = argparse.ArgumentParser(description="Sync Kindle system clock with host computer local time")
    parser.add_argument("--ip", default=default_ip, help=f"Kindle IP address or host nickname (default: {default_ip})")
    parser.add_argument("--port", type=int, help="Kindle SSH port")
    parser.add_argument("--user", default=DEFAULT_KINDLE_USER, help=f"Kindle SSH user (default: {DEFAULT_KINDLE_USER})")
    parser.add_argument("--password", default=DEFAULT_KINDLE_PASSWORD, help="Kindle SSH password")
    
    args = parser.parse_args()
    
    # Resolve from hosts config if nickname is used
    for nickname in [args.ip, f"{args.ip}_kindle"]:
        if nickname in hosts_config:
            device = hosts_config[nickname]
            args.ip = device.get("ip", args.ip)
            args.port = device.get("port", args.port) or args.port
            args.user = device.get("user", args.user) or args.user
            args.password = device.get("password", args.password) or args.password
            break
            
    port = args.port or 2222
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to Kindle at {args.ip}:{port}...")
        ssh.connect(args.ip, port=port, username=args.user, password=args.password, timeout=5, look_for_keys=False, allow_agent=False)
        
        # 1. Get current Kindle time
        stdin, stdout, stderr = ssh.exec_command("date")
        kindle_time = stdout.read().decode('utf-8').strip()
        print(f"  Current Kindle time:  {kindle_time}")
        
        # 2. Get local time
        local_now = datetime.now()
        local_formatted = local_now.strftime("%Y-%m-%d %H:%M:%S")
        print(f"  Local computer time:  {local_formatted}")
        
        # 3. Set Kindle time
        print("  Updating Kindle clock...")
        stdin, stdout, stderr = ssh.exec_command(f'date -s "{local_formatted}"')
        err = stderr.read().decode('utf-8').strip()
        if err:
            print(f"  Error setting time: {err}")
            return
            
        # 4. Save to hardware clock
        ssh.exec_command("hwclock -w")
        print("  Hardware clock saved.")
        
        # 5. Verify
        stdin, stdout, stderr = ssh.exec_command("date")
        updated_time = stdout.read().decode('utf-8').strip()
        print(f"  Verified Kindle time: {updated_time}")
        print("\nClock synced successfully!")
        
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
