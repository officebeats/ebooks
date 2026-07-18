-- Auto Local Time Sync Patch
local UIManager = require("ui/uimanager")
local NetworkMgr = require("ui/network/manager")
local logger = require("logger")

local AutoLocalTimeSync = {}

function AutoLocalTimeSync:init()
    self:onWakeUp()
end

function AutoLocalTimeSync:onWakeUp()
    UIManager:scheduleIn(15, function()
        if NetworkMgr:isWifiOn() then
            logger.info("AutoLocalTimeSync: Wi-Fi is on. Fetching local time...")
            
            -- Fetch time for Chicago directly via WorldTimeAPI
            local script = [[
                #!/bin/sh
                # Use curl to get the current datetime for Chicago
                JSON=$(curl -s --max-time 10 http://worldtimeapi.org/api/timezone/America/Chicago)
                
                # Extract the datetime string (e.g. 2026-07-18T14:05:30.123456-05:00)
                DATETIME=$(echo "$JSON" | grep -o '"datetime":"[^"]*' | cut -d'"' -f4)
                
                if [ -n "$DATETIME" ]; then
                    # Extract date and time parts
                    DATE_PART=$(echo "$DATETIME" | cut -dT -f1)
                    TIME_PART=$(echo "$DATETIME" | cut -dT -f2 | cut -d. -f1)
                    
                    # Set the system date directly to local time!
                    date -s "$DATE_PART $TIME_PART"
                    hwclock -w 2>/dev/null
                fi
            ]]
            
            local f = io.open("/tmp/sync_time.sh", "w")
            if f then
                f:write(script)
                f:close()
                os.execute("chmod +x /tmp/sync_time.sh && /tmp/sync_time.sh &")
            end
        end
    end)
end

-- Run once on startup, then loop every 5 minutes to fight the Kindle OS UTC override
local function loopSync()
    AutoLocalTimeSync:onWakeUp()
    UIManager:scheduleIn(300, loopSync)
end
UIManager:scheduleIn(5, loopSync)

return AutoLocalTimeSync
