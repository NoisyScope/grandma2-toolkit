"""Command recipes served by the MCP tool `ma2_guide`.

Marks: [v] sent to grandMA2 onPC 3.9.61 over Telnet by this project and the result checked;
[doc] from MA's own help pages, not tried here; [x] tried here and failed.
"""
from __future__ import annotations

INSTRUCTIONS = """grandMA2 onPC remote control over its Telnet command line.
Start with ma2_status: it reports the connection, the loaded show, whether DMX hardware is connected, and lists
every tool and guide topic. Use ma2_guide(topic) for verified command recipes and ma2_help(query) for MA's
official help pages before guessing syntax. ma2_command sends any command line; ma2_list and ma2_export read
the show; ma2_set changes object properties; ma2_patch creates and patches fixtures.
Rules: commands that change the show are refused on shows outside the configured allow-list; deleting or
replacing data needs allow_destructive=true; when DMX hardware is connected, changes need confirm_live=true
and a human at the rig. Run ma2_backup before large changes."""

GUIDE: dict[str, tuple[str, str]] = {
    "basics": (
        "Command syntax, the object tree, and what behaves differently over Telnet",
        """SYNTAX  [Function] [Object] [/option=value]. Keywords are not case-sensitive. [v]
  Fixture 1 Thru 10 | Fixture 1 + 3 + 5 | Group 5 | Preset 4.2 (type.number) | names in "quotes", * wildcard [v]
  Several commands on one line: a ; b [v]
  /nc = no confirmation dialog, /o = overwrite, /merge [v]

OBJECT TREE  `cd "EditSetup"`, `cd 4`, `cd ..`, `cd /`; `List` shows the children of the current place. [v]
  Root children: Showfile, Settings, EditSetup (patch), Macros, Plugins, Presets, Groups, Effects, Sequences,
  ExecutorPages, Timecodes, Layouts, UserProfiles, Users ... (use ma2_list with path=[] to see them all)
  Pools have a "Global" pool level: Groups/1/<n>, Sequences/1/<n>/<cue>, Macros/1/<n>/<line>,
  Layouts/1/<n>, ExecutorPages/1/<page>/<exec>. Timecodes/<n> has no pool level. [v]

TELNET DIFFERENCES FOUND ON 3.9.61
  [x] `Assign <Object> N /property=value` typed at the root answers Error #14 (Group, Sequence, Macro line,
      Timecode, Executor, Fixture all failed).
  [v] The same assignment works from inside the tree: cd to the parent, then `Assign N /Property=value`.
      Use the tool ma2_set, which does this and returns to the root.
  [v] These work at the root: Store, Label, Delete, List, Export, Import, `Assign Dmx u.a At Fixture N`,
      `Assign Group 1 Layout 5 /x=2 /y=3`, `Assign Fade/…` forms need a selected executor.
  [x] The keyword `Executor p.n` at the root answers Error #14 here; reach executors through the tree.
  [doc] Staying inside EditSetup locks the patch for other users: always `cd /` when done
      (ma2_command and the other tools do this automatically).
  A command's reply can open a dialog; tools answer Cancel unless answer_dialogs says otherwise.

ERRORS  #14 OBJECT DOES NOT EXIST (also: not reachable from here) · #28 NO CUE SOURCE GIVEN ·
  #59 ILLEGAL DESTINATION · #66 CANNOT ASSIGN · #72 COMMAND NOT EXECUTED.
  `WARNING, NO OBJECTS FOUND FOR LIST` = the pool or range is empty.""",
    ),
    "patch": (
        "Import a fixture type from the library, create a layer and fixtures, set IDs and DMX addresses",
        """Easiest: the tool ma2_patch does all of this in one call and checks for address clashes.

By hand (every line [v]):
  cd "EditSetup"; cd "FixtureTypes"
  List                                   -> No., LongName, Mode, DMXFootprint, Used
  Import "generic@dimmer@00"             -> library file name without extension; becomes the next type number
  cd /; cd "EditSetup"; cd "Layers"
  List                                   -> existing layers
  Store 4 "MyLayer"                      -> new layer number 4
  cd 4
  Store 1 Thru 4                         -> four fixtures in the layer
  Assign 1 Thru 4 /FixId=901             -> IDs 901..904 (counts up); /ChaId= for channel IDs
  Assign 1 Thru 4 /Name="Dim 1"
  Assign FixtureType 5 At 1 Thru 4
  cd 1; Assign 1 /Patch="5.001"; cd ..   -> universe.address on the fixture's first subfixture
  cd /
From the root: `Assign Dmx 5.003 At Fixture 903` patches one fixture. [v]
Library files: the console's `library` folder; list them with the command ListLibrary. [v]
Delete: `cd "EditSetup"; cd "Layers"; Delete 4 /nc` (layer and its fixtures), and in FixtureTypes
`Delete 5 /nc` for an unused type. [v]
Subfixture columns (inside the fixture): Patch, ReacttoMaster, PanDMXInvert, TiltDMXInvert, PanEnc.Invert,
TiltEnc.Invert, PanOffset, TiltOffset, Swap, Color, PosX/Y/Z, RotX/Y/Z. [v]""",
    ),
    "position": (
        "Place and rotate fixtures in the 3D stage",
        """From the root, on the current selection (metres, degrees):
  ClearSelection; Fixture 902; Move3D At 2.5 -5 3.3      absolute X Y Z [v]
  Rotate3D At 0 0 90                                     absolute rotation X Y Z [v]
  Move3D At 1 0 0 /relative                              relative move [v]
Always ClearSelection (or ClearAll) between fixtures: a new `Fixture N` ADDS to the selection when no
value was set in between, so earlier fixtures would move too. [v]
Inside the patch: cd "EditSetup"; cd "Layers"; cd <layer>; cd <fixture index>;
  Assign 1 /PosX=1 /PosY=2 /PosZ=3 /RotZ=90; cd /   [v]   (ma2_patch accepts positions directly)
X = across the stage, Y = towards or away from the audience, Z = height. [doc]
The Stage view shows positions and programmer pan/tilt; it does not show patch offsets or inverts. [v]""",
    ),
    "presets": (
        "Create dimmer, position, gobo, color, beam, focus and control presets",
        """Preset types: 0 All, 1 Dimmer, 2 Position, 3 Gobo, 4 Color, 5 Beam, 6 Focus, 7 Control, 8 Shapers, 9 Video.
Recipe: clear, select, set values, store, label, clear.
  ClearAll
  Fixture 901 Thru 904 At 75                       dimmer value [v]
  Store Preset 1.900                               [v]   (occupied slot: add /o or /merge)
  Label Preset 1.900 "Dim 75"                      [v]
  ClearAll
  Fixture 200 Thru 219
  Attribute "COLORRGB1" At 100                     one attribute; names from `List Attribute` [v]
  Attribute "COLORRGB2" At 0; Attribute "COLORRGB3" At 0
  Store Preset 4.900; Label Preset 4.900 "Red"     [v]
  Fixture 100 Thru 111; Attribute "PAN" At 20; Attribute "TILT" At 40; Store Preset 2.900   [v]
`List Attribute` (with fixtures selected) lists the attribute names of the show: DIM, PAN, TILT, GOBO1,
COLORRGB1..n, SHUTTER, FOCUS, PRISMA1 ... [v]
Read a preset's values: ma2_export object="Preset 2.900" (one PresetValue per fixture and attribute). [v]
Use: `Fixture 901 Thru 904 At Preset 1.900`. [v]   List one type: `List Preset 4.*`. [v]
Programmer values reach the DMX output when hardware is connected.""",
    ),
    "sequences": (
        "Store cues and sequences, cue names and timing",
        """  ClearAll
  Fixture 901 Thru 904 At Preset 1.900
  Store Cue 1 Sequence 900                 creates sequence 900 if needed [v]
  ClearAll; Fixture 901 Thru 904 At 10; Store Cue 2 Sequence 900   [v]
  Label Sequence 900 "My Seq"; Label Cue 1 Sequence 900 "First"     [v]
Cue timing and other cue properties: from inside the tree,
  ma2_set path=["Sequences","1","900"] target="2" properties={"Fade": 1.5}   [v accepted]
  (`List` there shows Number, MIB, Trig, TrigTime, Mode, Loop; ma2_export object="Sequence 900" shows all values)
[x] `Assign Cue 2 Sequence 900 /fade=2` and `Assign Fade 2.5 Cue 2 Sequence 900` at the root: Error #14.
[doc] `Store Cue 3 Fade 4`, `Assign Fade 3 Cue 2` act on the selected executor's sequence.
Sequence properties (ma2_list what="Sequence"): Track, ReleaseFirststep, CueZero, InputFilter, TimecodeSlot.
Delete: `Delete Sequence 900 /nc`. [v]""",
    ),
    "executors": (
        "Put sequences on executors (faders and buttons) and set executor options",
        """Executors live at ExecutorPages / 1 (Global) / <page> / <executor number>.
  cd "ExecutorPages"; cd 1; cd 1                  page 1
  Assign Sequence 900 At 15                       sequence 900 on executor 15 of this page [v]
  List                                            one line per executor: No.=1.15 Name=… Sequence=… AutoStart=… [v]
  Assign 15 /Name="Front" /AutoStart="off"        executor options [v]
  Delete 15 /nc                                   empty the executor [v]
  cd /
Options seen: Width, SwopProtect, KillProtect, AutoStart, AutoStop, AutoFix, OoO, SoftLTP, MasterGo, Restart,
Wrap, Crossfade, AutoStomp, Chaser, Priority, Prepos, MIBNever, MIBAlways, TriggerIsGo, CmdDisable, Speed,
SpeedMaster, RateMaster, Filter, OffTime, BreakingGo, PlaybackMaster. [v listed]
[v] `Store 15` on a page creates an executor AND a new empty sequence for it: assign a sequence instead.
[x] Not working here: `Assign Sequence 900 At Executor 1.15` at the root (Error #14), and changing button or
    fader functions by command (`Assign Flash At 16` #59, `Assign 16 /Button1="Flash"` #66).
    Button and fader functions are in the executor's XML (ma2_export object="15" with the page path:
    <AssignmentExec fader=…><Button>…</Button>); changing them by XML import is not verified.
[doc] `Assign Go ExecButton1 1.1`, `Assign Toggle At Executor 101`, `Go Executor 1.1`, `Off Executor 1.1`.
Running playbacks outputs light when hardware is connected.""",
    ),
    "macros": (
        "Create macros and their command lines",
        """  Store Macro 900                                 empty macro [v]
  Store Macro 1.900.1; Store Macro 1.900.2        two lines (1 = Global macro pool) [v]
  Label Macro 900 "My Macro"                      [v]
Line contents, from inside the tree:
  ma2_set path=["Macros","1","900"] target="1" properties={"CMD": "ClearAll"}                  [v]
  ma2_set path=["Macros","1","900"] target="2" properties={"CMD": "Group 1 At 50", "Wait": 0.5} [v]
[x] `Assign Macro 1.900.1 /cmd="…"` at the root: Error #14.
Run: `Macro 900`. [v]   Delete: `Delete Macro 900 /nc`. [v]
Whole macros can also be imported from XML: ma2_import xml=… destination="Macro 901". [v]
In macro lines only: `(prompt text)` asks the operator, `@` waits for input, `[$var==0] cmd` is a condition. [doc]""",
    ),
    "layouts": (
        "Build layout views with fixtures, groups and macros",
        """  ClearAll; Fixture 100 Thru 111
  Store Layout 900                               layout with the selected fixtures in a row [v]
  Label Layout 900 "Rig"                         [v]
  ClearAll
  Assign Group 1 Layout 900 /x=2 /y=3            a group button at grid x,y [v]
  Assign Macro 900 Layout 900 /x=4 /y=3          a macro button [v]
  Layout 900                                     show it in layout windows that follow the selection [doc]
Exact placement and looks: ma2_export object="Layout 900" returns one LayoutSubFix per fixture with
center_x, center_y, size_w, size_h, background_color, icon; grid settings are in LayoutData
(Layouts/1/900 in the tree: GridX, GridY, SnapGridX, Background ...). [v read]
Editing that XML and importing it back with ma2_import is not verified yet.
Delete: `Delete Layout 900 /nc`. [v]""",
    ),
    "views": (
        "Store screen views and view buttons",
        """  Store View 900 /screen=1          stores what screen 1 shows right now as view 900 [v]
  Label View 900 "My View"          [v]
  View 900                          recall it; `View 900 /screen=2` on another screen [doc]
  ma2_list what="View"              No., Name, Screen [v]
  Store ViewButton 2.5              [doc] store a view on button 5 of view page 2
  Label ViewButton 2.5 "Layout"     [doc]
A view only captures windows that are already open: the window arrangement itself cannot be built by
command (not found). Open and arrange windows on the console, then store the view.
Delete: `Delete View 900 /nc`. [v]""",
    ),
    "timecode": (
        "Create timecode shows and connect sequences to timecode",
        """  Store Timecode 900                               new timecode show [v]
  ma2_set path=["Timecodes"] target="900" properties={"Name": "Song 1", "Length": 60}   [v]
  ma2_list what="Timecode"   columns: Name, Slot, Length, Offset, Runs, SwitchOff, StatusCall, TimeUnit,
                             WhenEnding, WhenStopping, AutoStart, RecordMode, UserBits [v]
Property values [doc]: Slot "Intern" | "Link Selected" | "1".."8"; Runs "Endless Repeat" | "No Repeat" | 2..1000;
SwitchOff "Playbacks Off" | "Keep Playbacks"; TimeUnit "1/100 Seconds" | "24 FPS" | "25 FPS" | "30 FPS".
Functions [doc]: Go Timecode 900 (play), Record Timecode 900, Top Timecode 900 (rewind), Off Timecode 900.
Sequences have a TimecodeSlot property (ma2_set path=["Sequences","1"] target="900"). [v listed]
Events (which cue fires when) are tracks inside the timecode show. No command to add single events was
found; an empty show exports as <Timecode name=… lenght=…/>. To script events: record or build one small
timecode show on the console, read it with ma2_export object="Timecode N", then generate XML in the same
shape and load it with ma2_import (not verified yet).
Delete: `Delete Timecode 900 /nc`. [v]""",
    ),
    "effects": (
        "Effects pool basics",
        """ma2_list what="Effect" lists the pool; each effect has lines with Attrib, Mode, Form, Rate, Speed, Dir,
Low/High Value, Phase, Width, Attack, Decay, Groups, Blocks, Wings. [v read]
Use: `Fixture 1 Thru 10 At Effect 3`, then store in a cue or preset. [doc]
Change a line from inside the tree (Effects/1/<effect>), target = line number, e.g. {"Phase": "0..360"}.
(not verified)   Import ready-made effects: ma2_import file="name" destination="Effect 101". [doc]""",
    ),
    "lua": (
        "Reading the show with Lua (ma2_lua)",
        """ma2_lua runs code inside the console's Lua 5.3 and returns what it prints or returns.
  local h = gma.show.getobj.handle("Fixture 100")           handle or nil
  gma.show.getobj.class(h), .index(h), .number(h), .name(h), .label(h), .amount(h), .child(h, i), .parent(h)
  gma.show.property.amount(h), .name(h, i), .get(h, i or "Name")      (i is 0-based)
  gma.show.getvar("SHOWFILE"), gma.user.getvar("x"), gma.show.getdmx(address)
  gma.cmd("…") runs a command line and returns nil or an error text (it cannot return the command's output)
Example: print every property of a fixture's first subfixture:
  local s = gma.show.getobj.child(gma.show.getobj.handle("Fixture 100"), 0)
  for i = 0, gma.show.property.amount(s) - 1 do print(gma.show.property.name(s, i), gma.show.property.get(s, i)) end
There is no function that returns the selection or programmer values; $SELECTEDFIXTURESCOUNT has the count.""",
    ),
    "safety": (
        "What the server refuses and why",
        """- Shows: when [safety] allowed_shows is set in config.toml, commands that change the show are refused on
  any other show. Reading always works.
- Destructive commands (Delete, NewShow, LoadShow, Shutdown, Reboot, Restart, anything with /nc) need
  allow_destructive=true. Login/Logout are refused: credentials come from the config file only.
- Live output: ma2_status reports fader modules and granted DMX universes. When hardware is connected,
  every changing command needs confirm_live=true; values, highlight, playbacks and patch changes then move
  and light real fixtures. Only confirm with a person at the rig.
- Dialogs are answered Cancel unless answer_dialogs is set.
- ma2_backup saves the show and keeps a timestamped copy; use it before patch or bulk changes.
- The session always returns to the root of the tree (`cd /`), which releases the patch lock.""",
    ),
}
