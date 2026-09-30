import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = '''                queued_items = [ident for ident, data in self.metadata_cache.items() if data.get("derivation_state") == "queued"]'''
repl1 = '''                queued_items = [ident for ident, data in self.metadata_cache.items() if data.get("derivation_state") in ["queued", "error"]]'''

target2 = '''                            if result.returncode == 0:'''
repl2 = '''                            if result.returncode == 0 or "success:" in (result.stderr + result.stdout).lower():'''

if target1 in content:
    content = content.replace(target1, repl1)
    print("Replaced target1")
else:
    print("Target1 not found")

# Only replace the SECOND occurrence of target2 (which is in the daemon queueing logic, not the bulk metadata one, or I can replace both since they both use ia tasks)
# Actually, target2 appears a few times. Let's just use string replace for the specific block.
target3 = '''                            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                            if result.returncode == 0:
                                self.metadata_cache[ident]["derivation_state"] = "queued"'''
repl3 = '''                            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                            if result.returncode == 0 or "success:" in (result.stderr + result.stdout).lower():
                                self.metadata_cache[ident]["derivation_state"] = "queued"'''

if target3 in content:
    content = content.replace(target3, repl3)
    print("Replaced target3")
else:
    print("Target3 not found")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

