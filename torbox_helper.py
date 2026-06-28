import os
import time
import requests

# Base URL for TorBox API v1
TORBOX_BASE_URL = "https://api.torbox.app/v1/api"

def get_headers():
    # Retrieve API key from environment variables for security
    api_key = os.environ.get("TORBOX_API_KEY")
    if not api_key:
        raise ValueError("Error: TORBOX_API_KEY environment variable is not set.")
    return {
        "Authorization": f"Bearer {api_key}"
    }

def add_torrent(magnet_link):
    """
    Add a magnet link or torrent to TorBox.
    """
    url = f"{TORBOX_BASE_URL}/torrents/createtorrent"
    headers = get_headers()
    data = {
        "magnet": magnet_link,
        "seed": "false",
        "allow_zip": "false"
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            print("Successfully added torrent to TorBox!")
            return result.get("data", {})
        else:
            print(f"Failed to add torrent: {result.get('detail')}")
    except Exception as e:
        print(f"Error calling TorBox API: {e}")
    return None

def check_torrent_status(torrent_id):
    """
    Check the download progress/status of a specific torrent.
    """
    url = f"{TORBOX_BASE_URL}/torrents/mylist"
    headers = get_headers()
    params = {
        "id": torrent_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            torrents = result.get("data", [])
            # If queried with a specific ID, data can be a dict or a list containing the item
            if isinstance(torrents, list) and len(torrents) > 0:
                return torrents[0]
            elif isinstance(torrents, dict):
                return torrents
        else:
            print(f"Failed to fetch status: {result.get('detail')}")
    except Exception as e:
        print(f"Error checking torrent status: {e}")
    return None

def get_download_link(torrent_id, file_id=None):
    """
    Request a direct download link for a completed torrent.
    """
    url = f"{TORBOX_BASE_URL}/torrents/requestdl"
    headers = get_headers()
    params = {
        "token": os.environ.get("TORBOX_API_KEY"), # TorBox requestdl often uses token in params or headers
        "torrent_id": torrent_id
    }
    if file_id:
        params["file_id"] = file_id
        
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            return result.get("data")
        else:
            print(f"Failed to request download link: {result.get('detail')}")
    except Exception as e:
        print(f"Error requesting download link: {e}")
    return None

if __name__ == "__main__":
    # Example usage:
    # Set your API key in the terminal first:
    # Windows cmd:  set TORBOX_API_KEY=your_key_here
    # PowerShell:   $env:TORBOX_API_KEY="your_key_here"
    
    # Try checking account status or listing active torrents
    try:
        headers = get_headers()
        response = requests.get(f"{TORBOX_BASE_URL}/user/me", headers=headers)
        if response.status_code == 200:
            user_data = response.json().get("data", {})
            print(f"Connected to TorBox. Account user: {user_data.get('email', 'Unknown')}")
            print(f"Premium Status: {user_data.get('premium', 'None')}")
        else:
            print(f"Failed to connect: {response.text}")
    except Exception as err:
        print(f"Initialization check failed: {err}")
