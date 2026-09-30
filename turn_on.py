import json

with open('settings.json', 'r', encoding='utf-8') as f:
    s = json.load(f)

s['auto_derive'] = True

with open('settings.json', 'w', encoding='utf-8') as f:
    json.dump(s, f, indent=4)

