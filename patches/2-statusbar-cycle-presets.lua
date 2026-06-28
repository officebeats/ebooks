local ok, guard = pcall(require, "patches/guard")
if ok and guard:korDoesNotMeet("v2025.04-52") then return end

local ReaderFooter = require("apps/reader/modules/readerfooter")
local util = require("util")
-- local logger = require("logger")

local FooterCurrentPresetSetting = "footer_current_preset"

function ReaderFooter:nextNamedPreset() -- return true when we have a next preset to show
    local presets = self:getPresets()
    if #presets > 1 then -- at least 2 presets
        local off_preset = "" -- can't be a user-defined preset
        table.insert(presets, off_preset)
        local current_preset = G_reader_settings:readSetting(FooterCurrentPresetSetting)
        local i = util.arrayContains(presets, current_preset) or 0
        local next_preset = presets[1 + (i % #presets)]
        G_reader_settings:saveSetting(FooterCurrentPresetSetting, next_preset)
        if next_preset ~= off_preset then
            self:onLoadFooterPreset(next_preset)
            return true
        end
    end
end

local function saveCurrentPresetName()
    local function getVarAtDepth(var_name, depth)
        local i = 1
        while true do -- look in locals
            local name, value = debug.getlocal(depth, i)
            if not name then break end
            if name == var_name then return value end
            i = i + 1
        end
        i = 1
        local caller = debug.getinfo(depth, "f").func
        while true do -- look in upvalues
            local name, value = debug.getupvalue(caller, i)
            if not name then break end
            if name == var_name then return value end
            i = i + 1
        end
    end

    local preset_name = getVarAtDepth("preset_name", 4) -- in the caller's caller's caller !
    if preset_name then G_reader_settings:saveSetting(FooterCurrentPresetSetting, preset_name) end
end

local need_full_refresh_settings = {
    "container_height",
    "bottom_horizontal_separator",
    "progress_style_thin",
    "progress_style_thick_height",
    "progress_style_thin_height",
    "text_font_bold",
    "text_font_size",
    "reclaim_height",
}

local orig_ReaderFooter_refreshFooter = ReaderFooter.refreshFooter
local orig_ReaderFooter_loadPreset = ReaderFooter.loadPreset

ReaderFooter.loadPreset = function(self, preset)
    local previous_settings = util.tableDeepCopy(self.settings)
    ReaderFooter.refreshFooter = function(self, refresh, signal)
        local force_full_refresh = false
        for _, setting in ipairs(need_full_refresh_settings) do
            if previous_settings[setting] ~= self.settings[setting] then
                force_full_refresh = true
                break
            end
        end
        self.progress_bar:updateStyle(not self.settings.progress_style_thin)
        self:setTocMarkers()
        orig_ReaderFooter_refreshFooter(self, true, force_full_refresh) -- full refresh only when needed
    end
    saveCurrentPresetName()
    orig_ReaderFooter_loadPreset(self, preset)
    ReaderFooter.refreshFooter = orig_ReaderFooter_refreshFooter
end

local orig_ReaderFooter_buildPreset = ReaderFooter.buildPreset

ReaderFooter.buildPreset = function(self)
    saveCurrentPresetName()
    return orig_ReaderFooter_buildPreset(self)
end

local orig_ReaderFooter_onToggleFooterMode = ReaderFooter.onToggleFooterMode

ReaderFooter.onToggleFooterMode = function(self)
    if self.has_no_mode and self.settings.disable_progress_bar then return end
    if self.settings.all_at_once or self.has_no_mode then
        if self:nextNamedPreset() then -- we have a next preset
            self.mode = 0 -- will force self.mode_list.page_progress in onToggleFooterMode
        end
    end
    return orig_ReaderFooter_onToggleFooterMode(self)
end
