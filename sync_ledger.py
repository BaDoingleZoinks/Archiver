import os
import re
import json
import subprocess
import unicodedata
from difflib import SequenceMatcher

def normalize(text):
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def main():
    channel_url = "https://www.youtube.com/@argenvia"
    folder_path = r"D:\ARCHIVE"
    archive_file = "archive.txt"
    
    print(f"Scanning folder: {folder_path}")
    if not os.path.exists(folder_path):
        print("Folder does not exist!")
        return

    print(f"Fetching video list from {channel_url} (this takes a few seconds)...")
    cmd = ["python", "-m", "yt_dlp", "--flat-playlist", "--dump-json", channel_url]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"Failed to run yt-dlp: {e}")
        return

    videos = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            info = json.loads(line)
            title = info.get("title")
            vid = info.get("id")
            if title and vid:
                videos[title] = vid
        except:
            pass

    print(f"Found {len(videos)} videos on the YouTube channel.")

    local_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(('.mp4', '.mkv', '.webm'))]
    print(f"Found {len(local_files)} local video files.")

    found_ids = set()

    for filename in local_files:
        name_without_ext = os.path.splitext(filename)[0]
        
        match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', name_without_ext)
        if match:
            found_ids.add(match.group(1))
            continue
            
        if name_without_ext in videos:
            found_ids.add(videos[name_without_ext])
            continue
            
        best_match = None
        best_ratio = 0
        clean_local = normalize(name_without_ext)
        
        for yt_title, yt_id in videos.items():
            clean_yt = normalize(yt_title)
            
            if clean_local == clean_yt or clean_local in clean_yt or clean_yt in clean_local:
                best_match = yt_id
                best_ratio = 1.0
                break
                
            ratio = similar(clean_local, clean_yt)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = yt_id
                
        if best_match and best_ratio > 0.65:
            found_ids.add(best_match)

    existing_ids = set()
    if os.path.exists(archive_file):
        with open(archive_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("youtube "):
                    existing_ids.add(line.strip().split(" ")[1])

    new_ids = found_ids - existing_ids
    if not new_ids:
        print("\nNo new videos to add to the ledger. You are fully synced!")
        return
        
    print(f"\nAdding {len(new_ids)} new videos to {archive_file}...")
    with open(archive_file, "a", encoding="utf-8") as f:
        for vid in new_ids:
            f.write(f"youtube {vid}\n")
            
    print(f"Done! Extracted {len(found_ids)} total IDs from {len(local_files)} local files.")

if __name__ == "__main__":
    main()
