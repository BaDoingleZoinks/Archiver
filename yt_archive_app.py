import os
import glob
import json
import re
import time
import threading
import subprocess
import shutil
import sys
import ctypes
import ast
import tkinter as tk
import imageio_ffmpeg
import sv_ttk
import requests
import queue
import internetarchive as ia
import unicodedata
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog

APP_VERSION = "1.5.1"

def normalize_title(text):
    """Normalizes titles by stripping accents, symbols, and whitespace for duplicate matching."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

class ArchiveApp:
    def __init__(self, root):
        self.root = root
        self.github_repo = "BaDoingleZoinks/Archiver"
        self.ia_uploader_email = ""
        self.ledger_name_var = tk.StringVar(value="Main Archive")
        self.ledger_file_var = tk.StringVar(value="archive.txt")
        self.ledger_presets = {"Main Archive": "archive.txt"}
        self.root.title(f"The Archiver - v{APP_VERSION}")
        self.root.geometry("920x700")
        self.root.minsize(850, 650)
        
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Not paused initially
        self.worker_thread = None
        self.current_process = None
        
        # Metadata Editor state
        self.meta_stop_event = threading.Event()
        self.meta_worker_thread = None
        self.metadata_cache = {}
        self.meta_selected_ids = set()
        self.meta_all_items = []
        self.meta_filtered_items = []
        self.meta_sort_col = "date"
        self.meta_sort_reverse = True
        self.load_metadata_cache()
        
        # Cloud Cooldown Synchronization state
        self._cached_remote_upload_time = 0
        self._last_remote_check_time = 0
        self._is_checking_remote_upload = False
        self._last_local_log_time = 0
        
        self.url_presets = []
        self.tags_presets = []
        
        self.create_widgets()
        self.load_settings()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self.check_updates_background, daemon=True).start()
        self.root.after(1000, self.check_ia_credentials_startup)
        self.root.after(2000, self._periodic_remote_sync)

    def load_settings(self):
        self.url_presets = []
        self.tags_presets = []
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    s = json.load(f)
                self.github_repo = s.get("github_repo", getattr(self, "github_repo", "BaDoingleZoinks/Archiver"))
                self.ledger_presets = s.get("ledger_presets", {"Main Archive": "archive.txt"})
                if not isinstance(self.ledger_presets, dict):
                    self.ledger_presets = {"Main Archive": "archive.txt"}
                if "Main Archive" not in self.ledger_presets and os.path.exists("archive.txt"):
                    self.ledger_presets["Main Archive"] = "archive.txt"
                default_ledger_name = list(self.ledger_presets.keys())[0] if self.ledger_presets else "Main Archive"
                curr_ledger_name = s.get("ledger_name", default_ledger_name)
                if curr_ledger_name not in self.ledger_presets:
                    curr_ledger_name = default_ledger_name
                self.ledger_name_var.set(curr_ledger_name)
                curr_path = self.ledger_presets.get(curr_ledger_name, s.get("ledger_file", "archive.txt"))
                self.ledger_file_var.set(curr_path)
                if hasattr(self, 'ledger_combo'):
                    self.ledger_combo['values'] = list(self.ledger_presets.keys())
                    self.ledger_combo.set(curr_ledger_name)
                if hasattr(self, 'ledger_path_lbl'):
                    self.ledger_path_lbl.config(text=f"File: {curr_path}")
                self.ia_uploader_email = s.get("ia_uploader_email", "")
                self.url_presets = s.get("url_presets", [])
                self.tags_presets = s.get("tags_presets", [])
                self.url_combo['values'] = self.url_presets
                self.tags_combo['values'] = self.tags_presets
                if hasattr(self, 'meta_tags_combo'):
                    self.meta_tags_combo['values'] = self.tags_presets
                self.url_combo.set(s.get("url", ""))
                self.tags_combo.set(s.get("tags", ""))
                self.res_var.set(s.get("max_resolution", "1080p (Recommended)"))
                self.lang_var.set(s.get("language", "None"))
                self.cookies_var.set(s.get("cookies_browser", ""))
                self.dir_var.set(s.get("download_dir", os.path.abspath(".")))
                self.keep_files_var.set(s.get("keep_files", False))
                self.prevent_sleep_var.set(s.get("prevent_sleep", True))
                self.delay_var.set(s.get("delay", 20))
                self.dark_mode_var.set(s.get("dark_mode", False))
                self.reverse_playlist_var.set(s.get("reverse_playlist", False))
                if hasattr(self, 'spn_screenshot_var'):
                    self.spn_screenshot_var.set(s.get("spn_screenshot", True))
                    self.spn_outlinks_var.set(s.get("spn_outlinks", False))
                    self.spn_personal_var.set(s.get("spn_personal", True))
                    self.spn_delay_var.set(s.get("spn_delay", 10))
            except Exception:
                pass
        self.toggle_dark_mode()

    def save_settings(self):
        s = {
            "github_repo": getattr(self, "github_repo", "BaDoingleZoinks/Archiver"),
            "ia_uploader_email": getattr(self, "ia_uploader_email", ""),
            "ledger_name": self.ledger_name_var.get(),
            "ledger_file": self.ledger_file_var.get(),
            "ledger_presets": getattr(self, "ledger_presets", {"Main Archive": "archive.txt"}),
            "url": self.url_combo.get(),
            "url_presets": self.url_presets,
            "tags": self.tags_combo.get(),
            "tags_presets": self.tags_presets,
            "max_resolution": self.res_var.get(),
            "language": self.lang_var.get(),
            "cookies_browser": self.cookies_var.get(),
            "download_dir": self.dir_var.get(),
            "keep_files": self.keep_files_var.get(),
            "prevent_sleep": self.prevent_sleep_var.get(),
            "delay": self.delay_var.get(),
            "dark_mode": self.dark_mode_var.get(),
            "reverse_playlist": self.reverse_playlist_var.get()
        }
        if hasattr(self, 'spn_screenshot_var'):
            s["spn_screenshot"] = self.spn_screenshot_var.get()
            s["spn_outlinks"] = self.spn_outlinks_var.get()
            s["spn_personal"] = self.spn_personal_var.get()
            s["spn_delay"] = self.spn_delay_var.get()
            
        try:
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(s, f, indent=4)
        except Exception:
            pass

    def save_tags_preset(self):
        val = self.tags_combo.get().strip()
        if val and val not in self.tags_presets:
            self.tags_presets.append(val)
            self.tags_combo['values'] = self.tags_presets
            if hasattr(self, 'meta_tags_combo'):
                self.meta_tags_combo['values'] = self.tags_presets
            messagebox.showinfo("Preset Saved", "Tags preset saved successfully!")
            self.save_settings()

    def save_url_preset(self):
        val = self.url_combo.get().strip()
        if not val:
            return
            
        def fetch_title():
            self.save_url_btn.config(state=tk.DISABLED, text="Fetching...")
            try:
                cmd = [self.get_executable("yt-dlp"), "--print", "%(playlist_title)s", "--playlist-items", "1", val]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                title = result.stdout.strip()
                if not title or title == "NA":
                    title = "Unknown Playlist"
                
                preset_str = f"{title} ({val})"
                if preset_str not in self.url_presets:
                    self.url_presets.append(preset_str)
                    self.root.after(0, lambda: self.url_combo.config(values=self.url_presets))
                    self.root.after(0, lambda: self.url_combo.set(preset_str))
                    self.save_settings()
                    self.root.after(0, lambda: messagebox.showinfo("Preset Saved", f"Saved: {title}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not fetch title: {e}"))
            finally:
                self.root.after(0, lambda: self.save_url_btn.config(state=tk.NORMAL, text="Save Preset"))

        threading.Thread(target=fetch_title, daemon=True).start()

    def delete_url_preset(self):
        val = self.url_combo.get().strip()
        if val in self.url_presets:
            self.url_presets.remove(val)
            self.url_combo.config(values=self.url_presets)
            self.url_combo.set("")
            self.save_settings()

    def rename_url_preset(self):
        val = self.url_combo.get().strip()
        if val in self.url_presets:
            match = re.search(r'\((https?://[^\)]+)\)', val)
            if not match:
                messagebox.showwarning("Warning", "Cannot rename a preset without a URL in parentheses.")
                return
            url = match.group(1)
            
            new_title = simpledialog.askstring("Rename Preset", "Enter new name for this playlist:", initialvalue=val.split(" (")[0])
            if new_title and new_title.strip():
                new_preset = f"{new_title.strip()} ({url})"
                idx = self.url_presets.index(val)
                self.url_presets[idx] = new_preset
                self.url_combo.config(values=self.url_presets)
                self.url_combo.set(new_preset)
                self.save_settings()

    def delete_tags_preset(self):
        val = self.tags_combo.get().strip()
        if val in self.tags_presets:
            if messagebox.askyesno("Delete Preset", f"Are you sure you want to delete this preset?\n\n'{val}'"):
                self.tags_presets.remove(val)
                self.tags_combo.config(values=self.tags_presets)
                self.tags_combo.set("")
                if hasattr(self, 'meta_tags_combo'):
                    self.meta_tags_combo.config(values=self.tags_presets)
                self.save_settings()
                messagebox.showinfo("Preset Deleted", "Tags preset deleted successfully!")

    def toggle_dark_mode(self):
        if self.dark_mode_var.get():
            sv_ttk.set_theme("dark")
            if hasattr(self, 'log_area'):
                self.log_area.config(bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff")
                self.history_area.config(bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff")
        else:
            sv_ttk.set_theme("light")
            if hasattr(self, 'log_area'):
                self.log_area.config(bg="#ffffff", fg="#000000", insertbackground="#000000")
                self.history_area.config(bg="#ffffff", fg="#000000", insertbackground="#000000")

    def on_close(self):
        self.save_settings()
        self.stop_event.set()
        self.pause_event.set()
        if hasattr(self, 'meta_stop_event'):
            self.meta_stop_event.set()
        if hasattr(self, 'spn_queue'):
            self.spn_queue.put(None)
        self.root.destroy()
        
    def create_widgets(self):
        # Header Toolbar with App Version, Account Setup, and Updates Button
        header_bar = ttk.Frame(self.root)
        header_bar.pack(fill=tk.X, padx=10, pady=(6, 2))
        
        title_lbl = ttk.Label(header_bar, text=f"The Archiver (v{APP_VERSION})", font=("Segoe UI", 10, "bold"))
        title_lbl.pack(side=tk.LEFT)
        
        self.updater_btn = ttk.Button(header_bar, text="🔄 Check for Updates / Sync", command=self.open_updater_dialog)
        self.updater_btn.pack(side=tk.RIGHT)

        self.ia_account_btn = ttk.Button(header_bar, text="🔑 IA Account Setup", command=self.open_ia_credentials_dialog)
        self.ia_account_btn.pack(side=tk.RIGHT, padx=(0, 6))

        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tab1_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.tab1_frame, text="YouTube Video Archiver")
        
        self.tab2_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.tab2_frame, text="Wayback Page Archiver")
        
        self.tab3_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.tab3_frame, text="Metadata Editor")
        
        self.create_tab1_widgets()
        self.create_tab2_widgets()
        self.create_tab3_widgets()

    def create_tab1_widgets(self):
        # Frame for inputs
        input_frame = ttk.LabelFrame(self.tab1_frame, text="Configuration", padding=(10, 10))
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # URL
        ttk.Label(input_frame, text="YouTube Playlist URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        url_frame = ttk.Frame(input_frame)
        url_frame.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.url_combo = ttk.Combobox(url_frame)
        self.url_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.save_url_btn = ttk.Button(url_frame, text="Save Preset", command=self.save_url_preset)
        self.save_url_btn.pack(side=tk.LEFT, padx=(5, 0))
        self.rename_url_btn = ttk.Button(url_frame, text="Rename", width=8, command=self.rename_url_preset)
        self.rename_url_btn.pack(side=tk.LEFT, padx=(5, 0))
        self.del_url_btn = ttk.Button(url_frame, text="Delete", width=8, command=self.delete_url_preset)
        self.del_url_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Tags
        ttk.Label(input_frame, text="Custom Tags (comma-separated):").grid(row=1, column=0, sticky=tk.W, pady=5)
        tags_frame = ttk.Frame(input_frame)
        tags_frame.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.tags_combo = ttk.Combobox(tags_frame)
        self.tags_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.save_tags_btn = ttk.Button(tags_frame, text="Save Preset", command=self.save_tags_preset)
        self.save_tags_btn.pack(side=tk.LEFT, padx=(5, 0))
        self.del_tags_btn = ttk.Button(tags_frame, text="Delete", width=8, command=self.delete_tags_preset)
        self.del_tags_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Max Resolution
        ttk.Label(input_frame, text="Max Resolution:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.res_var = tk.StringVar(value="1080p (Recommended)")
        self.res_combo = ttk.Combobox(
            input_frame, 
            textvariable=self.res_var, 
            values=["1080p (Recommended)", "720p", "480p", "1440p (2K)", "2160p (4K)", "Best Available (No limit)"],
            state="readonly",
            width=30
        )
        self.res_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Language
        ttk.Label(input_frame, text="Metadata Language:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.lang_var = tk.StringVar(value="None")
        self.lang_combo = ttk.Combobox(
            input_frame, 
            textvariable=self.lang_var, 
            values=["None", "English (eng)", "Spanish (spa)", "French (fre)", "German (ger)", "Italian (ita)", "Portuguese (por)", "Russian (rus)", "Japanese (jpn)", "Chinese (chi)"],
            state="readonly",
            width=30
        )
        self.lang_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Browser Cookies
        ttk.Label(input_frame, text="Browser Cookies (e.g. chrome, edge):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.cookies_var = tk.StringVar(value="")
        self.cookies_entry = ttk.Entry(input_frame, textvariable=self.cookies_var, width=30)
        self.cookies_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # Upload Delay
        ttk.Label(input_frame, text="Upload Delay (minutes):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.delay_var = tk.IntVar(value=20)
        self.delay_spin = ttk.Spinbox(input_frame, from_=1, to=1440, textvariable=self.delay_var, width=10)
        self.delay_spin.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Download Directory
        ttk.Label(input_frame, text="Download Directory:").grid(row=6, column=0, sticky=tk.W, pady=5)
        dir_frame = ttk.Frame(input_frame)
        dir_frame.grid(row=6, column=1, sticky=tk.EW, padx=5, pady=5)
        
        self.dir_var = tk.StringVar(value=os.path.abspath("."))
        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.browse_btn = ttk.Button(dir_frame, text="Browse...", command=self.browse_dir)
        self.browse_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Archive Ledger Row (Friendly Name + Path)
        ttk.Label(input_frame, text="Active Ledger:").grid(row=7, column=0, sticky=tk.NW, pady=5)
        ledger_frame = ttk.Frame(input_frame)
        ledger_frame.grid(row=7, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ledger_top_bar = ttk.Frame(ledger_frame)
        ledger_top_bar.pack(fill=tk.X)
        
        self.ledger_combo = ttk.Combobox(ledger_top_bar, textvariable=self.ledger_name_var, state="readonly")
        self.ledger_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ledger_combo.bind("<<ComboboxSelected>>", self.on_ledger_selected)
        
        self.rename_ledger_btn = ttk.Button(ledger_top_bar, text="Rename", width=8, command=self.rename_ledger_preset)
        self.rename_ledger_btn.pack(side=tk.LEFT, padx=(5, 2))
        
        self.delete_ledger_btn = ttk.Button(ledger_top_bar, text="Remove", width=8, command=self.delete_ledger_preset)
        self.delete_ledger_btn.pack(side=tk.LEFT, padx=2)
        
        self.choose_ledger_btn = ttk.Button(ledger_top_bar, text="Choose File...", command=self.choose_ledger_file)
        self.choose_ledger_btn.pack(side=tk.LEFT, padx=2)
        
        self.new_ledger_btn = ttk.Button(ledger_top_bar, text="New Ledger...", command=self.create_new_ledger_file)
        self.new_ledger_btn.pack(side=tk.LEFT, padx=(2, 0))

        self.ledger_path_lbl = ttk.Label(ledger_frame, text=f"File: {self.get_ledger_path()}", font=("Segoe UI", 8), foreground="gray")
        self.ledger_path_lbl.pack(anchor=tk.W, pady=(2, 0))

        self.keep_files_var = tk.BooleanVar(value=False)
        self.keep_files_chk = ttk.Checkbutton(input_frame, text="Keep video files locally after successful upload", variable=self.keep_files_var)
        self.keep_files_chk.grid(row=8, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Prevent Sleep Checkbox
        self.prevent_sleep_var = tk.BooleanVar(value=True)
        self.prevent_sleep_chk = ttk.Checkbutton(input_frame, text="Prevent PC from sleeping while archiving", variable=self.prevent_sleep_var)
        self.prevent_sleep_chk.grid(row=9, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Dark Mode Checkbox
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.dark_mode_chk = ttk.Checkbutton(input_frame, text="Enable Dark Mode", variable=self.dark_mode_var, command=self.toggle_dark_mode)
        self.dark_mode_chk.grid(row=10, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Reverse Playlist Checkbox
        self.reverse_playlist_var = tk.BooleanVar(value=False)
        self.reverse_playlist_chk = ttk.Checkbutton(input_frame, text="Download Oldest First (Reverse Playlist)", variable=self.reverse_playlist_var)
        self.reverse_playlist_chk.grid(row=11, column=1, sticky=tk.W, padx=5, pady=5)
        
        input_frame.columnconfigure(1, weight=1)
        
        # Frame for buttons
        btn_frame = ttk.Frame(self.tab1_frame, padding=(10, 0))
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="Start Archiving", command=self.start_archiving)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_archiving, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.open_archive_btn = ttk.Button(btn_frame, text="Open Active Ledger", command=self.open_archive_file)
        self.open_archive_btn.pack(side=tk.LEFT, padx=5)
        
        self.open_settings_btn = ttk.Button(btn_frame, text="Open Settings", command=self.open_settings_file)
        self.open_settings_btn.pack(side=tk.LEFT, padx=5)
        
        self.elapsed_label = ttk.Label(btn_frame, text="Time since last upload: Calculating...", font=("TkDefaultFont", 9, "bold"), cursor="hand2")
        self.elapsed_label.pack(side=tk.RIGHT, padx=10)
        self.elapsed_label.bind("<Button-1>", lambda e: self.refresh_remote_upload_time(force=True))
        
        # Tabs for logs
        self.notebook = ttk.Notebook(self.tab1_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Activity Log
        self.activity_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.activity_tab, text="Activity Log")
        
        self.log_area = scrolledtext.ScrolledText(self.activity_tab, wrap=tk.WORD, state=tk.NORMAL)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 2: Archive History
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="Archive History")
        
        history_top_frame = ttk.Frame(self.history_tab)
        history_top_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        self.history_sync_btn = ttk.Button(history_top_frame, text="🔄 Sync & Refresh from Account", command=self.sync_history_from_account)
        self.history_sync_btn.pack(side=tk.LEFT)
        
        self.history_status_lbl = ttk.Label(history_top_frame, text="", font=("Segoe UI", 8), foreground="gray")
        self.history_status_lbl.pack(side=tk.LEFT, padx=10)

        self.history_area = scrolledtext.ScrolledText(self.history_tab, wrap=tk.WORD, state=tk.DISABLED)
        self.history_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        
        # Load initial history
        self.refresh_history_view()
        self.update_elapsed_time()

    def create_tab2_widgets(self):
        # Top input frame
        input_frame = ttk.LabelFrame(self.tab2_frame, text="Wikipedia Page Settings", padding=(10, 10))
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # URL Input
        ttk.Label(input_frame, text="Wikipedia URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.wiki_url_var = tk.StringVar()
        self.wiki_url_entry = ttk.Entry(input_frame, textvariable=self.wiki_url_var)
        self.wiki_url_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        self.fetch_wiki_btn = ttk.Button(input_frame, text="Fetch References", command=self.fetch_wiki_references)
        self.fetch_wiki_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # SPN Settings
        settings_frame = ttk.Frame(input_frame)
        settings_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=5)
        
        self.spn_screenshot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Save Screenshot", variable=self.spn_screenshot_var).pack(side=tk.LEFT, padx=5)
        
        self.spn_outlinks_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Save Outlinks", variable=self.spn_outlinks_var).pack(side=tk.LEFT, padx=5)
        
        self.spn_personal_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Save to My Web Archive (Requires ia login)", variable=self.spn_personal_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(settings_frame, text=" | SPN Cooldown (s):").pack(side=tk.LEFT, padx=(10, 2))
        self.spn_delay_var = tk.IntVar(value=10)
        ttk.Spinbox(settings_frame, from_=1, to=300, textvariable=self.spn_delay_var, width=5).pack(side=tk.LEFT)
        
        input_frame.columnconfigure(1, weight=1)
        
        # Scrollable Canvas for Pills
        canvas_frame = ttk.Frame(self.tab2_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.pill_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.pill_canvas.yview)
        
        self.pill_container = ttk.Frame(self.pill_canvas)
        self.pill_container.bind(
            "<Configure>",
            lambda e: self.pill_canvas.configure(scrollregion=self.pill_canvas.bbox("all"))
        )
        
        self.pill_canvas.create_window((0, 0), window=self.pill_container, anchor="nw", width=self.pill_canvas.winfo_reqwidth())
        self.pill_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.pill_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas resize binding to keep pills wide
        self.pill_canvas.bind("<Configure>", lambda e: self.pill_canvas.itemconfig(self.pill_canvas.find_withtag("all")[0], width=e.width))

        # Mouse wheel scrolling binding
        self.pill_canvas.bind('<Enter>', self._bound_to_mousewheel)
        self.pill_canvas.bind('<Leave>', self._unbound_to_mousewheel)

        # Status Label
        self.tab2_status_var = tk.StringVar(value="Ready.")
        ttk.Label(self.tab2_frame, textvariable=self.tab2_status_var, font=("TkDefaultFont", 9, "italic")).pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        # SPN Queue logic
        self.spn_queue = queue.Queue()
        self.spn_worker_thread = threading.Thread(target=self.spn_worker_loop, daemon=True)
        self.spn_worker_thread.start()

    def _bound_to_mousewheel(self, event):
        self.pill_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _unbound_to_mousewheel(self, event):
        self.pill_canvas.unbind_all("<MouseWheel>")
        
    def _on_mousewheel(self, event):
        # Only scroll if the scrollbar is needed (content is larger than canvas)
        if self.pill_container.winfo_reqheight() > self.pill_canvas.winfo_height():
            # For Windows
            self.pill_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def alert_user(self):
        if os.name == 'nt':
            try:
                class FLASHWINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint),
                                ("hwnd", ctypes.c_void_p),
                                ("dwFlags", ctypes.c_uint),
                                ("uCount", ctypes.c_uint),
                                ("dwTimeout", ctypes.c_uint)]
                
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                info = FLASHWINFO()
                info.cbSize = ctypes.sizeof(FLASHWINFO)
                info.hwnd = hwnd
                # FLASHW_TRAY (2) | FLASHW_TIMERNOFG (12)
                info.dwFlags = 2 | 12 
                info.uCount = 0
                info.dwTimeout = 0
                ctypes.windll.user32.FlashWindowEx(ctypes.pointer(info))
            except Exception as e:
                self.log(f"Warning: Could not flash window: {e}")

    def update_elapsed_time(self):
        last_time = self.get_last_upload_time()
        if last_time == 0:
            self.elapsed_label.config(text="Time since last upload: No uploads yet")
        else:
            elapsed = int(time.time() - last_time)
            if elapsed < 0:
                elapsed = 0
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            else:
                time_str = f"{minutes}m {seconds}s"
                
            remote_time = getattr(self, '_cached_remote_upload_time', 0)
            local_log_time = getattr(self, '_last_local_log_time', 0)
            if remote_time > 0 and remote_time > local_log_time:
                self.elapsed_label.config(text=f"Time since last upload: {time_str} ☁")
            else:
                self.elapsed_label.config(text=f"Time since last upload: {time_str}")
            
        # Loop every second
        self.root.after(1000, self.update_elapsed_time)
        
    def refresh_history_view(self):
        self.history_area.config(state=tk.NORMAL)
        self.history_area.delete(1.0, tk.END)
        if os.path.exists("archive_history.log"):
            try:
                with open("archive_history.log", "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        clean = line.strip()
                        if not clean:
                            continue
                        parts = clean.split(" | ")
                        if len(parts) >= 5:
                            self.history_area.insert(tk.END, f"{parts[0]} | {parts[2]} | {parts[3]} | [Ledger: {parts[4]}]\n")
                        elif len(parts) >= 4:
                            self.history_area.insert(tk.END, f"{parts[0]} | {parts[2]} | {parts[3]}\n")
                        else:
                            self.history_area.insert(tk.END, clean + "\n")
            except Exception as e:
                self.history_area.insert(tk.END, f"Error reading history: {e}\n")
        else:
            self.history_area.insert(tk.END, "No archives recorded yet.")
        self.history_area.see(tk.END)
        self.history_area.config(state=tk.DISABLED)
        
    def log(self, message):
        def append():
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END)
        self.root.after(0, append)

    def browse_dir(self):
        directory = filedialog.askdirectory(initialdir=self.dir_var.get(), title="Select Download Directory")
        if directory:
            self.dir_var.set(os.path.abspath(directory))

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.config(text="Resume")
            self.log("\n[PAUSE] Pipeline paused by user. Click 'Resume' to continue.")
        else:
            self.pause_event.set()
            self.pause_btn.config(text="Pause")
            self.log("\n[RESUME] Pipeline resumed.")
        
    def sync_history_from_account(self):
        """Fetches all account uploads from Archive.org and synchronizes archive_history.log."""
        if getattr(self, '_syncing_history', False):
            messagebox.showinfo("Sync in Progress", "History sync is already running.")
            return

        self._syncing_history = True
        self.history_sync_btn.config(state=tk.DISABLED)
        self.history_status_lbl.config(text="Connecting to Archive.org account...")

        def _worker():
            try:
                username = self.get_ia_account_identifier()
                if not username:
                    self.root.after(0, lambda: self.history_status_lbl.config(text="Error: No IA account configured."))
                    self.root.after(0, lambda: messagebox.showerror("Error", "No Internet Archive account or S3 keys found. Please set them up in 'IA Account Setup'."))
                    return

                self.root.after(0, lambda: self.history_status_lbl.config(text="Fetching account uploads..."))
                query = f"uploader:{username}"
                s = ia.search_items(query, fields=["identifier", "title", "publicdate", "addeddate", "date", "ledger"])
                total = getattr(s, "num_found", 0)

                # Read existing history log with case-insensitive deduplication
                existing_entries = {}  # vid_lower -> { "date_str", "ts", "vid", "title", "ledger" }
                if os.path.exists("archive_history.log"):
                    try:
                        with open("archive_history.log", "r", encoding="utf-8", errors="replace") as f:
                            for line in f:
                                parts = line.strip().split(" | ")
                                if len(parts) >= 4:
                                    date_str = parts[0].strip("[]")
                                    try:
                                        epoch = float(parts[1])
                                    except Exception:
                                        epoch = 0
                                    raw_vid = parts[2].strip()
                                    raw_title = parts[3].strip()
                                    raw_ledger = parts[4].strip() if len(parts) >= 5 else ""
                                    
                                    vid_key = re.sub(r'[^a-z0-9]', '', raw_vid.lower())
                                    if vid_key not in existing_entries:
                                        existing_entries[vid_key] = {
                                            "date_str": date_str,
                                            "ts": epoch,
                                            "vid": raw_vid,
                                            "title": raw_title,
                                            "ledger": raw_ledger
                                        }
                                    else:
                                        # Prefer the mixed-case ID / underscores over sanitized dashes
                                        curr = existing_entries[vid_key]
                                        if (any(c.isupper() for c in raw_vid) or '_' in raw_vid) and not (any(c.isupper() for c in curr["vid"]) or '_' in curr["vid"]):
                                            curr["vid"] = raw_vid
                                        if raw_ledger and not curr["ledger"]:
                                            curr["ledger"] = raw_ledger
                    except Exception:
                        pass

                added_count = 0
                updated_count = 0
                for item in s:
                    ident = item.get("identifier", "")
                    if not ident.lower().startswith("yt-archive-"):
                        continue
                    ia_vid = ident[11:].strip()
                    if not ia_vid:
                        continue

                    vid_key = re.sub(r'[^a-z0-9]', '', ia_vid.lower())
                    raw_ledger = item.get("ledger", "")
                    if isinstance(raw_ledger, list):
                        raw_ledger = raw_ledger[0] if raw_ledger else ""
                    ledger_tag = raw_ledger.strip() or "Main Archive"

                    if vid_key in existing_entries:
                        curr = existing_entries[vid_key]
                        if not curr["ledger"] and raw_ledger:
                            curr["ledger"] = ledger_tag
                            updated_count += 1
                        continue

                    title = item.get("title", "Unknown Title")
                    date_raw = item.get("addeddate") or item.get("publicdate") or item.get("date") or ""
                    ts = self.parse_ia_date(date_raw)
                    if ts > 0:
                        date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                    else:
                        ts = time.time()
                        date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

                    existing_entries[vid_key] = {
                        "date_str": date_str,
                        "ts": ts,
                        "vid": ia_vid,
                        "title": title,
                        "ledger": ledger_tag
                    }
                    added_count += 1

                # Re-sort all history entries chronologically
                sorted_entries = sorted(existing_entries.values(), key=lambda x: x["ts"])
                with open("archive_history.log", "w", encoding="utf-8") as f:
                    for entry in sorted_entries:
                        ledger_str = entry["ledger"] if entry["ledger"] else "Main Archive"
                        f.write(f"[{entry['date_str']}] | {entry['ts']} | {entry['vid']} | {entry['title']} | {ledger_str}\n")

                if sorted_entries:
                    newest_ts = sorted_entries[-1]["ts"]
                    if newest_ts > getattr(self, '_cached_remote_upload_time', 0):
                        self._cached_remote_upload_time = newest_ts
                        self._last_remote_check_time = time.time()

                self.root.after(0, self.refresh_history_view)
                status_msg = f"✓ Synced ({added_count} new"
                if updated_count > 0:
                    status_msg += f", {updated_count} enriched"
                status_msg += ")"
                self.root.after(0, lambda m=status_msg: self.history_status_lbl.config(text=m))

                if hasattr(self, 'load_items_from_history'):
                    self.root.after(0, self.load_items_from_history)

                self.root.after(0, lambda: messagebox.showinfo(
                    "History Synced",
                    f"Successfully synchronized upload history from Archive.org!\n\n"
                    f"• Account items fetched: {total}\n"
                    f"• New items added to history log: {added_count}\n"
                    f"• Total history entries: {len(sorted_entries)}\n\n"
                    f"(Note: Your local download ledgers remain unchanged.)"
                ))
            except Exception as e:
                self.root.after(0, lambda: self.history_status_lbl.config(text="Sync failed"))
                self.root.after(0, lambda err=e: messagebox.showerror("Sync Error", f"Could not sync history: {type(err).__name__}: {err}"))
            finally:
                self._syncing_history = False
                self.root.after(0, lambda: self.history_sync_btn.config(state=tk.NORMAL))

        threading.Thread(target=_worker, daemon=True).start()

    def start_archiving(self):
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
        delay_minutes = self.delay_var.get()
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
        
        self.log(f"=== Archival Pipeline Started (Max Resolution: {selected_res}) ===")
        self.log(f"Active Ledger: '{active_ledger_name}' ({os.path.basename(active_ledger_path)})")
        self.worker_thread = threading.Thread(
            target=self.run_pipeline, 
            args=(url, self.tags_combo.get().strip(), selected_res, base_dir, keep_files, prevent_sleep, delay_minutes, lang_code, reverse_playlist, active_ledger_path, active_ledger_name), 
            daemon=True
        )
        self.worker_thread.start()
        
    def stop_archiving(self):
        self.log("\n=== Stop Requested ===")
        self.log("Terminating current tasks and stopping pipeline...")
        self.stop_event.set()
        self.pause_event.set()  # Unblock thread if paused
        
        # If a subprocess is actively running, terminate it
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except Exception:
                pass
                
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        
    def open_settings_file(self):
        try:
            if not os.path.exists("settings.json"):
                with open("settings.json", "w") as f:
                    f.write("{}")
            os.startfile("settings.json")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open settings.json: {e}")

    def get_ledger_path(self):
        """Returns absolute path of the currently selected ledger file."""
        name = self.ledger_name_var.get().strip() if hasattr(self, 'ledger_name_var') else "Main Archive"
        presets = getattr(self, "ledger_presets", {})
        path = presets.get(name)
        if not path:
            val = getattr(self, "ledger_file_var", None)
            path = val.get().strip() if val else ""
        if not path:
            path = "archive.txt"
        return os.path.abspath(path)

    def on_ledger_selected(self, event=None):
        """Called when user selects a ledger preset from the combobox."""
        name = self.ledger_combo.get().strip()
        if not name:
            return
        path = self.ledger_presets.get(name, "archive.txt")
        self.ledger_name_var.set(name)
        self.ledger_file_var.set(path)
        if hasattr(self, 'ledger_path_lbl'):
            self.ledger_path_lbl.config(text=f"File: {path}")
        self.save_settings()
        self.log(f"Active archive ledger switched to: '{name}' ({path})")

    def rename_ledger_preset(self):
        """Renames the current active ledger preset display name."""
        curr_name = self.ledger_name_var.get().strip()
        if not curr_name:
            return
        new_name = simpledialog.askstring("Rename Ledger", "Enter new display name for this ledger:", initialvalue=curr_name)
        if new_name and new_name.strip() and new_name.strip() != curr_name:
            clean_name = new_name.strip()
            path = self.ledger_presets.pop(curr_name, self.ledger_file_var.get())
            self.ledger_presets[clean_name] = path
            self.ledger_name_var.set(clean_name)
            self.ledger_combo['values'] = list(self.ledger_presets.keys())
            self.ledger_combo.set(clean_name)
            self.save_settings()
            self.log(f"Ledger '{curr_name}' renamed to: '{clean_name}'")

    def delete_ledger_preset(self):
        """Removes the current active ledger preset, with an option to delete the physical file."""
        curr_name = self.ledger_name_var.get().strip()
        if not curr_name:
            return

        if len(self.ledger_presets) == 1 and curr_name == "Main Archive" and self.ledger_presets.get("Main Archive") == "archive.txt":
            messagebox.showinfo("Cannot Remove", "'Main Archive' is the only default ledger and cannot be removed.\n\nYou can use 'Choose File...' or 'New Ledger...' to switch to a different ledger.")
            return

        confirm = messagebox.askyesno(
            "Remove Ledger",
            f"Are you sure you want to remove '{curr_name}' from your saved ledgers?\n\n(This will remove it from the list in the application.)"
        )
        if not confirm:
            return

        file_path = self.ledger_presets.pop(curr_name, self.ledger_file_var.get())

        # Ask if they want to delete the physical text file
        if file_path and os.path.isfile(file_path):
            del_file = messagebox.askyesno(
                "Delete Physical File?",
                f"Would you also like to permanently delete the physical text file from your computer?\n\nFile: {file_path}\n\n• Click 'Yes' to permanently delete the file.\n• Click 'No' to keep the text file safe on your computer."
            )
            if del_file:
                try:
                    os.remove(file_path)
                    self.log(f"Deleted physical ledger file: {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete physical ledger file:\n{e}")

        # Ensure at least one default ledger remains in presets
        if not self.ledger_presets:
            self.ledger_presets = {"Main Archive": "archive.txt"}

        # Select the next available ledger
        next_name = list(self.ledger_presets.keys())[0]
        next_path = self.ledger_presets[next_name]

        self.ledger_name_var.set(next_name)
        self.ledger_file_var.set(next_path)
        self.ledger_combo['values'] = list(self.ledger_presets.keys())
        self.ledger_combo.set(next_name)
        if hasattr(self, 'ledger_path_lbl'):
            self.ledger_path_lbl.config(text=f"File: {next_path}")

        self.save_settings()
        self.log(f"Removed ledger '{curr_name}'. Active ledger is now: '{next_name}' ({next_path})")
        messagebox.showinfo("Ledger Removed", f"Ledger '{curr_name}' has been removed.\n\nActive ledger set to: '{next_name}'.")

    def choose_ledger_file(self):
        """Allows user to browse and select an existing ledger text file with a friendly name."""
        init_dir = os.path.dirname(self.get_ledger_path())
        if not os.path.isdir(init_dir):
            init_dir = os.path.abspath(".")
        filename = filedialog.askopenfilename(
            title="Choose Archive Ledger File",
            filetypes=[("Text Ledger Files (*.txt)", "*.txt"), ("All Files (*.*)", "*.*")],
            initialdir=init_dir
        )
        if filename:
            default_display = os.path.splitext(os.path.basename(filename))[0].replace("_", " ").title()
            friendly_name = simpledialog.askstring("Ledger Name", "Enter a friendly display name for this ledger:", initialvalue=default_display)
            if not friendly_name or not friendly_name.strip():
                friendly_name = default_display

            friendly_name = friendly_name.strip()
            self.ledger_presets[friendly_name] = filename
            self.ledger_name_var.set(friendly_name)
            self.ledger_file_var.set(filename)
            self.ledger_combo['values'] = list(self.ledger_presets.keys())
            self.ledger_combo.set(friendly_name)
            if hasattr(self, 'ledger_path_lbl'):
                self.ledger_path_lbl.config(text=f"File: {filename}")
            self.save_settings()
            self.log(f"Added and selected ledger: '{friendly_name}' ({filename})")

    def create_new_ledger_file(self):
        """Allows user to create a new ledger file with a friendly name."""
        friendly_name = simpledialog.askstring("New Ledger", "Enter a friendly display name for the new ledger:\n(e.g. 'Trenes Archive', 'Collaborative Ledger')", initialvalue="My Archive")
        if not friendly_name or not friendly_name.strip():
            return
        friendly_name = friendly_name.strip()
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', friendly_name.lower()) + ".txt"

        init_dir = os.path.dirname(self.get_ledger_path())
        if not os.path.isdir(init_dir):
            init_dir = os.path.abspath(".")

        filename = filedialog.asksaveasfilename(
            title="Save New Ledger File",
            defaultextension=".txt",
            filetypes=[("Text Ledger Files (*.txt)", "*.txt"), ("All Files (*.*)", "*.*")],
            initialdir=init_dir,
            initialfile=safe_filename
        )
        if filename:
            try:
                if not os.path.exists(filename):
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(f"# Archive Ledger: {friendly_name}\n# Created {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                self.ledger_presets[friendly_name] = filename
                self.ledger_name_var.set(friendly_name)
                self.ledger_file_var.set(filename)
                self.ledger_combo['values'] = list(self.ledger_presets.keys())
                self.ledger_combo.set(friendly_name)
                if hasattr(self, 'ledger_path_lbl'):
                    self.ledger_path_lbl.config(text=f"File: {filename}")
                self.save_settings()
                self.log(f"Created new ledger: '{friendly_name}' ({filename})")
                messagebox.showinfo("New Ledger Created", f"New ledger '{friendly_name}' created and set as active:\n\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create ledger file: {e}")

    def open_archive_file(self):
        """Opens the active ledger file in Notepad or default text editor."""
        path = self.get_ledger_path()
        name = self.ledger_name_var.get() if hasattr(self, 'ledger_name_var') else "Archive Ledger"
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                self.log(f"Warning: Could not open ledger: {e}")
        else:
            ans = messagebox.askyesno("File Not Found", f"Ledger file for '{name}' does not exist yet:\n\n{path}\n\nWould you like to create it now?")
            if ans:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(f"# Archive Ledger: {name}\n# Created {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    os.startfile(path)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not create ledger file: {e}")

    def parse_ia_date(self, date_str):
        """Parses Internet Archive date strings into epoch timestamps."""
        if not date_str:
            return 0
        date_str = str(date_str).strip()
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str[:19], fmt)
                return dt.replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                pass
        return 0

    def get_ia_account_identifier(self):
        """Dynamically retrieves the account email/username from saved settings or S3 keys."""
        uploader_val = getattr(self, "ia_uploader_email", "").strip()
        if uploader_val:
            return uploader_val
        try:
            cfg = ia.config.get_config()
            s3 = cfg.get("s3", {})
            ak = s3.get("access")
            sk = s3.get("secret")
            if ak and sk:
                derived = ia.get_username(ak, sk)
                if derived:
                    self.ia_uploader_email = derived
                    return derived
            cookies = cfg.get("cookies", {})
            user = cookies.get("logged-in-user") or cfg.get("general", {}).get("screenname")
            if user:
                self.ia_uploader_email = user
                return user
        except Exception:
            pass
        return ""

    def refresh_remote_upload_time(self, force=False, block=False):
        """Fetches the timestamp of the latest upload on the user's IA account across all devices."""
        if getattr(self, '_is_checking_remote_upload', False) and not block:
            return
        if not force and (time.time() - getattr(self, '_last_remote_check_time', 0) < 120):
            return

        def _worker():
            self._is_checking_remote_upload = True
            try:
                username = self.get_ia_account_identifier()
                if not username:
                    return
                s = ia.search_items(f"uploader:{username}", sorts=["addeddate desc"], fields=["identifier", "addeddate", "publicdate"])
                item = next(iter(s), None)
                if item:
                    raw_date = item.get("addeddate") or item.get("publicdate")
                    ts = self.parse_ia_date(raw_date)
                    if ts > 0:
                        self._cached_remote_upload_time = ts
                        self._last_remote_check_time = time.time()
            except Exception:
                pass
            finally:
                self._is_checking_remote_upload = False

        if block:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

    def _periodic_remote_sync(self):
        """Periodically checks the latest account upload time in the background."""
        self.refresh_remote_upload_time()
        self.root.after(120000, self._periodic_remote_sync)

    def get_last_upload_time(self):
        """Reads archive_history.log and remote IA account status, returning the timestamp of the latest upload."""
        log_time = 0
        if os.path.exists("archive_history.log"):
            try:
                with open("archive_history.log", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        parts = last_line.split(" | ")
                        if len(parts) >= 2:
                            log_time = float(parts[1])
            except Exception:
                pass
                
        self._last_local_log_time = log_time
        artificial_time = getattr(self, 'artificial_last_upload_time', 0)
        remote_time = getattr(self, '_cached_remote_upload_time', 0)
        return max(log_time, artificial_time, remote_time)

    def record_successful_upload(self, video_id, title, tags_str=None, lang_code=None, ledger_name="Main Archive"):
        """Records a successful upload to the human-readable history log."""
        try:
            now = time.time()
            self._cached_remote_upload_time = now
            self._last_remote_check_time = now
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
            ledger_label = ledger_name.strip() if ledger_name else "Main Archive"
            with open("archive_history.log", "a", encoding="utf-8") as f:
                f.write(f"[{date_str}] | {now} | {video_id} | {title} | {ledger_label}\n")
            self.log(f"[History] Recorded successful upload to archive_history.log (Ledger: {ledger_label})")
            
            # Automatically update local metadata cache
            ident = f"yt-archive-{video_id}".lower()
            ident = re.sub(r'[^a-z0-9\-]', '-', ident)
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
            self.metadata_cache[ident] = {
                "identifier": ident,
                "video_id": video_id,
                "title": title,
                "tags": tags,
                "language": lang_code or "",
                "date": date_str,
                "source": "app",
                "ledger": ledger_label,
                "last_updated": date_str
            }
            self.save_metadata_cache()
            if hasattr(self, 'load_items_from_history'):
                self.root.after(0, self.load_items_from_history)
                    
            self.root.after(0, self.refresh_history_view)
        except Exception as e:
            self.log(f"[History] Warning: Could not write to archive_history.log: {e}")

    def get_executable(self, name):
        """Reliably finds pip-installed CLI tools even if they are not in the system PATH."""
        # 1. Try finding it in the system PATH
        path = shutil.which(name)
        if path:
            return path
            
        # 2. Try looking in the active Python's Scripts folder (common on Windows)
        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        exe_path = os.path.join(scripts_dir, f"{name}.exe")
        if os.path.exists(exe_path):
            return exe_path
            
        # 3. Fallback to just the name
        return name

    def wait_if_paused(self):
        """Blocks while paused, checks for stop requests."""
        if not self.pause_event.is_set():
            self.log("[PAUSED] Waiting for Resume...")
            while not self.pause_event.is_set():
                if self.stop_event.is_set():
                    return False
                time.sleep(0.5)
        return not self.stop_event.is_set()
        
    def run_pipeline(self, url, tags_str, max_resolution, base_dir, keep_files, prevent_sleep, delay_minutes, lang_code, reverse_playlist, active_ledger_path=None, active_ledger_name="Main Archive"):
        try:
            if not active_ledger_path:
                active_ledger_path = self.get_ledger_path()
            if not active_ledger_name:
                active_ledger_name = self.ledger_name_var.get().strip() or "Main Archive"

            # Prevent Windows from going to sleep while the pipeline is active
            if prevent_sleep and os.name == 'nt':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                
            # Create a dedicated temp folder inside the selected base_dir for safety
            temp_dir = os.path.join(base_dir, ".yt_archive_temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Map resolution option to yt-dlp format string
            format_map = {
                "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
                "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "1080p (Recommended)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "1440p (2K)": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
                "2160p (4K)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
                "Best Available (No limit)": "bestvideo+bestaudio/best"
            }
            format_string = format_map.get(max_resolution, "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best")
            
            while not self.stop_event.is_set():
                if not self.wait_if_paused():
                    return
                    
                self.log("\n--- Starting yt-dlp to fetch the next video ---")
                
                # Clean up temp directory before starting next video
                for f in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except Exception as e:
                        self.log(f"Warning: Could not remove {f}: {e}")
                        
                # Create a temporary clone of the pinned archive ledger.
                # yt-dlp will write to the temp ledger, and we only overwrite the real one upon successful IA upload.
                if os.path.exists(active_ledger_path):
                    shutil.copy(active_ledger_path, "temp_archive.txt")
                elif os.path.exists("temp_archive.txt"):
                    os.remove("temp_archive.txt")
                        
                cmd = [
                    self.get_executable("yt-dlp"),
                    "--max-downloads", "1",
                    "--download-archive", "temp_archive.txt",
                    "--restrict-filenames",
                    "--write-info-json",
                    "--write-description",
                    "--no-write-playlist-metafiles",
                    "--ignore-errors",
                    "-f", format_string,
                    "--merge-output-format", "mp4",
                    "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
                    "--paths", temp_dir
                ]
                
                if reverse_playlist:
                    cmd.append("--playlist-reverse")
                    
                cookies_browser = self.cookies_var.get().strip().lower()
                if cookies_browser:
                    cmd.extend([
                        "--cookies-from-browser", cookies_browser,
                        "--js-runtimes", "node",
                        "--remote-components", "ejs:github"
                    ])
                    
                cmd.append(url)
                
                try:
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.STDOUT, 
                        text=True, 
                        encoding='utf-8',
                        errors='replace',
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    self.current_process = process
                    
                    for line in process.stdout:
                        self.log(f"[yt-dlp] {line.strip()}")
                        if self.stop_event.is_set():
                            process.terminate()
                            self.log("yt-dlp terminated by user.")
                            return
                            
                    process.wait()
                    self.current_process = None
                    
                except Exception as e:
                    self.log(f"Error running yt-dlp: {e}")
                    self.root.after(0, self.alert_user)
                    self.current_process = None
                    break
                    
                if self.stop_event.is_set():
                    return

                # Check for successfully downloaded JSON info
                json_files = glob.glob(os.path.join(temp_dir, "*.info.json"))
                if not json_files:
                    self.log("\nNo new videos found, or yt-dlp finished. The playlist may be fully archived.")
                    break
                    
                info_file = json_files[0]
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                except Exception as e:
                    self.log(f"Error parsing metadata JSON: {e}")
                    self.root.after(0, self.alert_user)
                    break
                    
                title = info.get('title', 'Unknown_Title')
                description = info.get('description', '')
                uploader = info.get('uploader', 'Unknown_Uploader')
                upload_date = info.get('upload_date', '19700101')
                if len(upload_date) == 8 and upload_date.isdigit():
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                video_id = info.get('id', 'Unknown_ID')
                
                # Find the video file (not json, not description)
                video_files = [f for f in glob.glob(os.path.join(temp_dir, "*")) if not f.endswith('.json') and not f.endswith('.description')]
                if not video_files:
                    self.log("Error: Metadata found but video file is missing.")
                    self.root.after(0, self.alert_user)
                    self.remove_from_archive(video_id)
                    break
                video_file = video_files[0]
                
                # Check for duplicate: Has this video (or matching title) already been archived on the IA account?
                target_ident = f"yt-archive-{video_id}".lower()
                target_ident = re.sub(r'[^a-z0-9\-]', '-', target_ident)
                
                already_archived = False
                match_desc = ""
                
                if target_ident in self.metadata_cache:
                    already_archived = True
                    match_desc = f"account item '{target_ident}'"
                else:
                    clean_curr = normalize_title(title)
                    for c_ident, c_item in self.metadata_cache.items():
                        c_title = c_item.get('title', '')
                        if clean_curr and normalize_title(c_title) == clean_curr:
                            already_archived = True
                            match_desc = f"pre-existing archive '{c_ident}' ('{c_title}')"
                            break
                            
                if already_archived:
                    self.log(f"\n[Duplicate Prevention] '{title}' is already archived on your account ({match_desc}).")
                    self.log(f"Recording to local ledger '{active_ledger_name}' ({os.path.basename(active_ledger_path)}) to skip on future runs...")
                    try:
                        with open(active_ledger_path, "a", encoding="utf-8") as f:
                            archival_time = time.strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"# {title} (Account-consolidated: {archival_time})\nyoutube {video_id}\n\n")
                    except Exception as e:
                        self.log(f"Warning: Could not update ledger: {e}")
                    self.record_successful_upload(video_id, title, tags_str, lang_code, active_ledger_name)
                    
                    # Clean up temp files and skip to next
                    for f in os.listdir(temp_dir):
                        try:
                            os.remove(os.path.join(temp_dir, f))
                        except Exception:
                            pass
                    continue
                
                if not self.wait_if_paused():
                    return
                
                self.log(f"\nMetadata parsed for '{title}'.")
                
                # Enforce real-world configurable cooldown & Retry Logic
                upload_success = False
                max_attempts = 3
                
                for attempt in range(max_attempts):
                    if self.stop_event.is_set() or not self.wait_if_paused():
                        return
                        
                    # On first attempt for this item, sync with Archive.org to check if another device uploaded
                    if attempt == 0:
                        self.log("Syncing upload cooldown with Archive.org account across devices...")
                        self.refresh_remote_upload_time(force=True, block=True)

                    while True:
                        if self.stop_event.is_set() or not self.wait_if_paused():
                            return
                        wait_needed = (delay_minutes * 60) - (time.time() - self.get_last_upload_time())
                        if wait_needed <= 0:
                            break
                        if int(wait_needed) % 60 == 0 or wait_needed <= 10:
                            self.log(f"--- Enforcing rate limit: Waiting {int(wait_needed)}s before upload is permitted ---")
                        time.sleep(1)
                        
                    # Sanitize the identifier for Internet Archive (lowercase alphanumeric and dashes only)
                    identifier = f"yt-archive-{video_id}".lower()
                    identifier = re.sub(r'[^a-z0-9\-]', '-', identifier)
                    
                    self.log(f"--- Starting ia upload for identifier: {identifier} (Attempt {attempt+1}/{max_attempts}) ---")
                    
                    ia_cmd = [
                        self.get_executable("ia"), "upload", identifier,
                        video_file,
                        "-m", f"title:{title}",
                        "-m", f"description:{description}",
                        "-m", f"creator:{uploader}",
                        "-m", f"date:{upload_date}",
                        "-m", "collection:opensource_movies",
                        "-m", "mediatype:movies",
                        "-m", f"ledger:{active_ledger_name}",
                        "--retries", "3"
                    ]
                    
                    # Process user tags
                    if tags_str:
                        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                        for tag in tags:
                            ia_cmd.extend(["-m", f"subject:{tag}"])
                    
                    # Process language
                    if lang_code:
                        ia_cmd.extend(["-m", f"language:{lang_code}"])
                                
                    try:
                        ia_process = subprocess.Popen(
                            ia_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        self.current_process = ia_process
                        
                        for line in ia_process.stdout:
                            self.log(f"[ia upload] {line.strip()}")
                            if self.stop_event.is_set():
                                ia_process.terminate()
                                self.log("ia upload terminated by user.")
                                return
                                
                        ia_process.wait()
                        self.current_process = None
                        
                        if ia_process.returncode == 0:
                            upload_success = True
                            
                            # Write title and ID to master ledger upon SUCCESS
                            try:
                                with open(active_ledger_path, "a", encoding="utf-8") as f:
                                    archival_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                    f.write(f"# {title} (Archived: {archival_time})\nyoutube {video_id}\n\n")
                            except Exception as e:
                                self.log(f"Warning: Could not update ledger: {e}")
                            
                            self.record_successful_upload(video_id, title, tags_str, lang_code, active_ledger_name)
                            break
                        else:
                            self.log(f"\n[ERROR] ia upload failed with exit code {ia_process.returncode}.")
                            self.root.after(0, self.alert_user)
                            if attempt < max_attempts - 1:
                                self.log("Going back to sleep for the cooldown period before retrying...")
                                self.artificial_last_upload_time = time.time()
                            else:
                                self.log("Max retries reached. Stopping pipeline to prevent hard ban.")
                                break
                                
                    except Exception as e:
                        self.log(f"Error running ia upload: {e}")
                        self.root.after(0, self.alert_user)
                        self.current_process = None
                        break
                        
                if not upload_success:
                    break
                    
                if keep_files:
                    self.log(f"\nUpload confirmed. Moving video to {base_dir}...")
                    try:
                        shutil.move(video_file, os.path.join(base_dir, os.path.basename(video_file)))
                    except Exception as e:
                        self.log(f"Warning: Could not move file: {e}")
                else:
                    self.log("\nUpload confirmed successful. Cleaning up temp files...")
                    
                for f in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except Exception as e:
                        self.log(f"Warning: Could not remove {f}: {e}")
                    
        finally:
            # Allow Windows to sleep again
            if os.name == 'nt':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                
            self.current_process = None
            self.log("\n=== Archival Pipeline Finished/Stopped ===")
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.pause_btn.config(text="Pause", state=tk.DISABLED))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.ledger_combo.config(state="readonly"))
            self.root.after(0, lambda: self.rename_ledger_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.delete_ledger_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.choose_ledger_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.new_ledger_btn.config(state=tk.NORMAL))

    # --- Wayback Machine Tab Logic ---

    def fetch_wiki_references(self):
        url = self.wiki_url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a Wikipedia URL.")
            return
        
        self.fetch_wiki_btn.config(state=tk.DISABLED)
        self.tab2_status_var.set("Fetching Wikipedia page...")
        
        # Clear existing pills
        for widget in self.pill_container.winfo_children():
            widget.destroy()
            
        threading.Thread(target=self._fetch_wiki_thread, args=(url,), daemon=True).start()

    def _fetch_wiki_thread(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            links = set()
            # Extract from references
            for ref in soup.select('ol.references a.external'):
                links.add(ref.get('href'))
                
            # Fallback/additional: extract all external links in body
            for ext in soup.select('#bodyContent a.external'):
                links.add(ext.get('href'))
                
            # Filter out some common non-archivable or junk links
            valid_links = []
            for link in sorted(links):
                if link and link.startswith('http') and 'archive.org' not in link:
                    valid_links.append(link)
                    
            if not valid_links:
                self.root.after(0, lambda: self.tab2_status_var.set("No external references found."))
                self.root.after(0, lambda: self.fetch_wiki_btn.config(state=tk.NORMAL))
                return
                
            self.root.after(0, lambda: self.tab2_status_var.set(f"Found {len(valid_links)} external links. Fetching availability..."))
            
            # Build UI pills
            for link in valid_links:
                self.root.after(0, self.build_pill, link)
                
            self.root.after(0, lambda: self.fetch_wiki_btn.config(state=tk.NORMAL))
            
            # Start background availability fetcher
            threading.Thread(target=self._fetch_availability_thread, args=(valid_links,), daemon=True).start()
            
        except Exception as e:
            self.root.after(0, lambda: self.tab2_status_var.set(f"Error: {e}"))
            self.root.after(0, lambda: self.fetch_wiki_btn.config(state=tk.NORMAL))

    def build_pill(self, url):
        pill_frame = ttk.Frame(self.pill_container, relief=tk.RAISED, borderwidth=1)
        pill_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # URL Container Frame
        url_frame = ttk.Frame(pill_frame)
        url_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)
        
        # Dead Status Label (Hidden initially)
        dead_label = ttk.Label(url_frame, text="", font=("TkDefaultFont", 9, "bold"), foreground="#d9534f")
        dead_label.pack(side=tk.LEFT)
        
        # Selectable URL Entry
        url_var = tk.StringVar(value=url)
        url_entry = ttk.Entry(url_frame, textvariable=url_var, state="readonly")
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        pill_frame.dead_label = dead_label
        pill_frame.url_var = url_var
        
        # Availability Label
        avail_label = ttk.Label(pill_frame, text="Checking Wayback Machine...", foreground="gray")
        avail_label.grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 5))
        
        # Result Entry (Hidden initially)
        result_var = tk.StringVar()
        result_entry = ttk.Entry(pill_frame, textvariable=result_var, state="readonly", width=60)
        
        # Save Button
        save_btn = ttk.Button(pill_frame, text="Archive Now")
        
        # Store references to widgets in the button for the callback
        pill_frame.url = url
        pill_frame.avail_label = avail_label
        pill_frame.result_entry = result_entry
        pill_frame.result_var = result_var
        pill_frame.save_btn = save_btn
        
        save_btn.config(command=lambda f=pill_frame: self.queue_spn_job(f))
        save_btn.grid(row=0, column=1, rowspan=2, sticky=tk.E, padx=10, pady=5)
        
        pill_frame.columnconfigure(0, weight=1)

    def _fetch_availability_thread(self, links):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        for url in links:
            if self.stop_event.is_set():
                break
                
            # Live web check
            is_dead = False
            try:
                live_resp = requests.get(url, headers=headers, stream=True, timeout=5)
                if live_resp.status_code >= 400:
                    is_dead = True
                live_resp.close()
            except Exception:
                is_dead = True
                
            if is_dead:
                self.root.after(0, self._mark_url_dead, url)
                
            # Wayback Machine check
            try:
                avail_url = f"https://archive.org/wayback/available?url={url}"
                resp = requests.get(avail_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    snapshots = data.get("archived_snapshots", {})
                    closest = snapshots.get("closest")
                    if closest and closest.get("available"):
                        ts = closest.get("timestamp", "")
                        if len(ts) >= 8:
                            formatted_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                            self.root.after(0, self._update_avail_label, url, f"Last archived: {formatted_date}", "green")
                        else:
                            self.root.after(0, self._update_avail_label, url, "Archived (Date Unknown)", "green")
                    else:
                        self.root.after(0, self._update_avail_label, url, "Not found in archive", "red")
                else:
                    self.root.after(0, self._update_avail_label, url, f"Availability check failed (HTTP {resp.status_code})", "orange")
            except Exception as e:
                self.root.after(0, self._update_avail_label, url, f"Check error: {str(e)[:40]}", "orange")
                
            time.sleep(0.5) # Prevent aggressive spamming of availability API
            
        self.root.after(0, lambda: self.tab2_status_var.set("Availability check complete."))

    def _mark_url_dead(self, url):
        for widget in self.pill_container.winfo_children():
            if getattr(widget, "url", None) == url:
                widget.dead_label.config(text="[DEAD]")
                break

    def _update_avail_label(self, url, text, color):
        for widget in self.pill_container.winfo_children():
            if getattr(widget, "url", None) == url:
                widget.avail_label.config(text=text, foreground=color)
                break

    def get_ia_auth_header(self):
        try:
            result = subprocess.run(
                [self.get_executable("ia"), "configure", "--print-auth-header"], 
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                header = result.stdout.strip()
                if header.startswith("Authorization: "):
                    return header.replace("Authorization: ", "")
        except Exception:
            pass
        return None

    def queue_spn_job(self, pill_frame):
        pill_frame.save_btn.config(state=tk.DISABLED, text="Queued...")
        self.spn_queue.put(pill_frame)
        self.tab2_status_var.set(f"Queued {pill_frame.url}")

    def spn_worker_loop(self):
        while True:
            pill_frame = self.spn_queue.get()
            if pill_frame is None:
                break # Exit signal
                
            if not pill_frame.winfo_exists():
                self.spn_queue.task_done()
                continue
                
            url = pill_frame.url
            self.root.after(0, lambda f=pill_frame: f.save_btn.config(text="Saving..."))
            self.root.after(0, lambda: self.tab2_status_var.set(f"Archiving: {url}"))
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            }
            
            if self.spn_personal_var.get():
                auth = self.get_ia_auth_header()
                if auth:
                    headers["Authorization"] = auth
                else:
                    self.root.after(0, lambda f=pill_frame: f.avail_label.config(text="Error: Could not read ia credentials", foreground="red"))
                    self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
                    self.spn_queue.task_done()
                    continue
                    
            data = {
                "url": url,
                "capture_screenshot": "1" if self.spn_screenshot_var.get() else "0",
                "capture_outlinks": "1" if self.spn_outlinks_var.get() else "0",
                "force_get": "1"
            }
            
            try:
                resp = requests.post("https://web.archive.org/save/", data=data, headers=headers, timeout=20)
                if resp.status_code in [200, 429] or "job_id" in resp.text:
                    if resp.status_code == 429:
                        # Sometimes 429 still returns a job id or is just a hard block
                        self.root.after(0, lambda f=pill_frame: f.avail_label.config(text="Rate Limit Hit (429)", foreground="red"))
                        self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
                        self.root.after(0, self.alert_user)
                    else:
                        resp_data = resp.json()
                        job_id = resp_data.get("job_id")
                        if job_id:
                            # Poll for success
                            success = False
                            archive_url = ""
                            for _ in range(15): # Poll for up to 15*5 = 75 seconds
                                time.sleep(5)
                                status_resp = requests.get(f"https://web.archive.org/save/status/{job_id}", headers=headers, timeout=10)
                                if status_resp.status_code == 200:
                                    s_data = status_resp.json()
                                    if s_data.get("status") == "success":
                                        success = True
                                        ts = s_data.get("timestamp")
                                        archive_url = f"https://web.archive.org/web/{ts}/{url}"
                                        break
                                    elif s_data.get("status") == "error":
                                        break
                                        
                            if success:
                                self.root.after(0, lambda f=pill_frame, u=archive_url: self._on_spn_success(f, u))
                            else:
                                self.root.after(0, lambda f=pill_frame: f.avail_label.config(text="Status check timed out or failed", foreground="red"))
                                self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
                        else:
                            self.root.after(0, lambda f=pill_frame: f.avail_label.config(text="No job_id returned", foreground="red"))
                            self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
                else:
                    self.root.after(0, lambda f=pill_frame: f.avail_label.config(text=f"HTTP {resp.status_code}", foreground="red"))
                    self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
            except Exception as e:
                self.root.after(0, lambda f=pill_frame: f.avail_label.config(text=f"Error: {str(e)[:40]}", foreground="red"))
                self.root.after(0, lambda f=pill_frame: f.save_btn.config(state=tk.NORMAL, text="Retry"))
                
            self.spn_queue.task_done()
            
            # Enforce SPN delay before processing the next item
            delay = self.spn_delay_var.get()
            self.root.after(0, lambda: self.tab2_status_var.set(f"Waiting {delay}s cooldown..."))
            time.sleep(delay)
            self.root.after(0, lambda: self.tab2_status_var.set("Ready."))

    def _on_spn_success(self, pill_frame, archive_url):
        pill_frame.save_btn.config(text="Saved!", state=tk.DISABLED)
        pill_frame.avail_label.config(text="Successfully archived just now", foreground="green")
        pill_frame.result_var.set(archive_url)
        pill_frame.result_entry.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=5)
        pill_frame.rowconfigure(2, weight=1)

    # ---------------------------------------------------------
    # TAB 3: Metadata Editor Methods
    # ---------------------------------------------------------
    def load_metadata_cache(self):
        """Loads locally cached tags from archive_tags_cache.json."""
        self.metadata_cache = {}
        if os.path.exists("archive_tags_cache.json"):
            try:
                with open("archive_tags_cache.json", "r", encoding="utf-8") as f:
                    self.metadata_cache = json.load(f)
            except Exception as e:
                print(f"Error loading metadata cache: {e}")

    def save_metadata_cache(self):
        """Saves current tags cache to archive_tags_cache.json."""
        try:
            with open("archive_tags_cache.json", "w", encoding="utf-8") as f:
                json.dump(self.metadata_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving metadata cache: {e}")

    def create_tab3_widgets(self):
        """Builds the UI for Tab 3: Bulk Metadata Editor."""
        # 1. Top Control & Search Frame
        top_frame = ttk.LabelFrame(self.tab3_frame, text="Search & Item Selection", padding=(10, 8))
        top_frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        
        # Search row
        search_row = ttk.Frame(top_frame)
        search_row.pack(fill=tk.X, pady=(0, 6))
        
        ttk.Label(search_row, text="Search Videos:").pack(side=tk.LEFT, padx=(0, 5))
        self.meta_search_var = tk.StringVar()
        self.meta_search_entry = ttk.Entry(search_row, textvariable=self.meta_search_var, width=35)
        self.meta_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.meta_search_var.trace_add("write", lambda *_: self.filter_metadata_table())
        
        self.meta_clear_search_btn = ttk.Button(search_row, text="Clear", width=6, command=lambda: self.meta_search_var.set(""))
        self.meta_clear_search_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(search_row, text="Source:").pack(side=tk.LEFT, padx=(0, 4))
        self.meta_source_var = tk.StringVar(value="All")
        self.meta_source_combo = ttk.Combobox(
            search_row,
            textvariable=self.meta_source_var,
            values=["All", "App Uploads", "Legacy / Pre-App"],
            state="readonly",
            width=15
        )
        self.meta_source_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.meta_source_combo.bind("<<ComboboxSelected>>", lambda *_: self.filter_metadata_table())
        
        self.meta_sync_btn = ttk.Button(search_row, text="Sync with Account", command=self.trigger_ia_sync)
        self.meta_sync_btn.pack(side=tk.RIGHT)
        
        self.meta_sync_status_label = ttk.Label(search_row, text="", font=("TkDefaultFont", 8, "italic"))
        self.meta_sync_status_label.pack(side=tk.RIGHT, padx=10)
        
        # Selection row
        sel_row = ttk.Frame(top_frame)
        sel_row.pack(fill=tk.X)
        
        ttk.Button(sel_row, text="Select Filtered", command=self.select_filtered_items).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sel_row, text="Select All", command=self.select_all_items).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sel_row, text="Deselect All", command=self.deselect_all_items).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sel_row, text="Invert Selection", command=self.invert_selection).pack(side=tk.LEFT, padx=(0, 10))
        
        self.meta_sel_count_label = ttk.Label(sel_row, text="Selected: 0 / 0", font=("TkDefaultFont", 9, "bold"))
        self.meta_sel_count_label.pack(side=tk.LEFT, padx=5)

        # 2. Center Table (Treeview)
        tree_frame = ttk.Frame(self.tab3_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        
        # Treeview styling
        style = ttk.Style()
        style.configure("Meta.Treeview", rowheight=26)
        
        columns = ("sel", "date", "id", "title", "lang", "tags", "status")
        self.meta_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended", style="Meta.Treeview")
        
        self.meta_tree.heading("sel", text="[✓]", command=self.toggle_all_filtered)
        self.meta_tree.heading("date", text="Archive Date", command=lambda: self.sort_metadata_table("date"))
        self.meta_tree.heading("id", text="Identifier / ID", command=lambda: self.sort_metadata_table("id"))
        self.meta_tree.heading("title", text="Title", command=lambda: self.sort_metadata_table("title"))
        self.meta_tree.heading("lang", text="Lang", command=lambda: self.sort_metadata_table("lang"))
        self.meta_tree.heading("tags", text="Current Subject Tags", command=lambda: self.sort_metadata_table("tags"))
        self.meta_tree.heading("status", text="Status", command=lambda: self.sort_metadata_table("status"))
        
        self.meta_tree.column("sel", width=42, anchor="center", stretch=False)
        self.meta_tree.column("date", width=130, anchor="center", stretch=False)
        self.meta_tree.column("id", width=140, anchor="center", stretch=False)
        self.meta_tree.column("title", width=300, anchor="w", stretch=True)
        self.meta_tree.column("lang", width=65, anchor="center", stretch=False)
        self.meta_tree.column("tags", width=250, anchor="w", stretch=True)
        self.meta_tree.column("status", width=95, anchor="center", stretch=False)
        
        tree_vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.meta_tree.yview)
        tree_hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.meta_tree.xview)
        self.meta_tree.configure(yscrollcommand=tree_vscroll.set, xscrollcommand=tree_hscroll.set)
        
        self.meta_tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_vscroll.grid(row=0, column=1, sticky=tk.NS)
        tree_hscroll.grid(row=1, column=0, sticky=tk.EW)
        
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        # Event bindings
        self.meta_tree.bind("<Button-1>", self.on_tree_click)
        self.meta_tree.bind("<space>", self.on_tree_space)
        self.meta_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 3. Bottom Overwrite & Controls Frame
        bottom_frame = ttk.LabelFrame(self.tab3_frame, text="Bulk Metadata Overwrite", padding=(10, 8))
        bottom_frame.pack(fill=tk.X, padx=10, pady=(4, 8))
        
        # Tags row
        tag_input_row = ttk.Frame(bottom_frame)
        tag_input_row.pack(fill=tk.X, pady=(0, 4))
        
        self.meta_apply_tags_var = tk.BooleanVar(value=True)
        self.meta_apply_tags_chk = ttk.Checkbutton(tag_input_row, text="Update Tags:", variable=self.meta_apply_tags_var)
        self.meta_apply_tags_chk.pack(side=tk.LEFT, padx=(0, 5))
        
        self.meta_tags_combo = ttk.Combobox(tag_input_row, values=self.tags_presets)
        self.meta_tags_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.meta_save_preset_btn = ttk.Button(tag_input_row, text="Save Preset", command=self.save_meta_tags_preset)
        self.meta_save_preset_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.meta_del_preset_btn = ttk.Button(tag_input_row, text="Delete Preset", command=self.delete_meta_tags_preset)
        self.meta_del_preset_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Language row
        lang_input_row = ttk.Frame(bottom_frame)
        lang_input_row.pack(fill=tk.X, pady=(0, 6))
        
        self.meta_apply_lang_var = tk.BooleanVar(value=False)
        self.meta_apply_lang_chk = ttk.Checkbutton(lang_input_row, text="Update Language:", variable=self.meta_apply_lang_var)
        self.meta_apply_lang_chk.pack(side=tk.LEFT, padx=(0, 5))
        
        self.meta_lang_combo = ttk.Combobox(
            lang_input_row,
            values=["Spanish (spa)", "English (eng)", "French (fre)", "German (ger)", "Italian (ita)", "Portuguese (por)", "Russian (rus)", "Japanese (jpn)", "Chinese (chi)", "None (Clear Language)"],
            width=26
        )
        self.meta_lang_combo.set("Spanish (spa)")
        self.meta_lang_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(lang_input_row, text="(Tip: Check the boxes for the fields you want to update)", font=("TkDefaultFont", 8, "italic")).pack(side=tk.LEFT)
        
        # Action row
        action_row = ttk.Frame(bottom_frame)
        action_row.pack(fill=tk.X, pady=(0, 4))
        
        self.meta_update_btn = ttk.Button(
            action_row, 
            text="Overwrite Metadata for Selected Items", 
            command=self.start_bulk_metadata_update
        )
        self.meta_update_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.meta_cancel_btn = ttk.Button(
            action_row, 
            text="Cancel", 
            command=self.cancel_bulk_metadata_update, 
            state=tk.DISABLED
        )
        self.meta_cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.meta_status_label = ttk.Label(action_row, text="Ready. Double-click a row to load its metadata.", font=("TkDefaultFont", 8, "italic"))
        self.meta_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Progress bar
        self.meta_prog_bar = ttk.Progressbar(bottom_frame, orient="horizontal", mode="determinate")
        self.meta_prog_bar.pack(fill=tk.X, pady=(2, 0))
        
        # Populate table
        self.load_items_from_history()

    def load_items_from_history(self):
        """Populates items from local metadata cache (account history) and enriches with local history."""
        self.meta_all_items = []
        
        # 1. Read archive_history.log to enrich with exact YouTube IDs and timestamps
        history_map = {}
        if os.path.exists("archive_history.log"):
            try:
                with open("archive_history.log", "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        parts = line.strip().split(" | ")
                        if len(parts) >= 4:
                            date_str = parts[0].strip("[]")
                            epoch = float(parts[1]) if parts[1].replace('.', '', 1).isdigit() else 0
                            vid = parts[2].strip()
                            hist_ident = f"yt-archive-{vid}".lower()
                            hist_ident = re.sub(r'[^a-z0-9\-]', '-', hist_ident)
                            history_map[hist_ident] = {
                                "date": date_str,
                                "timestamp": epoch,
                                "video_id": vid
                            }
            except Exception as e:
                print(f"Error reading archive_history.log: {e}")
                
        # 2. Iterate over self.metadata_cache (ground truth of account items)
        for ident, cached in self.metadata_cache.items():
            hist_info = history_map.get(ident.lower(), {})
            vid = hist_info.get("video_id") or cached.get("video_id", "")
            date_str = hist_info.get("date") or cached.get("date", "")
            epoch = hist_info.get("timestamp", 0)
            if not epoch and date_str:
                try:
                    epoch = time.mktime(time.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S"))
                except Exception:
                    epoch = 0
                    
            source = cached.get("source")
            if not source:
                source = "app" if ident.lower().startswith("yt-archive-") else "legacy"
                
            status = "Ready" if source == "app" else "Legacy"
            
            lang = cached.get("language", "")
            if isinstance(lang, list):
                lang = lang[0] if lang else ""
            elif lang is None:
                lang = ""
                
            self.meta_all_items.append({
                "identifier": ident,
                "vid": vid,
                "video_id": vid,
                "title": cached.get("title", "Unknown Title"),
                "date": date_str,
                "timestamp": epoch,
                "tags": cached.get("tags", []),
                "language": lang,
                "status": status,
                "source": source,
                "creator": cached.get("creator", "")
            })
            
        # Apply default sort (newest first)
        self.meta_all_items.sort(key=lambda x: x["timestamp"], reverse=self.meta_sort_reverse)
        self.filter_metadata_table()

    def filter_metadata_table(self):
        """Filters items based on search entry and source dropdown, then updates Treeview."""
        query = self.meta_search_var.get().strip().lower()
        source_filter = getattr(self, 'meta_source_var', None)
        source_val = source_filter.get() if source_filter else "All"
        
        self.meta_filtered_items = []
        for item in self.meta_all_items:
            # Check source filter
            if source_val == "App Uploads" and item.get("source") != "app":
                continue
            if source_val == "Legacy / Pre-App" and item.get("source") != "legacy":
                continue
                
            # Check query filter
            if not query:
                self.meta_filtered_items.append(item)
            else:
                title_match = query in item["title"].lower()
                id_match = query in item["identifier"].lower() or query in item.get("video_id", "").lower()
                tags_match = any(query in t.lower() for t in item["tags"])
                lang_match = query in (item.get("language") or "").lower()
                creator_match = query in item.get("creator", "").lower()
                if title_match or id_match or tags_match or lang_match or creator_match:
                    self.meta_filtered_items.append(item)
                    
        # Repopulate treeview
        self.meta_tree.delete(*self.meta_tree.get_children())
        for item in self.meta_filtered_items:
            ident = item["identifier"]
            sel_char = "☑" if ident in self.meta_selected_ids else "☐"
            tags_str = ", ".join(item["tags"]) if item["tags"] else "—"
            lang_str = item.get("language") or "—"
            disp_id = item.get("video_id") or ident
            self.meta_tree.insert(
                "",
                tk.END,
                iid=ident,
                values=(sel_char, item.get("date", ""), disp_id, item["title"], lang_str, tags_str, item["status"])
            )
            
        self.update_selection_count_label()

    def update_selection_count_label(self):
        """Updates the selection count readout."""
        sel_count = len(self.meta_selected_ids)
        total_count = len(self.meta_all_items)
        filt_count = len(self.meta_filtered_items)
        if filt_count < total_count:
            self.meta_sel_count_label.config(text=f"Selected: {sel_count} / Total: {total_count} (Showing: {filt_count})")
        else:
            self.meta_sel_count_label.config(text=f"Selected: {sel_count} / Total: {total_count}")

    def toggle_item_selection(self, ident):
        """Toggles selection for a single item by identifier."""
        if ident in self.meta_selected_ids:
            self.meta_selected_ids.remove(ident)
            sel_char = "☐"
        else:
            self.meta_selected_ids.add(ident)
            sel_char = "☑"
            
        if self.meta_tree.exists(ident):
            cur_vals = list(self.meta_tree.item(ident, "values"))
            cur_vals[0] = sel_char
            self.meta_tree.item(ident, values=cur_vals)
            
        self.update_selection_count_label()

    def on_tree_click(self, event):
        """Handles single click in treeview to toggle checkbox when clicking the sel column."""
        region = self.meta_tree.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            col = self.meta_tree.identify_column(event.x)
            item_ident = self.meta_tree.identify_row(event.y)
            if item_ident and col == "#1":
                self.toggle_item_selection(item_ident)

    def on_tree_space(self, event):
        """Toggles checkboxes for all highlighted rows when spacebar is pressed."""
        selected_rows = self.meta_tree.selection()
        if not selected_rows:
            focused = self.meta_tree.focus()
            if focused:
                selected_rows = [focused]
                
        all_checked = all(r in self.meta_selected_ids for r in selected_rows)
        for r in selected_rows:
            if all_checked:
                self.meta_selected_ids.discard(r)
                sel_char = "☐"
            else:
                self.meta_selected_ids.add(r)
                sel_char = "☑"
            if self.meta_tree.exists(r):
                cur_vals = list(self.meta_tree.item(r, "values"))
                cur_vals[0] = sel_char
                self.meta_tree.item(r, values=cur_vals)
                
        self.update_selection_count_label()
        return "break"

    def on_tree_double_click(self, event):
        """Loads the clicked row's tags and language into the edit inputs."""
        item_ident = self.meta_tree.identify_row(event.y)
        if not item_ident:
            item_ident = self.meta_tree.focus()
        if item_ident and self.meta_tree.exists(item_ident):
            item_data = next((x for x in self.meta_all_items if x["identifier"] == item_ident), None)
            if item_data:
                tags = item_data.get("tags", [])
                tags_str = ", ".join(tags)
                self.meta_tags_combo.set(tags_str)
                
                lang = item_data.get("language", "")
                if lang:
                    matched = False
                    for val in self.meta_lang_combo["values"]:
                        if f"({lang.lower()})" in val.lower() or val.lower().startswith(lang.lower()):
                            self.meta_lang_combo.set(val)
                            matched = True
                            break
                    if not matched:
                        self.meta_lang_combo.set(lang)
                else:
                    self.meta_lang_combo.set("None (Clear Language)")
                    
                self.meta_status_label.config(text=f"Loaded metadata from '{item_data['title'][:35]}...'")

    def select_filtered_items(self):
        """Selects all currently visible filtered items."""
        for item in self.meta_filtered_items:
            ident = item["identifier"]
            self.meta_selected_ids.add(ident)
            if self.meta_tree.exists(ident):
                cur_vals = list(self.meta_tree.item(ident, "values"))
                cur_vals[0] = "☑"
                self.meta_tree.item(ident, values=cur_vals)
        self.update_selection_count_label()

    def select_all_items(self):
        """Selects all items."""
        for item in self.meta_all_items:
            ident = item["identifier"]
            self.meta_selected_ids.add(ident)
            if self.meta_tree.exists(ident):
                cur_vals = list(self.meta_tree.item(ident, "values"))
                cur_vals[0] = "☑"
                self.meta_tree.item(ident, values=cur_vals)
        self.update_selection_count_label()

    def deselect_all_items(self):
        """Deselects all items."""
        self.meta_selected_ids.clear()
        for item in self.meta_filtered_items:
            ident = item["identifier"]
            if self.meta_tree.exists(ident):
                cur_vals = list(self.meta_tree.item(ident, "values"))
                cur_vals[0] = "☐"
                self.meta_tree.item(ident, values=cur_vals)
        self.update_selection_count_label()

    def invert_selection(self):
        """Inverts selection for currently filtered items."""
        for item in self.meta_filtered_items:
            ident = item["identifier"]
            if ident in self.meta_selected_ids:
                self.meta_selected_ids.remove(ident)
                sel_char = "☐"
            else:
                self.meta_selected_ids.add(ident)
                sel_char = "☑"
            if self.meta_tree.exists(ident):
                cur_vals = list(self.meta_tree.item(ident, "values"))
                cur_vals[0] = sel_char
                self.meta_tree.item(ident, values=cur_vals)
        self.update_selection_count_label()

    def toggle_all_filtered(self):
        """Header checkbox click: toggles all filtered."""
        if any(item["identifier"] not in self.meta_selected_ids for item in self.meta_filtered_items):
            self.select_filtered_items()
        else:
            self.deselect_all_items()

    def sort_metadata_table(self, col):
        """Sorts table by column."""
        if self.meta_sort_col == col:
            self.meta_sort_reverse = not self.meta_sort_reverse
        else:
            self.meta_sort_col = col
            self.meta_sort_reverse = False
            
        key_funcs = {
            "sel": lambda x: x["identifier"] in self.meta_selected_ids,
            "date": lambda x: x["timestamp"],
            "id": lambda x: (x.get("video_id") or x["identifier"]).lower(),
            "title": lambda x: x["title"].lower(),
            "lang": lambda x: (x.get("language") or "").lower(),
            "tags": lambda x: ", ".join(x["tags"]).lower(),
            "status": lambda x: x["status"].lower(),
        }
        key_fn = key_funcs.get(col, lambda x: x["timestamp"])
        self.meta_all_items.sort(key=key_fn, reverse=self.meta_sort_reverse)
        self.filter_metadata_table()

    def save_meta_tags_preset(self):
        """Saves current tags as a preset."""
        val = self.meta_tags_combo.get().strip()
        if val and val not in self.tags_presets:
            self.tags_presets.append(val)
            self.tags_combo['values'] = self.tags_presets
            self.meta_tags_combo['values'] = self.tags_presets
            self.save_settings()
            messagebox.showinfo("Preset Saved", "Tags preset saved successfully!")

    def delete_meta_tags_preset(self):
        """Deletes the current preset from saved presets."""
        val = self.meta_tags_combo.get().strip()
        if not val:
            return
        if val in self.tags_presets:
            if messagebox.askyesno("Delete Preset", f"Are you sure you want to delete this preset?\n\n'{val}'"):
                self.tags_presets.remove(val)
                self.tags_combo['values'] = self.tags_presets
                self.meta_tags_combo['values'] = self.tags_presets
                self.meta_tags_combo.set("")
                self.save_settings()
                messagebox.showinfo("Preset Deleted", "Tags preset deleted successfully!")
        else:
            messagebox.showwarning("Not Found", "The current tags do not match any saved preset.")

    def trigger_ia_sync(self):
        """Spawns background sync from Internet Archive Search API across the entire account."""
        if hasattr(self, '_sync_in_progress') and self._sync_in_progress:
            messagebox.showinfo("Sync in Progress", "Account sync is already running.")
            return
            
        self._sync_in_progress = True
        self.meta_sync_btn.config(state=tk.DISABLED)
        self.meta_sync_status_label.config(text="Connecting to Archive.org account...")
        threading.Thread(target=self._ia_sync_worker, daemon=True).start()

    def _ia_sync_worker(self):
        """Worker thread to fetch all account items and consolidate with local archive ledger."""
        try:
            # Determine account uploader query dynamically
            uploader_val = self.get_ia_account_identifier()
            if not uploader_val:
                self.root.after(0, lambda: self.meta_sync_status_label.config(text="Error: No IA account credentials configured."))
                self._sync_in_progress = False
                self.meta_sync_btn.config(state=tk.NORMAL)
                return
            query = f"uploader:{uploader_val}"
            s = ia.search_items(query, fields=["identifier", "title", "subject", "language", "publicdate", "addeddate", "date", "creator", "mediatype"])
            total = getattr(s, "num_found", 0)
            
            self.root.after(0, lambda: self.meta_sync_status_label.config(text=f"Fetching {total} account items..."))
            
            count = 0
            app_count = 0
            legacy_count = 0
            new_txt_entries = []
            
            # Read current ledger IDs
            ledger_path = self.get_ledger_path()
            current_txt_ids = set()
            if os.path.exists(ledger_path):
                with open(ledger_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("youtube "):
                            current_txt_ids.add(line.strip().split()[1])
                            
            for item in s:
                ident = item.get("identifier", "")
                if not ident:
                    continue
                title = item.get("title", "Unknown Title")
                subj = item.get("subject", [])
                if isinstance(subj, str):
                    subj = [subj]
                date = item.get("publicdate") or item.get("addeddate") or item.get("date") or ""
                if "T" in date:
                    date = date.replace("T", " ").replace("Z", "")
                    
                is_app = ident.lower().startswith("yt-archive-")
                if is_app:
                    vid = ident[11:]
                    app_count += 1
                    source = "app"
                    # Check if missing from local ledger
                    if vid and vid not in current_txt_ids:
                        new_txt_entries.append((vid, title))
                        current_txt_ids.add(vid)
                else:
                    vid = ""
                    legacy_count += 1
                    source = "legacy"
                    
                lang = item.get("language", "")
                if isinstance(lang, list):
                    lang = lang[0] if lang else ""
                elif lang is None:
                    lang = ""
                    
                self.metadata_cache[ident] = {
                    "identifier": ident,
                    "video_id": vid,
                    "title": title,
                    "tags": subj,
                    "language": lang,
                    "date": date,
                    "source": source,
                    "creator": item.get("creator", "")
                }
                count += 1
                if count % 50 == 0:
                    self.root.after(0, lambda c=count, t=total: self.meta_sync_status_label.config(text=f"Fetched {c}/{t} items..."))
                    
            # Consolidate into local ledger
            if new_txt_entries:
                try:
                    with open(ledger_path, "a", encoding="utf-8") as f:
                        for vid, t in new_txt_entries:
                            f.write(f"# {t} (Synced from Account)\nyoutube {vid}\n\n")
                except Exception as e:
                    print(f"Error appending to ledger: {e}")
                    
            self.save_metadata_cache()
            self.root.after(0, lambda: self._on_ia_sync_complete(count, app_count, legacy_count, len(new_txt_entries)))
        except Exception as e:
            self.root.after(0, lambda err=e: self._on_ia_sync_error(err))

    def _on_ia_sync_complete(self, count, app_count, legacy_count, added_to_ledger):
        self._sync_in_progress = False
        self.meta_sync_btn.config(state=tk.NORMAL)
        self.meta_sync_status_label.config(text=f"✓ Synced {count} items")
        self.load_items_from_history()
        msg = f"Successfully synced {count} total items from your Archive.org account!\n\n• App Uploads: {app_count}\n• Legacy / Pre-App Uploads: {legacy_count}"
        if added_to_ledger > 0:
            msg += f"\n• Consolidated {added_to_ledger} missing item(s) into local archive.txt."
        else:
            msg += "\n• Local archive.txt ledger is fully up to date."
        messagebox.showinfo("Account Sync Complete", msg)

    def _on_ia_sync_error(self, err):
        self._sync_in_progress = False
        self.meta_sync_btn.config(state=tk.NORMAL)
        self.meta_sync_status_label.config(text="Sync failed")
        messagebox.showerror("Sync Error", f"Could not sync from Archive.org: {err}")

    def start_bulk_metadata_update(self):
        """Initiates the bulk metadata overwrite process."""
        selected_idents = [ident for ident in self.meta_selected_ids if any(x["identifier"] == ident for x in self.meta_all_items)]
        if not selected_idents:
            messagebox.showwarning("No Items Selected", "Please select at least one video to update using the checkboxes.")
            return
            
        update_tags = self.meta_apply_tags_var.get()
        update_lang = self.meta_apply_lang_var.get()

        if not update_tags and not update_lang:
            messagebox.showwarning("No Fields Selected", "Please check at least one field to update ('Update Tags' or 'Update Language').")
            return

        new_tags = []
        if update_tags:
            tags_str = self.meta_tags_combo.get().strip()
            new_tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            if not new_tags:
                if not messagebox.askyesno("Confirm Clear Tags", "You checked 'Update Tags' but did not enter any tags.\n\nThis will REMOVE/CLEAR all subject tags for the selected items.\n\nAre you sure you want to proceed?"):
                    return

        target_lang_code = ""
        if update_lang:
            raw_lang = self.meta_lang_combo.get().strip()
            if raw_lang.lower().startswith("none") or raw_lang == "":
                target_lang_code = ""
            else:
                m = re.search(r'\(([a-z0-9]{2,3})\)', raw_lang, re.IGNORECASE)
                if m:
                    target_lang_code = m.group(1).lower()
                else:
                    target_lang_code = raw_lang.lower()

        # Build confirmation message
        preview_items = []
        for ident in selected_idents[:3]:
            item_obj = next((x for x in self.meta_all_items if x["identifier"] == ident), None)
            title = item_obj["title"] if item_obj else ident
            preview_items.append(f"• {title}")
        if len(selected_idents) > 3:
            preview_items.append(f"...and {len(selected_idents) - 3} more")

        changes_summary = []
        if update_tags:
            changes_summary.append(f"• Tags: {', '.join(new_tags) if new_tags else '[CLEAR ALL TAGS]'}")
        else:
            changes_summary.append("• Tags: (Keep Existing)")

        if update_lang:
            changes_summary.append(f"• Language: {target_lang_code if target_lang_code else '[CLEAR LANGUAGE]'}")
        else:
            changes_summary.append("• Language: (Keep Existing)")

        msg = (
            f"You are about to overwrite metadata for {len(selected_idents)} item(s) on Internet Archive:\n\n"
            + "\n".join(changes_summary) + "\n\n"
            f"Target Items:\n" + "\n".join(preview_items) + "\n\n"
            f"Do you want to proceed?"
        )
        if not messagebox.askyesno("Confirm Bulk Metadata Overwrite", msg):
            return
                
        # Setup UI for execution
        self.meta_stop_event.clear()
        self.meta_update_btn.config(state=tk.DISABLED)
        self.meta_cancel_btn.config(state=tk.NORMAL)
        self.meta_sync_btn.config(state=tk.DISABLED)
        self.meta_prog_bar["value"] = 0
        self.meta_prog_bar["maximum"] = len(selected_idents)
        self.meta_status_label.config(text=f"Starting bulk update for {len(selected_idents)} item(s)...")
        
        self.meta_worker_thread = threading.Thread(
            target=self._bulk_metadata_worker, 
            args=(selected_idents, update_tags, new_tags, update_lang, target_lang_code), 
            daemon=True
        )
        self.meta_worker_thread.start()

    def cancel_bulk_metadata_update(self):
        """Requests cancellation of bulk metadata update."""
        self.meta_stop_event.set()
        self.meta_cancel_btn.config(state=tk.DISABLED)
        self.meta_status_label.config(text="Stopping bulk update... please wait.")

    def _bulk_metadata_worker(self, identifiers, update_tags, new_tags, update_lang, target_lang_code):
        """Background worker that calls Archive.org Metadata API with rate limiting."""
        total = len(identifiers)
        success_count = 0
        fail_count = 0
        
        for idx, ident in enumerate(identifiers):
            if self.meta_stop_event.is_set():
                break
                
            # Find item title
            item_data = next((x for x in self.meta_all_items if x["identifier"] == ident), None)
            title = item_data["title"] if item_data else ident
            old_tags = self.metadata_cache.get(ident, {}).get("tags", [])
            old_lang = self.metadata_cache.get(ident, {}).get("language", "")
            
            # Update UI to in-progress
            self.root.after(0, lambda i=idx, t=total, idnt=ident: self._update_meta_ui_progress(i, t, f"Updating ({i+1}/{t}): {idnt}..."))
            self.root.after(0, lambda idnt=ident: self._set_row_status(idnt, "Updating..."))
            
            try:
                item = ia.get_item(ident)
                patch_dict = {}
                if update_tags:
                    patch_dict["subject"] = new_tags if new_tags else "REMOVE_TAG"
                if update_lang:
                    patch_dict["language"] = target_lang_code if target_lang_code else "REMOVE_TAG"
                
                # Apply metadata patch with priority -5
                resp = item.modify_metadata(patch_dict, priority=-5)
                
                if resp.status_code == 200:
                    success_count += 1
                    # Update cache
                    if ident in self.metadata_cache:
                        if update_tags:
                            self.metadata_cache[ident]["tags"] = new_tags
                        if update_lang:
                            self.metadata_cache[ident]["language"] = target_lang_code
                        self.metadata_cache[ident]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    if item_data:
                        if update_tags:
                            item_data["tags"] = new_tags
                        if update_lang:
                            item_data["language"] = target_lang_code
                        item_data["status"] = "✓ Updated"
                        
                    self.root.after(0, lambda idnt=ident, ut=update_tags, t=new_tags, ul=update_lang, l=target_lang_code: self._on_item_meta_success(idnt, ut, t, ul, l))
                    
                    # Audit log
                    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    log_details = []
                    if update_tags:
                        log_details.append(f"Tags: {old_tags} -> {new_tags}")
                    if update_lang:
                        log_details.append(f"Lang: '{old_lang}' -> '{target_lang_code}'")
                    with open("metadata_edits.log", "a", encoding="utf-8") as f:
                        f.write(f"[{now_str}] SUCCESS | {ident} | {title} | {' | '.join(log_details)}\n")
                else:
                    fail_count += 1
                    err_msg = resp.text[:100]
                    if item_data:
                        item_data["status"] = "✗ Error"
                    self.root.after(0, lambda idnt=ident: self._set_row_status(idnt, "✗ Error"))
                    
                    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    with open("metadata_edits.log", "a", encoding="utf-8") as f:
                        f.write(f"[{now_str}] ERROR ({resp.status_code}) | {ident} | {title} | {err_msg}\n")
                        
            except Exception as e:
                fail_count += 1
                if item_data:
                    item_data["status"] = "✗ Error"
                self.root.after(0, lambda idnt=ident: self._set_row_status(idnt, "✗ Error"))
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                with open("metadata_edits.log", "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] EXCEPTION | {ident} | {title} | {e}\n")
                    
            # Courtesy delay between items (1.5s) to respect IA rate limits
            for _ in range(15):
                if self.meta_stop_event.is_set():
                    break
                time.sleep(0.1)
                
        self.save_metadata_cache()
        self.root.after(0, lambda s=success_count, f=fail_count, stopped=self.meta_stop_event.is_set(): self._on_bulk_meta_finish(s, f, stopped))

    def _update_meta_ui_progress(self, current, total, text):
        self.meta_prog_bar["value"] = current + 1
        self.meta_status_label.config(text=text)

    def _set_row_status(self, ident, status_text):
        if self.meta_tree.exists(ident):
            cur_vals = list(self.meta_tree.item(ident, "values"))
            if len(cur_vals) >= 7:
                cur_vals[6] = status_text
                self.meta_tree.item(ident, values=cur_vals)

    def _on_item_meta_success(self, ident, update_tags, new_tags, update_lang, new_lang):
        if self.meta_tree.exists(ident):
            cur_vals = list(self.meta_tree.item(ident, "values"))
            if len(cur_vals) >= 7:
                if update_lang:
                    cur_vals[4] = new_lang if new_lang else "—"
                if update_tags:
                    cur_vals[5] = ", ".join(new_tags) if new_tags else "—"
                cur_vals[6] = "✓ Updated"
                self.meta_tree.item(ident, values=cur_vals)

    def _on_bulk_meta_finish(self, success_count, fail_count, was_stopped):
        self.meta_update_btn.config(state=tk.NORMAL)
        self.meta_cancel_btn.config(state=tk.DISABLED)
        self.meta_sync_btn.config(state=tk.NORMAL)
        
        status_msg = f"Completed: {success_count} updated"
        if fail_count > 0:
            status_msg += f", {fail_count} failed"
        if was_stopped:
            status_msg += " (Stopped by user)"
            
        self.meta_status_label.config(text=status_msg)
        
        detail_msg = f"Bulk update finished!\n\nSuccessfully updated: {success_count}\nFailed: {fail_count}"
        if was_stopped:
            detail_msg += "\n\nThe process was stopped early by user request."
        messagebox.showinfo("Bulk Update Complete", detail_msg)

    def get_ia_credentials_status(self):
        """Checks if valid IA S3 credentials exist in the user's local ia.ini."""
        try:
            cfg = ia.config.get_config()
            s3 = cfg.get("s3", {})
            access = s3.get("access")
            secret = s3.get("secret")
            if access and secret:
                return True, access
        except Exception:
            pass
        return False, None

    def check_ia_credentials_startup(self):
        """Prompts user on first startup if no IA credentials are configured on this computer."""
        has_keys, access = self.get_ia_credentials_status()
        if not has_keys:
            ans = messagebox.askyesno(
                "Internet Archive Setup Required",
                "Welcome to The Archiver!\n\nNo Internet Archive credentials were found on this computer.\n\n"
                "To upload videos and use archive features, you need to configure your Internet Archive account.\n\n"
                "Would you like to configure your credentials now?"
            )
            if ans:
                self.open_ia_credentials_dialog()
        else:
            masked = access[:4] + "***" if access and len(access) >= 4 else "Connected"
            if hasattr(self, 'ia_account_btn'):
                self.ia_account_btn.config(text=f"🔑 IA: {masked}")

    def open_ia_credentials_dialog(self):
        """Opens the Internet Archive Credentials & Account Setup dialog."""
        import webbrowser
        dialog = tk.Toplevel(self.root)
        dialog.title("Internet Archive Account Setup")
        dialog.geometry("540x510")
        dialog.minsize(500, 470)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center over parent window
        dialog.update_idletasks()
        try:
            x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
            y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # 1. Current Status Frame
        status_frame = ttk.LabelFrame(dialog, text="Account Connection Status", padding=(10, 8))
        status_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        has_keys, access = self.get_ia_credentials_status()
        status_text = f"✓ Configured & Active (Access Key: {access[:4]}***)" if has_keys else "⚠ Not Configured - Credentials Missing"
        status_color = "#28a745" if has_keys else "#dc3545"
        status_lbl = ttk.Label(status_frame, text=status_text, foreground=status_color, font=("Segoe UI", 9, "bold"))
        status_lbl.pack(anchor=tk.W)

        # 2. Setup Notebook
        mode_notebook = ttk.Notebook(dialog)
        mode_notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Tab 1: S3 API Keys (Recommended)
        tab_s3 = ttk.Frame(mode_notebook, padding=(12, 10))
        mode_notebook.add(tab_s3, text="S3 API Keys (Recommended)")

        ttk.Label(tab_s3, text="You can generate or view your free S3 API keys on Archive.org:", wraplength=460).pack(anchor=tk.W, pady=(0, 4))
        
        link_btn = ttk.Button(tab_s3, text="🔗 Open https://archive.org/account/s3.php", command=lambda: webbrowser.open("https://archive.org/account/s3.php"))
        link_btn.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(tab_s3, text="S3 Access Key:").pack(anchor=tk.W, pady=(2, 2))
        s3_access_entry = ttk.Entry(tab_s3, width=45)
        s3_access_entry.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(tab_s3, text="S3 Secret Key:").pack(anchor=tk.W, pady=(2, 2))
        s3_secret_entry = ttk.Entry(tab_s3, width=45, show="*")
        s3_secret_entry.pack(fill=tk.X, pady=(0, 6))

        show_secret_var = tk.BooleanVar(value=False)
        def toggle_show_secret():
            s3_secret_entry.config(show="" if show_secret_var.get() else "*")
        ttk.Checkbutton(tab_s3, text="Show secret key", variable=show_secret_var, command=toggle_show_secret).pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(tab_s3, text="Account Email / Screenname (Optional, for account search):").pack(anchor=tk.W, pady=(2, 2))
        s3_email_entry = ttk.Entry(tab_s3, width=45)
        s3_email_entry.pack(fill=tk.X, pady=(0, 4))
        if hasattr(self, 'ia_uploader_email') and self.ia_uploader_email:
            s3_email_entry.insert(0, self.ia_uploader_email)

        # Tab 2: Login with Email & Password
        tab_login = ttk.Frame(mode_notebook, padding=(12, 10))
        mode_notebook.add(tab_login, text="Log In with Email & Password")

        ttk.Label(tab_login, text="Log in with your Archive.org credentials to automatically fetch and save your keys:", wraplength=460).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(tab_login, text="Archive.org Email:").pack(anchor=tk.W, pady=(2, 2))
        login_email_entry = ttk.Entry(tab_login, width=45)
        login_email_entry.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(tab_login, text="Archive.org Password:").pack(anchor=tk.W, pady=(2, 2))
        login_pwd_entry = ttk.Entry(tab_login, width=45, show="*")
        login_pwd_entry.pack(fill=tk.X, pady=(0, 6))

        show_pwd_var = tk.BooleanVar(value=False)
        def toggle_show_pwd():
            login_pwd_entry.config(show="" if show_pwd_var.get() else "*")
        ttk.Checkbutton(tab_login, text="Show password", variable=show_pwd_var, command=toggle_show_pwd).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(tab_login, text="Note: If your account uses Two-Factor Authentication (2FA), please use the S3 API Keys tab instead.", font=("Segoe UI", 8), foreground="gray", wraplength=460).pack(anchor=tk.W, pady=(6, 0))

        # Action status label
        cred_status_lbl = ttk.Label(dialog, text="", foreground="gray")
        cred_status_lbl.pack(fill=tk.X, padx=15, pady=(2, 2))

        # Bottom Button Frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=(6, 12))

        save_btn = ttk.Button(btn_frame, text="💾 Save Credentials")
        try:
            save_btn.config(style="Accent.TButton")
        except Exception:
            pass
        save_btn.pack(side=tk.LEFT, padx=(0, 6))

        close_btn = ttk.Button(btn_frame, text="Close", command=dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

        def save_worker():
            selected_tab = mode_notebook.index(mode_notebook.select())
            try:
                if selected_tab == 0:
                    # S3 Keys Tab
                    acc = s3_access_entry.get().strip()
                    sec = s3_secret_entry.get().strip()
                    em = s3_email_entry.get().strip()
                    if not acc or not sec:
                        dialog.after(0, lambda: messagebox.showerror("Missing Keys", "Please enter both S3 Access Key and Secret Key.", parent=dialog))
                        dialog.after(0, lambda: save_btn.config(state=tk.NORMAL))
                        return
                    
                    auth_config = {
                        "s3": {"access": acc, "secret": sec},
                        "general": {"screenname": em} if em else {},
                        "cookies": {"logged-in-user": em} if em else {}
                    }
                    ia.config.write_config_file(auth_config)
                    if em:
                        self.ia_uploader_email = em
                        self.save_settings()

                else:
                    # Login Tab
                    em = login_email_entry.get().strip()
                    pwd = login_pwd_entry.get().strip()
                    if not em or not pwd:
                        dialog.after(0, lambda: messagebox.showerror("Missing Fields", "Please enter your email and password.", parent=dialog))
                        dialog.after(0, lambda: save_btn.config(state=tk.NORMAL))
                        return
                    
                    dialog.after(0, lambda: cred_status_lbl.config(text="Authenticating with Archive.org..."))
                    auth_config = ia.config.get_auth_config(em, pwd)
                    ia.config.write_config_file(auth_config)
                    self.ia_uploader_email = em
                    self.save_settings()

                def on_success():
                    save_btn.config(state=tk.NORMAL)
                    cred_status_lbl.config(text="Credentials saved successfully!")
                    has_k, acc_k = self.get_ia_credentials_status()
                    if has_k:
                        masked = acc_k[:4] + "***" if len(acc_k) >= 4 else "Connected"
                        self.ia_account_btn.config(text=f"🔑 IA: {masked}")
                    messagebox.showinfo("Success", "Internet Archive credentials configured successfully!\n\nYour keys are safely saved to your local user profile (ia.ini) and will never be shared.", parent=dialog)
                    dialog.destroy()

                dialog.after(0, on_success)

            except Exception as e:
                def on_err():
                    save_btn.config(state=tk.NORMAL)
                    cred_status_lbl.config(text="Authentication / Save error.")
                    messagebox.showerror("Configuration Error", f"Could not save credentials:\n{e}", parent=dialog)
                dialog.after(0, on_err)

        def on_save_click():
            save_btn.config(state=tk.DISABLED)
            cred_status_lbl.config(text="Saving credentials to local profile...")
            threading.Thread(target=save_worker, daemon=True).start()

        save_btn.config(command=on_save_click)

    def check_updates_background(self):
        """Background check to detect newer releases or commits on GitHub without blocking UI."""
        time.sleep(2.5)
        try:
            repo = getattr(self, "github_repo", "").strip()
            if not repo or "/" not in repo:
                return

            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "TheArchiver-App"}
            
            # Check for GitHub Releases
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                tag = data.get("tag_name", "").strip()
                clean_tag = tag.lstrip("v").strip()
                clean_curr = APP_VERSION.lstrip("v").strip()
                if clean_tag and clean_tag != clean_curr:
                    self.root.after(0, lambda: self.updater_btn.config(text=f"✨ Update Available ({tag})"))
        except Exception:
            pass

    def open_updater_dialog(self):
        """Opens the Version & Update Manager dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Version & Update Manager")
        dialog.geometry("630x560")
        dialog.minsize(580, 500)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center over parent window
        dialog.update_idletasks()
        try:
            x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
            y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # 1. Repository Configuration Frame
        repo_frame = ttk.LabelFrame(dialog, text="GitHub Repository Configuration", padding=(10, 8))
        repo_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        ttk.Label(repo_frame, text="GitHub Repo (user/repo):").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=3)
        repo_var = tk.StringVar(value=getattr(self, "github_repo", "BaDoingleZoinks/Archiver"))
        repo_entry = ttk.Entry(repo_frame, textvariable=repo_var, width=32)
        repo_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3)

        def save_repo_config():
            val = repo_var.get().strip()
            if not val or "/" not in val:
                messagebox.showerror("Invalid Format", "Please enter the repository in the format: owner/repository\nExample: BaDoingleZoinks/Archiver", parent=dialog)
                return
            self.github_repo = val
            self.save_settings()
            messagebox.showinfo("Saved", f"Repository set to: {val}", parent=dialog)
            fetch_versions_thread()

        save_repo_btn = ttk.Button(repo_frame, text="Save & Connect", command=save_repo_config)
        save_repo_btn.grid(row=0, column=2, padx=(6, 0), pady=3)
        repo_frame.columnconfigure(1, weight=1)

        # 2. Status Frame
        status_frame = ttk.LabelFrame(dialog, text="Installed Build Status", padding=(10, 8))
        status_frame.pack(fill=tk.X, padx=12, pady=6)

        ttk.Label(status_frame, text=f"Installed Version: v{APP_VERSION} (Current)", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=2)

        backup_file = "yt_archive_app.py.bak"
        backup_info = "No previous local backup found"
        if os.path.exists(backup_file):
            try:
                mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(backup_file)))
                sz = os.path.getsize(backup_file) // 1024
                backup_info = f"Backup available: {mtime} ({sz} KB)"
            except Exception:
                backup_info = "Backup file exists"
        backup_lbl = ttk.Label(status_frame, text=f"Local Rollback: {backup_info}", foreground="#007acc" if os.path.exists(backup_file) else "gray")
        backup_lbl.grid(row=1, column=0, sticky=tk.W, pady=2)

        # 3. Target Version Selection Frame
        ver_frame = ttk.LabelFrame(dialog, text="Target Version / Build Selection", padding=(10, 8))
        ver_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        select_row = ttk.Frame(ver_frame)
        select_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(select_row, text="Select Target Version:").pack(side=tk.LEFT, padx=(0, 5))
        version_combo = ttk.Combobox(select_row, state="readonly", width=36)
        version_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        refresh_btn = ttk.Button(select_row, text="🔄 Fetch Versions")
        refresh_btn.pack(side=tk.RIGHT)

        show_commits_var = tk.BooleanVar(value=False)
        show_commits_chk = ttk.Checkbutton(ver_frame, text="Show individual Git commits (Advanced)", variable=show_commits_var)
        show_commits_chk.pack(anchor=tk.W, pady=(0, 4))

        ttk.Label(ver_frame, text="Version Notes & Details:").pack(anchor=tk.W, pady=(4, 2))
        notes_box = scrolledtext.ScrolledText(ver_frame, height=8, wrap=tk.WORD)
        notes_box.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        action_status_lbl = ttk.Label(dialog, text="", foreground="gray")
        action_status_lbl.pack(fill=tk.X, padx=15, pady=(2, 2))

        # 4. Action Buttons Frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=(6, 12))

        apply_btn = ttk.Button(btn_frame, text="🚀 Update / Switch to Selected Version")
        try:
            apply_btn.config(style="Accent.TButton")
        except Exception:
            pass
        apply_btn.pack(side=tk.LEFT, padx=(0, 6))

        rollback_btn = ttk.Button(btn_frame, text="⏪ Rollback to Local Backup")
        rollback_btn.pack(side=tk.LEFT, padx=6)
        if not os.path.exists(backup_file):
            rollback_btn.config(state=tk.DISABLED)

        close_btn = ttk.Button(btn_frame, text="Close", command=dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

        version_data = {}
        release_items = []
        commit_items = []

        def on_version_selected(event=None):
            sel = version_combo.get()
            info = version_data.get(sel, {})
            notes_box.delete("1.0", tk.END)
            if not info:
                return
            txt = f"Selected Target: {sel}\n"
            if "type" in info:
                txt += f"Type: {info['type']}\n"
            if "date" in info:
                txt += f"Date: {info['date']}\n"
            if "sha" in info:
                txt += f"Commit SHA: {info['sha']}\n"
            txt += "\n" + ("-" * 45) + "\n\n"
            txt += info.get("body", "No release notes provided.")
            notes_box.insert(tk.END, txt)

        version_combo.bind("<<ComboboxSelected>>", on_version_selected)

        def update_combo():
            current_sel = version_combo.get()
            active_items = list(release_items)
            if show_commits_var.get():
                active_items.extend(commit_items)
            version_combo['values'] = active_items
            if current_sel in active_items:
                version_combo.set(current_sel)
            elif active_items:
                version_combo.current(0)
                on_version_selected()
            action_status_lbl.config(text=f"Loaded {len(active_items)} target(s).")
            refresh_btn.config(state=tk.NORMAL)

        show_commits_chk.config(command=update_combo)

        def fetch_versions_worker():
            repo = repo_var.get().strip()
            if not repo or "/" not in repo:
                action_status_lbl.config(text="Please set a valid GitHub repository (owner/repo).")
                refresh_btn.config(state=tk.NORMAL)
                return

            action_status_lbl.config(text=f"Connecting to GitHub ({repo})...")
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "TheArchiver-Updater"}
            
            release_items.clear()
            commit_items.clear()
            version_data.clear()

            # Always offer "Latest (main branch)"
            latest_key = "Latest (main branch)"
            release_items.append(latest_key)
            version_data[latest_key] = {
                "type": "Bleeding-Edge Branch",
                "ref": "main",
                "body": "Fetches the latest code from the 'main' branch on GitHub.\nUse this to stay completely up to date with any push from another PC."
            }

            try:
                # 1. Official Releases
                rel_url = f"https://api.github.com/repos/{repo}/releases?per_page=15"
                r = requests.get(rel_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    releases = r.json()
                    for rel in releases:
                        tag = rel.get("tag_name", "")
                        name = rel.get("name", tag)
                        key = f"Release: {tag} ({name})" if name and name != tag else f"Release: {tag}"
                        release_items.append(key)
                        version_data[key] = {
                            "type": "Official Release",
                            "ref": tag,
                            "date": rel.get("published_at", ""),
                            "body": rel.get("body", "No release notes.")
                        }

                # 2. Git Tags
                tag_url = f"https://api.github.com/repos/{repo}/tags?per_page=15"
                tr = requests.get(tag_url, headers=headers, timeout=8)
                if tr.status_code == 200:
                    tags = tr.json()
                    for t in tags:
                        t_name = t.get("name", "")
                        key = f"Tag: {t_name}"
                        if key not in release_items and f"Release: {t_name}" not in release_items:
                            release_items.append(key)
                            version_data[key] = {
                                "type": "Git Tag",
                                "ref": t_name,
                                "sha": t.get("commit", {}).get("sha", "")[:7],
                                "body": f"Git tag: {t_name}"
                            }

                # 3. Recent commits on main (stored separately in commit_items)
                commit_url = f"https://api.github.com/repos/{repo}/commits?sha=main&per_page=10"
                cr = requests.get(commit_url, headers=headers, timeout=8)
                if cr.status_code == 200:
                    commits = cr.json()
                    for c in commits:
                        sha = c.get("sha", "")[:7]
                        msg = c.get("commit", {}).get("message", "").splitlines()[0]
                        date = c.get("commit", {}).get("author", {}).get("date", "")
                        key = f"Commit: {sha} - {msg[:35]}"
                        commit_items.append(key)
                        version_data[key] = {
                            "type": "Git Commit",
                            "ref": sha,
                            "sha": sha,
                            "date": date,
                            "body": c.get("commit", {}).get("message", "")
                        }

                dialog.after(0, update_combo)

            except Exception as e:
                def on_err():
                    action_status_lbl.config(text=f"Notice: GitHub check: {e}")
                    refresh_btn.config(state=tk.NORMAL)
                    dialog.after(0, update_combo)
                dialog.after(0, on_err)
                dialog.after(0, on_err)

        def fetch_versions_thread():
            refresh_btn.config(state=tk.DISABLED)
            action_status_lbl.config(text="Connecting to GitHub...")
            threading.Thread(target=fetch_versions_worker, daemon=True).start()

        refresh_btn.config(command=fetch_versions_thread)

        def apply_update_worker(selected_key):
            info = version_data.get(selected_key, {})
            target_ref = info.get("ref", "main")
            repo = repo_var.get().strip()

            action_status_lbl.config(text=f"Downloading target ({target_ref}) from GitHub...")
            raw_url = f"https://raw.githubusercontent.com/{repo}/{target_ref}/yt_archive_app.py"

            try:
                resp = requests.get(raw_url, timeout=15)
                if resp.status_code != 200:
                    raise Exception(f"Download failed (HTTP {resp.status_code}).\nVerify repository '{repo}' exists and is public.")

                code_content = resp.text
                if not code_content.strip():
                    raise Exception("Downloaded file content is empty!")

                # Syntax verification
                action_status_lbl.config(text="Verifying code syntax integrity...")
                try:
                    ast.parse(code_content)
                except SyntaxError as se:
                    raise Exception(f"Downloaded code has syntax errors: {se}")

                # Backup current code
                action_status_lbl.config(text="Creating local backup (yt_archive_app.py.bak)...")
                curr_file = "yt_archive_app.py"
                if os.path.exists(curr_file):
                    shutil.copy(curr_file, "yt_archive_app.py.bak")

                # Write new code
                action_status_lbl.config(text="Installing updated code...")
                with open(curr_file, "w", encoding="utf-8") as f:
                    f.write(code_content)

                # Keep Git in sync if repo is a git clone
                if os.path.isdir(".git"):
                    try:
                        if target_ref == "main":
                            subprocess.run(["git", "pull", "origin", "main"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                        else:
                            subprocess.run(["git", "checkout", target_ref], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        pass

                def on_success():
                    action_status_lbl.config(text="Update completed successfully!")
                    apply_btn.config(state=tk.NORMAL)
                    rollback_btn.config(state=tk.NORMAL)
                    ans = messagebox.askyesno("Update Complete", f"Successfully updated The Archiver to {selected_key}!\n\nA backup of the previous build was saved to yt_archive_app.py.bak.\n\nWould you like to restart the application now?", parent=dialog)
                    if ans:
                        dialog.destroy()
                        self.on_close()
                        subprocess.Popen([sys.executable, "yt_archive_app.py"])

                dialog.after(0, on_success)

            except Exception as e:
                def on_fail():
                    action_status_lbl.config(text="Update failed.")
                    apply_btn.config(state=tk.NORMAL)
                    messagebox.showerror("Update Failed", f"Could not complete update:\n{e}", parent=dialog)
                dialog.after(0, on_fail)

        def on_apply_click():
            sel = version_combo.get()
            if not sel:
                messagebox.showwarning("Select Target", "Please select a target version to update/switch to.", parent=dialog)
                return
            if not messagebox.askyesno("Confirm Update", f"Switch / Update The Archiver to:\n\n{sel}\n\nYour current code will be safely backed up so you can roll back anytime.\n\nProceed?", parent=dialog):
                return
            apply_btn.config(state=tk.DISABLED)
            threading.Thread(target=apply_update_worker, args=(sel,), daemon=True).start()

        apply_btn.config(command=on_apply_click)

        def on_rollback_click():
            if not os.path.exists("yt_archive_app.py.bak"):
                messagebox.showerror("No Backup", "No local backup file (yt_archive_app.py.bak) found.", parent=dialog)
                return
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime("yt_archive_app.py.bak")))
            if not messagebox.askyesno("Confirm Rollback", f"Restore previous backup created on:\n{mtime}?\n\nThis will restore the previous build and restart.", parent=dialog):
                return
            try:
                temp_curr = "yt_archive_app_temp.py"
                shutil.copy("yt_archive_app.py", temp_curr)
                shutil.copy("yt_archive_app.py.bak", "yt_archive_app.py")
                shutil.move(temp_curr, "yt_archive_app.py.bak")
                messagebox.showinfo("Rollback Complete", "Successfully restored previous backup! Restarting...", parent=dialog)
                dialog.destroy()
                self.on_close()
                subprocess.Popen([sys.executable, "yt_archive_app.py"])
            except Exception as e:
                messagebox.showerror("Rollback Failed", f"Failed to restore backup: {e}", parent=dialog)

        rollback_btn.config(command=on_rollback_click)

        # Initial fetch on dialog open
        fetch_versions_thread()

if __name__ == "__main__":
    root = tk.Tk()
    app = ArchiveApp(root)
    root.mainloop()
