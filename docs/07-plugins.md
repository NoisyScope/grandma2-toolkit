# Lua plugins

Plugins live in the repo under `lua/plugins/<name>.lua`. `ma2kit plugins ...` puts them into the loaded show.

## Commands

| Command | What it does |
|---|---|
| `ma2kit plugins list` | Repo plugins, whether each is installed in the loaded show (and in which slot), plus other plugins in the show. |
| `ma2kit plugins install <name> [--slot N]` | Builds the plugin file, copies it to the console's plugin folder under `ma2kit/`, imports it into the first free plugin slot from `[pools] plugin_start` (default 100). |
| `ma2kit plugins update [<name> ...]` | Rebuilds and imports again over the same slot. Use after editing a plugin. Default: every installed ma2kit plugin. |
| `ma2kit plugins run <name or number> [--wait S]` | Starts the plugin and prints its output. For ma2kit plugins it waits until the plugin finishes and reports errors with the source file and line. |
| `ma2kit plugins remove <name> ...` | Deletes the plugin from the pool and removes its files. |

`install`, `update` and `remove` change the show, so they respect `[safety] allowed_shows`.

## Writing a plugin

```lua
-- description: One line shown by `ma2kit plugins list`.

local function Start()
    local slot = ma2kit.free_slot("Group", 500)
    ma2kit.log("first free group from 500:", slot)
    ma2kit.must("Fixture 1 Thru 10")      -- stops the plugin with an error if the command fails
    local ok, err = ma2kit.cmd("Store Group %d", slot)
    if not ok then ma2kit.log("store failed:", err) end
end

return Start
```

Rules:

- The file name is the plugin's name in the pool: letters, digits and `_`, starting with a letter. Prefix
  your own plugins with `ma2kit_` so they never clash with plugins already in a show.
- End the file with `return Start` (or `return Start, Cleanup`), as for any grandMA2 plugin.
- Never hard-code fixture IDs, group numbers or fixture types: read them from the show (`ma2kit.exists`,
  `ma2kit.free_slot`, `ma2kit.var`, `gma.show.getobj.*`) so the plugin works in any show.

### Helper library (`lua/lib/ma2kit.lua`)

Added in front of every plugin at install time, available as the local table `ma2kit`:

| Function | Purpose |
|---|---|
| `ma2kit.log(...)` | Print to the command line (shown by `plugins run`) and the system monitor. |
| `ma2kit.cmd(fmt, ...)` | Run a command line (`string.format` style). Returns `true` or `false, error_text`. |
| `ma2kit.must(fmt, ...)` | Same, but stops the plugin with an error when the command fails. |
| `ma2kit.exists("Group 5")` | Whether an object exists. |
| `ma2kit.free_slot(pool, start, count)` | First number from `start` where `count` slots in a row are empty. |
| `ma2kit.var(name)` | A system variable, e.g. `ma2kit.var("SHOWFILE")`. |
| `ma2kit.confirm(title, text)` / `ma2kit.input(title, default)` | Pop-ups on the console screen. |

## How it works (verified on 3.9.61)

- The installed file is `<plugin folder>/ma2kit/<name>.lua` (helper library + your code wrapped in a
  function) plus `<name>.xml`. `Import "ma2kit/<name>.xml" At Plugin N` resolves the path inside the plugin folder.
- **The show stores a copy of the plugin code at import time.** `ReloadPlugins` restarts the Lua engine
  but does not read edited files; that is why `update` imports again over the same slot (answering the
  console's "Overwrite Confirmation" with Overwrite for that one object).
- `Plugin "name"` returns to the prompt at once and the plugin runs afterwards. The wrapper ends every
  run with `MA2KIT_DONE <name> ok` or `MA2KIT_DONE <name> error: ...` on the command line; `plugins run`
  waits for that marker.
- The console's Lua is **5.3**. `gma.cmd()` returns `nil` on success and the error text on failure.
  `gma.show.getobj.handle()` returns `nil` for missing objects. `gma.echo()` goes to the system monitor,
  `gma.feedback()` to the command line.
- Inside a plugin, `$USER` is the console's own user (e.g. `administrator`), not the Telnet user.
- Lua errors name the chunk `plugin_<slot>_<name>` with the line in the installed file; `plugins run`
  translates that to `lua/plugins/<name>.lua:<line>`.
