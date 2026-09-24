import sys
import re
import os

def get_app_version():
    with open('yt_archive_app.py', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('APP_VERSION ='):
                match = re.search(r'APP_VERSION = ["\'](.+)["\']', line)
                if match:
                    return match.group(1)
    return "Unknown"

def main():
    if len(sys.argv) < 2:
        print("[Info] No commit message provided for changelog.")
        return
    
    commit_msg = sys.argv[1].strip()
    if not commit_msg or commit_msg.lower() == "update build":
        print("[Info] Generic commit message. Skipping changelog auto-update.")
        return

    version = get_app_version()
    
    # Determine category
    lower_msg = commit_msg.lower()
    category = "Changed"
    if lower_msg.startswith("fix") or lower_msg.startswith("resolve") or lower_msg.startswith("patch"):
        category = "Fixed"
    elif lower_msg.startswith("add") or lower_msg.startswith("feat") or lower_msg.startswith("new"):
        category = "Added"
    elif lower_msg.startswith("remove") or lower_msg.startswith("delete"):
        category = "Removed"

    # Format the message (capitalize first letter, ensure it ends with period)
    formatted_msg = commit_msg[0].upper() + commit_msg[1:]
    
    # Simple bolding if there is a colon (e.g., "Feature: description" -> "**Feature**: description")
    if ":" in formatted_msg:
        parts = formatted_msg.split(":", 1)
        formatted_msg = f"**{parts[0].strip()}**:{parts[1]}"
    
    new_entry = f"- {formatted_msg}\n"

    try:
        with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Changelog\n\n"

    version_header = f"## [{version}]"
    
    if version_header in content:
        # Version exists, find the category or insert it
        pattern = re.compile(rf"({re.escape(version_header)}.*?)(?=## \[|\Z)", re.DOTALL)
        match = pattern.search(content)
        if match:
            section_content = match.group(1)
            cat_header = f"### {category}"
            
            if cat_header in section_content:
                # Append to existing category
                updated_section = section_content.replace(f"{cat_header}\n", f"{cat_header}\n{new_entry}")
            else:
                # Add new category
                # Put it right after the version header
                # Handle "- Latest" if present
                lines = section_content.split('\n')
                updated_section = lines[0] + f"\n{cat_header}\n{new_entry}" + '\n'.join(lines[1:])
            
            content = content[:match.start()] + updated_section + content[match.end():]
    else:
        # New version
        # Remove "- Latest" from old latest version
        content = content.replace(" - Latest", "")
        
        new_section = f"## [{version}] - Latest\n### {category}\n{new_entry}\n"
        
        # Insert after the main header
        if "## [" in content:
            first_header_idx = content.find("## [")
            content = content[:first_header_idx] + new_section + content[first_header_idx:]
        else:
            content += new_section

    with open('CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"[Success] Added '{commit_msg}' to v{version} in CHANGELOG.md")

if __name__ == "__main__":
    main()
