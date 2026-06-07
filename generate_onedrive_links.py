import os
import sys
import json
import base64
import urllib.parse
import argparse
import time
import requests
import msal

# Default Client ID (Microsoft Graph CLI public client registration)
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
SCOPES = ["Files.ReadWrite", "User.Read"]

# Paths
ONEDRIVE_EBOOKS_DIR = r"C:\Users\admin-beats\OneDrive\03_Personal_Archive\eBooks"
REPO_DIR = os.path.join(ONEDRIVE_EBOOKS_DIR, "ebooks")
BOOKS_JSON_PATH = os.path.join(REPO_DIR, "books.json")
TOKEN_CACHE_PATH = os.path.join(REPO_DIR, ".onedrive_token_cache.json")

def to_direct_download(sharing_url):
    """
    Converts a standard OneDrive sharing URL into a direct download URL.
    This works by base64 encoding the sharing URL and formatting it as a share link endpoint.
    """
    try:
        b64_val = base64.b64encode(sharing_url.encode('utf-8')).decode('utf-8')
        # Make the base64 string url-safe and remove trailing equals signs
        clean_b64 = b64_val.replace('/', '_').replace('+', '-').rstrip('=')
        return f"https://api.onedrive.com/v1.0/shares/u!{clean_b64}/root/content"
    except Exception as e:
        print(f"Error converting sharing URL: {e}")
        return sharing_url

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

def get_access_token(client_id):
    """
    Acquire access token via MSAL. Tries silently first (using token cache),
    falling back to Device Code Flow if necessary.
    """
    # Initialize MSAL serializable token cache
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        try:
            with open(TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
                cache.deserialize(f.read())
        except Exception as e:
            print(f"Warning: Could not read token cache: {e}")

    app = msal.PublicClientApplication(
        client_id,
        authority="https://login.microsoftonline.com/common",
        token_cache=cache
    )

    accounts = app.get_accounts()
    result = None

    if accounts:
        print(f"Found cached account: {accounts[0]['username']}. Attempting silent sign-in...")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        print("Silent sign-in failed. Initiating Device Code Flow...")
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise ValueError(f"Failed to create device flow: {json.dumps(flow, indent=2)}")

        # Print user instructions
        print("\n" + "="*80)
        print(flow["message"])
        print("="*80 + "\n")
        sys.stdout.flush()

        result = app.acquire_token_by_device_flow(flow)

    if result and "access_token" in result:
        # Save token cache state if changed
        if cache.has_state_changed:
            try:
                with open(TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
                    f.write(cache.serialize())
                print("Token cache updated successfully.")
            except Exception as e:
                print(f"Warning: Could not write token cache: {e}")
        return result["access_token"]
    else:
        error_msg = result.get("error_description") or result.get("error") or "Unknown error"
        raise Exception(f"Authentication failed: {error_msg}")

def generate_links_for_db(access_token, onedrive_root_folder, force_update=False):
    db = load_books_db()
    if not db:
        print("No books found in database to process.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Count books that need share links
    total_books = len(db)
    to_process = []
    
    for key, entry in db.items():
        if not entry.get("onedrive_path"):
            continue
        
        has_links = "onedrive_share_link" in entry and "onedrive_download_link" in entry
        if force_update or not has_links:
            to_process.append((key, entry))

    print(f"Total books in DB: {total_books}")
    print(f"Books needing OneDrive links: {len(to_process)}")

    if not to_process:
        print("All books already have OneDrive links generated. Use --force to regenerate.")
        return

    success_count = 0
    fail_count = 0

    # Ensure root folder has correct formatting (no leading/trailing slashes for path construction)
    root_folder = onedrive_root_folder.strip("/")

    for index, (key, entry) in enumerate(to_process, 1):
        rel_path = entry["onedrive_path"]
        print(f"[{index}/{len(to_process)}] Processing: {entry['title']}")
        
        # Build full OneDrive path relative to drive root
        # onedrive_path in DB is like 'Epubs/title.epub'
        # root_folder is '03_Personal_Archive/eBooks'
        full_path_in_drive = f"/{root_folder}/{rel_path}"
        escaped_path = urllib.parse.quote(full_path_in_drive)
        
        # Graph API URL for createLink
        # POST /me/drive/root:/{item-path}:/createLink
        create_link_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{escaped_path}:/createLink"
        
        payload = {
            "type": "view",
            "scope": "anonymous"
        }

        try:
            # We do a POST request to create the sharing link
            response = requests.post(create_link_url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                res_data = response.json()
                sharing_url = res_data.get("link", {}).get("webUrl")
                if sharing_url:
                    direct_url = to_direct_download(sharing_url)
                    
                    entry["onedrive_share_link"] = sharing_url
                    entry["onedrive_download_link"] = direct_url
                    
                    success_count += 1
                    print(f"  Success! Share Link: {sharing_url[:50]}...")
                else:
                    fail_count += 1
                    print(f"  Error: Response succeeded but did not contain webUrl.")
            elif response.status_code == 404:
                fail_count += 1
                print(f"  Error 404: File not found on OneDrive at '{full_path_in_drive}'. Please ensure it is synced.")
            else:
                fail_count += 1
                print(f"  Error {response.status_code}: {response.text}")
                
            # Periodically save progress (every 10 books) to prevent data loss on interrupts
            if success_count % 10 == 0 and success_count > 0:
                save_books_db(db)
                print("  [Progress Saved to books.json]")
                
            # Sleep slightly to respect rate limits
            time.sleep(0.5)

        except Exception as e:
            fail_count += 1
            print(f"  Exception when processing '{entry['title']}': {e}")
            time.sleep(1.0)

    # Save final results
    save_books_db(db)
    print("\n" + "="*50)
    print("Process Complete!")
    print(f"Successfully generated sharing links for {success_count} books.")
    print(f"Failed to generate links for {fail_count} books.")
    print("="*50)

def main():
    # Force stdout/stderr to UTF-8
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

    parser = argparse.ArgumentParser(description="Generate public read-only OneDrive sharing links for eBooks.")
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID, help="Microsoft Azure AD App Client ID.")
    parser.add_argument("--onedrive-root", default="03_Personal_Archive/eBooks", help="Relative path of eBooks folder in OneDrive (e.g. 03_Personal_Archive/eBooks).")
    parser.add_argument("--force", action="store_true", help="Force regeneration of sharing links for all files.")
    args = parser.parse_args()

    print("Authenticating with Microsoft OneDrive...")
    try:
        access_token = get_access_token(args.client_id)
        print("Successfully authenticated!")
    except Exception as e:
        print(f"Authentication Error: {e}")
        sys.exit(1)

    print("\nStarting link generation...")
    generate_links_for_db(access_token, args.onedrive_root, force_update=args.force)

if __name__ == "__main__":
    main()
