import codecs
with codecs.open('yt_archive_app.py', 'r', 'utf-8') as f:
    content = f.read()

# Insert button in create_tab3_widgets
btn_code = '''        self.meta_open_log_btn = ttk.Button(
            action_row,
            text="Open Log",
            command=self.open_metadata_log
        )
        self.meta_open_log_btn.pack(side=tk.LEFT, padx=(0, 10))
        '''

content = content.replace('        self.meta_status_label = ttk.Label(action_row', btn_code + '\n        self.meta_status_label = ttk.Label(action_row')

# Insert handler method
handler_code = '''    def open_metadata_log(self):
        """Opens the metadata edits log file."""
        import os
        log_path = "metadata_edits.txt"
        if not os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=== Metadata Edits Log ===\\n")
        try:
            os.startfile(log_path)
        except AttributeError:
            # Fallback for non-Windows
            import subprocess, sys
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, log_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log: {e}")

'''

idx = content.rfind('    def start_bulk_metadata_update(self):')
content = content[:idx] + handler_code + content[idx:]

with codecs.open('yt_archive_app.py', 'w', 'utf-8') as f:
    f.write(content)
