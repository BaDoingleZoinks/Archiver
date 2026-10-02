import re

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(r"\((https?://[^\)]+)\)", r"\(([^)]+)\)\s*$")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced!")
