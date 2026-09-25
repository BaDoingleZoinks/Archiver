import sys
import re
import os

APP_FILE = 'yt_archive_app.py'
CHANGELOG_FILE = 'CHANGELOG.md'

def get_app_version():
    """Reads APP_VERSION directly from the application source."""
    if not os.path.exists(APP_FILE):
        return "Unknown"
    with open(APP_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('APP_VERSION ='):
                match = re.search(r'APP_VERSION = ["\'](.+?)["\']', line)
                if match:
                    return match.group(1).strip()
    return "Unknown"

def set_app_version(new_version):
    """Updates APP_VERSION in the application source."""
    with open(APP_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    updated = re.sub(r'APP_VERSION = ["\'].+?["\']', f'APP_VERSION = "{new_version}"', content, count=1)
    with open(APP_FILE, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"[Success] Updated {APP_FILE} APP_VERSION -> {new_version}")

def get_latest_changelog_version():
    """Gets the topmost version listed in CHANGELOG.md."""
    if not os.path.exists(CHANGELOG_FILE):
        return None
    with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'## \[([^\]]+)\]', content)
    if match:
        return match.group(1).strip()
    return None

def calculate_bump(version_str, bump_type):
    """Calculates next semver string (e.g. 1.7.0 -> 1.7.1 or 1.8.0)."""
    match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', version_str.strip())
    if not match:
        return version_str
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    
    if bump_type == 'patch':
        patch += 1
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    return f"{major}.{minor}.{patch}"

def categorize_and_format_message(msg):
    """Determines changelog category and formats entry nicely."""
    clean = msg.strip()
    if not clean:
        return "Changed", "Maintenance update."
        
    lower = clean.lower()
    
    category = "Changed"
    if any(lower.startswith(k) for k in ["fix", "resolve", "patch", "bug", "revert"]):
        category = "Fixed"
    elif any(lower.startswith(k) for k in ["add", "feat", "new"]):
        category = "Added"
    elif any(lower.startswith(k) for k in ["remove", "delete", "deprecat"]):
        category = "Removed"
    elif any(lower.startswith(k) for k in ["perf", "refactor", "chore", "doc", "update"]):
        category = "Changed"

    formatted = clean[0].upper() + clean[1:]
    if ":" in formatted:
        parts = formatted.split(":", 1)
        formatted = f"**{parts[0].strip()}**:{parts[1]}"
    elif not formatted.startswith("**"):
        words = formatted.split(" ", 1)
        if len(words) == 2 and words[0].lower() in ["added", "fixed", "updated", "removed", "changed"]:
            formatted = f"**{words[0]}**: {words[1]}"
            
    return category, formatted

def update_changelog(version, category, formatted_entry):
    """Updates CHANGELOG.md ensuring correct headers and categories."""
    try:
        with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Changelog\n\nAll notable changes to **The Archiver**.\n\n"

    new_bullet = f"- {formatted_entry}\n" if formatted_entry else ""
    version_header = f"## [{version}]"
    
    # Strip any existing "- Latest" markers across the file to ensure only top has it
    content = re.sub(r'## \[([^\]]+)\] - Latest', r'## [\1]', content)

    if version_header in content:
        # Version already exists in CHANGELOG.md; attach "- Latest" and append entry
        pattern = re.compile(rf"({re.escape(version_header)})(.*?)(?=## \[|\Z)", re.DOTALL)
        match = pattern.search(content)
        if match:
            v_head, section_body = match.group(1), match.group(2)
            new_v_head = f"{version_header} - Latest"
            
            if new_bullet:
                cat_header = f"### {category}"
                if cat_header in section_body:
                    # Append directly beneath category header
                    updated_body = section_body.replace(f"{cat_header}\n", f"{cat_header}\n{new_bullet}")
                else:
                    # Add category header at the start of section body
                    updated_body = f"\n{cat_header}\n{new_bullet}" + section_body.lstrip('\n')
            else:
                updated_body = section_body
                
            content = content[:match.start()] + new_v_head + updated_body + content[match.end():]
    else:
        # New version section needs to be created at the top
        new_section = f"## [{version}] - Latest\n"
        if new_bullet:
            new_section += f"### {category}\n{new_bullet}\n"
        else:
            new_section += f"### Changed\n- Maintenance update.\n\n"
            
        first_header_idx = content.find("## [")
        if first_header_idx != -1:
            content = content[:first_header_idx] + new_section + "\n" + content[first_header_idx:]
        else:
            content += "\n" + new_section

    # Clean up redundant empty lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    with open(CHANGELOG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[Success] Updated {CHANGELOG_FILE} for v{version}")

def interactive_prompt(commit_msg):
    """Runs interactive version selector before committing/publishing."""
    current_ver = get_app_version()
    patch_ver = calculate_bump(current_ver, 'patch')
    minor_ver = calculate_bump(current_ver, 'minor')
    major_ver = calculate_bump(current_ver, 'major')

    print("\n" + "=" * 58)
    print(f"        Release & Version Manager (Current: v{current_ver})")
    print("=" * 58)
    print(f"  [1] Patch bump   -> v{patch_ver} (Bug fixes, small enhancements)")
    print(f"  [2] Minor bump   -> v{minor_ver} (New features, functionality)")
    print(f"  [3] Major bump   -> v{major_ver} (Major architectural change)")
    print(f"  [4] Keep current -> v{current_ver} (Sub-release / no version bump)")
    print("  [5] Custom version string")
    print("=" * 58)

    try:
        choice = input("Select version bump [1-5, default 4]: ").strip()
    except EOFError:
        choice = "4"
        
    if choice == "1":
        target_ver = patch_ver
    elif choice == "2":
        target_ver = minor_ver
    elif choice == "3":
        target_ver = major_ver
    elif choice == "5":
        try:
            target_ver = input("Enter custom version (e.g. 1.7.1): ").strip()
        except EOFError:
            target_ver = current_ver
        if not target_ver:
            target_ver = current_ver
    else:
        target_ver = current_ver

    # Update app version if changed
    if target_ver != current_ver:
        set_app_version(target_ver)
    else:
        print(f"[Info] Keeping current version v{current_ver}")

    # Add changelog entry
    if commit_msg and commit_msg.lower() not in ["update build", "build", "publish"]:
        category, formatted = categorize_and_format_message(commit_msg)
        update_changelog(target_ver, category, formatted)
    else:
        update_changelog(target_ver, None, None)

    return target_ver

def main():
    args = sys.argv[1:]
    
    if not args:
        print("Usage: python auto_changelog.py [--prompt] <commit message>")
        return

    is_interactive = False
    if "--prompt" in args:
        is_interactive = True
        args.remove("--prompt")

    commit_msg = " ".join(args).strip() if args else ""

    if is_interactive:
        interactive_prompt(commit_msg)
    else:
        current_ver = get_app_version()
        if commit_msg and commit_msg.lower() not in ["update build", "build", "publish"]:
            category, formatted = categorize_and_format_message(commit_msg)
            update_changelog(current_ver, category, formatted)
        else:
            update_changelog(current_ver, None, None)

if __name__ == "__main__":
    main()
