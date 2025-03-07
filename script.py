import os
import requests
import time
import telegram
import asyncio

# Configuration
GITHUB_TOKEN = "tk"  # Optional for higher API limits
TELEGRAM_BOT_TOKEN = "tk"
TELEGRAM_CHANNEL_ID = "@ch"
REPO_LIST_FILE = "repos.txt"
TRACK_FILE = "tracked_versions.txt"
DOWNLOAD_DIR = "./downloads"

# Initialize Telegram Bot
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def get_repo_name(repo_url):
    return "/".join(repo_url.rstrip("/").split("/")[-2:])

def get_latest_release(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/releases/latest"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else None

def get_latest_commit(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/commits/main"
    response = requests.get(url, headers=HEADERS)
    return response.json().get("sha") if response.status_code == 200 else None

def download_file(url, filename):
    response = requests.get(url, headers=HEADERS, stream=True)
    if response.status_code == 200:
        with open(filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return filename
    return None


async def upload_to_telegram_async(file_path):
    """Handles async file upload properly."""
    try:
        with open(file_path, "rb") as f:
            message = await bot.send_document(
                chat_id=TELEGRAM_CHANNEL_ID, 
                document=f, 
                caption=os.path.basename(file_path),
                timeout=60  # Increase timeout to avoid failure on large files
            )

        # Ensure successful upload before deleting the file
        if message and message.document:
            print(f"✅ Successfully uploaded {file_path}")
            os.remove(file_path)  # Delete only after confirmation
        else:
            print(f"⚠ Upload failed for {file_path}, keeping file.")
    except Exception as e:
        print(f"❌ Failed to upload {file_path}: {e}")

def upload_to_telegram(file_path):
    """Runs the async function properly without event loop issues."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(upload_to_telegram_async(file_path))



def track_version(repo_name, release_version, commit_sha):
    tracked_versions = load_tracked_versions()
    tracked_versions[repo_name] = f"{release_version} {commit_sha}"
    with open(TRACK_FILE, "w") as f:
        for repo, ver in tracked_versions.items():
            f.write(f"{repo} {ver}\n")

def load_tracked_versions():
    if not os.path.exists(TRACK_FILE):
        return {}
    with open(TRACK_FILE, "r") as f:
        return dict(line.strip().split(" ", 1) for line in f if " " in line)

def process_repository(repo_url):
    repo_name = get_repo_name(repo_url)
    tracked_versions = load_tracked_versions()

    latest_commit = get_latest_commit(repo_name)
    if not latest_commit:
        print(f"⚠ Failed to fetch commit data for {repo_name}")
        return

    release = get_latest_release(repo_name)
    latest_release_version = release["tag_name"] if release else "none"

    last_version, last_commit = tracked_versions.get(repo_name, "none none").split()

    # Download and upload updated source code
    if last_commit != latest_commit:
        print(f"📥 New commit detected for {repo_name}, downloading source code...")
        zip_url = f"https://github.com/{repo_name}/archive/refs/heads/main.zip"
        zip_filename = os.path.join(DOWNLOAD_DIR, f"{repo_name.replace('/', '_')}_source.zip")
        
        file_path = download_file(zip_url, zip_filename)
        if file_path:
            print(f"📤 Uploading {zip_filename} to Telegram...")
            upload_to_telegram(file_path)

    # Download and upload updated release binaries
    if latest_release_version != "none" and last_version != latest_release_version:
        print(f"📥 New release detected for {repo_name}: {latest_release_version}")
        for asset in release.get("assets", []):
            url = asset["browser_download_url"]
            filename = os.path.join(DOWNLOAD_DIR, asset["name"])
            print(f"📥 Downloading {filename}...")

            file_path = download_file(url, filename)
            if file_path:
                print(f"📤 Uploading {filename} to Telegram...")
                upload_to_telegram(file_path)

    track_version(repo_name, latest_release_version, latest_commit)

def main():
    if not os.path.exists(REPO_LIST_FILE):
        print(f"Error: {REPO_LIST_FILE} not found!")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with open(REPO_LIST_FILE, "r") as f:
        repos = [line.strip() for line in f if line.strip()]

    for repo_url in repos:
        print(f"\n🔍 Checking {repo_url}...")
        process_repository(repo_url)

if __name__ == "__main__":
    while True:
        main()
        print("\nFinished\n")
 
