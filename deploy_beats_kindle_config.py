import os
import sys
import json
import urllib.request
import zipfile
import shutil
import tempfile
import argparse
import sqlite3
import io
import paramiko
import re
import datetime

# Configurations
DEFAULT_KINDLE_IP = "192.168.68.82"
DEFAULT_KINDLE_PORT = 2222
DEFAULT_KINDLE_USER = "root"
DEFAULT_KINDLE_PASSWORD = ""

# Remote paths on Kindle
REMOTE_PLUGINS_DIR = "/mnt/us/koreader/plugins"
REMOTE_PATCHES_DIR = "/mnt/us/koreader/patches"
REMOTE_SETTINGS_DIR = "/mnt/us/koreader/settings"
REMOTE_ICONS_DIR = "/mnt/us/koreader/icons"
REMOTE_DB_PATH = "/mnt/us/koreader/settings/PT_bookinfo_cache.sqlite3"

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
        "target_folder": "koassistant.koplugin"
    }
}

# Optimal Project: Title settings
PROJECT_TITLE_SETTINGS = {
    "config_version": "6",
    "filemanager_display_mode": "list_image_meta",
    "history_display_mode": "list_image_meta",
    "collection_display_mode": "list_image_meta",
    "series_mode": "series_in_separate_line",
    "hide_file_info": "1",
    "show_progress_in_mosaic": "1",
    "unified_display_mode": "1",
    "autoscan_on_eject": "0"
}

LUA_KEEPALIVE_PATCH_CONTENT = """-- Keep SSH alive when plugged in by preventing sleep
local UIManager = require("ui/uimanager")
local function pollCharging()
    local f = io.popen("lipc-get-prop com.lab126.powerd isCharging 2>/dev/null")
    local is_charging = false
    if f then
        local res = f:read("*a")
        f:close()
        if res and tonumber(res) == 1 then is_charging = true end
    end
    if is_charging then
        os.execute("lipc-set-prop com.lab126.powerd preventScreenSaver 1")
    else
        os.execute("lipc-set-prop com.lab126.powerd preventScreenSaver 0")
    end
    UIManager:scheduleIn(30, pollCharging)
end
UIManager:scheduleIn(10, pollCharging)
"""

# Image filter patch to prevent duplicates from cover JPGs/PNGs
LUA_IMAGE_PATCH_CONTENT = """-- Disable raw image files from being treated as readable books
local DocumentRegistry = require("document/documentregistry")

local image_exts = { "jpg", "jpeg", "png", "gif", "webp", "bmp" }
for _, ext in ipairs(image_exts) do
    DocumentRegistry.filetype_provider[ext] = nil
end

local clean_providers = {}
for _, p in ipairs(DocumentRegistry.providers) do
    local is_img = false
    for _, ext in ipairs(image_exts) do
        if p.extension == ext then
            is_img = true
            break
        end
    end
    if not is_img then
        table.insert(clean_providers, p)
    end
end
DocumentRegistry.providers = clean_providers
"""

# Rounded corners patch for Project: Title book covers
LUA_ROUNDED_PATCH_CONTENT = """--[[ User patch for Project title plugin to add rounded corners to book covers ]]--
local userpatch  = require("userpatch")
local logger     = require("logger")
local IconWidget = require("ui/widget/iconwidget")
local Screen = require("device").screen
local Blitbuffer = require("ffi/blitbuffer")

local function patchBookCoverRoundedCorners(plugin)
    local MosaicMenu = require("mosaicmenu")
    local MosaicMenuItem = userpatch.getUpValue(MosaicMenu._updateItemsBuildUI, "MosaicMenuItem")
	
    -- Load as IconWidget
    local function svg_widget(icon)
        return IconWidget:new{ icon = icon, alpha  = true }
    end

    local icons = {
        tl = "rounded.corner.tl",
        tr = "rounded.corner.tr",
        bl = "rounded.corner.bl",
        br = "rounded.corner.br",
    }
    local corners = {}
    for k, name in pairs(icons) do
        corners[k] = svg_widget(name)
        if not corners[k] then
            logger.warn("Failed to load SVG icon: " .. tostring(name))
        end
    end

    local _corner_w, _corner_h
    if corners.tl then
        local sz = corners.tl:getSize() --all four SVGs are same size so grab once
        _corner_w, _corner_h = sz.w, sz.h
    end
	
    local orig_MosaicMenuItem_paint = MosaicMenuItem.paintTo

    function MosaicMenuItem:paintTo(bb, x, y)
	
		-- First, call the original paintTo method to draw the cover normally
		orig_MosaicMenuItem_paint(self, bb, x, y)
		
        -- Locate the cover frame widget as the base code does
        local target = self[1][1][1]
      
        if target and target.dimen then
            -- Outer frame rect (already centered)
            local fx = x + math.floor((self.width  - target.dimen.w) / 2)
            local fy = y + math.floor((self.height - target.dimen.h) / 2)
            local fw, fh = target.dimen.w, target.dimen.h
    
            -- Inner content rect = cover area inside padding
            local pad = target.padding or 0
            local inset = 0--Screen:scaleBySize(1)
            local ix = math.floor(fx + pad + inset)
            local iy = math.floor(fy + pad + inset)
            local iw = math.max(1, fw - 2*(pad + inset))
            local ih = math.max(1, fh - 2*(pad + inset))
    
            local cover_border = Screen:scaleBySize(0.5)  -- tweak for thicker line
            if not self.is_directory then
                bb:paintBorder(ix, iy, iw, ih, cover_border, Blitbuffer.COLOR_BLACK, 0, false)
            end
        end

        -- Paint rounded corners on the outer frame rect
        if target and target.dimen and not self.is_directory then
            local fx = x + math.floor((self.width  - target.dimen.w) / 2)
            local fy = y + math.floor((self.height - target.dimen.h) / 2)
            local fw, fh = target.dimen.w, target.dimen.h

            local TL, TR, BL, BR = corners.tl, corners.tr, corners.bl, corners.br
			
			-- Helper to get size for IconWidget (getSize)
            local function _sz(w)
                if w.getSize then local s = w:getSize(); return s.w, s.h end
                if w.getWidth then return w:getWidth(), w:getHeight() end
                return 0, 0
            end
			
            local tlw, tlh = _sz(TL)
            local trw, trh = _sz(TR)
            local blw, blh = _sz(BL)
            local brw, brh = _sz(BR)

			-- Top-left
            if TL.paintTo then TL:paintTo(bb, fx, fy) else bb:blitFrom(TL, fx, fy) end
            -- Top-right
            if TR.paintTo then TR:paintTo(bb, fx + fw - trw, fy) else bb:blitFrom(TR, fx + fw - trw, fy) end
            -- Bottom-left
            if BL.paintTo then BL:paintTo(bb, fx, fy + fh - blh) else bb:blitFrom(BL, fx, fy + fh - blh) end
            -- Bottom-right
            if BR.paintTo then BR:paintTo(bb, fx + fw - brw, fy + fh - brh) else bb:blitFrom(BR, fx + fw - brw, fy + fh - rh) end
        end
    end
end
userpatch.registerPatchPluginFunc("coverbrowser", patchBookCoverRoundedCorners)
"""

def get_gemini_api_key():
    """Load the Gemini API Key from environment, .env file, or config.json."""
    # 1. Environment Variable
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
        
    # 2. Local .env file (Git ignored)
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
            
    # 3. Local config.json (Git ignored)
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

def fetch_latest_release_zip(repo):
    """Fetch the download URL for the latest release zip of a GitHub repository."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Try to find a custom zip asset
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".zip"):
                    return asset.get("browser_download_url")
                    
            # Fall back to zipball
            zipball = data.get("zipball_url")
            if zipball:
                return zipball
    except Exception as e:
        print(f"  Error querying GitHub API for {repo}: {e}")
        
    # Handle main branch defaults
    if "simpleui" in repo.lower():
        return f"https://github.com/{repo}/archive/refs/heads/main.zip"
        
    # Fallback to master branch zip
    return f"https://github.com/{repo}/archive/refs/heads/master.zip"

def download_file(url, dest_path):
    """Download a file from a URL to a local path."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def find_plugin_root_dir(extract_dir):
    """Search extracted files for the plugin root containing 'main.lua'."""
    for root, dirs, files in os.walk(extract_dir):
        if "main.lua" in files:
            return root
    return None

def safe_chmod(sftp, remote_path, mode):
    """Safely apply chmod, ignoring failures on non-supportive filesystems like FAT32."""
    try:
        sftp.chmod(remote_path, mode)
    except Exception:
        pass

def sftp_mkdir_recursive(sftp, remote_path):
    """Recursively create directories on the remote Kindle."""
    path_parts = remote_path.replace('\\', '/').split('/')
    current_path = ""
    for part in path_parts:
        if not part:
            continue
        if current_path == "":
            current_path = "/" + part if remote_path.startswith('/') else part
        else:
            current_path = current_path + "/" + part
        try:
            sftp.mkdir(current_path)
        except IOError:
            pass

def sftp_put_dir(sftp, local_dir, remote_dir, dry_run=False):
    """Recursively upload a directory via SFTP."""
    if not dry_run:
        sftp_mkdir_recursive(sftp, remote_dir)
    else:
        print(f"  [Dry Run] Would create remote directory: {remote_dir}")
        
    for entry in os.listdir(local_dir):
        local_path = os.path.join(local_dir, entry)
        remote_path = remote_dir + "/" + entry
        if os.path.isdir(local_path):
            sftp_put_dir(sftp, local_path, remote_path, dry_run)
        else:
            if not dry_run:
                try:
                    sftp.put(local_path, remote_path)
                except Exception as e:
                    print(f"    Failed to upload {entry}: {e}")
            else:
                print(f"  [Dry Run] Would upload: {local_path} -> {remote_path}")

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

def configure_koreader_sh(sftp, dry_run=False):
    """Ensure mount-bind for Kindle screensaver is injected in koreader.sh."""
    remote_path = "/mnt/us/koreader/koreader.sh"
    if dry_run:
        print("  [Dry Run] Would configure koreader.sh to mount-bind screensavers")
        return
        
    try:
        import tempfile
        fd, local_temp = tempfile.mkstemp()
        os.close(fd)
        sftp.get(remote_path, local_temp)
        
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Clean and rotate KPPMainAppV2 crash logs and run pre-launch optimizations
        if "KPPMainAppV2" not in content:
            kpp_code = (
                "\n# --- INSTANT PRE-LAUNCH OPTIMIZATION SWEEP ---\n"
                "stop fontscanner 2>/dev/null || true\n"
                "stop kfxreader 2>/dev/null || true\n"
                "stop scanner 2>/dev/null || true\n"
                "stop tod 2>/dev/null || true\n"
                "stop phd 2>/dev/null || true\n"
                "stop scanlogd 2>/dev/null || true\n"
                "stop otav3 2>/dev/null || true\n"
                "sysctl vm.vfs_cache_pressure=100 2>/dev/null || true\n"
                "sysctl vm.dirty_ratio=20 2>/dev/null || true\n"
                "echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true\n"
                "# Enforce No-Framework mode by default\n"
                "case \"$*\" in\n"
                "    *framework_stop*) ;;\n"
                "    *) set -- \"$@\" --framework_stop ;;\n"
                "esac\n\n"
                "# Relocate and rotate KPPMainAppV2 crash logs to hidden folder\n"
                "mkdir -p /mnt/us/system/crash_logs\n"
                "for f in /mnt/us/documents/KPPMainAppV2_*; do\n"
                "    [ -e \"$f\" ] || continue\n"
                "    mv \"$f\" /mnt/us/system/crash_logs/ 2>/dev/null\n"
                "done\n"
                "rm -f /mnt/us/system/crash_logs/*.core 2>/dev/null\n"
                "tgz_files=$(ls -1tr /mnt/us/system/crash_logs/KPPMainAppV2_*.tgz 2>/dev/null)\n"
                "count=$(echo \"$tgz_files\" | grep -c \"KPPMainAppV2_\")\n"
                "if [ \"$count\" -gt 1 ]; then\n"
                "    oldest_files=$(echo \"$tgz_files\" | head -n -1)\n"
                "    for f in $oldest_files; do\n"
                "        rm -f \"$f\"\n"
                "        rm -rf \"${f%.tgz}.sdr\"\n"
                "    done\n"
                "fi\n\n"
            )
            content = content.replace("#!/bin/sh", "#!/bin/sh\n" + kpp_code)
            
        # Avoid double-injection
        if "mount -o bind /mnt/us/screensavers" not in content:
            # Inject mount before RETURN_VALUE=85
            mount_code = (
                "# Mount custom screensaver path\n"
                "mkdir -p /mnt/us/screensavers\n"
                "mount -o bind /mnt/us/screensavers /usr/share/blanket/screensaver\n\n"
            )
            content = content.replace("RETURN_VALUE=85", mount_code + "RETURN_VALUE=85")
            
            # Inject umount after the while loop finishes
            umount_code = (
                "\n# Unmount custom screensaver path\n"
                "umount -l /usr/share/blanket/screensaver\n"
            )
            loop_pattern = 'done\n\n# clean up our own process tree'
            if loop_pattern in content:
                content = content.replace(loop_pattern, 'done\n' + umount_code + '\n# clean up our own process tree')
            else:
                # Fallback replacement if formatting varies slightly
                content = content.replace("done\n\n# clean up", "done\n" + umount_code + "\n# clean up")
                
        with open(local_temp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            
        sftp.put(local_temp, remote_path)
        safe_chmod(sftp, remote_path, 0o777)
        os.remove(local_temp)
        print("  Successfully injected screensaver mount-bind in koreader.sh")
    except Exception as e:
        print(f"  Error configuring koreader.sh: {e}")

def configure_settings_reader_lua(sftp, dry_run=False):
    """Ensure SimpleUI and cover screensaver defaults are set in settings.reader.lua."""
    remote_path = "/mnt/us/koreader/settings.reader.lua"
    if dry_run:
        print(f"  [Dry Run] Would configure settings.reader.lua to start with homescreen_simpleui and screensaver_type cover")
        return
        
    try:
        # Download settings.reader.lua
        fd, local_temp = tempfile.mkstemp()
        os.close(fd)
        try:
            sftp.get(remote_path, local_temp)
        except Exception:
            # File doesn't exist, start with empty table
            with open(local_temp, "w", encoding="utf-8") as f:
                f.write("return {\n}")
                
        with open(local_temp, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Ensure homescreen_simpleui is start_with
        if '["start_with"]' in content:
            content = re.sub(r'\["start_with"\]\s*=\s*"[^"]*"', '["start_with"] = "homescreen_simpleui"', content)
        else:
            content = content.replace("return {", 'return {\n    ["start_with"] = "homescreen_simpleui",')
            
        # Ensure screensaver_type is cover
        if '["screensaver_type"]' in content:
            content = re.sub(r'\["screensaver_type"\]\s*=\s*"[^"]*"', '["screensaver_type"] = "cover"', content)
        else:
            content = content.replace("return {", 'return {\n    ["screensaver_type"] = "cover",')
            
        # Ensure default frontlight intensity is 7
        if '["fl_intensity"]' in content:
            content = re.sub(r'\["fl_intensity"\]\s*=\s*\d+', '["fl_intensity"] = 7', content)
        else:
            content = content.replace("return {", 'return {\n    ["fl_intensity"] = 7,')

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
            
        # Ensure migrated flag is true
        if '["simpleui_userdata_migrated_v1"]' not in content:
            content = content.replace("return {", 'return {\n    ["simpleui_userdata_migrated_v1"] = true,')
            
        # Strip custom screen_dpi, ui_scale, and font_scaling to restore default legible hardware resolution
        if '["screen_dpi"]' in content:
            content = re.sub(r'\["screen_dpi"\]\s*=\s*[^,\n]+,?\n?', '', content)
        if '["ui_scale"]' in content:
            content = re.sub(r'\["ui_scale"\]\s*=\s*[^,\n]+,?\n?', '', content)
        if '["font_scaling"]' in content:
            content = re.sub(r'\["font_scaling"\]\s*=\s*[^,\n]+,?\n?', '', content)

        with open(local_temp, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Upload back
        sftp.put(local_temp, remote_path)
        safe_chmod(sftp, remote_path, 0o777)
        print("  Successfully configured settings.reader.lua defaults.")
    except Exception as e:
        print(f"  Warning: Failed to configure settings.reader.lua: {e}")
    finally:
        if os.path.exists(local_temp):
            os.remove(local_temp)

def build_connection(ip, port, user, password):
    """Build SSH connection trying default ports 2222 and 22."""
    ports_to_try = [port, 22] if port and port != 22 else [2222, 22]
    for p in ports_to_try:
        ssh = test_connection(ip, p, user, password)
        if ssh:
            return ssh
    return None

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    hosts_config = load_kindle_hosts()
    default_ip = DEFAULT_KINDLE_IP
    if "older" in hosts_config:
        default_ip = hosts_config["older"].get("ip", DEFAULT_KINDLE_IP)

    parser = argparse.ArgumentParser(description="Deploy 'beats' KOReader configuration to a Kindle")
    parser.add_argument("--ip", default=default_ip, help=f"Kindle IP address or host nickname (default: {default_ip})")
    parser.add_argument("--port", type=int, help="Kindle SSH port (tries 2222 and 22 by default)")
    parser.add_argument("--user", default=DEFAULT_KINDLE_USER, help=f"Kindle SSH user (default: {DEFAULT_KINDLE_USER})")
    parser.add_argument("--password", default=DEFAULT_KINDLE_PASSWORD, help="Kindle SSH password")
    parser.add_argument("--dry-run", action="store_true", help="Dry run: prepare files locally but do not upload or restart")
    
    args = parser.parse_args()
    dry_run = args.dry_run
    
    # Resolve from hosts config if nickname is used
    for key, device in hosts_config.items():
        ip_addr = device.get("ip", "")
        if args.ip == key or args.ip in key or args.ip == ip_addr or args.ip in ip_addr:
            args.ip = ip_addr
            args.port = device.get("port", args.port) or args.port
            args.user = device.get("user", args.user) or args.user
            args.password = device.get("password", args.password) or args.password
            break
            break
    
    print("=== Deploying 'beats' Kindle KOReader Configuration ===")
    
    # Try resolving API key
    api_key = get_gemini_api_key()
    if not api_key:
        print("  WARNING: Gemini API Key was not found in environment, .env, or config.json.")
            
    if dry_run:
        print(">>> DRY RUN ACTIVE: Local compilation only.")
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = tempfile.mkdtemp()
    print(f"Created temporary workspace: {temp_dir}")
    
    try:
        # 1. Download and structure all plugins
        prepared_plugins = {}
        for name, info in PLUGINS_TO_INSTALL.items():
            print(f"\n[Plugin] Fetching {name}...")
            repo = info["repo"]
            target_folder = info["target_folder"]
            
            # Check for local plugin directory override in repository root
            local_override_path = os.path.join(script_dir, target_folder)
            if os.path.exists(local_override_path):
                print(f"  Using local override from {local_override_path}")
                final_local_path = os.path.join(temp_dir, target_folder)
                shutil.copytree(local_override_path, final_local_path)
            else:
                zip_url = info.get("url")
                if not zip_url:
                    zip_url = fetch_latest_release_zip(repo)
                zip_path = os.path.join(temp_dir, f"{name}.zip")
                print(f"  Downloading from: {zip_url}")
                download_file(zip_url, zip_path)
                
                extract_path = os.path.join(temp_dir, f"{name}_extracted")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                    
                plugin_root = find_plugin_root_dir(extract_path)
                if not plugin_root:
                    print(f"  ERROR: Could not find main.lua inside the zip for {name}!")
                    continue
                    
                final_local_path = os.path.join(temp_dir, target_folder)
                shutil.copytree(plugin_root, final_local_path)
            
            # Configure KOAssistant Gemini API key
            if name == "koassistant":
                if api_key:
                    print("  Configuring Gemini API key...")
                    apikey_lua_path = os.path.join(final_local_path, "apikeys.lua")
                    lua_content = f'return {{\n    gemini = "{api_key}"\n}}\n'
                    with open(apikey_lua_path, 'w', encoding='utf-8') as f:
                        f.write(lua_content)
                    print(f"  Generated apikeys.lua inside {target_folder}")
                else:
                    print("  Skipping Gemini API key configuration (none provided).")
                
            prepared_plugins[name] = final_local_path
            
        # 2. Build local settings database (deprecated for SimpleUI)
        print("\n[Settings] SimpleUI setup (skipping settings database compilation)...")
        
        # 3. Create patches
        print("\n[Patches] Preparing user patches...")
        temp_patches_dir = os.path.join(temp_dir, "patches")
        os.makedirs(temp_patches_dir, exist_ok=True)
        
        repo_patches_dir = "patches"
        if os.path.isdir(repo_patches_dir):
            print(f"  Copying custom patches from local '{repo_patches_dir}' folder...")
            for f in os.listdir(repo_patches_dir):
                src_path = os.path.join(repo_patches_dir, f)
                if os.path.isfile(src_path):
                    shutil.copy(src_path, temp_patches_dir)
                    print(f"    Copied {f}")
        else:
            print("  Local 'patches' directory not found. Creating fallback patches...")
            # Fallback A: Image filter patch
            patch_image_path = os.path.join(temp_patches_dir, "2-disable-image-docs.lua")
            with open(patch_image_path, "w", encoding="utf-8") as f:
                f.write(LUA_IMAGE_PATCH_CONTENT)
                
            # Fallback B: Rounded corners patch
            patch_rounded_path = os.path.join(temp_patches_dir, "2--rounded-corners.lua")
            with open(patch_rounded_path, "w", encoding="utf-8") as f:
                f.write(LUA_ROUNDED_PATCH_CONTENT)
                
            # Fallback C: Keep SSH alive on charge patch
            patch_keepalive_path = os.path.join(temp_patches_dir, "3-keep-ssh-alive-charging.lua")
            with open(patch_keepalive_path, "w", encoding="utf-8") as f:
                f.write(LUA_KEEPALIVE_PATCH_CONTENT)
                
        print("  Patches prepared successfully.")
        
        # 4. Download and extract rounded corner SVGs from SeriousHornet patches repo
        print("\n[Icons] Fetching rounded corner SVGs from SeriousHornet patches repo...")
        sh_url = "https://github.com/SeriousHornet/KOReader.patches/archive/refs/heads/main.zip"
        sh_zip_path = os.path.join(temp_dir, "sh_patches.zip")
        download_file(sh_url, sh_zip_path)
        
        sh_extract_path = os.path.join(temp_dir, "sh_patches_extracted")
        with zipfile.ZipFile(sh_zip_path, 'r') as zip_ref:
            zip_ref.extractall(sh_extract_path)
            
        # Select black and white (bw) icons for Kindle E-Ink screen
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
        
        local_icons_dir = os.path.join(temp_dir, "icons")
        os.makedirs(local_icons_dir, exist_ok=True)
        
        for name, zip_path in target_icons.items():
            full_zip_path = os.path.join(sh_extract_path, zip_path)
            if os.path.exists(full_zip_path):
                shutil.copy(full_zip_path, os.path.join(local_icons_dir, name))
                print(f"  Extracted {name}")
            else:
                print(f"  WARNING: Could not find {name} in SeriousHornet zip!")
                
        # 5. Connect to Kindle
        ssh = None
        sftp = None
        if not dry_run:
            ssh = build_connection(args.ip, args.port, args.user, args.password)
            if not ssh:
                print("\nERROR: Could not connect to Kindle. Aborting deployment.")
                sys.exit(1)
            sftp = ssh.open_sftp()
            print("SSH/SFTP connection established successfully!")
            
            # Clean up old ProjectTitle files to prevent conflicts
            print("\n[Deploy] Cleaning up legacy ProjectTitle installation...")
            ssh.exec_command("rm -rf /mnt/us/koreader/plugins/ProjectTitle.koplugin")
            ssh.exec_command("rm -f /mnt/us/koreader/settings/PT_bookinfo_cache.sqlite3")
            ssh.exec_command("rm -f /mnt/us/koreader/patches/2--rounded-corners.lua")
            
        # 6. Upload Plugins
        print("\n[Deploy] Uploading plugins...")
        for name, local_path in prepared_plugins.items():
            target_folder = PLUGINS_TO_INSTALL[name]["target_folder"]
            remote_dest = f"{REMOTE_PLUGINS_DIR}/{target_folder}"
            print(f"  Deploying {name} -> {remote_dest}...")
            sftp_put_dir(sftp, local_path, remote_dest, dry_run=dry_run)
            
        # 7. Upload settings database (deprecated for SimpleUI)
        pass
            
        # 8. Upload patches
        print("\n[Deploy] Uploading Lua patches...")
        if not dry_run:
            ssh.exec_command("rm -f /mnt/us/koreader/patches/4-auto-timesync.lua")
            # Create KUAL backup directory for self-healing patches
            backup_patches_dir = "/mnt/us/extensions/koreader/patches"
            sftp_mkdir_recursive(sftp, backup_patches_dir)
            
            for f in os.listdir(temp_patches_dir):
                local_patch_path = os.path.join(temp_patches_dir, f)
                if os.path.isfile(local_patch_path):
                    # 1. Main deployment
                    remote_patch_dest = f"{REMOTE_PATCHES_DIR}/{f}"
                    sftp.put(local_patch_path, remote_patch_dest)
                    safe_chmod(sftp, remote_patch_dest, 0o777)
                    
                    # 2. Local self-heal backup
                    backup_patch_dest = f"{backup_patches_dir}/{f}"
                    sftp.put(local_patch_path, backup_patch_dest)
                    safe_chmod(sftp, backup_patch_dest, 0o777)
                    
                    print(f"  Deployed patch & self-heal backup -> {f}")
        else:
            print(f"  [Dry Run] Would deploy patches from {temp_patches_dir} to {REMOTE_PATCHES_DIR}/")

        # 8.5 Deploy SimpleUI Baseline Configuration
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_sui_baseline = os.path.join(script_dir, "simpleui_settings_baseline", "sui_settings.lua")
        if os.path.exists(local_sui_baseline):
            print("\n[Deploy] Pushing SimpleUI baseline configuration...")
            remote_sui_dir = "/mnt/us/koreader/settings/simpleui"
            if not dry_run:
                sftp_mkdir_recursive(sftp, remote_sui_dir)
                sftp.put(local_sui_baseline, f"{remote_sui_dir}/sui_settings.lua")
                safe_chmod(sftp, f"{remote_sui_dir}/sui_settings.lua", 0o666)
                print(f"  Deployed SimpleUI baseline -> {remote_sui_dir}/sui_settings.lua")
            else:
                print(f"  [Dry Run] Would deploy SimpleUI baseline to {remote_sui_dir}/sui_settings.lua")

        # 8.6 Deploy KUAL No-Framework Auto-Launch Menu
        print("\n[Deploy] Configuring KUAL No Framework 1-Tap Launch...")
        kual_menu = {
            "items": [
                {
                    "name": "Start KOReader (Max Performance)",
                    "priority": 1,
                    "action": "bin/koreader.sh",
                    "params": "--kual --framework_stop"
                },
                {
                    "name": "Heal & Clean KOReader",
                    "priority": 2,
                    "action": "bin/heal_koreader.sh"
                }
            ]
        }
        if not dry_run:
            sftp_mkdir_recursive(sftp, "/mnt/us/extensions/koreader/bin")
            fd, temp_menu = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f:
                json.dump(kual_menu, f, indent=2)
            sftp.put(temp_menu, "/mnt/us/extensions/koreader/menu.json")
            os.remove(temp_menu)
            
            # Upload the KUAL launch wrapper script
            local_kual_wrapper = os.path.join(script_dir, "koreader_kual_launcher", "koreader.sh")
            if os.path.exists(local_kual_wrapper):
                sftp.put(local_kual_wrapper, "/mnt/us/extensions/koreader/bin/koreader.sh")
                safe_chmod(sftp, "/mnt/us/extensions/koreader/bin/koreader.sh", 0o777)
                print("  Custom KUAL menu.json and bin/koreader.sh wrapper deployed.")
            else:
                print("  Warning: local KUAL wrapper script not found!")
                
            # Upload the KUAL heal script
            local_heal_script = os.path.join(script_dir, "koreader_kual_launcher", "heal_koreader.sh")
            if os.path.exists(local_heal_script):
                sftp.put(local_heal_script, "/mnt/us/extensions/koreader/bin/heal_koreader.sh")
                safe_chmod(sftp, "/mnt/us/extensions/koreader/bin/heal_koreader.sh", 0o777)
                print("  Custom KUAL bin/heal_koreader.sh deployed.")
            else:
                print("  Warning: local KUAL heal script not found!")
        else:
            print("  [Dry Run] Would deploy KUAL menu.json, bin/koreader.sh wrapper, and bin/heal_koreader.sh.")
            
        # 8.7 Deploy Native One-Click Home Screen Launcher
        print("\n[Deploy] Deploying native one-click home screen launcher...")
        local_launcher_root = os.path.join(script_dir, "koreader_home_launcher")
        if os.path.exists(local_launcher_root):
            if not dry_run:
                # Create E:\documents directories
                sftp_mkdir_recursive(sftp, "/mnt/us/documents/koreader.sh.sdr")
                sftp_mkdir_recursive(sftp, "/mnt/us/documents/koreader.sh.sdr")
                sftp_mkdir_recursive(sftp, "/mnt/us/documents/koreader.sdr")
                
                # Delete files first to avoid locked-file errors if open
                ssh.exec_command("rm -f /mnt/us/documents/koreader.sh /mnt/us/documents/koreader.sh.sdr/icon.png /mnt/us/documents/koreader.sdr/metadata.sh.lua /mnt/us/documents/koreader.sh.sdr/metadata.sh.lua")
                
                # Upload files
                sftp.put(os.path.join(local_launcher_root, "koreader.sh"), "/mnt/us/documents/koreader.sh")
                safe_chmod(sftp, "/mnt/us/documents/koreader.sh", 0o777)
                
                sftp.put(os.path.join(local_launcher_root, "koreader.sh.sdr", "icon.png"), "/mnt/us/documents/koreader.sh.sdr/icon.png")
                sftp.put(os.path.join(local_launcher_root, "koreader.sh.sdr", "icon.png"), "/mnt/us/documents/koreader.sdr/icon.png")
                safe_chmod(sftp, "/mnt/us/documents/koreader.sh.sdr/icon.png", 0o777)
                safe_chmod(sftp, "/mnt/us/documents/koreader.sdr/icon.png", 0o777)
                
                sftp.put(os.path.join(local_launcher_root, "koreader.sdr", "metadata.sh.lua"), "/mnt/us/documents/koreader.sdr/metadata.sh.lua")
                sftp.put(os.path.join(local_launcher_root, "koreader.sdr", "metadata.sh.lua"), "/mnt/us/documents/koreader.sh.sdr/metadata.sh.lua")
                safe_chmod(sftp, "/mnt/us/documents/koreader.sdr/metadata.sh.lua", 0o777)
                safe_chmod(sftp, "/mnt/us/documents/koreader.sh.sdr/metadata.sh.lua", 0o777)
                
                print("  Native home screen booklet launcher deployed successfully.")
            else:
                print("  [Dry Run] Would deploy native home screen booklet launcher.")
        else:
            print("  Warning: local launcher files not found!")

        # 8.8 Clean Home Screen Documents (Safely isolate ebooks in /mnt/us/epubs/, preserving launchers)
        print("\n[Deploy] Isolating native home screen items (moving ebooks to /mnt/us/epubs/)...")
        if not dry_run:
            clean_docs_script = """
            mkdir -p /mnt/us/epubs
            for item in /mnt/us/documents/*; do
                [ -e "$item" ] || continue
                base=$(basename "$item")
                
                # Explicitly skip launchers, booklets, scripts, dictionaries, or system folders
                if echo "$base" | grep -iqE "koreader|kual|kindleforge|dictionaries|system|\\.azw2$|\\.kual$|\\.sh$"; then
                    continue
                fi
                
                # Move ONLY recognized ebook file formats
                if echo "$base" | grep -iqE "\\.(epub|mobi|azw3|pdf|txt|docx|cbz|cbr|fb2)$"; then
                    mv "$item" "/mnt/us/epubs/" 2>/dev/null || true
                    sdr_folder="/mnt/us/documents/${base}.sdr"
                    if [ -d "$sdr_folder" ]; then
                        mv "$sdr_folder" "/mnt/us/epubs/" 2>/dev/null || true
                    fi
                fi
            done
            
            # Launcher Self-Healing & Verification
            for pattern in "koreader" "kual" "KUAL" "kindleforge"; do
                for f in /mnt/us/epubs/*${pattern}*; do
                    [ -e "$f" ] || continue
                    mv "$f" "/mnt/us/documents/" 2>/dev/null || true
                done
            done
            
            find /mnt/us/documents -mindepth 1 -maxdepth 1 -type d -empty -not -name "dictionaries" -not -name "system" -exec rmdir {} \\; 2>/dev/null || true
            """
            ssh.exec_command(clean_docs_script)
            print("  Home screen isolated. Only KUAL & KOReader launchers remain in /mnt/us/documents.")
            
        # 9. Upload Icons
        print("\n[Deploy] Uploading corner SVG icons...")
        if not dry_run:
            sftp_mkdir_recursive(sftp, REMOTE_ICONS_DIR)
            for name in target_icons.keys():
                local_icon_path = os.path.join(local_icons_dir, name)
                if os.path.exists(local_icon_path):
                    remote_icon_dest = f"{REMOTE_ICONS_DIR}/{name}"
                    sftp.put(local_icon_path, remote_icon_dest)
                    safe_chmod(sftp, remote_icon_dest, 0o777)
                    print(f"  Deployed icon -> {remote_icon_dest}")
        else:
            print("  [Dry Run] Would deploy corner SVGs to {REMOTE_ICONS_DIR}/")

        # 9.5 Force Time Sync from Deployment Machine
        print("\n[Deploy] Configuring robust Kindle timezone offsets...")
        if not dry_run:
            # 1. Restore native Amazon NTP daemons (so the OS clock naturally syncs to true UTC)
            ssh.exec_command("mntroot rw; mv /usr/sbin/ntpd.bak /usr/sbin/ntpd 2>/dev/null; mv /usr/bin/ntpdate.bak /usr/bin/ntpdate 2>/dev/null; mntroot ro")
            
            # 2. Tell the Kindle OS to apply Chicago offset to the top-bar lockscreen clock
            ssh.exec_command("lipc-set-prop com.lab126.wan timezone America/Chicago")

            # 2.5 Force native home screen filter to Downloaded items only and permanently suppress Cloud pop-ups
            suppress_script = """
            mntroot rw
            UPSTART_DIR="/etc/upstart"
            [ -d /etc/init ] && UPSTART_DIR="/etc/init"
            
            cat << 'EOF' > ${UPSTART_DIR}/suppress-cloud-popup.conf
start on started lab126_gui

script
    stop cloudcomm 2>/dev/null || true
    stop todo 2>/dev/null || true
    stop todo.kaf 2>/dev/null || true
    stop phd 2>/dev/null || true
    stop tod 2>/dev/null || true
    stop otav3 2>/dev/null || true
    stop scanlogd 2>/dev/null || true

    for sec in 1 3 5 10 15 30 60; do
        /bin/sleep $sec
        lipc-set-prop com.lab126.booklet.home setFilterId 1 2>/dev/null || true
    done
end script
EOF
            chmod 644 ${UPSTART_DIR}/suppress-cloud-popup.conf 2>/dev/null || true

            cat << 'EOF' > ${UPSTART_DIR}/koreader-watchdog.conf
start on started lab126_gui

script
    while true; do
        /bin/sleep 15s
        IS_READER=$(ps | grep reader.lua | grep -v grep || true)
        IS_GUI=$(ps | grep cvm | grep -v grep || true)
        if [ -z "$IS_READER" ] && [ -z "$IS_GUI" ]; then
            start lab126_gui 2>/dev/null || true
        fi
    done
end script
EOF
            chmod 644 ${UPSTART_DIR}/koreader-watchdog.conf 2>/dev/null || true

            cat << 'EOF' > ${UPSTART_DIR}/keep-wifi-alive.conf
start on started lipcd

script
    while true; do
        is_charging=$(lipc-get-prop com.lab126.powerd isCharging 2>/dev/null || echo 0)
        if [ "$is_charging" = "1" ] || [ "$is_charging" = "1\n" ]; then
            lipc-set-prop com.lab126.wifid enable 1 2>/dev/null || true
            lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null || true
        fi
        sleep 15
    done
end script
EOF
            chmod 644 ${UPSTART_DIR}/keep-wifi-alive.conf 2>/dev/null || true

            if ! grep -q "cloudcomm.amazon.com" /etc/hosts 2>/dev/null; then
                echo "127.0.0.1 todo.amazon.com todo-g7.amazon.com kindle-time.amazon.com cloudcomm.amazon.com ffs.amazon.com" >> /etc/hosts 2>/dev/null || true
            fi
            mntroot ro

            lipc-set-prop com.lab126.booklet.home setFilterId 1 2>/dev/null || true
            stop todo 2>/dev/null || true
            stop todo.kaf 2>/dev/null || true
            stop cloudcomm 2>/dev/null || true
            """
            ssh.exec_command(suppress_script)
            
            # 3. Inject TZ into KOReader's launch script so Lua os.date("*t") evaluates local time flawlessly
            ssh.exec_command("sed -i '/export LC_ALL/a export TZ=CST6CDT' /mnt/us/koreader/koreader.sh")
            
            print("  Successfully shifted clock contexts to Central Time & suppressed Cloud pop-ups.")
        else:
            print("  [Dry Run] Would inject TZ and LIPC offsets.")

        # 10. Configure settings.reader.lua defaults (SimpleUI & Screensaver Cover)
        print("\n[Deploy] Configuring settings.reader.lua defaults...")
        configure_settings_reader_lua(sftp, dry_run=dry_run)
        configure_koreader_sh(sftp, dry_run=dry_run)
            
        # 11. Strict Plugin Baseline Cleanup
        print("\n[Deploy] Enforcing strict plugin baseline...")
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
        
        if not dry_run:
            stdin, stdout, stderr = ssh.exec_command("ls -1 /mnt/us/koreader/plugins")
            installed_plugins = [line.strip() for line in stdout.read().decode('utf-8').splitlines() if line.strip().endswith(".koplugin")]
            removed_count = 0
            for plugin in installed_plugins:
                if plugin not in KEEP_PLUGINS:
                    print(f"  Removing unauthorized plugin: {plugin}")
                    ssh.exec_command(f"rm -rf /mnt/us/koreader/plugins/{plugin}")
                    removed_count += 1
            print(f"  Cleanup complete. Removed {removed_count} bloat plugins.")
        else:
            print("  [Dry Run] Would enforce strict baseline plugin deletion.")
            
        # 11. Restart KOReader
        if not dry_run:
            print("\n[Deploy] Restarting KOReader to apply all updates...")
            ssh.exec_command("killall -9 reader.lua 2>/dev/null; /bin/sleep 1; /mnt/us/koreader/koreader.sh /mnt/us/koreader >/dev/null 2>&1 &")
            print("  Restart command sent successfully.")
            
        print("\n" + "="*50)
        print(" 'BEATS' KINDLE CONFIGURATION DEPLOYED SUCCESSFULLY!")
        print("="*50)
        
    finally:
        print(f"\nCleaning up local temp folder: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()
            print("SSH connection closed.")

if __name__ == "__main__":
    main()
