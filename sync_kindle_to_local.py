import os
import re
import sys
import hashlib
import argparse
import paramiko
import socket

# Configurations
DEFAULT_KINDLE_IP = "192.168.68.82"
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""
DEFAULT_LOCAL_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks\Epubs"

def get_file_md5(filepath):
    """Calculate MD5 hash of a local file in chunks."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error calculating MD5 for {filepath}: {e}")
        return None

def normalize_filename(filename):
    """Normalize filename to compare names for potential duplicates."""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\(Z-Library\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^a-z0-9]', '', name.lower())
    return name

def evaluate_filename_quality(filename):
    """
    Evaluate how 'clean' a filename is. Lower score is cleaner.
    Penalizes duplicate suffixes, Z-Library tags, and long names.
    """
    score = 0
    basename = filename.lower()
    
    # Penalize common copy patterns
    if re.search(r'\(\d+\)', basename):
        score += 100
    if re.search(r'_\d+', basename):
        score += 50
    if 'copy' in basename:
        score += 150
    if 'z-library' in basename:
        score += 80
        
    # Favor slightly shorter filenames (avoiding long trailing noise)
    score += len(filename) * 0.1
    return score

def select_best_file_to_keep(filepaths):
    """Select the file path with the cleanest filename from a list of duplicates."""
    if not filepaths:
        return None
    return min(filepaths, key=lambda p: evaluate_filename_quality(os.path.basename(p)))

def get_remote_file_md5(ssh, remote_path):
    """Run md5sum on the Kindle to get the remote file's MD5 hash."""
    # Escape path for shell execution
    escaped_path = remote_path.replace('"', '\\"')
    cmd = f'md5sum "{escaped_path}"'
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        err = stderr.read().decode('utf-8', errors='ignore').strip()
        
        if out:
            # md5sum outputs "hash  filename"
            parts = out.split()
            if parts:
                return parts[0].lower()
        
        # Try openssl md5 as fallback
        cmd_fallback = f'openssl md5 "{escaped_path}"'
        stdin, stdout, stderr = ssh.exec_command(cmd_fallback, timeout=5)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        if out:
            # openssl md5 outputs "MD5(filename)= hash"
            parts = out.split('=')
            if len(parts) > 1:
                return parts[1].strip().lower()
                
    except Exception as e:
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
        print(f"Failed to connect on port {port}: {e}")
        return None

def main():
    # Set encoding to prevent print errors with Unicode book titles
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Sync and deduplicate EPUBs from Kindle to local folder")
    parser.add_argument("--ip", default=DEFAULT_KINDLE_IP, help=f"Kindle IP address (default: {DEFAULT_KINDLE_IP})")
    parser.add_argument("--port", type=int, help="Kindle SSH port (tries 2222 and 22 by default)")
    parser.add_argument("--user", default=DEFAULT_KINDLE_USER, help=f"Kindle SSH user (default: {DEFAULT_KINDLE_USER})")
    parser.add_argument("--password", default=DEFAULT_KINDLE_PASSWORD, help="Kindle SSH password")
    parser.add_argument("--local-dir", default=DEFAULT_LOCAL_DIR, help=f"Local target directory (default: {DEFAULT_LOCAL_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="Dry run: preview changes without writing/deleting files")
    parser.add_argument("--exclude", action="append", help="Exclude files matching string/pattern")
    
    args = parser.parse_args()
    
    local_dir = args.local_dir
    dry_run = args.dry_run
    
    print(f"=== Kindle EPUB Sync & Deduplicate ===")
    if dry_run:
        print(">>> DRY RUN MODE ACTIVE - No changes will be written or files deleted.")
    print(f"Local Directory: {local_dir}")
    os.makedirs(local_dir, exist_ok=True)
    
    # 1. Index local files and calculate MD5
    print("\nScanning local directory for existing EPUBs...")
    local_files = [os.path.join(local_dir, f) for f in os.listdir(local_dir) if f.lower().endswith('.epub')]
    print(f"Found {len(local_files)} local EPUB files.")
    
    # Group local files by MD5 to identify existing duplicates
    local_by_md5 = {}
    print("Calculating local file checksums...")
    for filepath in local_files:
        h = get_file_md5(filepath)
        if h:
            if h not in local_by_md5:
                local_by_md5[h] = []
            local_by_md5[h].append(filepath)
            
    # Deduplicate local files (if same MD5 exists multiple times)
    local_duplicates_to_remove = []
    active_local_md5s = set()
    
    for h, paths in local_by_md5.items():
        if len(paths) > 1:
            best_path = select_best_file_to_keep(paths)
            print(f"\n[Duplicate Content Found] {len(paths)} identical files (MD5: {h}):")
            for p in paths:
                mark = "KEEP" if p == best_path else "DELETE"
                print(f"  - {os.path.basename(p)} ({mark})")
            
            for p in paths:
                if p != best_path:
                    local_duplicates_to_remove.append(p)
            active_local_md5s.add(h)
        else:
            active_local_md5s.add(h)
            
    # Perform local deletion of duplicates if not in dry-run
    if local_duplicates_to_remove:
        print(f"\nIdentified {len(local_duplicates_to_remove)} local duplicate files to clean up.")
        for p in local_duplicates_to_remove:
            if not dry_run:
                try:
                    os.remove(p)
                    print(f"Deleted local duplicate: {os.path.basename(p)}")
                except Exception as e:
                    print(f"Error deleting local duplicate {p}: {e}")
            else:
                print(f"[Dry Run] Would delete local duplicate: {os.path.basename(p)}")
                
    # 2. Connect to Kindle
    ssh = None
    if args.port:
        ssh = test_connection(args.ip, args.port, args.user, args.password)
    else:
        # Try port 2222 first, then 22
        ssh = test_connection(args.ip, 2222, args.user, args.password)
        if not ssh:
            print("Port 2222 failed. Trying port 22...")
            ssh = test_connection(args.ip, 22, args.user, args.password)
            
    if not ssh:
        print("\nERROR: Could not connect to Kindle. Please verify:")
        print("  - Kindle is awake and connected to Wi-Fi")
        print(f"  - IP address '{args.ip}' is correct")
        print("  - SSH service is active on the Kindle")
        sys.exit(1)
        
    print("Connected successfully to Kindle!")
    
    sftp = None
    try:
        sftp = ssh.open_sftp()
        
        # 3. Search Kindle for EPUBs
        print("\nSearching Kindle for EPUB files...")
        # Search /mnt/us and exclude system folders
        find_cmd = 'find /mnt/us -name "*.epub" ! -path "/mnt/us/system/*" 2>/dev/null'
        stdin, stdout, stderr = ssh.exec_command(find_cmd)
        kindle_files = [line.strip() for line in stdout.read().decode('utf-8', errors='ignore').splitlines() if line.strip()]
        
        print(f"Found {len(kindle_files)} EPUB files on Kindle.")
        
        # 4. Sync files
        download_count = 0
        skip_count = 0
        error_count = 0
        
        for k_path in kindle_files:
            basename = os.path.basename(k_path)
            print(f"\nProcessing remote file: {basename}")
            
            # Check exclusions
            exclude_match = False
            if args.exclude:
                for pattern in args.exclude:
                    if pattern.lower() in basename.lower() or pattern.lower() in k_path.lower():
                        exclude_match = True
                        break
            if exclude_match:
                print("  Status: Excluded by pattern. Skipping.")
                skip_count += 1
                continue
            
            # Check size from SFTP
            try:
                stat = sftp.stat(k_path)
                remote_size = stat.st_size
            except Exception as e:
                print(f"  Error reading Kindle file size: {e}")
                error_count += 1
                continue
                
            # Get remote MD5 hash
            print("  Calculating remote checksum...")
            remote_md5 = get_remote_file_md5(ssh, k_path)
            
            if remote_md5:
                print(f"  MD5: {remote_md5} | Size: {remote_size} bytes")
                # Check if we already have this file by MD5
                if remote_md5 in active_local_md5s:
                    print("  Status: Already synced (duplicate content found locally). Skipping.")
                    skip_count += 1
                    continue
            else:
                # If remote MD5 fails, fallback to name and size comparison
                print("  Warning: Remote MD5 check failed. Falling back to name and size comparison.")
                local_name_match = False
                for h in active_local_md5s:
                    # Look at local files for this hash
                    local_paths = local_by_md5.get(h, [])
                    for lp in local_paths:
                        if os.path.basename(lp) == basename and os.path.getsize(lp) == remote_size:
                            local_name_match = True
                            break
                    if local_name_match:
                        break
                if local_name_match:
                    print("  Status: File with same name and size exists. Skipping.")
                    skip_count += 1
                    continue
            
            # Download file
            local_dest = os.path.join(local_dir, basename)
            
            # Avoid naming conflicts in local_dest if file with same name but different MD5 exists
            if os.path.exists(local_dest):
                base_no_ext, ext = os.path.splitext(basename)
                counter = 1
                while os.path.exists(os.path.join(local_dir, f"{base_no_ext}_{counter}{ext}")):
                    counter += 1
                local_dest = os.path.join(local_dir, f"{base_no_ext}_{counter}{ext}")
                print(f"  Name conflict resolved. Downloading as: {os.path.basename(local_dest)}")
            
            print(f"  Downloading to {local_dest}...")
            if not dry_run:
                try:
                    sftp.get(k_path, local_dest)
                    # Add to tracking
                    download_count += 1
                    if remote_md5:
                        active_local_md5s.add(remote_md5)
                        if remote_md5 not in local_by_md5:
                            local_by_md5[remote_md5] = []
                        local_by_md5[remote_md5].append(local_dest)
                    print("  Download complete!")
                except Exception as e:
                    print(f"  Error downloading file: {e}")
                    error_count += 1
            else:
                print(f"  [Dry Run] Would download to: {local_dest}")
                download_count += 1
                
        print("\n" + "="*50)
        print(" SYNCHRONIZATION SUMMARY")
        print("="*50)
        print(f"  Total remote files found: {len(kindle_files)}")
        print(f"  Downloaded:               {download_count}")
        print(f"  Skipped (duplicates):     {skip_count}")
        print(f"  Errors:                   {error_count}")
        print("="*50)
        
    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()
            print("\nSSH connection closed.")

if __name__ == "__main__":
    main()
