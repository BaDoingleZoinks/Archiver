# The Archiver

A Python desktop application for backing up YouTube playlists and videos directly to the Internet Archive, along with Wayback Machine snapshots and metadata editing tools.

## Features
- **YouTube Video Archiver**: Batch download and upload YouTube playlists to Internet Archive with automatic metadata generation.
- **Wayback Page Archiver**: Capture web pages, screenshots, and outlinks to the Wayback Machine.
- **Metadata Editor**: View, edit, tag, and synchronize uploaded item metadata across your Archive.org account.
- **Custom & Shared Ledgers**: Choose existing ledgers or create new ones (`Choose File...` / `New Ledger...`). Put ledger files in shared cloud or network folders for team/device collaboration without conflict.
- **Internet Archive Account Setup**: Automatic first-run setup to configure your personal `ia.ini` credentials (via S3 API keys or Archive.org login). Credentials remain strictly in your private local profile and are never tracked in Git.
- **In-App Version & Update Manager**: Seamlessly check for updates, upgrade to latest builds, or roll back to previous versions directly within the application.

## Setup & Running

### Requirements
- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Launching
- Double-click `start_app.bat` to launch the app.
- On any synced machine, double-click `update_and_run.bat` to pull the latest changes from GitHub before launching.
- On first launch, enter your Internet Archive S3 credentials when prompted to enable uploading.
