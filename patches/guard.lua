--[[--
Prevent patches from executing when they don't meet a KOReader's version requirement.
Patches that don't meet their requirement, will be flagged as non-working in the menu.
@usage, @the very beginning of a patch:

    local ok, guard = pcall(require, "patches/guard")
    if ok and guard:korDoesNotMeet("v2025.04-103") then return end

--]]

local FileManagerMenu = require("apps/filemanager/filemanagermenu")
local ReaderMenu = require("apps/reader/modules/readermenu")
local Version = require("version")
local logger = require("logger")
local userPatch = require("userpatch")

local guard = {
    current_version = Version:getNormalizedCurrentVersion(), -- cur KOR version
    dont_meet_version = {}, -- patches with too old KOR versions
}

function guard:korDoesNotMeet(min_version)
    local patch_name = debug.getinfo(2, "S").source:match("[^/]*.lua$")
    if self.current_version < Version:getNormalizedVersion(min_version) then
        logger.err('"' .. patch_name .. '": You need at least Koreader', min_version)
        table.insert(self.dont_meet_version, patch_name)
        return true
    end
    logger.info('"' .. patch_name .. '": meet KOReader version requirement')
end

-- mark patches that don't meet Koreader version requirement
function guard:markPatches()
    for _, patch_name in ipairs(self.dont_meet_version) do
        userPatch.execution_status[patch_name] = false
    end
end

local orig_FileManagerMenu_setUpdateItemTable = FileManagerMenu.setUpdateItemTable
function FileManagerMenu:setUpdateItemTable()
    guard:markPatches()
    orig_FileManagerMenu_setUpdateItemTable(self)
end

local orig_ReaderMenu_setUpdateItemTable = ReaderMenu.setUpdateItemTable
function ReaderMenu:setUpdateItemTable()
    guard:markPatches()
    orig_ReaderMenu_setUpdateItemTable(self)
end

return guard
