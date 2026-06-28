-- Disable raw image files from being treated as readable books
local DocumentRegistry = require("document/documentregistry")

local image_exts = { "jpg", "jpeg", "png", "gif", "webp", "bmp" }
for _, ext in ipairs(image_exts) do
    DocumentRegistry.filetype_provider[ext] = nil
end

local clean_providers = {}
for _, p in ipairs(DocumentRegistry.providers) do
    local is_img = false
    for _, ext in ipairs(image_exts) do
        if p.extension == ext then
            is_img = true
            break
        end
    end
    if not is_img then
        table.insert(clean_providers, p)
    end
end
DocumentRegistry.providers = clean_providers
