import os
import json
import paramiko
import shutil

BOOKS_JSON_PATH = "books.json"

def load_books_db():
    if os.path.exists(BOOKS_JSON_PATH):
        try:
            with open(BOOKS_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading books.json: {e}")
    return {}

def list_books(books, page=1, page_size=20, search_query=""):
    filtered_books = []
    query = search_query.lower().strip()
    
    for book in books:
        if (query in book["title"].lower() or 
            query in book["author"].lower() or 
            any(query in s.lower() for s in book["subjects"])):
            filtered_books.append(book)
            
    total_books = len(filtered_books)
    total_pages = (total_books + page_size - 1) // page_size if total_books > 0 else 1
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_books)
    
    page_books = filtered_books[start_idx:end_idx]
    
    print("\n" + "="*80)
    print(f" EBOOKS CATALOG (Page {page}/{total_pages} - Total Books Found: {total_books})")
    if search_query:
        print(f" Active Search: '{search_query}'")
    print("="*80)
    
    print(f"{'#':<4} | {'Title & Author':<45} | {'Year':<6} | {'Location':<18}")
    print("-"*80)
    
    for idx, book in enumerate(page_books, start_idx + 1):
        title_author = f"{book['title']} by {book['author']}"
        if len(title_author) > 45:
            title_author = title_author[:42] + "..."
            
        location = "Kindle & OneDrive" if book["is_on_kindle"] else "OneDrive Only"
        print(f"{idx:<4} | {title_author:<45} | {book['year']:<6} | {location:<18}")
        
    print("="*80)
    return filtered_books, total_pages

def handle_download_local(selected_books, onedrive_root_path, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    success_count = 0
    
    for book in selected_books:
        rel_path = book["onedrive_path"]
        if not rel_path:
            print(f"Skipping '{book['title']}': No OneDrive path available.")
            continue
            
        # The stored path is relative to the eBooks root (e.g. "Epubs/file.epub")
        src_path = os.path.join(onedrive_root_path, rel_path)
        if not os.path.exists(src_path):
            # Try to resolve relative path if the root path is correct
            # If user provided parent directory
            src_path = os.path.join(onedrive_root_path, os.path.basename(rel_path))
            if not os.path.exists(src_path):
                # Try subfolder
                src_path = os.path.join(onedrive_root_path, "Epubs", os.path.basename(rel_path))
                
        if os.path.exists(src_path):
            dest_path = os.path.join(dest_dir, os.path.basename(src_path))
            print(f"Copying '{book['title']}'...")
            try:
                shutil.copy(src_path, dest_path)
                success_count += 1
            except Exception as e:
                print(f"Error copying file: {e}")
        else:
            print(f"Error: Could not find file locally at '{src_path}'. Make sure your OneDrive folder is synced.")
            
    print(f"\nCompleted! Successfully copied {success_count}/{len(selected_books)} books to '{dest_dir}'.")

def handle_download_kindle(selected_books, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    
    ip = input("Enter Kindle IP Address [default: 192.168.68.79]: ").strip()
    if not ip:
        ip = "192.168.68.79"
        
    port_input = input("Enter Kindle SSH Port [default: 2222]: ").strip()
    port = int(port_input) if port_input else 2222
    
    print(f"Connecting to Kindle at {ip}:{port}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, port=port, username="root", password="", look_for_keys=False, allow_agent=False)
        sftp = ssh.open_sftp()
        print("Connected successfully!")
        
        success_count = 0
        for book in selected_books:
            k_path = book["kindle_path"]
            if not k_path:
                print(f"Skipping '{book['title']}': This book is not on your Kindle.")
                continue
                
            basename = os.path.basename(k_path)
            dest_path = os.path.join(dest_dir, basename)
            print(f"Downloading '{book['title']}' from Kindle...")
            try:
                sftp.get(k_path, dest_path)
                success_count += 1
            except Exception as e:
                print(f"Error downloading file: {e}")
                
        sftp.close()
        ssh.close()
        print(f"\nCompleted! Successfully downloaded {success_count}/{len(selected_books)} books to '{dest_dir}'.")
        
    except Exception as e:
        print(f"Failed to connect to Kindle: {e}")

def main():
    print("Loading eBooks database...")
    db = load_books_db()
    if not db:
        print("Error: books.json is empty or missing. Make sure you run sync_books.py first.")
        return
        
    books = list(db.values())
    # Sort alphabetically
    books.sort(key=lambda x: x["title"].lower())
    
    page = 1
    search_query = ""
    filtered_books = books
    
    while True:
        filtered_books, total_pages = list_books(books, page=page, search_query=search_query)
        
        print("\nCommands:")
        print("  [n] Next page            [p] Previous page")
        # Ask to search or download
        print("  [s] Search books         [c] Clear search")
        print("  [d] Download books       [i] View book info/synopsis")
        print("  [q] Quit")
        
        cmd = input("\nEnter command: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == 'n':
            if page < total_pages:
                page += 1
            else:
                print("Already on the last page.")
        elif cmd == 'p':
            if page > 1:
                page -= 1
            else:
                print("Already on the first page.")
        elif cmd == 'c':
            search_query = ""
            page = 1
        elif cmd == 's':
            search_query = input("Enter search term (title, author, or genre): ").strip()
            page = 1
        elif cmd == 'i':
            try:
                idx = int(input("Enter book index number to view info: ").strip())
                if 1 <= idx <= len(filtered_books):
                    book = filtered_books[idx - 1]
                    print("\n" + "="*80)
                    print(f"TITLE:       {book['title']}")
                    print(f"AUTHOR:      {book['author']}  ({book['year']})")
                    print(f"GENRES:      {', '.join(book['subjects'])}")
                    print(f"LOCATION:    {'Kindle & OneDrive' if book['is_on_kindle'] else 'OneDrive Only'}")
                    print(f"ONEDRIVE:    {book['onedrive_path']}")
                    print("-"*80)
                    print(f"SYNOPSIS:\n{book['description']}")
                    print("="*80)
                    input("\nPress Enter to return...")
                else:
                    print("Invalid index number.")
            except ValueError:
                print("Please enter a valid number.")
        elif cmd == 'd':
            # Download selection
            selection_input = input("Enter book index numbers to download (e.g. '1,5,10' or 'all'): ").strip()
            if not selection_input:
                continue
                
            selected_books = []
            if selection_input.lower() == 'all':
                selected_books = filtered_books
            else:
                try:
                    indices = [int(i.strip()) for i in selection_input.split(',')]
                    for idx in indices:
                        if 1 <= idx <= len(filtered_books):
                            selected_books.append(filtered_books[idx - 1])
                        else:
                            print(f"Warning: Index {idx} is out of range, skipping.")
                except ValueError:
                    print("Error: Invalid input format. Use numbers separated by commas (e.g., '1, 4, 8').")
                    continue
                    
            if not selected_books:
                print("No valid books selected.")
                continue
                
            print(f"\nSelected {len(selected_books)} books to download:")
            for b in selected_books:
                print(f" - {b['title']}")
                
            print("\nSelect Download Source:")
            print("  1. Copy from local OneDrive folder (synced on this PC)")
            print("  2. Download directly from Kindle over Wi-Fi (SSH/SFTP)")
            source_choice = input("Enter source (1 or 2): ").strip()
            
            dest_dir = input("Enter destination directory to save books [default: ./downloaded_books]: ").strip()
            if not dest_dir:
                dest_dir = "./downloaded_books"
                
            if source_choice == '1':
                onedrive_root = input(r"Enter local OneDrive root path [default: C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks]: ").strip()
                if not onedrive_root:
                    onedrive_root = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks"
                handle_download_local(selected_books, onedrive_root, dest_dir)
            elif source_choice == '2':
                handle_download_kindle(selected_books, dest_dir)
            else:
                print("Invalid source selection.")
                
            input("\nPress Enter to return...")

if __name__ == "__main__":
    main()
