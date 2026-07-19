-- Performance optimization settings patch for low-memory/single-core Kindles
local logger = require("logger")
local Device = require("device")

logger.info("Applying performance optimization tweaks...")

-- 1. Ensure debug logging is disabled to prevent I/O stalls
if G_reader_settings:isTrue("debug") or G_reader_settings:isTrue("verbose_debug") then
    G_reader_settings:saveSetting("debug", false)
    G_reader_settings:saveSetting("verbose_debug", false)
    logger.info("  Debug logging disabled.")
end


-- 3. Crisp Font Contrast Boost (Emboldening)
G_reader_settings:saveSetting("cr_contrast", 2)
logger.info("  Font contrast boost enforced.")

-- 4. Enable Snappy Edge Swipes (Left = Brightness, Right = Font Size)
G_reader_settings:saveSetting("edge_brightness_enabled", true)
G_reader_settings:saveSetting("edge_fontsize_enabled", true)
logger.info("  Edge swipes for brightness & font size enabled.")

-- 4.5 Battery Preservation (Auto-suspend after 10m)
G_reader_settings:saveSetting("auto_suspend_timeout", 10)
logger.info("  Battery preservation tweaks enforced (auto-suspend).")

-- 5. Zero-Animation Page Turns (Instant snappiness)
G_reader_settings:saveSetting("page_transition", "none")
G_reader_settings:saveSetting("page_animations_enabled", false)
logger.info("  Zero-animation page turns enforced.")

-- 6. Ensure heavy background plugins are disabled
local disabled = G_reader_settings:readSetting("plugins_disabled") or {}
local heavy_plugins = {
    "opds",
    "opdsplus",
    "newsdownloader",
    "wallabag",
    "profiles",
    "zlibrary",
    "readtimer",
    "vocabbuilder",
    "statistics",
    "httpinspector",
    "japanese",
}

local updated_plugins = false
for _, plugin in ipairs(heavy_plugins) do
    if not disabled[plugin] then
        disabled[plugin] = true
        updated_plugins = true
    end
end

if updated_plugins then
    G_reader_settings:saveSetting("plugins_disabled", disabled)
    logger.info("  Heavy background plugins disabled.")
end
