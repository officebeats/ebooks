import urllib.request
import json
import hashlib
import paramiko
import os
import tempfile
import re

USERNAME = "beats_kindle_fleet_2026"
PASSWORD = "BeatsKindleSyncPassword2026!"
ENDPOINT = "https://sync.koreader.rocks"

md5_hash = hashlib.md5(PASSWORD.encode('utf-8')).hexdigest()
sha256_hash = hashlib.sha256(PASSWORD.encode('utf-8')).hexdigest()

print(f"Deploying Kosync Account Configuration...")
print(f"Username: {USERNAME}")
print(f"MD5 Hash: {md5_hash}")

# Ensure account exists on KOReader sync server
data = json.dumps({
    "username": USERNAME,
    "password": PASSWORD
}).encode('utf-8')

for pass_h in [md5_hash, sha256_hash]:
    try:
        req = urllib.request.Request(
            f"{ENDPOINT}/users/create",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/vnd.koreader.v1+json",
                "x-auth-user": USERNAME,
                "x-auth-key": pass_h,
                "User-Agent": "KOReader"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"Kosync Server User Create Response: {resp.status}")
    except Exception as e:
        pass

hosts_path = "kindle_hosts.json"
if os.path.exists(hosts_path):
    with open(hosts_path, "r", encoding="utf-8") as f:
        hosts = json.load(f)
else:
    hosts = {}

for nickname, device in hosts.items():
    ip = device.get("ip")
    port = device.get("port", 2222)
    user = device.get("user", "root")
    password = device.get("password", "")
    
    dev_short = nickname.split()[0].replace("-", "_")
    dev_id = f"kindle_{dev_short}"
    
    print(f"\n--- Deploying Kosync to {nickname} ({ip}:{port}) [Device ID: {dev_id}] ---")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port=port, username=user, password=password, timeout=5, look_for_keys=False, allow_agent=False)
        sftp = client.open_sftp()
        
        remote_path = "/mnt/us/koreader/settings.reader.lua"
        fd, local_temp = tempfile.mkstemp()
        os.close(fd)
        
        try:
            sftp.get(remote_path, local_temp)
            with open(local_temp, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = "return {\n}"

        # Map of string settings
        str_settings = {
            'kosync_username': USERNAME,
            'kosync_password_hash': md5_hash,
            'kosync_endpoint': ENDPOINT,
            'kosync_checksum_method': 'filename',
            'device_id': dev_id
        }
        
        for k, v in str_settings.items():
            pattern = rf'\["{k}"\]\s*=\s*"[^"]*",?\n?'
            if f'["{k}"]' in content:
                content = re.sub(pattern, f'["{k}"] = "{v}",\n', content)
            else:
                content = content.replace("return {", f'return {{\n    ["{k}"] = "{v}",')

        # Map of boolean auto-sync settings
        bool_settings = ['kosync_auto_sync', 'kosync_sync_on_open', 'kosync_sync_on_close']
        for flag in bool_settings:
            pattern = rf'\["{flag}"\]\s*=\s*[^,\n]+,?\n?'
            if f'["{flag}"]' in content:
                content = re.sub(pattern, f'["{flag}"] = true,\n', content)
            else:
                content = content.replace("return {", f'return {{\n    ["{flag}"] = true,')

        with open(local_temp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        sftp.put(local_temp, remote_path)
        sftp.close()
        os.remove(local_temp)
        
        # Restart KOReader cleanly
        client.exec_command("killall -9 reader.lua 2>/dev/null || true")
        client.exec_command("/mnt/us/koreader/koreader.sh /mnt/us/koreader >/dev/null 2>&1 &")
        client.close()
        print(f"  SUCCESS: Kosync reading progress sync configured on {nickname}!")
    except Exception as e:
        print(f"  Connection/Config error on {nickname}: {e}")

print("\nKosync Fleet Setup Complete!")
