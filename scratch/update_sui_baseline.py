import re
import os

path = r"C:\Users\admin-beats\Documents\antigravity\hopeful-bose\simpleui_settings_baseline\sui_settings.lua"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Update settings
updates = {
    r'\["simpleui_hs_hero_currently"\]\s*=\s*false': '["simpleui_hs_hero_currently"] = true',
    r'\["simpleui_hs_hero_currently_cover_scale"\]\s*=\s*\d+': '["simpleui_hs_hero_currently_cover_scale"] = 115',
    r'\["simpleui_hs_coverdeck_thumb_scale"\]\s*=\s*\d+': '["simpleui_hs_coverdeck_thumb_scale"] = 115',
    r'\["simpleui_hs_coverdeck_show_title"\]\s*=\s*true': '["simpleui_hs_coverdeck_show_title"] = false',
    r'\["simpleui_hs_reading_streaks"\]\s*=\s*false': '["simpleui_hs_reading_streaks"] = true',
    r'\["simpleui_hs_reading_goals_enabled"\]\s*=\s*false': '["simpleui_hs_reading_goals_enabled"] = true',
    r'\["simpleui_hs_quote_enabled"\]\s*=\s*false': '["simpleui_hs_quote_enabled"] = true',
}

for pattern, replacement in updates.items():
    content = re.sub(pattern, replacement, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("SimpleUI baseline updated successfully.")
