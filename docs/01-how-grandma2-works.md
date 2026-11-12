# How grandMA2 works (for scripting)

A working model of grandMA2 onPC 3.9.61 for someone who wants to automate it. It is not a replacement
for MA's user manual: it covers the parts a script touches.

Marks: **✔** observed on onPC 3.9.61.5 (build Oct 30 2025) by this project; **○** from MA's documentation or
general grandMA2 knowledge, not checked here yet.

## 1. The big picture

- ✔ A **show** is one tree of objects (fixtures, pools, sequences, settings, users…). Everything you see in
  the windows is a view of that tree.
- ✔ The **command line** can do everything the buttons do. Macros are stored command lines; Lua plugins
  mostly send command lines with `gma.cmd`; the Telnet remote is the same command line over TCP. So the
  command language ([03](03-command-cheatsheet.md)) is the real API.
- ✔ Reading is less complete than writing. A command's text output is visible on screen and over Telnet,
  but **not** to Lua (`gma.cmd` returns only an error string). Lua reads the tree through
  `gma.show.getobj` / `gma.show.property` ([02](02-lua-api.md)); outside tools read `List` output or
  exported XML ([06](06-show-reader-and-groups.md)).

## 2. The object tree

✔ `List` at the root of the tree (after `cd /`) shows its top level. Numbers are the positions used by `cd N`:

```
Showfile 1, TimeConfig 2, Settings 3, DMX_Protocols 4, NetConfig 5, CITPNetConfig 6, TrackingSystems 7,
UserImagePool 8, RDM_Data 9, LiveSetup 10, EditSetup 11, Macros 13, FlightRecordings 14, Plugins 15,
Gels 16, Presets 17, Worlds 18, Filters 19, FadePaths 20, Programmer 21, Groups 22, Forms 23, Effects 24,
Sequences 25, Timers 26, MasterSections 27, ExecutorPages 30, ChannelPages 31, Songs 33, Agendas 34,
Timecodes 35, RemoteTypes 36, DMXSnapshotPool 37, Layouts 38, UserProfiles 39, Users 40,
PixelMapperContainer 41, NDP_Root 42
```

✔ `EditSetup` (the patch you edit in *Setup → Patch & Fixture Schedule*) contains
`DMX_Profiles 1, PresetTypes 2, FixtureTypes 3, Layers 4, Universes 5, Objects3D 6`.

✔ Moving around: `cd "EditSetup"`, `cd 4`, `cd ..`, `cd /` (the console echoes `cd` as `ChangeDest`).
Inside the tree the prompt shows the path, e.g. `EditSetup/Layers 4/PAR_LED 3 >`; at the root it shows
the default keyword, ` [Group]>`. ✔ The current location belongs to the **command-line session**: each Telnet
login starts at the root, and a script that `cd`s somewhere must `cd /` before it leaves.

✔ Each object has a **class** (`CMD_GROUP`, `CMD_FIXTURE`, `CMD_MACRO_LINE_OBJECT` …), an index (0-based
position under its parent), a command-line number (`500`, `4.1`, `1.001`), a name, an optional label and
**properties** (the columns you see in sheets: `Name`, `Patch`, `PanOffset` …). See [02](02-lua-api.md#object-classes-seen)
for the classes found so far.

## 3. Fixtures, channels and the patch

- ✔ A fixture has a **Fixture ID** (`FixId`) and a **Channel ID** (`ChaId`); commands use `Fixture N` or
  `Channel N`. In the test show only Fixture IDs are used (`Channel 1` does not exist).
- ✔ Fixtures live in **layers** (`EditSetup/Layers`), e.g. one layer per fixture group in the rig. A fixture's
  parent in the tree is its layer (`CMD_FIXTURE_LAYER`).
- ✔ A fixture has one or more **subfixtures** (`CMD_SUBFIXTURE`, child 0 for a single-cell fixture). The
  subfixture holds the per-instance patch settings:
  `Patch` (`universe.address`, e.g. `2.001`), `React to Master`, **`Pan DMX Invert`, `Tilt DMX Invert`,
  `Pan Enc. Invert`, `Tilt Enc. Invert`, `Pan Offset`, `Tilt Offset`, `Swap`**, `Bitmap Disable`, `Color`,
  `Pos X/Y/Z`, `Rot X/Y/Z`. These are the settings pan/tilt normalization will write.
- ✔ Writing a subfixture setting: `cd` into its layer and fixture, then `Assign 1 /<Column>=<value>`
  (column name without spaces, e.g. `/PosX=-5`). The change applies at once (verified with `PosX`).
  ✔ The pan/tilt settings are silently ignored on a fixture type without pan/tilt.
  ✔ On a moving head `Assign 1 /PanOffset=5` is stored and shows in `List`; `/PanOffset=0` resets it.
  ○ The physical effect on the beam, and `/PanDMXInvert=On`, `/Swap=On`, are not yet confirmed. MA's own
  predefined macros use `Assign Fixture Thru /panoffset=$panoffset` on selected fixtures.
- ✔ **Fixture types** (`EditSetup/FixtureTypes`, class `CMD_FIXTURE_TYPE`) hold the channel layout:
  properties `LongName`, `ShortName`, `Manufacturer`, `DMX Footprint`, `Instances`, `Mode`.
  Type 1 is always `Universal Attributes` (automatic).
- ✔ **DMX universes** (`DmxUniverse N`) have 512 `CMD_DMX_CHANNEL` children whose properties tell which
  fixture and attribute sit on each address (`Fixture`, `Fix Id`, `Attrib`, `Type = Coarse/Fine`).
- ✔ `Export Fixture a Thru b "name"` writes `fixtures/name.xml` with absolute addresses and stage
  positions; this is how `ma2kit show fixtures --positions` reads them.

## 4. Programmer, selection and values

- ○ Selecting fixtures (`Fixture 1 Thru 10`, `Group 5`) puts them in the **selection**; giving values
  (`At 50`, `At Preset 4.2`) puts values in the **programmer**. The programmer has priority over
  playbacks until it is cleared (`Clear` / `ClearAll`).
- ✔ The selection order is kept: `Fixture 103 + 101 + 102` then `Store Group N` stores them in that order
  (it matters for effects and MAtricks).
- ✔ There is **no Lua function that returns the selection**; `$SELECTEDFIXTURESCOUNT` gives only the count.
  Workaround: store the selection to a scratch group and export it.
- ○ With a Command Wing or node connected, programmer values reach the DMX output immediately. This is why
  the toolkit never sends values or highlight without the operator present.

## 5. Pools

| Pool | Command-line object | Notes |
|---|---|---|
| Groups | `Group N` | ✔ ordered fixture lists; `Store Group N` into an empty slot asks nothing, into an occupied slot overwrites without asking |
| Presets | `Preset T.N` | ✔ `T` is the preset type: 1 Dimmer, 2 Position, 3 Gobo, 4 Color, 5 Beam, 6 Focus, 7 Control, 8 Shapers, 9 Video (0 = All). `List Preset 4.*` lists the color presets; `List Preset 4` alone finds nothing |
| Effects | `Effect N` | ✔ each effect has lines (`CMD_EFFECT_LINE`) with `Attrib`, `Mode`, `Form`, `Rate`, `Speed`, `Dir`, `Low/High Value`, `Phase`, `Width`, `Attack`, `Decay`, `Groups`, `Blocks`, `Wings`, `Single Shot` |
| Sequences / cues | `Sequence N`, `Cue N` | ○ playback lists; ✔ in the Lua tree, cue 0 is child 0 |
| Executors / pages | `Executor P.N`, `Page N` | ○ faders and buttons that run sequences |
| Macros | `Macro N` | ✔ lines are `CMD_MACRO_LINE_OBJECT` with `CMD`, `Wait`, `Disabled` |
| Plugins | `Plugin N` | ✔ class `CMD_LUA_PLUGIN`, property `ExecuteOnLoad` |
| Worlds / Filters | `World N`, `Filter N` | ✔ World 1 `Full` and Filter 1 `All` exist in every show we have seen |
| MAtricks | `MAtricks N` | ✔ MAtricks 1 is `Reset` |
| Layouts, Views, Forms, Timers | `Layout N`, `View N`, `Form N`, `Timer N` | ✔ exist; not used by the toolkit yet |

○ "Pool numbers" seen on screen and command-line numbers are the same; the Lua `index` is 0-based and
differs (`Group 500` has index 499).

## 6. Users and sessions

- ✔ Users (`List User`): `administrator`, `guest`, plus any you add. Each has rights (`Admin`, `Playback`…)
  and a user profile. Logging in over Telnet uses one of these users.
- ✔ Inside a plugin `$USER` is `administrator`, whoever started it.
- ✔ This onPC runs standalone (`$HOSTSTATUS = Standalone`). ○ In an MA-Net session several consoles share
  one show; the toolkit has not been tried in a session.

## 7. Files on disk

✔ The data root is `C:\ProgramData\MA Lighting Technologies\grandma\gma2_V_3.9.61\` (`$PATH`). Folders
that matter for scripting:

| Folder | Contents |
|---|---|
| `shows\` | show files `*.show.gz` (and `.backup`). `SaveShow` writes `<name>.show.gz` |
| `plugins\` | plugin `.xml`/`.lua` pairs; `Import "x.xml" At Plugin N` reads from here. `plugins\systemtests\` holds about 100 MA test plugins (good command examples); `plugins\requirements\` is on Lua's `package.path` |
| `macros\` | macro XML (`predefined.xml` is MA's predefined macro set) |
| `importexport\` | default target of `Export Group … "name"` |
| `fixtures\` | target of `Export Fixture …` |
| `library\` | fixture-type library (`.xmlp`, tens of thousands of files); `ListLibrary` lists it |
| `effects\`, `matricks\`, `fixture_layers\` | import/export folders for those objects |
| `temp\`, `reports\`, `webserver\` | console internals |

## 8. What this means for the toolkit

- Writes go through command lines; prefer XML import when many objects change at once.
- Reads go through `List` text or XML exports from Python, and through `getobj`/`property` from Lua.
- Anything that sets values, highlights, or changes pan/tilt patch settings affects the real rig.
- Keep `cd` state, the selection and the programmer as you found them: `cd /` and `ClearSelection` at
  the end of every script.
