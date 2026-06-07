import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
import paramiko
import subprocess
import sys
import argparse

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

# AI Keywords for primary classification (Title & Subjects)
AI_KEYWORDS_PRIMARY = [
    r'\bai\b', r'\bais\b', r'artificial intelligence', r'\bllm\w*', r'\bgpt\w*', r'generative',
    r'machine learning', r'deep learning', r'neural network', r'neural net', r'prompt engineering',
    r'agentic', r'openai', r'copilot', r'chatgpt', r'langchain', r'vibe coding', r'aeo', r'\bmlops\b'
]

def is_ai_book(book_meta):
    """
    Check if a book is AI-related based on its metadata.
    Uses title and subjects with a wider range of keywords, and filters descriptions
    with a highly restrictive subset of terms to eliminate false positives.
    """
    title = book_meta.get("title", "").lower()
    subjects = [s.lower() for s in book_meta.get("subjects", [])]
    description = book_meta.get("description", "").lower()
    
    # 1. Search Title and Subjects (Primary match)
    for kw in AI_KEYWORDS_PRIMARY:
        if re.search(kw, title) or any(re.search(kw, s) for s in subjects):
            return True
            
    # 2. Search Description with highly restrictive keywords (Secondary match)
    restrictive_desc_keywords = [
        r'artificial intelligence', r'\bllm\w*', r'\bgpt\w*', r'generative ai',
        r'machine learning', r'deep learning', r'neural network', r'neural net', r'prompt engineering',
        r'agentic ai', r'openai', r'\bcopilot\b', r'chatgpt', r'langchain', r'vibe coding', r'\bmlops\b'
    ]
    for kw in restrictive_desc_keywords:
        if re.search(kw, description):
            return True
            
    return False

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

def extract_cover(epub_path, covers_dir, norm_name):
    """
    Extracts the front (and optional back) cover image from an EPUB file.
    Returns a dict with paths: {"cover_path": "covers/x.jpg", "back_cover_path": "covers/x_back.jpg"} (or None values).
    """
    res_paths = {"cover_path": None, "back_cover_path": None}
    try:
        from PIL import Image
        import io
        
        front_filename = f"{norm_name}.jpg"
        front_path = os.path.join(covers_dir, front_filename)
        
        back_filename = f"{norm_name}_back.jpg"
        back_path = os.path.join(covers_dir, back_filename)
        
        # Check if front already exists
        if os.path.exists(front_path):
            res_paths["cover_path"] = f"covers/{front_filename}"
        if os.path.exists(back_path):
            res_paths["back_cover_path"] = f"covers/{back_filename}"
            
        # If both already exist, no need to open zip
        if res_paths["cover_path"] and res_paths["back_cover_path"]:
            return res_paths
            
        with zipfile.ZipFile(epub_path, 'r') as epub:
            # Read container.xml
            try:
                container_content = epub.read('META-INF/container.xml')
                root = ET.fromstring(container_content)
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//ns:rootfile', ns)
                if rootfile is None:
                    rootfile = root.find('.//rootfile')
                if rootfile is None:
                    return res_paths
                opf_path = rootfile.attrib.get('full-path')
            except:
                return res_paths
                
            if not opf_path:
                return res_paths
                
            # Read OPF content
            opf_dir = os.path.dirname(opf_path)
            opf_content = epub.read(opf_path)
            opf_root = ET.fromstring(opf_content)
            
            ns_opf = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            # Find cover item ID
            cover_id = None
            meta_elem = opf_root.find('.//opf:metadata', ns_opf)
            if meta_elem is None:
                meta_elem = opf_root.find('.//metadata')
            if meta_elem is not None:
                for meta in meta_elem.findall('.//opf:meta', ns_opf) or meta_elem.findall('.//meta'):
                    if meta.attrib.get('name') == 'cover':
                        cover_id = meta.attrib.get('content')
                        break
            
            # Look in manifest
            manifest = opf_root.find('.//opf:manifest', ns_opf)
            if manifest is None:
                manifest = opf_root.find('.//manifest')
                
            img_href = None
            back_img_href = None
            
            if manifest is not None:
                items = manifest.findall('.//opf:item', ns_opf) or manifest.findall('.//item')
                # Try to find by cover_id first
                if cover_id:
                    for item in items:
                        if item.attrib.get('id') == cover_id:
                            img_href = item.attrib.get('href')
                            break
                # Fallback: find any item that has properties="cover-image" or id/href containing "cover"
                for item in items:
                    props = item.attrib.get('properties', '')
                    item_id = item.attrib.get('id', '')
                    href = item.attrib.get('href', '')
                    media_type = item.attrib.get('media-type', '')
                    
                    if 'image/' in media_type:
                        if not img_href and ('cover-image' in props or 'cover' in item_id.lower() or 'cover' in href.lower()):
                            # Avoid grabbing back cover as front cover
                            if 'back' not in item_id.lower() and 'back' not in href.lower():
                                img_href = href
                        if not back_img_href and ('backcover' in item_id.lower() or 'back-cover' in item_id.lower() or 'back_cover' in item_id.lower() or 'backcover' in href.lower() or 'back-cover' in href.lower() or 'back_cover' in href.lower()):
                            back_img_href = href
                            
            if not img_href:
                # Last resort fallback for front cover
                for name in epub.namelist():
                    if 'cover' in name.lower() and 'back' not in name.lower() and (name.lower().endswith('.jpg') or name.lower().endswith('.jpeg') or name.lower().endswith('.png')):
                        img_href = name
                        opf_dir = "" # Path is already absolute within zip
                        break
                        
            if not back_img_href:
                # Last resort fallback for back cover
                for name in epub.namelist():
                    if 'back' in name.lower() and 'cover' in name.lower() and (name.lower().endswith('.jpg') or name.lower().endswith('.jpeg') or name.lower().endswith('.png')):
                        back_img_href = name
                        opf_dir = ""
                        break
                        
            # Helper to extract and save a specific image href
            def extract_and_resize(href, dest):
                if not href: return False
                if opf_dir:
                    zip_img_path = os.path.join(opf_dir, href).replace('\\', '/')
                else:
                    zip_img_path = href
                
                parts = []
                for p in zip_img_path.split('/'):
                    if p == '..':
                        if parts: parts.pop()
                    elif p != '.':
                        parts.append(p)
                zip_img_path = '/'.join(parts)
                
                try:
                    img_data = epub.read(zip_img_path)
                except:
                    try:
                        img_data = epub.read(href)
                    except:
                        return False
                
                img = Image.open(io.BytesIO(img_data))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                max_width = 400
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(float(img.height) * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                img.save(dest, 'JPEG', quality=85)
                return True

            if not res_paths["cover_path"] and img_href:
                if extract_and_resize(img_href, front_path):
                    res_paths["cover_path"] = f"covers/{front_filename}"
            if not res_paths["back_cover_path"] and back_img_href:
                if extract_and_resize(back_img_href, back_path):
                    res_paths["back_cover_path"] = f"covers/{back_filename}"
                    
    except Exception as e:
        print(f"Error extracting cover for {epub_path}: {e}")
    return res_paths

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
    # Force stdout/stderr to UTF-8 encoding on Windows to prevent UnicodeEncodeErrors when printing book metadata
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass

    parser = argparse.ArgumentParser(description="Sync ebooks between Kindle and OneDrive")
    parser.add_argument("--purge-non-ai", action="store_true", help="Purge non-AI books from Kindle")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (preview changes without deleting/writing files)")
    args = parser.parse_args()
    
    purge_non_ai = args.purge_non_ai
    dry_run = args.dry_run
    
    if dry_run:
        print("=== DRY RUN MODE: No files will be modified ===")

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
    local_norm_names = {normalize_filename(os.path.basename(p)): p for p in local_files}

    # 1. Back up Kindle -> OneDrive
    if kindle_connected:
        for k_path in kindle_epubs:
            basename = os.path.basename(k_path)
            norm_name = normalize_filename(basename)
            
            if norm_name not in local_norm_names:
                local_dest = os.path.join(ONEDRIVE_EPUB_DIR, basename)
                print(f"Backing up: {basename} -> OneDrive...")
                try:
                    if not dry_run:
                        sftp.get(k_path, local_dest)
                    local_files.append(local_dest)
                    local_norm_names[norm_name] = local_dest
                except Exception as ex:
                    print(f"Failed to download {basename}: {ex}")

    # 1b. Purge non-AI books from Kindle (if enabled)
    purged_count = 0
    if kindle_connected and purge_non_ai:
        print("Running AI-topic cleanup on Kindle...")
        kindle_epubs_remaining = list(kindle_epubs)
        for k_path in kindle_epubs:
            basename = os.path.basename(k_path)
            norm_name = normalize_filename(basename)
            
            local_path = local_norm_names.get(norm_name)
            if local_path and (dry_run or os.path.exists(local_path)):
                # Use metadata from db if cached, else read file
                if norm_name in db:
                    meta = db[norm_name]
                else:
                    meta = get_epub_metadata(local_path)
                
                if not is_ai_book(meta):
                    print(f"[Purge] Book '{meta.get('title', basename)}' is not AI-related.")
                    purged_count += 1
                    if not dry_run:
                        try:
                            sftp.remove(k_path)
                            print(f"  Deleted from Kindle: {basename}")
                            if k_path in kindle_epubs_remaining:
                                kindle_epubs_remaining.remove(k_path)
                        except Exception as ex:
                            print(f"  Failed to delete {basename} from Kindle: {ex}")
                    else:
                        print(f"  [Dry Run] Would delete from Kindle: {basename}")
            else:
                print(f"  Warning: Cannot purge '{basename}' because it is not backed up in OneDrive.")
        
        if not dry_run:
            kindle_epubs = kindle_epubs_remaining
        print(f"Purge check complete. Identified {purged_count} non-AI books.")

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
                    if not dry_run:
                        sftp.put(q_file, dest_path)
                        # Archive local file
                        archive_path = os.path.join(ONEDRIVE_EPUB_DIR, basename)
                        # If file already exists in archive, generate unique name
                        if os.path.exists(archive_path):
                            os.remove(q_file) # Just delete from queue since we have it archived
                        else:
                            os.rename(q_file, archive_path)
                            local_files.append(archive_path)
                    else:
                        print(f"  [Dry Run] Would upload {basename} and archive it.")
                        
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
        
        # Extract cover if missing (only if not dry_run)
        covers_dir = os.path.join(REPO_DIR, "covers")
        if not dry_run:
            os.makedirs(covers_dir, exist_ok=True)
            cover_path = entry.get("cover_path")
            back_cover_path = entry.get("back_cover_path")
            if not cover_path or not back_cover_path or not os.path.exists(os.path.join(REPO_DIR, cover_path)):
                covers_info = extract_cover(local_path, covers_dir, norm_name)
                if covers_info.get("cover_path"):
                    entry["cover_path"] = covers_info["cover_path"]
                if covers_info.get("back_cover_path"):
                    entry["back_cover_path"] = covers_info["back_cover_path"]
        else:
            if "cover_path" not in entry:
                entry["cover_path"] = f"covers/{norm_name}.jpg"
                
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
    # Determine AI status for all entries
    for entry in updated_db.values():
        entry["is_ai"] = is_ai_book(entry)

    if not dry_run:
        save_books_db(updated_db)
        print(f"Database updated. Total registered books: {len(updated_db)}")
    else:
        print(f"[Dry Run] Would save books database with {len(updated_db)} entries.")

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

    # Update index.html dynamically if it exists
    INDEX_HTML_PATH = os.path.join(REPO_DIR, "index.html")
    if os.path.exists(INDEX_HTML_PATH):
        try:
            with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
                html_content = f.read()
            # Replace placeholder link or old link
            updated_html = re.sub(
                r'href="([^"]+)"\s+id="onedrive-shared-btn"',
                f'href="{shared_link_placeholder}" id="onedrive-shared-btn"',
                html_content
            )
            # Also replace any other href="[Insert OneDrive Shared Link Here]"
            updated_html = updated_html.replace('[Insert OneDrive Shared Link Here]', shared_link_placeholder)
            
            if updated_html != html_content:
                if not dry_run:
                    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
                        f.write(updated_html)
                    print("index.html updated with OneDrive shared link.")
                else:
                    print(f"[Dry Run] Would update index.html with OneDrive shared link: {shared_link_placeholder}")
        except Exception as html_err:
            print(f"Failed to update index.html: {html_err}")

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
    md += "| AI Topic? | Status | Title & Author | Year | Subjects / Genres | Synopsis | Download / Access |\n"
    md += "| :---: | :---: | | :---: | | | :---: |\n"
    
    for book in sorted_books:
        status_icon = "📱 Kindle & 💾 OneDrive" if book["is_on_kindle"] else "💾 OneDrive Only"
        ai_icon = "🤖 Yes" if book.get("is_ai", False) else "❌ No"
        
        # Clean synopsis snippet (limit to 140 chars)
        synopsis = book["description"]
        if len(synopsis) > 140:
            synopsis = synopsis[:137] + "..."
        # Escape pipe symbols in markdown tables
        synopsis = synopsis.replace('|', '\\|')
        
        title_author = f"**{book['title']}**<br>_by {book['author']}_"
        subjects = ", ".join(book["subjects"]) if book["subjects"] else "_"
        
        # Clickable access links (local file link and/or public cloud download link)
        access_links = []
        if book["onedrive_path"]:
            # URL encode path segments for markdown link
            from urllib.parse import quote
            rel_path = book["onedrive_path"]
            abs_path = os.path.abspath(os.path.join(ONEDRIVE_EBOOKS_DIR, rel_path))
            file_url = f"file:///{abs_path.replace('\\', '/')}"
            access_links.append(f"[Local File]({file_url})")
            
        if book.get("onedrive_download_link"):
            access_links.append(f"[Cloud Download]({book['onedrive_download_link']})")
            
        links_str = " / ".join(access_links) if access_links else "_"
        
        md += f"| {ai_icon} | {status_icon} | {title_author} | {book['year']} | {subjects} | {synopsis} | {links_str} |\n"

    if not dry_run:
        with open(README_MD_PATH, 'w', encoding='utf-8') as f:
            f.write(md)
        print("README.md generated successfully!")
    else:
        print(f"[Dry Run] Would write README.md (length: {len(md)} characters).")

    # 5. Git Commit & Push
    if dry_run:
        print("[Dry Run] Skipping git commit and push.")
        return
        
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
            
        subprocess.run(["git", "add", "README.md", "books.json", "index.html", "recommendations.md", "recommendations.json", "covers/"], cwd=REPO_DIR, env=env, check=True)
        # Check if anything to commit
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_DIR, capture_output=True, text=True, check=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Auto-update book database, web portal, and recommendations"], cwd=REPO_DIR, env=env, check=True)
            subprocess.run(["git", "push"], cwd=REPO_DIR, env=env, check=True)
            print("Successfully committed and pushed updates to GitHub!")
        else:
            print("No changes to commit.")
    except Exception as git_err:
        print(f"Git push failed: {git_err}")

if __name__ == "__main__":
    main()
