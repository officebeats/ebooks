import os

with open('deploy_beats_kindle_config.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "[Deploy] Uploading Lua patches..." in line:
        lines.insert(i + 1, "        if not dry_run:\n            ssh.exec_command(\"rm -f /mnt/us/koreader/patches/4-auto-timesync.lua\")\n")
        break

with open('deploy_beats_kindle_config.py', 'w') as f:
    f.writelines(lines)
