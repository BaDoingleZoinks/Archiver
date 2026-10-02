import re

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace start_archiving
start_archiving_new = """    def start_archiving(self):
        raw_url = self.url_combo.get().strip()
        if not raw_url:
            messagebox.showwarning("Input Error", "Please enter a YouTube Playlist URL.")
            return
            
        # If it's a preset "Title (URL)", extract the URL
        match = re.search(r'\((https?://[^\)]+)\)', raw_url)
        url = match.group(1) if match else raw_url
            
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(text="Pause", state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)

        # Handle Content Type suffix
        content_type = getattr(self, 'content_type_var', tk.StringVar(value="All / Default")).get()
        if content_type in ["Videos", "Live", "Shorts"]:
            # Check if it's a playlist or watch URL
            if not ("playlist?list=" in url or "watch?v=" in url or "youtu.be/" in url):
                # Remove existing tab if present
                url = re.sub(r'/(videos|shorts|streams|live)$', '', url, flags=re.IGNORECASE).rstrip('/')
                
                if content_type == "Videos":
                    url += "/videos"
                elif content_type == "Live":
                    url += "/streams"
                elif content_type == "Shorts":
                    url += "/shorts"

        # Lock ledger controls while pipeline is active
        self.ledger_combo.config(state="disabled")
        self.rename_ledger_btn.config(state=tk.DISABLED)
        self.delete_ledger_btn.config(state=tk.DISABLED)
        self.choose_ledger_btn.config(state=tk.DISABLED)
        self.new_ledger_btn.config(state=tk.DISABLED)

        self.stop_event.clear()
        self.pause_event.set()
        
        selected_res = self.res_var.get()
        base_dir = self.dir_var.get().strip()
        keep_files = self.keep_files_var.get()
        prevent_sleep = self.prevent_sleep_var.get()
        rapid_mode = self.rapid_mode_var.get()
        delay_minutes = self.rapid_delay_var.get() if rapid_mode else self.delay_var.get()
        reverse_playlist = self.reverse_playlist_var.get()

        # Pin the active ledger for this run
        active_ledger_path = self.get_ledger_path()
        active_ledger_name = self.ledger_name_var.get().strip() or "Main Archive"
        
        # Extract 3-letter language code if not "None"
        raw_lang = self.lang_var.get()
        lang_code = None
        if raw_lang != "None":
            match = re.search(r'\(([a-z]{3})\)', raw_lang)
            if match:
                lang_code = match.group(1)
        
        def _precheck_and_run():
            self.log(f"Checking URL for items: {url} ...")
            cmd = [self.get_executable("yt-dlp"), "--print", "%(id)s", "--playlist-items", "1", url]
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if not res.stdout.strip() and not self.stop_event.is_set():
                    # Empty or error
                    self.log(f"[WARNING] yt-dlp found no items in {content_type} tab. Aborting.")
                    self.root.after(0, lambda: messagebox.showwarning("Empty Tab", f"No videos found in the selected {content_type} tab.\\nArchive engine will not start."))
                    self.root.after(0, self.stop_archiving)
                    self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                    return
            except Exception as e:
                self.log(f"Pre-check error: {e}")
                
            if self.stop_event.is_set():
                return
                
            mode_str = "RAPID" if rapid_mode else "NORMAL"
            self.root.after(0, lambda: self.log(f"=== Archival Pipeline Started [{mode_str} MODE] (Max Resolution: {selected_res}) ==="))
            self.root.after(0, lambda: self.log(f"Active Ledger: '{active_ledger_name}' ({os.path.basename(active_ledger_path)})"))
            self.worker_thread = threading.Thread(
                target=self.run_pipeline, 
                args=(url, self.tags_combo.get().strip(), selected_res, base_dir, keep_files, prevent_sleep, delay_minutes, lang_code, reverse_playlist, active_ledger_path, active_ledger_name, rapid_mode, content_type), 
                daemon=True
            )
            self.worker_thread.start()

        # Run precheck thread
        threading.Thread(target=_precheck_and_run, daemon=True).start()"""

content = re.sub(r'    def start_archiving\(self\):.*?    def stop_archiving\(self\):', start_archiving_new + '\n\n    def stop_archiving(self):', content, flags=re.DOTALL)

# 2. Replace run_pipeline signature
sig_old = 'def run_pipeline(self, url, tags_str, max_resolution, base_dir, keep_files, prevent_sleep, delay_minutes, lang_code, reverse_playlist, active_ledger_path=None, active_ledger_name="Main Archive", rapid_mode=False):'
sig_new = 'def run_pipeline(self, url, tags_str, max_resolution, base_dir, keep_files, prevent_sleep, delay_minutes, lang_code, reverse_playlist, active_ledger_path=None, active_ledger_name="Main Archive", rapid_mode=False, content_type_label="All / Default"):'
content = content.replace(sig_old, sig_new)

# 3. Update the progress matching
progress_old = """                        progress_match = re.search(r"Downloading (?:video|item) (\d+) of (\d+)", line_clean, re.IGNORECASE)
                        if progress_match:
                            current, total = progress_match.groups()
                            if hasattr(self, 'progress_label'):
                                self.root.after(0, lambda c=current, t=total: self.progress_label.config(text=f"{c}/{t} for channel/playlist"))"""
                                
progress_new = """                        progress_match = re.search(r"Downloading (?:video|item) (\d+) of (\d+)", line_clean, re.IGNORECASE)
                        if progress_match:
                            current, total = progress_match.groups()
                            if hasattr(self, 'progress_label'):
                                label_text = f"{current}/{total} for channel/playlist"
                                if content_type_label and content_type_label != "All / Default":
                                    label_text += f" ({content_type_label})"
                                self.root.after(0, lambda txt=label_text: self.progress_label.config(text=txt))"""

content = content.replace(progress_old, progress_new)

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updates applied")
