# grandMA2 command-line cheat sheet

The commands a script is most likely to need, with the syntax this project checked on onPC 3.9.61.

Marks: **✔** sent to onPC 3.9.61 by this project and the result checked; **○** taken from MA's own
predefined macros (`macros\predefined.xml`) or test plugins (`plugins\systemtests\`), or from MA's manual,
not sent here.

> ⚠ With a Command Wing or node connected, anything that selects with highlight on, sets values, runs
> playbacks or changes pan/tilt patch settings acts on real fixtures. ma2kit treats those as live and asks first.

## Syntax basics

| Form | Example | Notes |
|---|---|---|
| Keyword + number | `Group 5`, `Preset 4.2`, `Executor 1.3` | ✔ Presets are `type.number`; executors `page.number` |
| Ranges and lists | `Fixture 1 Thru 10`, `Fixture 1 + 3 + 5`, `Fixture 1 Thru 10 - 4` | ✔ `+` keeps the order you type |
| Open range | `Delete Group 500 Thru`, `Fixture Thru` | ○ "from 500 to the end"; `Fixture Thru` alone means the current selection |
| All in a pool | `List Preset 4.*` | ✔ `List Preset 4` alone finds nothing |
| By name | `Group "Front"`, `Preset "Color"."Red 2"`, `Preset 4."Red*"`, `Group "ALL*"` | ✔ quotes for names, `*` as wildcard. The name must match fully (`"Red"` does not find `Red 2`) |
| Options | `/nc` (no confirm), `/o` (overwrite), `/merge`, `/style=csv` | ✔ `/nc` skips the confirmation dialog |
| Properties | `cd "Groups"; cd 1; Assign 5 /Name="x"; cd /`, `Assign 1 /PosX=-5` | ✔ property = `List` column name without spaces. ✔ Over Telnet this only works **from inside the tree**, at the object's parent: `Assign Group 5 /Name="x"` at the root answers `Error #14` (same for Sequence, Macro line, Timecode, Executor, Fixture) |
| Several commands | `ClearAll; Group 5` | ✔ `;` separates commands on one line (also in `gma.cmd`) |
| Tree paths | `Assign Root ."Settings"."Global" /Telnet="Login Disabled"` | ○ dotted path from the root of the tree |
| Variables | `SetVar $x = 5`, `AddVar $x = +0.5`, `SetUserVar $y = "a"`, `$SHOWFILE` | ✔ `SetVar`, `$NAME` in commands; ○ `AddVar` |

Keywords are not case-sensitive (✔ `list group` works). The console echoes the normalised form, e.g.
`cd` → `ChangeDest`, `Lua` → `LUA`.

## Reading (safe)

| Command | What it shows |
|---|---|
| `List` | ✔ Children of the current tree location (at the root: the whole top level, see [01](01-how-grandma2-works.md#2-the-object-tree)) |
| `List Group`, `List Macro`, `List Plugin`, `List Effect`, `List Layout`, `List World`, `List MAtricks`, `List User` | ✔ Pool contents as a table |
| `List Preset 4.*` | ✔ One preset type |
| `ListVar` | ✔ All system variables (`$VERSION`, `$SHOWFILE`, `$USER`, `$PATH` …) |
| `ListUserVar` | ✔ The current user's variables |
| `ListShows` | ✔ Show files with date and size |
| `ListLibrary`, `ListMacroLibrary`, `ListEffectLibrary`, `ListPluginLibrary` | ✔ Files on disk available for import |
| `ListOops` | ✔ Undo list ("No more undos available") |
| `ListFaderModules` | ✔ Connected fader hardware |
| `Info Group 5` | ✔ Accepted; prints nothing for a group without an info text |

Missing objects: `Error #14: OBJECT DOES NOT EXIST` for an unknown keyword, but `WARNING, NO OBJECTS
FOUND FOR LIST` when the pool exists and is empty (✔ both).

## Navigating the object tree

| Command | Notes |
|---|---|
| `cd /` | ✔ Back to the root |
| `cd "EditSetup"`, `cd 11` | ✔ Into a child by name or by its number in `List` |
| `cd ..` | ○ Up one level |

✔ The prompt shows where you are (`EditSetup/Layers 4 >`). Each Telnet login starts at the root; always
`cd /` at the end of a script.

## Selection and programmer

| Command | Notes |
|---|---|
| `Fixture 1 Thru 10`, `Group 5`, `SelFix Group 5` | ✔ Select (no output change by itself) |
| `ClearSelection` | ✔ Deselect; `Error #72` when nothing was selected |
| `Clear`, `ClearAll` | ○ Clear selection / programmer (`ClearAll` clears both) |
| `At 50`, `Fixture 1 At 100`, `At Preset 4.2`, `Full`, `Off` | ○ Set values: **live output** |
| `Fixture 100; Attribute "Tilt" At 30` | ✔ One attribute of the selection; seen in the Stage view |
| `Highlight`, `Highlight Off` | ○ Highlight the selection: **live output** |
| `Align "<>"`, `Align "off"` | ○ Spread values across the selection |
| `MAtricksReset`, `MAtricks 1` | ○ |
| `Blind`, `Preview` | ○ Program without output (Blind) / preview mode |

## Storing and editing pool objects

| Command | Notes |
|---|---|
| `Store Group 500` | ✔ Empty slot: no question. Occupied slot: overwritten without asking, so check first (`ma2kit show free`) |
| `Store Group 500 /o /nc` | ○ Overwrite, no dialog |
| `Label Group 500 "Front"` | ✔ `WARNING, NO OBJECTS FOUND FOR LABEL` if the group does not exist |
| `Delete Plugin 101 /nc`, `Delete Group 500` | ✔ `/nc` deletes without a dialog; ○ without it the console may ask |
| `Copy Group 1 At 600`, `Move Group 1 At 600` | ○ |
| `Store Macro 900`, `Store Macro 1.900.1` | ✔ New macro, new macro line |
| `cd "Macros"; cd 1; cd 900; Assign 1 /CMD="ClearAll" /Wait=0.5; cd /` | ✔ Set a macro line's command and wait. `Assign Macro 1.900.1 /cmd="…"` at the root: `Error #14` over Telnet |
| `Assign Effect 1.1 /lowvalue=5 /speed=80` | ○ Effect line properties (`Effect 1.1` = effect 1, line 1); expect to need the in-tree form |
| `Store Preset 4.900`, `Label Preset 4.900 "Red"` | ✔ Preset from the programmer values (`Attribute "COLORRGB1" At 100` sets one attribute) |
| `Store Cue 1 Sequence 900`, `Label Cue 1 Sequence 900 "x"` | ✔ Creates the sequence if needed |
| `cd "ExecutorPages"; cd 1; cd 1; Assign Sequence 900 At 15; cd /` | ✔ Sequence on executor 15 of page 1. ✔ `Assign 15 /AutoStart="off"` there sets options. `Assign Sequence 900 At Executor 1.15` at the root: `Error #14` |
| `Store Layout 900`, `Assign Group 1 Layout 900 /x=2 /y=3` | ✔ Layout from the selection; group or macro button at a grid position |
| `Store View 900 /screen=1` | ✔ Saves what screen 1 shows now |
| `Store Timecode 900`; `cd "Timecodes"; Assign 900 /Name="x" /Length=60` | ✔ New timecode show and its properties |
| `Fixture 902; Move3D At 2.5 -5 3.3`, `Rotate3D At 0 0 90`, `Move3D At 1 0 0 /relative` | ✔ Place the selection in the 3D stage. `ClearSelection` between fixtures |
| `Assign Dmx 5.003 At Fixture 903` | ✔ Patch one fixture from the root |
| `cd "EditSetup"; cd "FixtureTypes"; Import "generic@dimmer@00"` | ✔ Fixture type from the library |
| `Import "name" At Macro 901 /path="C:/some/folder"` | ✔ Import from any folder |
| `Edit Effect 1`, `Menu Effect` | ○ Open editors on screen |

## Playback

| Command | Notes |
|---|---|
| `Go Executor 1.1`, `Go Sequence 5`, `Goto Cue 3`, `Off Executor 1.1`, `Pause` | ○ **live output** |
| `Macro 500` | ✔ Run a macro (○ also `Go Macro 500`) |
| `Plugin 100`, `Plugin "ma2kit_info"` | ✔ Run a plugin; its feedback arrives after the prompt |
| `Lua "gma.feedback('hi')"` | ✔ Run one line of Lua |

## Import and export

| Command | Writes / reads | Notes |
|---|---|---|
| `Export Group 5 "name"` | `importexport\name.xml` | ✔ members in selection order |
| `Export Fixture 1 Thru 10 "name"` | `fixtures\name.xml` | ✔ absolute addresses and stage positions |
| `cd "EditSetup"; cd "Layers"; Export 3 "name"` | `fixture_layers\name.xml` | ✔ one patch layer: fixtures, fixture type, absolute `<Address>` (`(universe-1)*512 + address`), position, rotation |
| `… Export … /style=csv` | same folder, still XML | ✔ only adds a CSV stylesheet reference to the file |
| `Export Sequence 1 "name" /style=trackingsheet` | | ○ |
| `Import "ma2kit/x.xml" At Plugin 100` | from `plugins\` | ✔ asks before overwriting an occupied slot |
| `Import "ma2kit/x.xml" At Macro 500` | from `macros\` | ✔ |
| `Import "name" At FixtureType 2` | from `library\` | ○ inside `EditSetup` |

## Patch (inside `EditSetup`)

The patch is edited in the `EditSetup` branch of the tree. MA's test plugin `test_init_fixtures.lua`
patches like this:

```
cd /; cd "EditSetup"; cd "Layers"
Store 4 "MyLayer"                  ○ new layer
cd 4
Store 1 Thru 10                    ○ ten fixtures in the layer
Assign Thru /FixId=101             ○ (numbers count up)
Assign FixtureType 3 At Thru       ○
cd 1; Assign 1 /Patch="1.001"; cd ..   ○ fixture 1's subfixture gets an address
cd /
```

Subfixture settings (✔ the method, checked with `PosX`):

```
cd /; cd "EditSetup"; cd "Layers"; cd 3; cd 1     (layer 3, its first fixture)
List                                              (shows the subfixture row and its columns)
Assign 1 /PosX=-5                                 (applies at once)
cd /
```

Columns that can be assigned this way: `ReacttoMaster`, `PanDMXInvert`, `TiltDMXInvert`, `PanEnc.Invert`,
`TiltEnc.Invert`, `PanOffset`, `TiltOffset`, `Swap`, `BitmapDisable`, `Color`, `PosX/Y/Z`, `RotX/Y/Z`.
✔ Pan/tilt columns are ignored for fixture types without pan/tilt. ✔ On a moving head `PanOffset`,
`TiltOffset` and `TiltDMXInvert` are stored (seen in `List`). ✔ They change the DMX output only: the Stage
view does not show them. ○ On selected fixtures MA's
predefined macros also use `Assign Fixture Thru /panoffset=0` from outside `EditSetup`; from the root
`Assign Fixture 200 /panoffset=5` gave `Error #14` here.

## Show files and console

| Command | Notes |
|---|---|
| `SaveShow` | ✔ "Show successfully saved as …"; writes `shows\<name>.show.gz` |
| `LoadShow "name"`, `NewShow` | ○ **Replaces the open show.** ma2kit refuses these without confirmation |
| `Login "user" "password"`, `Logout` | ✔ (Telnet) |
| `ReloadPlugins` | ✔ Asks to confirm; does **not** re-read edited `.lua` files |
| `Menu Toggle "Setup"` | ○ Opens windows on the console screen |

## In macros only

| Form | Example | Notes |
|---|---|---|
| Ask the user | `Store Group (Group number)`, `Delete @` | ○ `( … )` shows a prompt text and inserts the answer; `@` waits for input |
| Condition | `[$selectedfixturescount==0] Macro "warn"` | ○ line runs only when the test is true |
| Wait | macro line property `Wait` | ✔ ma2kit macros: `wait N` in the source file ([09](09-macros-batch-checks.md)) |

## Errors seen

| Code | Text | Typical cause |
|---|---|---|
| 14 | `OBJECT DOES NOT EXIST` | ✔ unknown keyword, missing object, or the object is not reachable from the current `cd` location |
| 28 | `NO CUE SOURCE GIVEN` | ✔ `Export Layer 3 …` from the root: there `Layer` is not the patch layer; use the `EditSetup` form |
| 72 | `COMMAND NOT EXECUTED` | ✔ failed `Login`, `ClearSelection` with nothing selected |
