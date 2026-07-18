-- Auto Dedupe Storage Patch (Clean up orphaned .sdr folders)
local Device = require("device")
local UIManager = require("ui/uimanager")
local logger = require("logger")

local AutoDedupe = {}

function AutoDedupe:init()
    self:onWakeUp()
end

function AutoDedupe:onWakeUp()
    -- Schedule a background cleanup 30 seconds after wake to not block UI
    UIManager:scheduleIn(30, function()
        logger.info("AutoDedupe: Scanning for orphaned .sdr folders...")
        -- Find .sdr directories and remove them if the base epub/pdf doesn't exist
        local script = [[
            for sdr in /mnt/us/epubs/*.sdr; do
                if [ -d "$sdr" ]; then
                    base="${sdr%.sdr}"
                    if [ ! -f "$base.epub" ] && [ ! -f "$base.pdf" ]; then
                        rm -rf "$sdr"
                    fi
                end
            done
        ]]
        os.execute(script)
    end)
end

return AutoDedupe
