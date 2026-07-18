import os
import re
import argparse
import paramiko

import json

# Configurations
def get_kindle_ips():
    try:
        with open("kindle_hosts.json", "r") as f:
            data = json.load(f)
            return [device["ip"] for device in data.values()]
    except Exception:
        return ["192.168.68.82", "192.168.68.70"]

KINDLE_IPS = get_kindle_ips()
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""
LOCAL_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks\Epubs"

def normalize_filename(filename):
    """Normalize filename to compare names for potential duplicates."""
    name = os.path.splitext(filename)[0]
    # Remove trailing parenthesis patterns like (237) or (97)
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\(Z-Library\)', '', name, flags=re.IGNORECASE)
    # Remove non-alphanumeric chars
    name = re.sub(r'[^a-z0-9]', '', name.lower())
    return name

def evaluate_filename_quality(filename):
    """Evaluate how 'clean' a filename is. Lower score is cleaner."""
    score = 0
    basename = filename.lower()
    if re.search(r'\(\d+\)', basename):
        score += 100
    if re.search(r'_\d+', basename):
        score += 50
    if 'copy' in basename:
        score += 150
    if 'z-library' in basename:
        score += 80
    score += len(filename) * 0.1
    return score

def select_best_file_to_keep(filenames):
    """Select the best filename (cleanest) from a list of duplicates."""
    if not filenames:
        return None
    return min(filenames, key=evaluate_filename_quality)

def test_connection(ip, port, user, password):
    """Test SSH connection to Kindle."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, port=port, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
        return ssh
    except Exception:
        return None

def build_connection(ip, port, user, password):
    ssh = test_connection(ip, 2222, user, password)
    if not ssh:
        ssh = test_connection(ip, 22, user, password)
    return ssh

def clean_remote_kindle(ip, sftp, ssh, dry_run=False):
    print(f"\nScanning Kindle at {ip} for duplicates...")
    # Search for all epubs on Kindle
    find_cmd = 'find /mnt/us -name "*.epub" ! -path "/mnt/us/system/*" 2>/dev/null'
    stdin, stdout, stderr = ssh.exec_command(find_cmd)
    remote_paths = [line.strip() for line in stdout.read().decode('utf-8', errors='ignore').splitlines() if line.strip()]
    
    print(f"Found {len(remote_paths)} EPUB files on Kindle {ip}.")
    
    # Group remote paths by normalized name
    by_norm = {}
    for rp in remote_paths:
        basename = os.path.basename(rp)
        norm = normalize_filename(basename)
        if norm not in by_norm:
            by_norm[norm] = []
        by_norm[norm].append(rp)
        
    removed_count = 0
    for norm, paths in by_norm.items():
        if len(paths) > 1:
            # We have duplicates! Choose the best one to keep
            basenames = [os.path.basename(p) for p in paths]
            best_basename = select_best_file_to_keep(basenames)
            best_path = next(p for p in paths if os.path.basename(p) == best_basename)
            
            print(f"\n[Duplicate Found on Kindle {ip}] Group: {norm}")
            for p in paths:
                mark = "KEEP" if p == best_path else "DELETE"
                print(f"  - {os.path.basename(p)} ({mark})")
                
            # Delete others
            for p in paths:
                if p != best_path:
                    if not dry_run:
                        try:
                            sftp.remove(p)
                            print(f"  Deleted remote file: {os.path.basename(p)}")
                            removed_count += 1
                        except Exception as e:
                            print(f"  Error deleting remote file {p}: {e}")
                    else:
                        print(f"  [Dry Run] Would delete remote file: {os.path.basename(p)}")
                        removed_count += 1
    return removed_count

def clean_local(dry_run=False):
    print(f"\nScanning local folder: {LOCAL_DIR} for duplicates...")
    local_files = [f for f in os.listdir(LOCAL_DIR) if f.lower().endswith('.epub')]
    
    by_norm = {}
    for f in local_files:
        norm = normalize_filename(f)
        if norm not in by_norm:
            by_norm[norm] = []
        by_norm[norm].append(f)
        
    removed_count = 0
    for norm, files in by_norm.items():
        if len(files) > 1:
            best_file = select_best_file_to_keep(files)
            print(f"\n[Duplicate Found Locally] Group: {norm}")
            for f in files:
                mark = "KEEP" if f == best_file else "DELETE"
                print(f"  - {f} ({mark})")
                
            for f in files:
                if f != best_file:
                    path = os.path.join(LOCAL_DIR, f)
                    if not dry_run:
                        try:
                            os.remove(path)
                            print(f"  Deleted local file: {f}")
                            removed_count += 1
                        except Exception as e:
                            print(f"  Error deleting local file {f}: {e}")
                    else:
                        print(f"  [Dry Run] Would delete local file: {f}")
                        removed_count += 1
    return removed_count

def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    parser = argparse.ArgumentParser(description="Deduplicate local folder and Kindles by normalized filenames")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting")
    args = parser.parse_args()
    
    dry_run = args.dry_run
    print("=== DEDUPLICATING EPUB LIBRARIES BY FILENAME ===")
    if dry_run:
        print(">>> DRY RUN ACTIVE: No files will be deleted.")
        
    # 1. Clean local folder
    local_deleted = clean_local(dry_run)
    
    # 2. Clean each Kindle
    kindle_deleted = {}
    for ip in KINDLE_IPS:
        ssh = build_connection(ip, DEFAULT_KINDLE_PORT, DEFAULT_KINDLE_USER, DEFAULT_KINDLE_PASSWORD)
        if not ssh:
            print(f"\nWARNING: Could not connect to Kindle at {ip}. Skipping.")
            continue
            
        sftp = ssh.open_sftp()
        try:
            kindle_deleted[ip] = clean_remote_kindle(ip, sftp, ssh, dry_run)
            
            # Restart KOReader to update UI library view
            if kindle_deleted[ip] > 0 and not dry_run:
                print(f"\nRestarting KOReader on Kindle {ip} to apply deduplication...")
                ssh.exec_command("killall reader.lua")
        finally:
            sftp.close()
            ssh.close()
            
    print("\n" + "="*50)
    print(" DEDUPLICATION SUMMARY")
    print("="*50)
    print(f"  Local files deleted:     {local_deleted}")
    for ip, count in kindle_deleted.items():
        print(f"  Kindle ({ip}) files deleted: {count}")
    print("="*50)

if __name__ == "__main__":
    main()
