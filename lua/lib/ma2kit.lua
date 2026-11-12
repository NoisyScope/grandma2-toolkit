-- ma2kit Lua helper library.
-- Prepended to every ma2kit plugin at install time (the console's Lua has no reliable `require` path).
-- Verified on grandMA2 onPC 3.9.61 (Lua 5.3):
--   gma.cmd(line) returns nil on success and the error text (e.g. "OBJECT DOES NOT EXIST") on failure;
--   gma.show.getobj.handle("Group 9999") returns nil for a missing object;
--   gma.echo() goes to the system monitor (Telnet port 30001), gma.feedback() to the command line.

local ma2kit = { version = "0.2.0" }

local function join(...)
    local parts = {}
    for i = 1, select("#", ...) do
        parts[#parts + 1] = tostring((select(i, ...)))
    end
    return table.concat(parts, " ")
end

-- Log to both the system monitor and the command line feedback.
function ma2kit.log(...)
    local text = join(...)
    gma.echo("[ma2kit] " .. text)
    gma.feedback(text)
end

-- Run a command line. Returns true, or false and the console's error text.
-- ma2kit.cmd("Store Group %d", 5)
function ma2kit.cmd(fmt, ...)
    local line = select("#", ...) > 0 and string.format(fmt, ...) or fmt
    local err = gma.cmd(line)
    if err ~= nil then
        gma.echo("[ma2kit] command failed: " .. line .. " -> " .. tostring(err))
        return false, err
    end
    return true
end

-- Like ma2kit.cmd but raises an error (stopping the plugin) when the command fails.
function ma2kit.must(fmt, ...)
    local ok, err = ma2kit.cmd(fmt, ...)
    if not ok then
        error(string.format("command failed: %s (%s)", select("#", ...) > 0 and string.format(fmt, ...) or fmt, tostring(err)), 2)
    end
end

-- true when an object exists, e.g. ma2kit.exists("Group 5")
function ma2kit.exists(object)
    return gma.show.getobj.handle(object) ~= nil
end

-- First number >= start where `count` consecutive slots of `pool` are free.
-- ma2kit.free_slot("Group", 500, 10)
function ma2kit.free_slot(pool, start, count, limit)
    count, limit = count or 1, limit or 10000
    local n = start or 1
    while n + count - 1 <= limit do
        local clash = nil
        for k = n + count - 1, n, -1 do
            if ma2kit.exists(pool .. " " .. k) then
                clash = k
                break
            end
        end
        if not clash then
            return n
        end
        n = clash + 1
    end
    return nil
end

function ma2kit.var(name)
    return gma.show.getvar(name)
end

function ma2kit.confirm(title, message)
    return gma.gui.confirm(title, message)
end

function ma2kit.input(title, default)
    return gma.textinput(title, default or "")
end

-- Internal: runs a plugin's Start function and reports the outcome on the command line, where
-- the ma2kit CLI waits for the "MA2KIT_DONE <name> ..." marker.
function ma2kit._run(name, start, ...)
    local ok, err = pcall(start, ...)
    if ok then
        gma.feedback("MA2KIT_DONE " .. name .. " ok")
    else
        gma.echo("[ma2kit] " .. name .. " error: " .. tostring(err))
        gma.feedback("MA2KIT_DONE " .. name .. " error: " .. tostring(err))
    end
end
