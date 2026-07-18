-- Auto Time Sync Patch (Trigger NTP on Wake/Boot if Wi-Fi is connected)
local Device = require("device")
local UIManager = require("ui/uimanager")
local NetworkMgr = require("ui/network/manager")
local logger = require("logger")

local AutoTimeSync = {}

function AutoTimeSync:init()
    self:onWakeUp()
end

function AutoTimeSync:onWakeUp()
    -- Wait a bit for Wi-Fi to potentially reconnect after wake
    UIManager:scheduleIn(15, function()
        if NetworkMgr:isWifiOn() then
            logger.info("AutoTimeSync: Wi-Fi is on. Triggering NTP sync...")
            -- Use the timesync plugin's command or basic ntpd
            os.execute("ntpd -q -p pool.ntp.org > /dev/null 2>&1 &")
        end
    end)
end

return AutoTimeSync
