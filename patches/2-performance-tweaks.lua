-- Performance optimization settings patch for low-memory/single-core Kindles
local logger = require("logger")

logger.info("Applying performance optimization tweaks...")

-- 1. Ensure debug logging is disabled to prevent I/O stalls
if G_reader_settings:isTrue("debug") or G_reader_settings:isTrue("verbose_debug") then
    G_reader_settings:saveSetting("debug", false)
    G_reader_settings:saveSetting("verbose_debug", false)
    logger.info("  Debug logging disabled.")
end

-- 2. Ensure heavy background plugins are disabled
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
