import paramiko

hosts = [
    ("white-bedroom", "192.168.68.93", 2222),
    ("older-floater", "192.168.68.82", 2222)
]

print("Enforcing KOReader & KUAL Launcher-Only Native Amazon Home Screen...")

for name, ip, port in hosts:
    print(f"\n--- Cleaning documents directory on {name} ({ip}:{port}) ---")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port=port, username="root", password="", timeout=5, look_for_keys=False, allow_agent=False)
        
        script = """
        mkdir -p /mnt/us/epubs
        
        echo "Current items in /mnt/us/documents before cleanup:"
        ls -la /mnt/us/documents/
        
        for item in /mnt/us/documents/*; do
            [ -e "$item" ] || continue
            base=$(basename "$item")
            
            # Explicitly protect KOReader and KUAL launchers and dictionaries
            if echo "$base" | grep -iqE "koreader|kual|KUAL|dictionaries"; then
                continue
            fi
            
            # Move ebook files to /mnt/us/epubs/
            if echo "$base" | grep -iqE "\\.(epub|mobi|azw3|azw|azw1|pdf|txt|docx|cbz|cbr|fb2|prc|tpz|html)$"; then
                echo "Moving ebook to /mnt/us/epubs/: $base"
                mv "$item" "/mnt/us/epubs/" 2>/dev/null || true
                if [ -d "/mnt/us/documents/${base}.sdr" ]; then
                    mv "/mnt/us/documents/${base}.sdr" "/mnt/us/epubs/" 2>/dev/null || true
                fi
            else
                echo "Deleting non-launcher item from /mnt/us/documents/: $base"
                rm -rf "$item" 2>/dev/null || true
            fi
        done
        
        # Self-healing: move any stray KOReader/KUAL files back to /mnt/us/documents/ if moved accidentally
        for pattern in "koreader" "kual" "KUAL"; do
            for f in /mnt/us/epubs/*${pattern}*; do
                [ -e "$f" ] || continue
                mv "$f" "/mnt/us/documents/" 2>/dev/null || true
            done
        done
        
        # Remove empty non-dictionary folders
        find /mnt/us/documents -mindepth 1 -maxdepth 1 -type d -not -name "dictionaries" -not -name "*.sdr" -exec rm -rf {} \\; 2>/dev/null || true
        
        # Refresh native home booklet view
        lipc-set-prop com.lab126.booklet.home setFilterId 1 2>/dev/null || true
        
        echo "\nFinal items in /mnt/us/documents/ after cleanup:"
        ls -la /mnt/us/documents/
        """
        
        stdin, stdout, stderr = client.exec_command(script)
        print(stdout.read().decode('utf-8', errors='ignore'))
        client.close()
        print(f"SUCCESS: {name} native home screen cleaned!")
    except Exception as e:
        print(f"Could not connect/clean {name}: {e}")
