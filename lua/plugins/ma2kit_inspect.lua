-- description: Print class, children and properties of objects in the show tree. Read-only.
--
-- Which objects: the show variable $MA2KIT_INSPECT, a ";"-separated list of command-line names, e.g.
--   SetVar $MA2KIT_INSPECT = "Fixture 101;Group 1"
-- If it is not set, the first object of a few common pools is inspected.
-- Output goes to the command line feedback, prefixed "OBJ ".

local O = gma.show.getobj
local P = gma.show.property

local function out(fmt, ...)
    gma.feedback("OBJ " .. string.format(fmt, ...))
end

local function props(h, indent)
    local n = P.amount(h) or 0
    for i = 0, n - 1 do
        local name = P.name(h, i)
        out("%s%s = %s", indent, tostring(name), tostring(P.get(h, i)))
    end
end

local function describe(name, h, depth)
    out("%s  class=%s index=%s number=%s name=%s label=%s children=%s", name, tostring(O.class(h)),
        tostring(O.index(h)), tostring(O.number(h)), tostring(O.name(h)), tostring(O.label(h)), tostring(O.amount(h)))
    props(h, "    ")
    local parent = O.parent(h)
    if parent then
        out("    parent: class=%s name=%s", tostring(O.class(parent)), tostring(O.name(parent)))
    end
    if depth > 0 and (O.amount(h) or 0) > 0 then
        local c = O.child(h, 0)
        if c then
            describe(name .. " / child 0", c, depth - 1)
        end
    end
end

local DEFAULT = {
    "Fixture 1", "Channel 1", "FixtureType 1", "Group 1", "Preset 1.1", "Preset 4.1", "Sequence 1",
    "Executor 1", "Page 1", "Effect 1", "Macro 1", "Plugin 1", "Layout 1", "View 1", "World 1",
    "Filter 1", "MAtricks 1", "Timecode 1", "Timer 1", "Agenda 1", "Form 1", "DmxUniverse 1",
}

local function Start()
    local list = gma.show.getvar("MA2KIT_INSPECT")
    local names = {}
    if list and list ~= "" then
        for item in string.gmatch(list, "[^;]+") do
            names[#names + 1] = item:match("^%s*(.-)%s*$")
        end
    else
        names = DEFAULT
    end
    for _, name in ipairs(names) do
        local h = O.handle(name)
        if h then
            describe(name, h, 1)
        else
            out("%s  (no object)", name)
        end
    end
end

return Start
