-- description: List the Lua environment: version, standard libraries and every gma.* function. Read-only.
--
-- Used to check docs/02-lua-api.md against the running console. Output goes to the command line
-- feedback (and the system monitor), one line per entry, prefixed "API ".

local function out(fmt, ...)
    gma.feedback("API " .. string.format(fmt, ...))
end

local function walk(tbl, prefix, seen)
    seen = seen or {}
    if seen[tbl] then return end
    seen[tbl] = true
    local keys = {}
    for k in pairs(tbl) do keys[#keys + 1] = tostring(k) end
    table.sort(keys)
    for _, k in ipairs(keys) do
        local v = tbl[k]
        local name = prefix .. "." .. k
        if type(v) == "table" then
            walk(v, name, seen)
        else
            out("%s %s", type(v), name)
        end
    end
end

local function Start()
    out("lua %s", _VERSION)
    local libs = {}
    for _, lib in ipairs({ "string", "table", "math", "utf8", "coroutine", "os", "io", "debug", "package",
                           "require", "load", "loadfile", "dofile", "pcall", "xpcall", "select" }) do
        libs[#libs + 1] = lib .. "=" .. type(_G[lib])
    end
    out("globals %s", table.concat(libs, " "))
    if type(os) == "table" then
        local f = {}
        for k in pairs(os) do f[#f + 1] = k end
        table.sort(f)
        out("os %s", table.concat(f, " "))
    end
    if type(io) == "table" then
        local f = {}
        for k in pairs(io) do f[#f + 1] = k end
        table.sort(f)
        out("io %s", table.concat(f, " "))
    end
    if type(package) == "table" then
        out("package.path %s", tostring(package.path))
    end
    walk(gma, "gma")
    out("hardware %s / host %s %s", tostring(gma.gethardwaretype and gma.gethardwaretype()),
        tostring(gma.network.gethosttype()), tostring(gma.network.gethostsubtype()))
    out("build %s %s %s", tostring(gma.build_date()), tostring(gma.build_time()), tostring(gma.git_version()))
    out("gettime %s", tostring(gma.gettime()))
end

return Start
