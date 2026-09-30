import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target4 = '''                result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    success_count += 1'''
repl4 = '''                result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0 or "success:" in (result.stderr + result.stdout).lower():
                    success_count += 1'''

if target4 in content:
    content = content.replace(target4, repl4)
    print("Replaced target4")
else:
    print("Target4 not found")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

