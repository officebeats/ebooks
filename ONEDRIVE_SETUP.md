# OneDrive Share Links Generator Setup

This project includes a standalone script, `generate_onedrive_links.py`, which integrates with Microsoft Graph API to automatically generate public, read-only download links for all EPUB files stored in your OneDrive books library.

The generated links are saved directly to `books.json` and are rendered as clickable **Download** buttons on the web portal (`index.html`) and as **Cloud Download** links in `README.md`.

---

## 1. Microsoft Azure App Registration Setup

To interact with the Microsoft Graph API, the script needs an Application (Client) ID registered in your Microsoft account. Creating this registration is completely free.

### Step-by-Step Instructions:

1. **Open Azure Portal / Microsoft Entra**:
   - Go to [Microsoft Entra admin center](https://entra.microsoft.com/) or [Azure Portal](https://portal.azure.com/).
   - Log in using your Microsoft account (personal, work, or school).

2. **Register a New Application**:
   - Navigate to **Identity** (in Entra) -> **Applications** -> **App registrations**, or search for "App registrations" in Azure.
   - Click **New registration**.
   - **Name**: Enter a friendly name, e.g. `eBooks OneDrive Link Generator`.
   - **Supported account types**: Select **"Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)"**.
     > [!IMPORTANT]
     > Selecting this multitenant + personal accounts option is required to allow personal OneDrive accounts to sign in.
   - **Redirect URI**: Leave this blank. Device Code flow does not require redirect URIs.
   - Click **Register**.

3. **Enable Public Client Flows**:
   - On the left sidebar under the App Registration page, click **Authentication**.
   - Scroll down to the **Advanced settings** section.
   - Find **Allow public client flows** (often labeled as *Enable the following mobile and desktop flows*).
   - Select **Yes**.
   - Click **Save** at the top.

4. **Add API Permissions**:
   - Click **API permissions** in the left sidebar.
   - Click **Add a permission** -> Select **Microsoft Graph**.
   - Choose **Delegated permissions**.
   - Search for and check:
     - `Files.ReadWrite` (Allows the script to request sharing link creation for files in your drive).
     - `User.Read` (Standard login permission).
   - Click **Add permissions** at the bottom.

5. **Copy the Client ID**:
   - Navigate to the **Overview** section in the left sidebar.
   - Copy the value of the **Application (client) ID**. You will pass this to the script.

---

## 2. Running the Link Generator

The script uses MSAL's **Device Code Flow** for user authentication. This is an interactive flow that does not expose your password.

### First Run:
Run the script using Python. You can specify your custom client ID using the `--client-id` parameter:

```bash
python generate_onedrive_links.py --client-id "YOUR_AZURE_CLIENT_ID"
```

When you run it for the first time:
1. The script will print instructions similar to:
   ```text
   ================================================================================
   To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code G7XJ9WK6M to authenticate.
   ================================================================================
   ```
2. Open the URL in a browser on any device.
3. Enter the code shown in your terminal.
4. Log into the Microsoft account associated with your OneDrive.
5. Approve the permission request.
6. The terminal will automatically detect the login and begin generating links.

### Subsequent Runs:
A token cache file named `.onedrive_token_cache.json` is saved in the repository folder. This file contains encrypted access/refresh tokens.
On subsequent runs, the script will silently authenticate using the cache without prompting you to log in again:

```bash
python generate_onedrive_links.py
```

---

## 3. Options and Parameters

You can customize the script's behavior using command-line arguments:

- `--client-id`: The Azure App Client ID. Defaults to a default public Azure Graph client ID if omitted.
- `--onedrive-root`: The folder path in your OneDrive where your books are stored, relative to the root. Defaults to `03_Personal_Archive/eBooks`.
- `--force`: Force the script to regenerate sharing links for all books. By default, the script runs incrementally and only generates links for books that do not have them.

**Example with custom OneDrive folder:**
```bash
python generate_onedrive_links.py --onedrive-root "MyLibrary/Books" --force
```

---

## 4. Security & Safety

> [!WARNING]
> The `.onedrive_token_cache.json` file contains active login tokens that grant access to your OneDrive.
> - **DO NOT** commit this file to public GitHub repositories.
> - This repository's `.gitignore` has been updated to automatically ignore `.onedrive_token_cache.json` and `.env` files.
