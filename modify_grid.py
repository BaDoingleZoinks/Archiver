import re

with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# First, insert the new block after the url_frame block
url_block_end = content.find('self.del_url_btn.pack(side=tk.LEFT, padx=(5, 0))') + len('self.del_url_btn.pack(side=tk.LEFT, padx=(5, 0))')

new_block = """
        
        # Content Type
        ttk.Label(input_frame, text="Content Type (Channel only):").grid(row=1, column=0, sticky=tk.W, pady=5)
        type_frame = ttk.Frame(input_frame)
        type_frame.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.content_type_var = tk.StringVar(value="All / Default")
        self.content_type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.content_type_var,
            values=["All / Default", "Videos", "Live", "Shorts"],
            state="readonly"
        )
        self.content_type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)"""

part1 = content[:url_block_end]
part2 = content[url_block_end:]

# In part2, increment all row=1 to row=2, row=2 to row=3, etc. up to row=8.
# But ONLY within `create_tab1_widgets`.
# Find the end of create_tab1_widgets
end_func = part2.find('def create_tab2_widgets')

sub_part1 = part2[:end_func]
sub_part2 = part2[end_func:]

# Replace rows in reverse order so we don't double replace
for i in range(8, 0, -1):
    sub_part1 = re.sub(rf'row={i}\b', f'row={i+1}', sub_part1)

with open('yt_archive_app.py', 'w', encoding='utf-8') as f:
    f.write(part1 + new_block + sub_part1 + sub_part2)

print("Done")
