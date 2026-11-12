# grandMA2 Lua API reference (onPC 3.9.61)

Marks: **✔** observed on onPC 3.9.61.5 by this project; **○** listed by MA (signature comments at the end of
`plugins\plugin_1.lua`) or used in MA's test plugins, but behaviour not checked here.

The list of functions below is complete: it was produced on the console by the read-only plugin
`lua/plugins/ma2kit_api_dump.lua` (`ma2kit plugins install ma2kit_api_dump`, then
`ma2kit plugins run ma2kit_api_dump`). Run it again after a console update to see what changed.

## The environment

- ✔ `_VERSION` is `Lua 5.3`.
- ✔ The standard libraries are all there: `string`, `table`, `math`, `utf8`, `coroutine`, `os`, `io`, `debug`,
  `package`, `require`, `load`, `loadfile`, `dofile`. `os` and `io` are **not** sandboxed (`os.execute`,
  `os.remove`, `io.open`, `io.popen` exist), so a plugin can read and write any file the onPC process can.
- ✔ `package.path` is `<data root>/plugins/?.lua;<data root>/plugins/requirements/?.lua`. ma2kit still
  bundles its helper library into each plugin, so plugins do not depend on files being in place.
- ✔ Errors are reported as `[string "plugin_<slot>_<name>"]:<line>: <message>`; ma2kit maps the line back
  to the source file ([07](07-plugins.md)).

## Plugin structure

✔ A plugin is a pool object made from an XML file that names a Lua file (MA's example,
`plugins\plugin_1.xml`, shortened):

```xml
<MA xmlns="http://schemas.malighting.de/grandma2/xml/MA" major_vers="3" minor_vers="0" stream_vers="187">
    <Info datetime="2015-03-20T10:08:17" showfile="lua_init" />
    <Plugin index="1" execute_on_load="0" name="Plugin 1" luafile="plugin_1.lua" />
</MA>
```

✔ The Lua file runs once when it is imported or loaded and must **return** the entry function, optionally
followed by a cleanup function: `return Start, Cleanup`. ○ The chunk receives two arguments,
`internal_name, visible_name = select(1, ...), select(2, ...)`. ○ `Cleanup` runs when the plugin is
stopped or when a timer registered with it ends.

✔ The show stores a copy of the code when it is imported. Editing the `.lua` file later changes nothing
until the plugin is imported again over its slot (`ReloadPlugins` does **not** re-read the files).

## Functions

### Output and commands

| Function | Notes |
|---|---|
| `gma.cmd(line)` | ✔ Runs one command line; several commands separated by `;` all run. Returns `nil` on success and the error text (e.g. `OBJECT DOES NOT EXIST`) of a failing command otherwise. The command's printed output is **not** returned; the feedback shows each command as `Macro : <command>` |
| `gma.feedback(...)` | ✔ Prints to the command-line feedback (and so to Telnet port 30000, after the prompt) |
| `gma.echo(...)` | ✔ Prints to the system monitor (Telnet port 30001), not to the command line |
| `gma.sleep(seconds)` | ✔ Pauses the plugin; the console keeps running (○ same as `coroutine.yield(seconds)`) |
| `gma.timer(fn, dt, max_count, [cleanup])` | ○ Calls `fn(timer, count)` every `dt` seconds, `max_count` times, then `cleanup` |
| `gma.gettime()` | ✔ Seconds since the console started, as a float (e.g. `32170.859`) |

### Dialogs (shown on the onPC screen)

These wait for someone at the console. A plugin started over Telnet with nobody watching will hang on them.

| Function | Notes |
|---|---|
| `gma.gui.confirm(title, message)` | ○ OK/Cancel box; returns a boolean |
| `gma.gui.msgbox(title, message)` | ○ Message box |
| `gma.textinput(title, [default])` | ○ Text entry; returns the string (○ `nil` when cancelled) |
| `gma.gui.progress.start(name)` → handle | ○ Progress bar; also `stop(h)`, `settext(h, text)`, `setrange(h, from, to)`, `set(h, value)` |

### Variables

| Function | Notes |
|---|---|
| `gma.show.getvar(name)` | ✔ Show/system variable without `$`: `getvar("VERSION")` → `3.9.61.5`. Also `SHOWFILE`, `USER`, `USERRIGHTS`, `HOSTSTATUS`, `PATH`, `PLUGINPATH`, `TEMPPATH`, `SELECTEDFIXTURESCOUNT`, `SELECTEDEXEC`, and anything set with `SetVar $X = …`. Missing → `nil` |
| `gma.show.setvar(name, value)` | ○ Sets a show variable (same as `SetVar`) |
| `gma.user.getvar(name)` / `gma.user.setvar(name, value)` | ○ Per-user variables (`SetUserVar`) |
| `gma.user.getcmddest()` | ○ Handle of the current `cd` location |
| `gma.user.getselectedexec()` | ○ Handle of the selected executor |

### The object tree: `gma.show.getobj`

Handles are numbers. Get one from a command-line name, then walk the tree.

| Function | Notes |
|---|---|
| `handle(name)` | ✔ `handle("Group 500")`, `handle("Preset 4.1")`, `handle("Fixture 100")`, `handle("FixtureType 1")`, `handle("DmxUniverse 1")` all work. Returns `nil` when the object does not exist |
| `class(h)` | ✔ Class name, e.g. `CMD_GROUP` (table below) |
| `index(h)` | ✔ 0-based position under the parent (`Group 500` → 499) |
| `number(h)` | ✔ Command-line number: `500`, `4.1`, `1.1` (DMX channel) |
| `name(h)` | ✔ Display name **followed by the number**: `ALL FIXTURES 500`, `White 1 4.1` |
| `label(h)` | ✔ The label alone (`ALL FIXTURES`), or `nil` when none is set. Prefer this for names |
| `amount(h)` | ✔ Number of children |
| `child(h, i)` | ✔ Child by **0-based** index (`child(fixture, 0)` is its first subfixture; in a sequence child 0 is cue 0) |
| `parent(h)` | ✔ Parent handle (a group's parent is the group pool, a fixture's is its layer) |
| `verify(h)` / `compare(h1, h2)` | ○ Handle still valid / same object |

### Properties: `gma.show.property`

| Function | Notes |
|---|---|
| `amount(h)` | ✔ Number of properties |
| `name(h, i)` | ✔ Property name by **0-based** index. Names are column headers; `\|` marks a line break in the header: `Pan DMX\|Invert`, `Pos\|X` |
| `get(h, i_or_name)` | ✔ Value as a string. By name, use the `List` column name (no spaces, no `\|`): `get(sub, "PanOffset")` → `"0.00"`. Booleans that `List` shows as `Off` come back as an empty string |

There is no `property.set`: change properties with `gma.cmd("Assign ... /Name=value")`.

### DMX, import/export, network, build

| Function | Notes |
|---|---|
| `gma.show.getdmx(addr)` / `getdmx(recycle_table, addr, amount)` | ○ Current DMX output value(s) by absolute address |
| `gma.export(file, table)`, `gma.export_csv(file, table)`, `gma.export_json(file, table)` | ○ Write a Lua table to a file |
| `gma.import(file, [subfolder])` | ○ Read an XML file into a Lua table |
| `gma.network.gethosttype()` / `gethostsubtype()` | ✔ `Console` / `onPC` |
| `gma.network.getprimaryip()`, `getsecondaryip()`, `getstatus()`, `getsessionnumber()`, `getsessionname()`, `getslot()` | ○ |
| `gma.network.gethostdata(ip, [recycle])`, `getmanetslot(slot, [recycle])`, `getperformance(slot, [recycle])` | ○ Tables of MA-Net data |
| `gma.gethardwaretype()` | ✔ `GMA2` |
| `gma.build_date()`, `gma.build_time()`, `gma.git_version()` | ✔ `Oct 30 2025`, `08:10:51`, a commit hash |

### Present but not documented by MA

✔ Found by the API dump; signatures unknown, not used by ma2kit.

- `gma.canbus.hardkey`, `gma.canbus.encoder`, `gma.canbus.fader`, `gma.canbus.wheel`, `gma.canbus.ball`:
  ○ simulate console hardware. MA's system tests call `gma.canbus.hardkey(...)` with key codes from
  `gma.canbus.data.hardkeys` (a table of about 130 keys: `STORE`, `AT`, `CLEAR`, `GO_PLUS`, `X1`…`X20`,
  `V1`…`V10`, …). Avoid: a pressed key acts like a real key press.
- `gma.timestamp.amount`, `gma.timestamp.name`, `gma.timestamp.time`.
- `gma.draw.getperformance`.

## Object classes seen

✔ From `ma2kit_inspect` on the test show:

| Object | Class | Parent class |
|---|---|---|
| `Group N` | `CMD_GROUP` | `CMD_GROUP_POOL` |
| `Preset T.N` | `CMD_PRESET` | `CMD_PRESET_POOL` |
| `Effect N` / its lines | `CMD_EFFECT` / `CMD_EFFECT_LINE` | `CMD_EFFECT_POOL` |
| `Macro N` / its lines | `CMD_MACRO` / `CMD_MACRO_LINE_OBJECT` | `CMD_MACRO_POOL` |
| `Plugin N` | `CMD_LUA_PLUGIN` | `CMD_LUA_PLUGIN_COLLECT` |
| `Fixture N` / subfixture | `CMD_FIXTURE` / `CMD_SUBFIXTURE` | `CMD_FIXTURE_LAYER` |
| `FixtureType N` | `CMD_FIXTURE_TYPE` | `CMD_FIXTURE_TYPE_COLLECT` |
| `DmxUniverse N` / channel | `CMD_DMX_UNIVERSE` / `CMD_DMX_CHANNEL` | `CMD_DMX_UNIVERSE_COLLECT` |
| `Layout N` | `CMD_GROUP` (with a `CMD_LAYOUT_DATA` child) | `CMD_LAYOUT_POOL` |
| `World N`, `Filter N` | `CMD_FILTER` | `CMD_WORLD_POOL`, `CMD_FILTER_POOL` |
| `MAtricks N` | `CMD_MATRIX` | `CMD_MATRIX_POOL` |
| `Page N`, `View N`, `Timer N`, `Form N` | `CMD_PAGE`, `CMD_VIEW`, `CMD_TIMER`, `CMD_FORM` | their pools |

To see any object's class, children and properties:

```
ma2kit cmd 'SetVar $MA2KIT_INSPECT = "Fixture 100;Effect 1"'
ma2kit plugins run ma2kit_inspect
```

## Patterns

```lua
-- Does an object exist?
local exists = gma.show.getobj.handle("Group 500") ~= nil

-- Run a command and check it.
local err = gma.cmd("Label Group 500 \"Front\"")
if err then gma.echo("failed: " .. err) end

-- Read a fixture's pan/tilt patch settings (child 0 = first subfixture).
local O, P = gma.show.getobj, gma.show.property
local sub = O.child(O.handle("Fixture 100"), 0)
local pan_offset = P.get(sub, "PanOffset")    -- "0.00"
local swapped    = P.get(sub, "Swap") ~= ""    -- "" means Off
```

ma2kit's helper library wraps the first two patterns as `ma2kit.exists` and `ma2kit.cmd` / `ma2kit.must`
([07](07-plugins.md)).
