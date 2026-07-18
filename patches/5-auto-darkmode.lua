-- Auto Dark Mode Patch based on Chicago sun positioning
local UIManager = require("ui/uimanager")
local logger = require("logger")

local AutoDarkMode = {}

-- Approximate Chicago Sunrise/Sunset by month (Minutes past midnight)
local sun_data = {
    [1] = { rise = 7*60 + 15, set = 16*60 + 45 }, -- Jan
    [2] = { rise = 6*60 + 45, set = 17*60 + 25 }, -- Feb
    [3] = { rise = 7*60 + 0,  set = 19*60 + 0  }, -- Mar (CDT shift)
    [4] = { rise = 6*60 + 10, set = 19*60 + 35 }, -- Apr
    [5] = { rise = 5*60 + 35, set = 20*60 + 5  }, -- May
    [6] = { rise = 5*60 + 15, set = 20*60 + 25 }, -- Jun
    [7] = { rise = 5*60 + 30, set = 20*60 + 25 }, -- Jul
    [8] = { rise = 6*60 + 0,  set = 19*60 + 55 }, -- Aug
    [9] = { rise = 6*60 + 30, set = 19*60 + 5  }, -- Sep
    [10] = { rise = 7*60 + 5,  set = 18*60 + 15 }, -- Oct
    [11] = { rise = 6*60 + 40, set = 16*60 + 35 }, -- Nov (CST shift)
    [12] = { rise = 7*60 + 10, set = 16*60 + 20 }  -- Dec
}

function AutoDarkMode:init()
    self:onWakeUp()
end

function AutoDarkMode:onWakeUp()
    -- Give the system a couple of seconds to settle or sync time if needed
    UIManager:scheduleIn(3, function()
        self:applyTheme()
    end)
end

function AutoDarkMode:applyTheme()
    local date_table = os.date("*t")
    if not date_table then return end
    
    local month = date_table.month
    local current_minutes = date_table.hour * 60 + date_table.min
    
    local today_data = sun_data[month]
    if not today_data then return end
    
    local is_night = (current_minutes < today_data.rise) or (current_minutes >= today_data.set)
    
    logger.info("AutoDarkMode: Current minutes=" .. current_minutes .. ", sunrise=" .. today_data.rise .. ", sunset=" .. today_data.set)
    
    local G_reader_settings = G_reader_settings
    if G_reader_settings then
        local current_night_mode = G_reader_settings:isTrue("night_mode")
        
        if is_night and not current_night_mode then
            logger.info("AutoDarkMode: Switching to Dark Mode")
            UIManager:ToggleNightMode(true)
        elseif not is_night and current_night_mode then
            logger.info("AutoDarkMode: Switching to Light Mode")
            UIManager:ToggleNightMode(false)
        end
    end
end

return AutoDarkMode
