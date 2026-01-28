function category_major_minor(tag, timestamp, record)
    local annotations = record["kubernetes"]["annotations"] -- k8s annotation
    if not record["stream"] then
        return -1, timestamp, record
    end
    local stream = record["stream"]  -- stdout/stderr
    if annotations and annotations["acryl.ai/appType"] then
        record["_cat_major"] = "jonathan"
        if annotations["acryl.ai/appType"] == "user" then
            record["_cat_minor"] = "user"
             if string.sub(string.lower(record["log"]), 1, 12) == "[jfb/worker/" then -- worker system log
                record["_cat_major"] = "jonathan"
                record["_cat_minor"] = "worker"
        elseif annotations["acryl.ai/appType"] == "system" then
            if string.sub(string.lower(record["log"]), 1, 9) == "[resource" then
                record["_cat_minor"] = "resource"
            elseif stream == "stdout" then
                record["_cat_minor"] = "usage"
            elseif stream == "stderr" then
                record["_cat_minor"] = "control"
            end
        end
    else 
        record["_cat_major"] = "thirdparty"
    end
    return 2, timestamp, record
end

function level_confirm(tag, timestamp, record)
    local lvl = "unmarked"
    if record["_cat_level"] then
        lvl = string.lower(record["_cat_level"])
        if lvl ~= "usage" and lvl ~= "debug" and lvl ~= "info" and lvl ~= "error" and lvl ~= "jonathan_usage" and lvl ~= "workspace_usage" then
            lvl = "unmarked"
        end
    end
    record["_cat_level"] = lvl
    if record["_cat_minor"] == "usage" and lvl ~= "usage" then
        record["_cat_minor"] = "control"
        record["_cat_level"] = "unmarked"
    end
    
    return 2, timestamp, record
end

function congregate_index(tag, timestamp, record)
    local _jfb_index = "congregate_failed"
    if record["_cat_major"] then
        local major = record["_cat_major"]
        if record["_cat_minor"] then
            local minor = record["_cat_minor"]
            if minor == "control" or minor == "resource" then
                local level = record["_cat_level"]
                _jfb_index = string.format("%s-%s-%s", major, minor, level)
            else
                _jfb_index = string.format("%s-%s", major, minor)
            end
        else
            _jfb_index = major
        end
    end
    record["_jfb_index"] = _jfb_index
    return 2, timestamp, record
end