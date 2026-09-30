import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            # Sleep for the interval, checking for stop event periodically
            interval_mins = self.auto_derive_interval_var.get()
            if interval_mins < 1: interval_mins = 1
            total_secs = interval_mins * 60
            self.root.after(0, lambda: self.engine_status_lbl.config(text=f"Waiting {interval_mins}m for next sweep..."))'''

repl = '''            # Sleep for the interval, checking for stop event periodically
            try:
                interval_mins = self.auto_derive_interval_var.get()
            except Exception:
                interval_mins = 5
            if interval_mins < 1: interval_mins = 1
            total_secs = interval_mins * 60
            self.root.after(0, lambda: self.engine_status_lbl.config(text=f"Waiting {interval_mins}m for next sweep..."))'''

if target in content:
    content = content.replace(target, repl)
    print("Replaced target")
else:
    print("Target not found")

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

