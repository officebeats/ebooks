import os
import json

def fix_usb_kindle():
    drive = "E:\\"
    ext_dir = os.path.join(drive, "extensions", "koreader")
    bin_dir = os.path.join(ext_dir, "bin")
    
    # 1. Create wrapper script
    wrapper_path = os.path.join(bin_dir, "koreader.sh")
    with open(wrapper_path, "w", newline="\n") as f:
        f.write("#!/bin/sh\n")
        f.write("exec /mnt/us/koreader/koreader.sh \"$@\"\n")
    print(f"Created {wrapper_path}")
    
    # 2. Fix menu.json
    menu_path = os.path.join(ext_dir, "menu.json")
    menu_data = {
        "items": [
            {
                "name": "Start KOReader (Max Performance)",
                "priority": 1,
                "action": "bin/koreader.sh",
                "params": "--kual --framework_stop"
            }
        ]
    }
    with open(menu_path, "w", newline="\n") as f:
        json.dump(menu_data, f, indent=2)
    print(f"Fixed {menu_path}")
    
    # 3. Clean Bloat (Core dumps)
    for file in os.listdir(drive):
        if file.startswith("KPPMainAppV2_") and file.endswith(".core"):
            os.remove(os.path.join(drive, file))
            print(f"Deleted bloat: {file}")
            
    if os.path.exists(os.path.join(drive, "update.bin.tmp.partial")):
        os.remove(os.path.join(drive, "update.bin.tmp.partial"))
        print("Deleted update.bin.tmp.partial")

if __name__ == "__main__":
    fix_usb_kindle()
