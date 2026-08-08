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

CACHE_FILE = os.path.join(os.path.dirname(__file__), "local_md5_cache.json")

def load_md5_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_md5_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass

def get_file_md5(filepath, cache=None):
    """Calculate MD5 hash of a local file in chunks with caching."""
    try:
        st = os.stat(filepath)
        key = filepath
        mtime = st.st_mtime
        size = st.st_size
        if cache is not None and key in cache:
            entry = cache[key]
            if entry.get("mtime") == mtime and entry.get("size") == size:
                return entry.get("md5")
        
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        res = hasher.hexdigest().lower()
        if cache is not None:
            cache[key] = {"mtime": mtime, "size": size, "md5": res}
        return res
    except Exception as e:
        print(f"Error calculating MD5 for {filepath}: {e}")
        return None

def get_all_remote_md5s(ssh, remote_dir):
    """Run batch md5sum on the Kindle to get all remote file MD5 hashes rapidly."""
    escaped_dir = remote_dir.replace('"', '\\"')
    cmd = f'find "{escaped_dir}" -name "*.epub" -exec md5sum {{}} +'
    remote_md5s = set()
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode('utf-8', errors='ignore')
        for line in out.splitlines():
            parts = line.strip().split()
            if parts and len(parts[0]) == 32:
                remote_md5s.add(parts[0].lower())
    except Exception as e:
        print(f"Error getting batch remote MD5s: {e}")
    return remote_md5s

def normalize_name(filename):
    return "".join(c.lower() for c in os.path.basename(filename) if c.isalnum())

def test_connection(ip, port, user, password):
    """Test SSH connection to Kindle."""
    print(f"Connecting to Kindle at {ip}:{port}...", flush=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, port=port, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
        return ssh
    except Exception as e:
        print(f"Failed to connect: {e}", flush=True)
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
    
    # 1. Scan local folder
    print("=== Syncing Local Books Delta to Kindle Fleet ===", flush=True)
    print(f"Scanning local directory: {LOCAL_DIR}...", flush=True)
    local_files = [os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR) if f.lower().endswith('.epub')]
    print(f"Found {len(local_files)} local EPUB files.", flush=True)

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
        print(f"\n" + "="*60, flush=True)
        print(f" Syncing with device: {host_name} ({target_ip})", flush=True)
        print("="*60, flush=True)
        
        ssh = build_connection(target_ip, target_port, target_user, target_pwd)
        if not ssh:
            print(f"WARNING: Could not connect to Kindle at {target_ip}. Skipping.", flush=True)
            continue
            
        sftp = ssh.open_sftp()
        try:
            ssh.exec_command(f"mkdir -p {REMOTE_BOOKS_DIR}")
            print("Scanning Kindle for existing books via SFTP...", flush=True)
            try:
                remote_files = sftp.listdir(REMOTE_BOOKS_DIR)
            except Exception:
                remote_files = []
            
            remote_epubs = [f for f in remote_files if f.lower().endswith('.epub')]
            remote_normalized = set(normalize_name(f) for f in remote_epubs)
            print(f"Found {len(remote_epubs)} EPUB files on Kindle.", flush=True)
                    
            print("\nCalculating delta (books missing from this Kindle)...", flush=True)
            to_upload = [lf for lf in local_files if normalize_name(lf) not in remote_normalized]
            print(f"Found {len(to_upload)} books to upload to {host_name}.", flush=True)
            
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
