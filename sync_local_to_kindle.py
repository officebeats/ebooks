import os
import sys
import hashlib
import argparse
import paramiko

import json

# Configurations
DEFAULT_KINDLE_IP = "192.168.68.70"
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""
LOCAL_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks\Epubs"
REMOTE_BOOKS_DIR = "/mnt/us/epubs"

def load_kindle_hosts():
    """Load Kindle hosts config from local JSON if it exists."""
    hosts_path = "kindle_hosts.json"
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {hosts_path}: {e}")
    return {}

def get_file_md5(filepath):
    """Calculate MD5 hash of a local file in chunks."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower()
    except Exception as e:
        print(f"Error calculating MD5 for {filepath}: {e}")
        return None

def get_remote_file_md5(ssh, remote_path):
    """Run md5sum on the Kindle to get the remote file's MD5 hash."""
    escaped_path = remote_path.replace('"', '\\"')
    cmd = f'md5sum "{escaped_path}"'
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        if out:
            parts = out.split()
            if parts:
                return parts[0].lower()
                
        # Fallback
        cmd_fallback = f'openssl md5 "{escaped_path}"'
        stdin, stdout, stderr = ssh.exec_command(cmd_fallback, timeout=5)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        if out:
            parts = out.split('=')
            if len(parts) > 1:
                return parts[1].strip().lower()
    except Exception:
        pass
    return None

def test_connection(ip, port, user, password):
    """Test SSH connection to Kindle."""
    print(f"Connecting to Kindle at {ip}:{port}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, port=port, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
        return ssh
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def build_connection(ip, port, user, password):
    if port:
        return test_connection(ip, port, user, password)
    ssh = test_connection(ip, 2222, user, password)
    if not ssh:
        ssh = test_connection(ip, 22, user, password)
    return ssh

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    hosts_config = load_kindle_hosts()

    parser = argparse.ArgumentParser(description="Sync missing books from local folder back to Kindle")
    parser.add_argument("--ip", help="Kindle IP address or host nickname (syncs all active hosts in kindle_hosts.json if omitted)")
    parser.add_argument("--port", type=int, help="Kindle SSH port")
    parser.add_argument("--user", default=DEFAULT_KINDLE_USER, help=f"Kindle SSH user (default: {DEFAULT_KINDLE_USER})")
    parser.add_argument("--password", default=DEFAULT_KINDLE_PASSWORD, help="Kindle SSH password")
    parser.add_argument("--dry-run", action="store_true", help="Dry run: print what would be uploaded without doing it")
    
    args = parser.parse_args()
    dry_run = args.dry_run
    
    # 1. Scan local folder and calculate MD5s
    print("=== Syncing Local Books Delta to Kindle Fleet ===")
    print(f"Scanning local directory: {LOCAL_DIR}...")
    local_files = [os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR) if f.lower().endswith('.epub')]
    print(f"Found {len(local_files)} local EPUB files.")
    
    local_by_md5 = {}
    for lf in local_files:
        h = get_file_md5(lf)
        if h:
            local_by_md5[h] = lf

    # Determine targets
    targets = []
    if args.ip:
        resolved_ip = args.ip
        target_port = args.port
        target_user = args.user
        target_pwd = args.password
        for key, device in hosts_config.items():
            ip_addr = device.get("ip", "")
            if args.ip == key or args.ip in key or args.ip == ip_addr or args.ip in ip_addr:
                resolved_ip = ip_addr
                target_port = device.get("port", target_port) or target_port
                target_user = device.get("user", target_user) or target_user
                target_pwd = device.get("password", target_pwd) or target_pwd
                break
        targets.append((key if 'key' in locals() else args.ip, resolved_ip, target_port, target_user, target_pwd))
    else:
        for key, device in hosts_config.items():
            targets.append((key, device.get("ip"), device.get("port"), device.get("user", DEFAULT_KINDLE_USER), device.get("password", DEFAULT_KINDLE_PASSWORD)))

    for host_name, target_ip, target_port, target_user, target_pwd in targets:
        print(f"\n" + "="*60)
        print(f" Syncing with device: {host_name} ({target_ip})")
        print("="*60)
        
        ssh = build_connection(target_ip, target_port, target_user, target_pwd)
        if not ssh:
            print(f"WARNING: Could not connect to Kindle at {target_ip}. Skipping.")
            continue
            
        sftp = ssh.open_sftp()
        try:
            ssh.exec_command(f"mkdir -p {REMOTE_BOOKS_DIR}")
            print("Scanning Kindle for existing books...")
            find_cmd = f'find {REMOTE_BOOKS_DIR} -name "*.epub" 2>/dev/null'
            stdin, stdout, stderr = ssh.exec_command(find_cmd)
            remote_paths = [line.strip() for line in stdout.read().decode('utf-8', errors='ignore').splitlines() if line.strip()]
            print(f"Found {len(remote_paths)} EPUB files on Kindle.")
            
            remote_md5s = set()
            for rp in remote_paths:
                h = get_remote_file_md5(ssh, rp)
                if h:
                    remote_md5s.add(h)
                    
            print("\nCalculating delta (books missing from this Kindle)...")
            to_upload = [lf for h, lf in local_by_md5.items() if h not in remote_md5s]
            print(f"Found {len(to_upload)} books to upload.")
            
            uploaded_count = 0
            error_count = 0
            for lf in to_upload:
                basename = os.path.basename(lf)
                remote_dest = f"{REMOTE_BOOKS_DIR}/{basename}"
                print(f"Uploading: {basename}")
                if not dry_run:
                    try:
                        sftp.put(lf, remote_dest)
                        sftp.chmod(remote_dest, 0o777)
                        print("  Status: Uploaded successfully!")
                        uploaded_count += 1
                    except Exception as e:
                        print(f"  Error uploading file: {e}")
                        error_count += 1
                else:
                    print(f"  [Dry Run] Would upload -> {remote_dest}")
                    uploaded_count += 1
                    
            print(f"\nDevice {host_name} Sync Completed: {uploaded_count} uploaded, {error_count} errors.")
        finally:
            sftp.close()
            ssh.close()

if __name__ == "__main__":
    main()
