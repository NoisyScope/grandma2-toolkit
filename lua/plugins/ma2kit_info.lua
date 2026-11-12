-- description: Print console, show and selection info. Read-only; used to test the plugin pipeline.
--
-- ma2kit plugin conventions:
--   * the file name (without .lua) is the plugin's name in the console's plugin pool;
--   * the first "-- description:" line is shown by `ma2kit plugins list`;
--   * the ma2kit helper library (lua/lib/ma2kit.lua) is available as the local table `ma2kit`;
--   * end the file with `return Start` (optionally `return Start, Cleanup`), like any grandMA2 plugin.

local function Start()
    ma2kit.log("ma2kit_info: library " .. ma2kit.version .. ", " .. _VERSION)
    for _, name in ipairs({ "VERSION", "SHOWFILE", "USER", "USERRIGHTS", "HOSTSTATUS", "SELECTEDFIXTURESCOUNT", "SELECTEDEXEC" }) do
        ma2kit.log(string.format("  $%s = %s", name, tostring(ma2kit.var(name))))
    end
    for _, pool in ipairs({ "Group", "Macro", "Effect", "Sequence" }) do
        ma2kit.log(string.format("  first free %s slot: %s", pool, tostring(ma2kit.free_slot(pool, 1))))
    end
end

return Start
