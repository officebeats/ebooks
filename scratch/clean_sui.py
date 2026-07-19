import re

path = r"C:\Users\admin-beats\Documents\antigravity\hopeful-bose\simpleui_settings_baseline\sui_settings.lua"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove the simpleui_stale_books_v1 block
# It starts with ["simpleui_stale_books_v1"] and ends at the first top-level property after it, or by matching braces.
# Actually, I can just use a regex that matches from ["simpleui_stale_books_v1"] to ["simpleui_statusbar_transparent"]
content = re.sub(r'\["simpleui_stale_books_v1"\].*?\["simpleui_statusbar_transparent"\]', '["simpleui_statusbar_transparent"]', content, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Cleaned!")
