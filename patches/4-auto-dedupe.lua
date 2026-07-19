-- Auto Optimize Storage Patch (Clean up logs, core dumps, indexer files, and orphaned .sdr directories)
local Device = require("device")
local UIManager = require("ui/uimanager")
local logger = require("logger")

local AutoDedupe = {}

function AutoDedupe:init()
    self:onWakeUp()
end

function AutoDedupe:onWakeUp()
    -- Schedule background cleanup 30 seconds after wake to avoid UI lag
    UIManager:scheduleIn(30, function()
        logger.info("AutoDedupe: Running self-optimization storage sweep...")
        
        local script = [[
            # 1. Unconditionally clean up crash logs, core dumps, and indexer spam
            rm -f /mnt/us/*.log
            rm -f /mnt/us/koreader/crash.log
            rm -rf /mnt/us/system/syslog
            rm -rf /var/log/*
            rm -rf /var/tmp/*
            rm -f /mnt/us/KPPMainAppV2_*.core
            rm -rf /mnt/us/Indexer_Dump_*

            # Ensure core dump disable flags exist
            touch /mnt/us/DISABLE_CORE_DUMP
            touch /mnt/us/DISABLE_CORE_DUMP_ALERT

            # 2. Clean up orphaned .sdr folders
            for sdr in /mnt/us/epubs/*.sdr; do
                if [ -d "$sdr" ]; then
                    base="${sdr%.sdr}"
                    if [ ! -f "$base.epub" ] && [ ! -f "$base.pdf" ]; then
                        rm -rf "$sdr"
                    fi
                end
            done

            # 3. Check storage thresholds for low storage cleanups (e.g. < 500MB free)
            if [ -d /mnt/us ]; then
                FREE_SPACE_KB=$(df -k /mnt/us | tail -1 | awk '{print $4}')
                # 500MB is 512000 KB
                if [ "$FREE_SPACE_KB" -lt 512000 ]; then
                    # Force delete all old logs and Amazon documents (keeping launchers)
                    find /mnt/us -name "*.log" -exec rm -f {} \;
                    rm -f /mnt/us/update.bin /mnt/us/*.bin
                    find /mnt/us/documents -type f \( -name "*.mobi" -o -name "*.azw*" -o -name "*.pdf" -o -name "*.txt" \) ! -iname "*KUAL*" ! -iname "*koreader*" -exec rm -f {} +
                fi
            fi
        ]]
        os.execute(script)
    end)
end

return AutoDedupe
