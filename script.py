import os
import json
import hashlib
import requests
from pathlib import Path
from telegram import Bot

# Telegram Bot Token & Chat ID (Replace with actual values)
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

# GitHub API Token (Replace with actual token)
GITHUB_TOKEN = "YOUR_GITHUB_API_TOKEN"
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

# File containing the list of repository URLs
REPOS_FILE = "repos.txt"

# Base directory to store repositories
BASE_DIR = Path("./github_repos")
BASE_DIR.mkdir(exist_ok=True)

# File to track last seen versions
VERSIONS_FILE = BASE_DIR / "versions.json"

# Load previous versions
if VERSIONS_FILE.exists():
    with open(VERSIONS_FILE, "r") as f:
        version_tracking = json.load(f)
else:
    version_tracking = {}

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def get_repo_name(repo_url):
    """Extract repository name from URL."""
    return repo_url.rstrip("/").split("/")[-2] + "_" + repo_url.rstrip("/").split("/")[-1]

def get_latest_commit(repo):
    """Get the latest commit hash of the default branch."""
    url = f"https://api.github.com/repos/{repo}/commits/main"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()["sha"]
    return None

def get_latest_release(repo):
    """Get the latest release version and download URLs."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data.get("tag_name"), [asset["browser_download_url"] for asset in data.get("assets", [])]
    return None, []

def download_file(url, dest_path):
    """Download a file synchronously and save it."""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

def calculate_checksum(file_path):
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def send_telegram_message(text):
    """Send a message to Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        print(f"⚠️ Failed to send message to Telegram: {e}")

def track_repository(repo_url):
    """Track a GitHub repository, download latest code/releases, and store versions."""
    repo_name = get_repo_name(repo_url)
    repo_path = BASE_DIR / repo_name
    repo_path.mkdir(exist_ok=True)

    owner_repo = "/".join(repo_url.rstrip("/").split("/")[-2:])

    # Get latest commit hash
    latest_commit = get_latest_commit(owner_repo)

    # Get latest release
    latest_version, release_urls = get_latest_release(owner_repo)

    updated = False
    message = f"🚀 **Repository Updated: {repo_name}**\n"

    # Store latest source code (if updated)
    if latest_commit and version_tracking.get(repo_name, {}).get("commit") != latest_commit:
        zip_url = f"https://github.com/{owner_repo}/archive/refs/heads/main.zip"
        zip_path = repo_path / "source.zip"
        print(f"📥 Downloading latest source for {repo_name}...")
        download_file(zip_url, zip_path)
        version_tracking.setdefault(repo_name, {})["commit"] = latest_commit
        message += f"🔹 **New Commit:** {latest_commit[:7]}\n"
        updated = True

    # Store latest release files (if updated)
    if latest_version and version_tracking.get(repo_name, {}).get("release") != latest_version:
        for url in release_urls:
            file_name = url.split("/")[-1]
            file_path = repo_path / file_name
            print(f"📥 Downloading release: {file_name}...")
            download_file(url, file_path)
        version_tracking[repo_name]["release"] = latest_version
        message += f"📦 **New Release:** {latest_version}\n"
        updated = True

    # Generate checksum file
    if updated:
        checksums_path = repo_path / "checksums.txt"
        with open(checksums_path, "w") as f:
            for file in repo_path.iterdir():
                if file.is_file():
                    checksum = calculate_checksum(file)
                    f.write(f"{file.name}: {checksum}\n")
        print(f"✅ Checksums updated for {repo_name}")

        # Send Telegram notification
        send_telegram_message(message)

    # Save version tracking
    with open(VERSIONS_FILE, "w") as f:
        json.dump(version_tracking, f, indent=4)

def load_repositories():
    """Load repository URLs from repos.txt file."""
    if not os.path.exists(REPOS_FILE):
        print(f"⚠️ {REPOS_FILE} not found. Creating an empty one.")
        with open(REPOS_FILE, "w") as f:
            f.write("")
        return []

    with open(REPOS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    repositories = load_repositories()
    for repo in repositories:
        track_repository(repo)

if __name__ == "__main__":
    main()
