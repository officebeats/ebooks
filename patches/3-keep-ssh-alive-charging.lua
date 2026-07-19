-- Keep SSH alive when plugged in by preventing sleep
local UIManager = require("ui/uimanager")
local function pollCharging()
    local f = io.popen("lipc-get-prop com.lab126.powerd isCharging 2>/dev/null")
    local is_charging = false
    if f then
        local res = f:read("*a")
        f:close()
        if res and tonumber(res) == 1 then is_charging = true end
    end
    if is_charging then
        os.execute("lipc-set-prop com.lab126.powerd preventScreenSaver 1")
    else
        os.execute("lipc-set-prop com.lab126.powerd preventScreenSaver 0")
    end
    UIManager:scheduleIn(30, pollCharging)
end
UIManager:scheduleIn(10, pollCharging)
