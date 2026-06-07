import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
import paramiko
import subprocess

# Configurations
KINDLE_IP = "192.168.68.79"
KINDLE_PORT = 2222
KINDLE_USER = "root"
KINDLE_PASSWORD = ""
KINDLE_EPUB_DIR = "/mnt/us/Epubs"

ONEDRIVE_EBOOKS_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks"
ONEDRIVE_EPUB_DIR = os.path.join(ONEDRIVE_EBOOKS_DIR, "Epubs")
ONEDRIVE_QUEUE_DIR = os.path.join(ONEDRIVE_EBOOKS_DIR, "SendToKindle")

REPO_DIR = os.path.join(ONEDRIVE_EBOOKS_DIR, "ebooks")
BOOKS_JSON_PATH = os.path.join(REPO_DIR, "books.json")
README_MD_PATH = os.path.join(REPO_DIR, "README.md")

# Create directories if they do not exist
os.makedirs(ONEDRIVE_EPUB_DIR, exist_ok=True)
os.makedirs(ONEDRIVE_QUEUE_DIR, exist_ok=True)

def normalize_filename(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\(Z-Library\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^a-z0-9]', '', name.lower())
    return name

def get_epub_metadata(epub_path):
    metadata = {
        "title": os.path.splitext(os.path.basename(epub_path))[0],
        "author": "Unknown",
        "year": "Unknown",
        "subjects": [],
        "description": "No synopsis available."
    }
    try:
        with zipfile.ZipFile(epub_path, 'r') as epub:
            container_xml = epub.read('META-INF/container.xml')
            root = ET.fromstring(container_xml)
            ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            rootfile = root.find('.//ns:rootfile', ns)
            if rootfile is None:
                rootfile = root.find('.//rootfile')
                
            if rootfile is not None:
                opf_path = rootfile.attrib.get('full-path')
                opf_content = epub.read(opf_path)
                opf_root = ET.fromstring(opf_content)
                
                ns_opf = {
                    'opf': 'http://www.idpf.org/2007/opf',
                    'dc': 'http://purl.org/dc/elements/1.1/'
                }
                
                meta_elem = opf_root.find('.//opf:metadata', ns_opf)
                if meta_elem is None:
                    meta_elem = opf_root.find('.//metadata')
                    
                if meta_elem is not None:
                    t_elem = meta_elem.find('.//dc:title', ns_opf)
                    if t_elem is not None and t_elem.text:
                        metadata["title"] = t_elem.text.strip()
                        
                    c_elem = meta_elem.find('.//dc:creator', ns_opf)
                    if c_elem is not None and c_elem.text:
                        metadata["author"] = c_elem.text.strip()
                        
                    d_elem = meta_elem.find('.//dc:date', ns_opf)
                    if d_elem is not None and d_elem.text:
                        date_text = d_elem.text.strip()
                        match = re.search(r'\d{4}', date_text)
                        if match:
                            metadata["year"] = match.group(0)
                        
                    desc_elem = meta_elem.find('.//dc:description', ns_opf)
                    if desc_elem is not None and desc_elem.text:
                        desc = re.sub('<[^<]+?>', '', desc_elem.text)
                        desc = re.sub(r'\s+', ' ', desc).strip()
                        metadata["description"] = desc
                        
                    s_elems = meta_elem.findall('.//dc:subject', ns_opf)
                    for s in s_elems:
                        if s.text:
                            metadata["subjects"].append(s.text.strip())
    except Exception as e:
        print(f"Error parsing metadata for {os.path.basename(epub_path)}: {e}")
    return metadata

def load_books_db():
    if os.path.exists(BOOKS_JSON_PATH):
        try:
            with open(BOOKS_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading books.json: {e}")
    return {}

def save_books_db(db):
    try:
        with open(BOOKS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving books.json: {e}")

def get_kindle_free_space(ssh):
    try:
        stdin, stdout, stderr = ssh.exec_command("df -k /mnt/us")
        lines = stdout.read().decode('utf-8').splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            # df -k outputs kilobytes. Third column is Available
            if len(parts) >= 4:
                # available space in KB
                return int(parts[3]) * 1024
    except Exception as e:
        print(f"Error checking Kindle disk space: {e}")
    return None

def main():
    print("Loading books database...")
    db = load_books_db()

    print("Connecting to Kindle via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    kindle_connected = False
    kindle_epubs = []
    
    try:
        ssh.connect(KINDLE_IP, port=KINDLE_PORT, username=KINDLE_USER, password=KINDLE_PASSWORD, look_for_keys=False, allow_agent=False)
        sftp = ssh.open_sftp()
        kindle_connected = True
        print("Connected successfully to Kindle!")
        
        # Ensure remote dir exists
        try:
            sftp.mkdir(KINDLE_EPUB_DIR)
        except:
            pass
            
        # List remote epubs
        stdin, stdout, stderr = ssh.exec_command(f"find {KINDLE_EPUB_DIR} -name '*.epub'")
        kindle_epubs = [line.strip() for line in stdout.read().decode('utf-8', errors='ignore').splitlines() if line.strip()]
        print(f"Found {len(kindle_epubs)} epubs on Kindle.")
        
    except Exception as e:
        print(f"Could not connect to Kindle: {e}")
        print("Proceeding with local-only metadata compilation...")

    # Scan local OneDrive archive
    local_files = [os.path.join(ONEDRIVE_EPUB_DIR, f) for f in os.listdir(ONEDRIVE_EPUB_DIR) if f.endswith(".epub")]
    print(f"Found {len(local_files)} epubs in OneDrive archive.")

    # 1. Back up Kindle -> OneDrive
    if kindle_connected:
        local_norm_names = {normalize_filename(os.path.basename(p)): p for p in local_files}
        
        for k_path in kindle_epubs:
            basename = os.path.basename(k_path)
            norm_name = normalize_filename(basename)
            
            if norm_name not in local_norm_names:
                local_dest = os.path.join(ONEDRIVE_EPUB_DIR, basename)
                print(f"Backing up: {basename} -> OneDrive...")
                try:
                    sftp.get(k_path, local_dest)
                    local_files.append(local_dest)
                    local_norm_names[norm_name] = local_dest
                except Exception as ex:
                    print(f"Failed to download {basename}: {ex}")

    # 2. Upload queue (SendToKindle) -> Kindle
    if kindle_connected:
        queue_files = [os.path.join(ONEDRIVE_QUEUE_DIR, f) for f in os.listdir(ONEDRIVE_QUEUE_DIR) if f.endswith(".epub")]
        if queue_files:
            print(f"Found {len(queue_files)} files in SendToKindle queue.")
            free_space = get_kindle_free_space(ssh)
            
            for q_file in queue_files:
                basename = os.path.basename(q_file)
                filesize = os.path.getsize(q_file)
                
                if free_space is not None and free_space < filesize + (5 * 1024 * 1024): # Keep 5MB safety buffer
                    print(f"Skipping {basename}: Not enough storage space on Kindle.")
                    continue
                    
                dest_path = f"{KINDLE_EPUB_DIR}/{basename}"
                print(f"Uploading {basename} to Kindle...")
                try:
                    sftp.put(q_file, dest_path)
                    # Archive local file
                    archive_path = os.path.join(ONEDRIVE_EPUB_DIR, basename)
                    # If file already exists in archive, generate unique name
                    if os.path.exists(archive_path):
                        os.remove(q_file) # Just delete from queue since we have it archived
                    else:
                        os.rename(q_file, archive_path)
                        local_files.append(archive_path)
                        
                    if free_space is not None:
                        free_space -= filesize
                except Exception as ex:
                    print(f"Failed to upload {basename}: {ex}")
                    
    if kindle_connected:
        sftp.close()
        ssh.close()

    # 3. Update Database (books.json) & Extract Metadata
    print("Updating metadata database...")
    updated_db = {}
    
    # Reload local files list
    local_files = [os.path.join(ONEDRIVE_EPUB_DIR, f) for f in os.listdir(ONEDRIVE_EPUB_DIR) if f.endswith(".epub")]
    
    # Maps normalized name to current files for status checking
    local_norm_map = {normalize_filename(os.path.basename(p)): p for p in local_files}
    kindle_norm_map = {}
    if kindle_connected:
        kindle_norm_map = {normalize_filename(os.path.basename(p)): p for p in kindle_epubs}

    for local_path in local_files:
        basename = os.path.basename(local_path)
        norm_name = normalize_filename(basename)
        
        # Check if already cached in db
        if norm_name in db:
            entry = db[norm_name]
            # Ensure path is updated in case user moved OneDrive root
            entry["onedrive_path"] = os.path.relpath(local_path, ONEDRIVE_EBOOKS_DIR).replace('\\', '/')
        else:
            print(f"Parsing new book metadata: {basename}...")
            meta = get_epub_metadata(local_path)
            entry = {
                "title": meta["title"],
                "author": meta["author"],
                "year": meta["year"],
                "subjects": meta["subjects"],
                "description": meta["description"],
                "onedrive_path": os.path.relpath(local_path, ONEDRIVE_EBOOKS_DIR).replace('\\', '/')
            }
            
        # Determine status
        is_on_kindle = False
        kindle_file_path = ""
        
        if kindle_connected:
            if norm_name in kindle_norm_map:
                is_on_kindle = True
                kindle_file_path = kindle_norm_map[norm_name]
        else:
            # Fall back to previous status if Kindle is not connected
            if norm_name in db:
                is_on_kindle = db[norm_name].get("is_on_kindle", False)
                kindle_file_path = db[norm_name].get("kindle_path", "")
                
        entry["is_on_kindle"] = is_on_kindle
        entry["kindle_path"] = kindle_file_path
        
        updated_db[norm_name] = entry

    # Handle books only on Kindle (in case we didn't back them up or Kindle disconnected)
    if kindle_connected:
        for k_path in kindle_epubs:
            basename = os.path.basename(k_path)
            norm_name = normalize_filename(basename)
            if norm_name not in updated_db:
                # Book is only on Kindle and failed to download
                entry = {
                    "title": os.path.splitext(basename)[0],
                    "author": "Unknown",
                    "year": "Unknown",
                    "subjects": [],
                    "description": "On Kindle only. Metadata not parsed.",
                    "onedrive_path": "",
                    "is_on_kindle": True,
                    "kindle_path": k_path
                }
                updated_db[norm_name] = entry

    save_books_db(updated_db)
    print(f"Database updated. Total registered books: {len(updated_db)}")

    # 4. Generate README.md Markdown Listing
    print("Generating README.md...")
    sorted_books = sorted(updated_db.values(), key=lambda x: x["title"].lower())
    
    # Read custom OneDrive Shared link if it exists in README.md to preserve it
    shared_link_placeholder = "[Insert OneDrive Shared Link Here]"
    if os.path.exists(README_MD_PATH):
        try:
            with open(README_MD_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find shared link pattern
                match = re.search(r'OneDrive Shared Library:\s*\*?\*?\[Click here to browse/download\]\((https://[^\)]+)\)\*?\*?', content)
                if match:
                    shared_link_placeholder = match.group(1)
        except:
            pass

    md = "# eBooks Repository\n\n"
    md += "A private repository to index and manage your personal EPUB library. \n\n"
    md += "### Quick Access Links\n"
    md += f"- **OneDrive Shared Library:** [Click here to browse/download]({shared_link_placeholder}) *(Paste your public OneDrive shareable link here to share with friends!)*\n"
    md += "- **Sync Status:** Automatically updated via `sync_books.py`\n\n"
    md += "### How to Use the Download Helper\n"
    md += "Clone this repository on any computer and run:\n"
    md += "```bash\n"
    md += "python download_books.py\n"
    md += "```\n"
    md += "This will list all books and let you choose which ones to download from OneDrive or your Kindle.\n\n"
    
    md += "## Books List\n\n"
    md += f"Total books cataloged: **{len(sorted_books)}**\n\n"
    md += "| Status | Title & Author | Year | Subjects / Genres | Synopsis | Local OneDrive Link |\n"
    md += "| :---: | | :---: | | | :---: |\n"
    
    for book in sorted_books:
        status_icon = "📱 Kindle & 💾 OneDrive" if book["is_on_kindle"] else "💾 OneDrive Only"
        
        # Clean synopsis snippet (limit to 140 chars)
        synopsis = book["description"]
        if len(synopsis) > 140:
            synopsis = synopsis[:137] + "..."
        # Escape pipe symbols in markdown tables
        synopsis = synopsis.replace('|', '\\|')
        
        title_author = f"**{book['title']}**<br>_by {book['author']}_"
        subjects = ", ".join(book["subjects"]) if book["subjects"] else "_"
        
        # Clickable local file link if onedrive path exists
        local_link = "_"
        if book["onedrive_path"]:
            # URL encode path segments for markdown link
            from urllib.parse import quote
            rel_path = book["onedrive_path"]
            abs_path = os.path.abspath(os.path.join(ONEDRIVE_EBOOKS_DIR, rel_path))
            file_url = f"file:///{abs_path.replace('\\', '/')}"
            local_link = f"[Open File]({file_url})"
            
        md += f"| {status_icon} | {title_author} | {book['year']} | {subjects} | {synopsis} | {local_link} |\n"

    with open(README_MD_PATH, 'w', encoding='utf-8') as f:
        f.write(md)
    print("README.md generated successfully!")

    # 5. Git Commit & Push
    try:
        print("Pushing updates to GitHub...")
        # Check if initialized
        if not os.path.exists(os.path.join(REPO_DIR, ".git")):
            print("Git repository not initialized in this folder yet.")
            return
            
        # Run Git commands
        # Unset GITHUB_TOKEN locally in subprocess env if it's set to dummy token
        env = os.environ.copy()
        if "GITHUB_TOKEN" in env and "dummy" in env["GITHUB_TOKEN"].lower():
            del env["GITHUB_TOKEN"]
            
        subprocess.run(["git", "add", "README.md", "books.json"], cwd=REPO_DIR, env=env, check=True)
        # Check if anything to commit
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_DIR, capture_output=True, text=True, check=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Auto-update book database and README.md"], cwd=REPO_DIR, env=env, check=True)
            subprocess.run(["git", "push"], cwd=REPO_DIR, env=env, check=True)
            print("Successfully committed and pushed updates to GitHub!")
        else:
            print("No changes to commit.")
    except Exception as git_err:
        print(f"Git push failed: {git_err}")

if __name__ == "__main__":
    main()
