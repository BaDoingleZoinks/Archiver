import sys

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            # Sleep for the interval, checking for stop event periodically
            interval_mins = self.auto_derive_interval_var.get()
            if interval_mins < 1: interval_mins = 1
            total_secs = interval_mins * 60
            for i in range(total_secs):
                if self.auto_derive_stop_event.is_set():
                    break
                secs_left = total_secs - i
                time_str = f"Next sweep in {secs_left//60}m {secs_left%60:02d}s"
                self.root.after(0, lambda t=time_str: self.engine_status_lbl.config(text=t))
                time.sleep(1)'''

replacement = '''            # Sleep for the interval, checking for stop event periodically
            interval_mins = self.auto_derive_interval_var.get()
            if interval_mins < 1: interval_mins = 1
            total_secs = interval_mins * 60
            self.root.after(0, lambda: self.engine_status_lbl.config(text=f"Waiting {interval_mins}m for next sweep..."))
            for i in range(total_secs):
                if self.auto_derive_stop_event.is_set():
                    break
                time.sleep(1)'''

if target.replace('\n', '\r\n') in content:
    content = content.replace(target.replace('\n', '\r\n'), replacement.replace('\n', '\r\n'))
    with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully (CRLF)')
elif target in content:
    content = content.replace(target, replacement)
    with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully (LF)')
else:
    print('Target not found in file')

