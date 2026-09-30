import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            except Exception as e:
                pass'''

repl = '''            except Exception as e:
                import time
                with open("metadata_edits.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] FATAL DAEMON CRASH | Exception: {str(e)}\\n\\n")'''

if target in content:
    content = content.replace(target, repl)
    print("Replaced target")
else:
    print("Target not found")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

