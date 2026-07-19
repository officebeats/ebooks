import os
import shutil
import re
import glob

KINDLE_DRIVE = "E:\\"

def copy_sui_baseline():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    baseline_path = os.path.join(script_dir, "..", "simpleui_settings_baseline", "sui_settings.lua")
    
    target_dir = os.path.join(KINDLE_DRIVE, "koreader", "settings", "simpleui")
    os.makedirs(target_dir, exist_ok=True)
    
    target_file = os.path.join(target_dir, "sui_settings.lua")
    if os.path.exists(baseline_path):
        shutil.copy2(baseline_path, target_file)
        print(f"Copied SimpleUI baseline to {target_file}")
    else:
        print(f"ERROR: {baseline_path} not found!")

def update_settings_reader():
    settings_path = os.path.join(KINDLE_DRIVE, "koreader", "settings.reader.lua")
    if not os.path.exists(settings_path):
        print(f"ERROR: {settings_path} not found!")
        return

    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # fl_intensity = 7
    if '["fl_intensity"]' in content:
        content = re.sub(r'\["fl_intensity"\]\s*=\s*\d+', '["fl_intensity"] = 7', content)
    else:
        content = content.replace("return {", 'return {\n    ["fl_intensity"] = 7,')

    # screensaver_type = cover
    if '["screensaver_type"]' in content:
        content = re.sub(r'\["screensaver_type"\]\s*=\s*"[^"]*"', '["screensaver_type"] = "cover"', content)
    else:
        content = content.replace("return {", 'return {\n    ["screensaver_type"] = "cover",')

    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated settings.reader.lua at {settings_path}")

def clean_amazon_bloat():
    docs_dir = os.path.join(KINDLE_DRIVE, "documents")
    if not os.path.exists(docs_dir):
        return
    
    removed = 0
    for root, dirs, files in os.walk(docs_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in ['.mobi', '.azw', '.azw3', '.pdf', '.txt']:
                if 'kual' not in file.lower() and 'koreader' not in file.lower():
                    filepath = os.path.join(root, file)
                    os.remove(filepath)
                    removed += 1
    print(f"Removed {removed} Amazon bloat documents.")

def clean_logs():
    removed = 0
    for file in glob.glob(os.path.join(KINDLE_DRIVE, "*.log")):
        os.remove(file)
        removed += 1
    print(f"Removed {removed} bloat logs from root.")

def main():
    print(f"Deploying to Kindle USB at {KINDLE_DRIVE}...")
    copy_sui_baseline()
    update_settings_reader()
    clean_amazon_bloat()
    clean_logs()
    print("USB Deployment Complete!")

if __name__ == "__main__":
    main()
