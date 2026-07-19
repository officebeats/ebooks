import os
import shutil
import re
import glob
import urllib.request
import json
import zipfile
import tempfile

KINDLE_DRIVE = "E:\\"

# Plugins definition
PLUGINS_TO_INSTALL = {
    "localsend": {
        "repo": "kaikozlov/localsend.koplugin",
        "target_folder": "localsend.koplugin",
        "url": "https://github.com/kaikozlov/localsend.koplugin/releases/download/v1.4.1/localsend-koplugin-arm-legacy.zip"
    },
    "simpleui": {
        "repo": "doctorhetfield-cmd/simpleui.koplugin",
        "target_folder": "simpleui.koplugin",
        "url": "https://github.com/doctorhetfield-cmd/simpleui.koplugin/archive/refs/heads/main.zip"
    },
    "simpleui_ext": {
        "repo": "omer-faruq/simpleui_ext.koplugin",
        "target_folder": "simpleui_ext.koplugin",
        "url": "https://github.com/omer-faruq/simpleui_ext.koplugin/archive/refs/heads/main.zip"
    },
    "koassistant": {
        "repo": "zeeyado/koassistant.koplugin",
        "target_folder": "koassistant.koplugin",
        "url": "https://github.com/zeeyado/koassistant.koplugin/releases/download/v0.20.0/koassistant.koplugin.zip"
    }
}

def get_gemini_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            if val:
                                return val
        except Exception:
            pass
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("GEMINI_API_KEY") or data.get("gemini_api_key")
                if val:
                    return val.strip()
        except Exception:
            pass
    return None

def download_file(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def find_plugin_root_dir(extract_dir):
    for root, dirs, files in os.walk(extract_dir):
        if "main.lua" in files:
            return root
    return None

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
        # Create empty settings table if not exists
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write("return {\n}")

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

    # start_with = homescreen_simpleui
    if '["start_with"]' in content:
        content = re.sub(r'\["start_with"\]\s*=\s*"[^"]*"', '["start_with"] = "homescreen_simpleui"', content)
    else:
        content = content.replace("return {", 'return {\n    ["start_with"] = "homescreen_simpleui",')

    # Fix SimpleUI "modules exceeded area" error by enforcing a strict vertical layout limit
    safe_modules = {
        "simpleui_modules_active_tbr": "false",
        "simpleui_modules_active_new_books": "false",
        "simpleui_modules_active_collections": "false"
    }
    for mod, val in safe_modules.items():
        if f'["{mod}"]' in content:
            content = re.sub(rf'\["{mod}"\]\s*=\s*(true|false)', f'["{mod}"] = {val}', content)
        else:
            content = content.replace("return {", f'return {{\n    ["{mod}"] = {val},')
        
    # Ensure SimpleUI userdata migrated is true
    if '["simpleui_userdata_migrated_v1"]' not in content:
        content = content.replace("return {", 'return {\n    ["simpleui_userdata_migrated_v1"] = true,')

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
                    try:
                        os.remove(filepath)
                        removed += 1
                    except Exception:
                        pass
    print(f"Removed {removed} Amazon bloat documents.")

def clean_logs():
    removed = 0
    for file in glob.glob(os.path.join(KINDLE_DRIVE, "*.log")):
        try:
            os.remove(file)
            removed += 1
        except Exception:
            pass
    print(f"Removed {removed} bloat logs from root.")

def deploy_launcher():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_launcher_root = os.path.join(script_dir, "..", "koreader_home_launcher")
    
    if os.path.exists(local_launcher_root):
        sdr_dir = os.path.join(KINDLE_DRIVE, "documents", "koreader.sh.sdr")
        meta_dir = os.path.join(KINDLE_DRIVE, "documents", "koreader.sdr")
        os.makedirs(sdr_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)
        
        # Delete existing files first to avoid write locks on E-Ink device
        for f in [os.path.join(KINDLE_DRIVE, "documents", "koreader.sh"),
                  os.path.join(sdr_dir, "icon.png"),
                  os.path.join(meta_dir, "metadata.sh.lua")]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        
        # Copy files
        shutil.copy2(os.path.join(local_launcher_root, "koreader.sh"), os.path.join(KINDLE_DRIVE, "documents", "koreader.sh"))
        shutil.copy2(os.path.join(local_launcher_root, "koreader.sh.sdr", "icon.png"), os.path.join(sdr_dir, "icon.png"))
        shutil.copy2(os.path.join(local_launcher_root, "koreader.sdr", "metadata.sh.lua"), os.path.join(meta_dir, "metadata.sh.lua"))
        print("Copied native home screen booklet launcher via USB.")
    else:
        print("ERROR: local launcher root not found for USB deploy!")

def deploy_kual_wrapper():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_wrapper = os.path.join(script_dir, "..", "koreader_kual_launcher", "koreader.sh")
    
    if os.path.exists(local_wrapper):
        target_dir = os.path.join(KINDLE_DRIVE, "extensions", "koreader", "bin")
        os.makedirs(target_dir, exist_ok=True)
        
        target_file = os.path.join(target_dir, "koreader.sh")
        if os.path.exists(target_file):
            try:
                os.remove(target_file)
            except Exception:
                pass
                
        shutil.copy2(local_wrapper, target_file)
        
        # Copy custom menu.json as well to force no framework and point to bin/koreader.sh
        kual_menu = {
            "items": [
                {
                    "name": "Start KOReader (Max Performance)",
                    "priority": 1,
                    "action": "bin/koreader.sh",
                    "params": "--kual --framework_stop"
                }
            ]
        }
        menu_path = os.path.join(KINDLE_DRIVE, "extensions", "koreader", "menu.json")
        with open(menu_path, "w", encoding="utf-8") as f:
            json.dump(kual_menu, f, indent=2)
            
        print("Copied custom KUAL launcher wrapper and menu.json via USB.")
    else:
        print("ERROR: local KUAL wrapper not found for USB deploy!")

def deploy_plugins_and_icons():
    temp_dir = tempfile.mkdtemp()
    api_key = get_gemini_api_key()
    
    try:
        # 1. Download and deploy plugins
        for name, info in PLUGINS_TO_INSTALL.items():
            print(f"Fetching plugin: {name}...")
            
            target_plugin_dir = os.path.join(KINDLE_DRIVE, "koreader", "plugins", info["target_folder"])
            if os.path.exists(target_plugin_dir):
                shutil.rmtree(target_plugin_dir, ignore_errors=True)
                
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_override_path = os.path.join(script_dir, "..", info["target_folder"])
            if os.path.exists(local_override_path):
                print(f"  Using local override from {local_override_path}")
                shutil.copytree(local_override_path, target_plugin_dir)
            else:
                zip_url = info["url"]
                zip_path = os.path.join(temp_dir, f"{name}.zip")
                download_file(zip_url, zip_path)
                
                extract_path = os.path.join(temp_dir, f"{name}_extracted")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                    
                plugin_root = find_plugin_root_dir(extract_path)
                if not plugin_root:
                    print(f"  ERROR: Could not find main.lua for {name}!")
                    continue
                shutil.copytree(plugin_root, target_plugin_dir)
            
            if name == "koassistant" and api_key:
                print("  Configuring Gemini API key inside koassistant...")
                apikey_lua_path = os.path.join(target_plugin_dir, "apikeys.lua")
                lua_content = f'return {{\n    gemini = "{api_key}"\n}}\n'
                with open(apikey_lua_path, 'w', encoding='utf-8') as f:
                    f.write(lua_content)
            print(f"  Deployed plugin -> {target_plugin_dir}")
            
        # 2. Deploy patches
        print("Deploying patches...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_patches = os.path.join(script_dir, "..", "patches")
        target_patches_dir = os.path.join(KINDLE_DRIVE, "koreader", "patches")
        os.makedirs(target_patches_dir, exist_ok=True)
        
        # Remove legacy timesync
        legacy_ts = os.path.join(target_patches_dir, "4-auto-timesync.lua")
        if os.path.exists(legacy_ts):
            try:
                os.remove(legacy_ts)
            except Exception:
                pass
                
        if os.path.exists(local_patches):
            for file in os.listdir(local_patches):
                src_path = os.path.join(local_patches, file)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, os.path.join(target_patches_dir, file))
            print(f"  Patches deployed to {target_patches_dir}")
            
        # 3. Download and deploy SeriousHornet E-Ink icons
        print("Fetching SeriousHornet SVG icons...")
        sh_url = "https://github.com/SeriousHornet/KOReader.patches/archive/refs/heads/main.zip"
        sh_zip_path = os.path.join(temp_dir, "sh_patches.zip")
        download_file(sh_url, sh_zip_path)
        
        sh_extract_path = os.path.join(temp_dir, "sh_patches_extracted")
        with zipfile.ZipFile(sh_zip_path, 'r') as zip_ref:
            zip_ref.extractall(sh_extract_path)
            
        target_icons = {
            "rounded.corner.tl.svg": "KOReader.patches-main/icons (bw)/rounded.corner.tl.svg",
            "rounded.corner.tr.svg": "KOReader.patches-main/icons (bw)/rounded.corner.tr.svg",
            "rounded.corner.bl.svg": "KOReader.patches-main/icons (bw)/rounded.corner.bl.svg",
            "rounded.corner.br.svg": "KOReader.patches-main/icons (bw)/rounded.corner.br.svg",
            "percent.badge.svg": "KOReader.patches-main/icons (bw)/percent.badge.svg",
            "dogear.abandoned.svg": "KOReader.patches-main/icons (bw)/dogear.abandoned.svg",
            "dogear.complete.svg": "KOReader.patches-main/icons (bw)/dogear.complete.svg",
            "dogear.reading.svg": "KOReader.patches-main/icons (bw)/dogear.reading.svg"
        }
        
        target_icons_dir = os.path.join(KINDLE_DRIVE, "koreader", "icons")
        os.makedirs(target_icons_dir, exist_ok=True)
        for name, subpath in target_icons.items():
            full_icon_src = os.path.join(sh_extract_path, subpath)
            if os.path.exists(full_icon_src):
                shutil.copy2(full_icon_src, os.path.join(target_icons_dir, name))
                print(f"  Extracted icon: {name}")
                
        # 4. Strict Plugin Baseline Cleanup
        print("Enforcing strict plugin baseline...")
        KEEP_PLUGINS = {
            "localsend.koplugin", "koassistant.koplugin", "simpleui.koplugin", "simpleui_ext.koplugin", "SSH.koplugin",
            "autodim.koplugin", "autostandby.koplugin", "autosuspend.koplugin", "autoturn.koplugin", "autowarmth.koplugin",
            "batterystat.koplugin", "systemstat.koplugin",
            "bookshortcuts.koplugin", "calibre.koplugin", "coverbrowser.koplugin", "coverimage.koplugin", "filebrowser.koplugin",
            "docsettingtweak.koplugin", "exporter.koplugin", "externalkeyboard.koplugin", "gestures.koplugin", "hotkeys.koplugin",
            "hello.koplugin", "keepalive.koplugin", "perceptionexpander.koplugin", "profiles.koplugin",
            "newsdownloader.koplugin", "opds.koplugin", "opds_plus.koplugin",
            "readest.koplugin", "readtimer.koplugin", "timesync.koplugin", "updatesmanager.koplugin",
            "terminal.koplugin", "texteditor.koplugin", "vocabbuilder.koplugin", "webbrowser.koplugin"
        }
        
        plugins_root = os.path.join(KINDLE_DRIVE, "koreader", "plugins")
        if os.path.exists(plugins_root):
            for entry in os.listdir(plugins_root):
                if entry.endswith(".koplugin") and entry not in KEEP_PLUGINS:
                    print(f"  Removing unauthorized plugin: {entry}")
                    shutil.rmtree(os.path.join(plugins_root, entry), ignore_errors=True)
                    
        # 5. Core Dump Blocker Flags
        print("Enforcing Core Dump Blockers...")
        for flag in ["DISABLE_CORE_DUMP", "DISABLE_CORE_DUMP_ALERT"]:
            flag_path = os.path.join(KINDLE_DRIVE, flag)
            if not os.path.exists(flag_path):
                with open(flag_path, "w") as f:
                    f.write("")
                print(f"  Created core dump blocker: {flag}")
                
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    print(f"Deploying to Kindle USB at {KINDLE_DRIVE}...")
    copy_sui_baseline()
    update_settings_reader()
    deploy_launcher()
    deploy_kual_wrapper()
    deploy_plugins_and_icons()
    clean_amazon_bloat()
    clean_logs()
    print("USB Deployment Complete!")

if __name__ == "__main__":
    main()
