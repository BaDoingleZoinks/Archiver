import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    def _auto_derive_daemon_loop(self):
        """Background loop that periodically queues and verifies derivations."""
        while not self.auto_derive_stop_event.is_set():'''

repl = '''    def _auto_derive_daemon_loop(self):
        """Background loop that periodically queues and verifies derivations."""
        import time
        while not self.auto_derive_stop_event.is_set():'''

if target in content:
    content = content.replace(target, repl)
    print("Replaced target")
else:
    print("Target not found")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

