import os
import re
import json
import subprocess

def get_words(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', ' ', text)
    return set(text.split())

def main():
    channel_url = "https://www.youtube.com/@argenvia"
    folder_path = r"D:\ARCHIVE"
    archive_file = "archive.txt"
    
    cmd = ["python", "-m", "yt_dlp", "--flat-playlist", "--dump-json", channel_url]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

    videos = {}
    for line in result.stdout.splitlines():
        if not line.strip(): continue
        try:
            info = json.loads(line)
            title = info.get("title")
            vid = info.get("id")
            if title and vid:
                videos[title] = vid
        except: pass

    local_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(('.mp4', '.mkv', '.webm'))]
    
    existing_ids = set()
    if os.path.exists(archive_file):
        with open(archive_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("youtube "):
                    existing_ids.add(line.strip().split(" ")[1])

    found_ids = set()
    for filename in local_files:
        name_without_ext = os.path.splitext(filename)[0]
        match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', name_without_ext)
        if match:
            found_ids.add(match.group(1))
            continue
            
        local_words = get_words(name_without_ext)
        if not local_words: continue
        
        best_match = None
        best_score = 0
        
        for yt_title, yt_id in videos.items():
            yt_words = get_words(yt_title)
            if not yt_words: continue
            
            overlap = len(local_words.intersection(yt_words))
            score = overlap / max(len(local_words), len(yt_words))
            
            if score > best_score:
                best_score = score
                best_match = yt_id
                
        if best_match and best_score > 0.3: # 30% word overlap
            found_ids.add(best_match)

    new_ids = found_ids - existing_ids
    print(f"Word-overlap matching found {len(new_ids)} new IDs.")
    
    with open(archive_file, "a", encoding="utf-8") as f:
        for vid in new_ids:
            f.write(f"youtube {vid}\n")

if __name__ == "__main__":
    main()
