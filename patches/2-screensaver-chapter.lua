-- Youd need a version >= v2025.04-12 to be able to show the screen saver's info message

local InfoMessage = require("ui/widget/infomessage")
local Math = require("optmath")
local ReaderUI = require("apps/reader/readerui")
local Screensaver = require("ui/screensaver")
local UIManager = require("ui/uimanager")
local _ = require("gettext")

local orig_Screensaver_expandSpecial = Screensaver.expandSpecial

Screensaver.expandSpecial = function(self, message)
    local chapter_title = ""
    local chapter_percent = 0

    local msg = orig_Screensaver_expandSpecial(self, message)
    local ui = ReaderUI.instance
    if ui then
        local current_page = ui.view.state.page or 1

        chapter_title = ui.toc:getTocTitleByPage(current_page)
        if chapter_title and chapter_title ~= "" then
            chapter_title = chapter_title:gsub(" ", "\xC2\xA0") -- replace space with no-break-space
        end

        local ch_read = ui.toc:getChapterPagesDone(current_page)
        if ch_read then
            ch_read = ch_read + 1
            local ch_count = ui.toc:getChapterPageCount(current_page)
            if ch_read == 1 then
                chapter_percent = 0
            elseif ch_read == ch_count then
                chapter_percent = 100
            else
                chapter_percent = Math.round(Math.clamp(((ch_read * 100) / ch_count), 1, 99))
            end
        end
    end
    local replace = {
        ["%C"] = chapter_title,
        ["%P"] = chapter_percent,
    }
    msg = msg:gsub("(%%%a)", replace)
    return msg
end

local info_text = [[
%T title
%A author(s)
%S series
%c current page number
%t total page number
%p percentage read
%h time left in chapter
%H time left in document
%b battery level
%B battery symbol
%C chapter title
%P chapter percent]]

local orig_Screensaver_setMessage = Screensaver.setMessage

Screensaver.setMessage = function(self)
    orig_Screensaver_setMessage(self)
    for widget in UIManager:topdown_widgets_iter() do
        if widget.title == _("Sleep screen message") then
            for _i, button in ipairs(widget.buttons[1]) do
                if button.text == _("Info") then
                    button.callback = function()
                        UIManager:show(InfoMessage:new {
                            text = _(info_text),
                            monospace_font = true,
                        })
                    end
                    return
                end
            end
        end
    end
end
