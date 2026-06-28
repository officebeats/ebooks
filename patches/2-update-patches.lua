local ok, guard = pcall(require, "patches/guard")
if ok and guard:korDoesNotMeet("v2025.04-107") then return end

local Blitbuffer = require("ffi/blitbuffer")
local ButtonDialog = require("ui/widget/buttondialog")
local CheckButton = require("ui/widget/checkbutton")
local ConfirmBox = require("ui/widget/confirmbox")
local DataStorage = require("datastorage")
local Geom = require("ui/geometry")
local InfoMessage = require("ui/widget/infomessage")
local LineWidget = require("ui/widget/linewidget")
local NetworkMgr = require("ui/network/manager")
local Size = require("ui/size")
local UIManager = require("ui/uimanager")
local Version = require("version")
local VerticalSpan = require("ui/widget/verticalspan")
local http = require("socket/http")
local json = require("json")
local lfs = require("libs/libkoreader-lfs")
local ltn12 = require("ltn12")
local md5 = require("ffi/MD5")
local userPatch = require("userpatch")

local _ = require("gettext")
local T = require("ffi/util").template
local logger = require("logger")

local UPDATES = "updates.json" -- dict of md5 of lua files
local GITHUB_REPO = "sebdelsol/KOReader.patches"
local LOCAL_PATCHES = DataStorage:getDataDir() .. "/patches/"
local ONLINE_PATCHES = "https://github.com/" .. GITHUB_REPO .. "/raw/refs/heads/main/"

-- download
local function httpRequest(options)
    local req_ok, r_val, r_code, _, r_status_str = pcall(http.request, options)
    if req_ok and r_code == 200 then return true end
    logger.err("Network request failed: ", tostring(r_val), r_code, r_status_str)
end

local function downloadFile(url, path)
    local file, err = io.open(path, "wb")
    if file then
        local options = {
            url = url,
            method = "GET",
            headers = { ["User-Agent"] = GITHUB_REPO },
            sink = ltn12.sink.file(file),
            redirect = true,
        }
        if httpRequest(options) then return true end
        pcall(os.remove, path)
        return
    end
    logger.err("Failed to open target file for download: ", err or "Unknown error")
end

-- version
local cur_kor_version = Version:getNormalizedCurrentVersion() -- cur KOR version

local function doMeetRequirement(path) -- path is supposed to be a patch
    local count = 0
    for line in io.lines(path) do
        count = count + 1
        if count > 3 then break end -- do not search for too many lines
        local min_ver = line:match(':korDoesNotMeet%(%"(v.+)%"%)')
        min_ver = Version:getNormalizedVersion(min_ver)
        if min_ver and cur_kor_version < min_ver then return false end
    end
    return true
end

-- tools
local function sortedPairs(tbl)
    local keys = {}
    -- stylua: ignore
    for key in pairs(tbl) do table.insert(keys, key) end
    table.sort(keys)
    local i = 0
    return function()
        i = i + 1
        local key = keys[i]
        if key ~= nil then return key, tbl[key] end
    end
end

-- ui
local ui = {}

function ui:close()
    if self.shown then
        UIManager:close(self.shown)
        self.shown = nil
    end
end

function ui:info(text)
    self:close()
    self.shown = InfoMessage:new { text = text, timeout = 5 }
    UIManager:show(self.shown)
end

function ui:process(func, text)
    self:close()
    self.shown = InfoMessage:new { text = text, dismissable = false }
    UIManager:show(self.shown)
    UIManager:scheduleIn(0.1, func)
end

function ui:confirm(options)
    self:close()
    local params = {
        text = options.text,
        no_ok_button = options.one_button,
    }
    params[options.one_button and "cancel_text" or "ok_text"] = options.ok
    params[options.one_button and "cancel_callback" or "ok_callback"] = options.callback
    self.shown = ConfirmBox:new(params)
    UIManager:show(self.shown)
end

function ui:confirmCheckList(options)
    self:close()
    local button_dialog
    self.shown = ButtonDialog:new {
        title = options.title,
        buttons = {
            {
                {
                    text = _("Cancel"),
                    callback = function() self.shown:onClose() end,
                },
                {
                    text = options.ok_text,
                    callback = function()
                        self.shown:onClose()
                        options.ok_callback()
                    end,
                },
            },
        },
    }
    self.shown:addWidget(LineWidget:new { --
        dimen = Geom:new {
            w = self.shown.width - 2 * (Size.border.window + Size.padding.button),
            h = Size.line.medium,
        },
        background = Blitbuffer.COLOR_GRAY,
    })
    self.shown:addWidget(VerticalSpan:new { width = Size.padding.default })
    for _, check in ipairs(options.checks or {}) do
        check.parent = self.shown
        self.shown:addWidget(CheckButton:new(check))
    end
    UIManager:show(self.shown)
end

-- files
local function isFile(path) return lfs.attributes(path, "mode") == "file" end
local function isDir(path) return lfs.attributes(path, "mode") == "directory" end
local function copy(src, dst) return os.execute('cp -vf "' .. src .. '" "' .. dst .. '"') == 0 end
local function remove(path) return os.execute('rm -vf "' .. path .. '"') == 0 end

-- ota
local ota = {
    local_patches = LOCAL_PATCHES,
    local_updates = LOCAL_PATCHES .. UPDATES,
    online_patches = ONLINE_PATCHES,
    online_updates = ONLINE_PATCHES .. UPDATES,
}

function ota:checkUpdates()
    if downloadFile(self.online_updates, self.local_updates) then
        logger.info("Patch updates list downloaded")
        local updates_file = io.open(self.local_updates, "r")
        if updates_file then
            local ok, updates = pcall(json.decode, updates_file:read("*a"))
            updates = ok and updates
            if updates then logger.info("Patch updates list decoded") end
            updates_file:close()
            return updates
        end
    end
end

function ota:cleanBrokenInstalls()
    local broken = false
    for name, ok in pairs(userPatch.execution_status) do
        local file = self.local_patches .. name
        local old_file = file .. ".old"
        if isFile(old_file) then
            if ok then
                remove(old_file)
            elseif copy(old_file, file) then -- revert install
                logger.info("Patch reverted:", file)
                remove(old_file)
                broken = true
            end
        end
    end
    if broken then
        UIManager:askForRestart(_("Some broken patches have been reverted, you need to restart!"))
    end
end

function ota:install(name, md5sum)
    local file = self.local_patches .. name
    local install = { name = name:sub(1, -5), installed = false, skip = false, exists = isFile(file) }

    function install.isNew() return not install.exists or (install.exists and md5.sumFile(file) ~= md5sum) end

    function install.apply()
        if install.skip then return end
        local url = self.online_patches .. name
        local new_file = file .. ".new"
        if downloadFile(url, new_file) then
            logger.info("Patch downloaded:", new_file)
            if md5.sumFile(new_file) == md5sum and doMeetRequirement(new_file) then -- validate
                if install.exists then
                    local old_file = file .. ".old"
                    copy(file, old_file) -- keep a copy
                end
                install.installed = copy(new_file, file) -- install
                logger.info("Patch " .. (install.installed and "" or "NOT ") .. "installed:", file)
            end
            remove(new_file)
        end
    end

    return install
end

function ota:getInstalls(updates)
    local installs = {}

    for name, md5sum in sortedPairs(updates) do
        local install = self:install(name, md5sum)
        if install.isNew() then table.insert(installs, install) end
    end

    function installs.apply()
        for _, install in ipairs(installs) do
            if not install.skip then install.apply() end
        end
    end

    function installs.checks() -- checkboxes
        local checks = {}
        for _, install in ipairs(installs) do
            install.skip = not install.exists -- skip new install by default
            table.insert(checks, {
                text = install.name,
                checked = not install.skip,
                callback = function() install.skip = not install.skip end,
            })
        end
        return checks
    end

    function installs.text(installed)
        local texts = {}
        for _, install in ipairs(installs) do
            if not install.skip and install.installed == installed then
                table.insert(texts, "\n · " .. install.name)
            end
        end
        return table.concat(texts)
    end

    function installs.empty(installed)
        for _, install in ipairs(installs) do
            if not install.skip and install.installed == installed then return false end
        end
        return true
    end

    return installs
end

function ota:_update()
    local function _update()
        local updates = self:checkUpdates()
        if not updates then
            ui:info(_("Can't download patch updates"))
            return
        end

        local installs = self:getInstalls(updates)
        if installs.empty(false) then
            ui:info(_("No patch updates found"))
            return
        end

        local function _install()
            installs.apply()

            local texts = {}
            if not installs.empty(false) then -- some failed
                table.insert(texts, _("Patches that failed to update:") .. installs.text(false))
            end
            if not installs.empty(true) then -- some succeded
                table.insert(texts, _("Patches updated:") .. installs.text(true))
            end
            ui:confirm {
                text = table.concat(texts, "\n"),
                ok = _("OK"),
                one_button = true,
                callback = function()
                    if not installs.empty(true) then UIManager:askForRestart(_("You need to restart!")) end
                end,
            }
        end

        ui:confirmCheckList {
            title = _("Patch updates available:"),
            checks = installs.checks(), -- so the user might skip some updates
            ok_text = _("Update"),
            ok_callback = function()
                if not installs.empty(false) then
                    ui:process(_install, _("Update patches:") .. installs.text(false))
                end
            end,
        }
    end

    ui:process(_update, _("Check for patch updates..."))
end

function ota:update()
    if not isDir(self.local_patches) then
        ui:info(_("You have no patches."))
        return
    end

    if NetworkMgr:isOnline() then
        self:_update()
    else
        ui:confirm {
            text = "Would you like to turn Wi-fi on ?",
            ok = _("Wi-fi on"),
            callback = function()
                NetworkMgr:turnOnWifiAndWaitForConnection(function() self:_update() end)
            end,
        }
    end
end

function ota:menu()
    return {
        text = T(_("Update %1"), GITHUB_REPO),
        callback = function() self:update() end,
    }
end

-- clean installs
local FileManager = require("apps/filemanager/filemanager")
local ReaderUI = require("apps/reader/readerui")

local orig_ReaderUI_showReader = ReaderUI.showReader
function ReaderUI:showReader(...)
    orig_ReaderUI_showReader(self, ...)
    ota:cleanBrokenInstalls()
end

local orig_FileManager_showFiles = FileManager.showFiles
function FileManager:showFiles(...)
    orig_FileManager_showFiles(self, ...)
    ota:cleanBrokenInstalls()
end

-- menu
local FileManagerMenu = require("apps/filemanager/filemanagermenu")
local ReaderMenu = require("apps/reader/modules/readermenu")

local function patch(menu, order)
    table.insert(order.more_tools, "----------------------------")
    table.insert(order.more_tools, "patch_update")
    menu.menu_items.patch_update = ota:menu()
end

local orig_FileManagerMenu_setUpdateItemTable = FileManagerMenu.setUpdateItemTable
function FileManagerMenu:setUpdateItemTable()
    patch(self, require("ui/elements/filemanager_menu_order"))
    orig_FileManagerMenu_setUpdateItemTable(self)
end

local orig_ReaderMenu_setUpdateItemTable = ReaderMenu.setUpdateItemTable
function ReaderMenu:setUpdateItemTable()
    patch(self, require("ui/elements/reader_menu_order"))
    orig_ReaderMenu_setUpdateItemTable(self)
end
