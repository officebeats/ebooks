import os
import sys
import time
import requests
import zipfile
import io

# Configurations
TORBOX_BASE_URL = "https://api.torbox.app/v1/api"
ONEDRIVE_EPUB_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks\Epubs"

def get_headers():
    api_key = os.environ.get("TORBOX_API_KEY")
    if not api_key:
        raise ValueError("Error: TORBOX_API_KEY environment variable is not set. Set it before running.")
    return {
        "Authorization": f"Bearer {api_key}"
    }

def add_torrent(magnet_link):
    url = f"{TORBOX_BASE_URL}/torrents/createtorrent"
    headers = get_headers()
    data = {
        "magnet": magnet_link,
        "seed": "false",
        "allow_zip": "true" # Pack multiple files into a zip for easy extraction
    }
    
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    result = response.json()
    if result.get("success"):
        return result.get("data", {})
    else:
        raise Exception(f"TorBox error adding link: {result.get('detail')}")

def check_status(torrent_id):
    url = f"{TORBOX_BASE_URL}/torrents/mylist"
    headers = get_headers()
    params = {"id": torrent_id}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    result = response.json()
    if result.get("success"):
        data = result.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
    return None

def download_and_extract(torrent_id, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    url = f"{TORBOX_BASE_URL}/torrents/requestdl"
    headers = get_headers()
    params = {
        "token": os.environ.get("TORBOX_API_KEY"),
        "torrent_id": torrent_id,
        "zip": "true" # Ensure we get a single zip archive back
    }
    
    print("Requesting download link from TorBox...")
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    result = response.json()
    
    if not result.get("success"):
        raise Exception(f"Failed to get download link: {result.get('detail')}")
        
    download_url = result.get("data")
    if not download_url:
        raise Exception("Download URL was empty.")
        
    print(f"Downloading file from TorBox...")
    file_response = requests.get(download_url, stream=True)
    file_response.raise_for_status()
    
    # Read zip into memory
    zip_data = io.BytesIO()
    for chunk in file_response.iter_content(chunk_size=8192):
        if chunk:
            zip_data.write(chunk)
            
    print("Extracting EPUBs to OneDrive...")
    zip_data.seek(0)
    with zipfile.ZipFile(zip_data) as z:
        for member in z.infolist():
            filename = os.path.basename(member.filename)
            # Only extract EPUB files directly into Epubs directory
            if filename.lower().endswith(".epub"):
                # Clean path traversal
                dest_path = os.path.join(dest_dir, filename)
                print(f"  Saving: {filename}")
                with open(dest_path, "wb") as f:
                    f.write(z.read(member.filename))
    print("Extraction completed successfully!")

def process_magnet(magnet_link):
    try:
        print(f"\nAdding magnet link: {magnet_link[:60]}...")
        info = add_torrent(magnet_link)
        torrent_id = info.get("torrent_id")
        name = info.get("name", "Torrent")
        print(f"Added successfully. Torrent ID: {torrent_id} ({name})")
        
        while True:
            status = check_status(torrent_id)
            if not status:
                print("Could not retrieve status, retrying...")
                time.sleep(5)
                continue
                
            progress = status.get("progress", 0)
            state = status.get("download_state", "unknown")
            print(f"Status: {state} | Progress: {progress * 100:.1f}%")
            
            if status.get("download_finished"):
                print("TorBox has finished downloading!")
                break
                
            time.sleep(10)
            
        download_and_extract(torrent_id, ONEDRIVE_EPUB_DIR)
        
    except Exception as e:
        print(f"Error processing torrent: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python torbox_download_to_onedrive.py <magnet_link>")
        sys.exit(1)
        
    magnet_link = sys.argv[1]
    process_magnet(magnet_link)
