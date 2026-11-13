# Agent brief: grandMA2 onPC toolkit

You are building a toolkit that talks to **grandMA2 onPC v3.9.61** on this Windows PC to speed up
three jobs for a lighting operator: **effects**, **patching**, and **pan/tilt normalization of moving
heads**. This file is your full set of instructions. Read it all before touching anything.

The repository root is this folder: `C:\Users\Admin\Documents\grandma2-toolkit`.

---

## 1. Decisions already made by the owner

| Topic | Decision |
|---|---|
| Tool form | **Python CLI** (terminal menus) that drives onPC from outside, **plus Lua plugins** that run inside onPC. |
| "Aligning" heads | Means **pan/tilt normalization**: make every moving head respond the same way (invert, swap, offset in the patch). Venue position presets, fans and XYZ calibration are *out of scope* for now. |
| DMX output | onPC is used with **MA hardware (wing/node)**, so commands can move and light **real fixtures**. Treat every command as live. *Update 2026-11-12: the wing is currently disconnected and work targets the software and Stage view only (see section 6, 0.4.0). The rule applies again as soon as hardware is reconnected.* |
| Repo location | This folder. Not yet a Git repository; you initialise it (Phase 0). |
| Language | English only (code, CLI, docs). |
| Publishing | The repo **will be public** on the owner's personal GitHub. Pick a permissive licence (MIT), keep all private data out of history (show files, show names, credentials, IPs, the owner's email), and do not copy third-party plugin code without its licence notice. |
| MA hardware | **grandMA2 Command Wing**. |
| Typical rig | Fewer than 50 fixtures: LED PARs, beams, blinders, washes. |
| Pool ranges | No preference. Default every generated object to a high, configurable start index (suggest 500+ for groups/presets/macros/sequences/effects, 50+ for layouts/plugins), always after checking the range is empty. |

## 2. What is on this machine (verified 2026-11-11)

- grandMA2 data root: `C:\ProgramData\MA Lighting Technologies\grandma\gma2_V_3.9.61\` (called `MA_ROOT` below).
  Relevant subfolders: `plugins\`, `macros\`, `effects\`, `matricks\`, `importexport\`, `fixture_layers\`,
  `library\` (fixture library, ~37k files), `shows\`, `reports\`, `webserver\`.
- `MA_ROOT\plugins\plugin_1.lua` + `plugin_1.xml`: MA's own example plugin. **Lines 97–164 of the `.lua`
  are the authoritative list of the Lua API.** `MA_ROOT\plugins\systemtests\` holds ~100 MA test plugins
  that show real usage of `gma.cmd` for almost every command keyword; `api_test.lua` exercises the whole API.
  `MA_ROOT\plugins\requirements\socket\` is a bundled LuaSocket.
- `MA_ROOT\macros\predefined.xml` (104 KB): MA's predefined macros, a good corpus of command syntax.
  `predefined_plugin_macros.xml` shows the plugin lifecycle commands (`Import ... At Plugin N`, `ReloadPlugins`, `Delete Plugin`).
- `MA_ROOT\macros\ColorPicker.lua/.xml` and `C:\Users\Admin\Documents\grandma2_colorpicker_plugin\`: a
  **third-party** color-picker plugin (MIT, by egidiusmengelberg) the owner already uses. Study it as prior
  art. If you reuse any of its code, keep its licence notice; otherwise write your own.
- The owner's show files live in `MA_ROOT\shows\` (`*.show.gz`). **They are private working files. Never
  modify, delete, or commit them.**
- Installed: Git, Python 3.12, Node.js. **Not** installed: a standalone Lua interpreter, GitHub CLI.
  Ask the owner before installing anything.
- ✔ With onPC running (checked 2026-11-11) it listens on TCP 80, 7001, 7003, 7005, **30000** and **30001**
  on all interfaces. Port 30001 streams the system monitor log without any login.
- ✔ Telnet is now set to *Login Enabled* by the owner. Port 30000 sends an ASCII-art "MA" banner, then
  `Logged in as User 'guest'`, then the prompt ` [Group]>Please login !` (lines end `\r\n` or `\n\r`, with
  ANSI codes). The prompt pattern is `[<default keyword>]>`. Before the setting was changed it answered
  `Remote commandline disabled`: use both strings in `ma2kit doctor`.
- ✔ The owner created an MA user named `toolkit` for this tool. Its password is known only to the owner:
  they enter it in the git-ignored `config.toml`. Never ask for it in chat, print it, or log it.

## 3. How grandMA2 is automated (starting knowledge; verify each item)

Items marked ✔ were confirmed from files on this PC. Items marked ? come from general MA2 knowledge and
must be confirmed against the running software or the official help (help.malighting.com, grandMA2 3.9)
before you rely on them. Record what you confirmed in `docs/`.

**Command line.** Everything the console does can be typed as a command: `Fixture 1 Thru 10 At 50`,
`Store Group 5`, `Assign`, `Label`, `Export`, `Import`, `List`, `cd` (navigate the object tree), etc.
Macros are stored lists of these commands. This is the real "API"; Lua mostly wraps it.

**Lua plugins.** ✔ A plugin is a pair: `name.xml` (pool metadata: index, name, `luafile`, `execute_on_load`)
and `name.lua`. The Lua file must end with `return Start, Cleanup`. ✔ API surface is small:
`gma.cmd`, `gma.echo`, `gma.feedback`, `gma.sleep`, `gma.timer`, `gma.textinput`, `gma.gui.confirm/msgbox/progress.*`,
`gma.show.getobj.*` (handle/class/index/number/name/label/amount/child/parent), `gma.show.property.*`,
`gma.show.getvar/setvar`, `gma.user.getvar/setvar/getcmddest/getselectedexec`, `gma.show.getdmx`,
`gma.export/export_csv/export_json/import`, `gma.network.*`. ✔ `gma.cmd` returns only an error string, not
the command's output. ✔ The embedded interpreter is Lua 5.3 (`_VERSION`, with full `os`, `io`, `debug`).
✔ Plugins are loaded with `Import "name.xml" At Plugin N` (file in `MA_ROOT\plugins\`), run with
`Plugin N` or `Plugin "Name"`; one-liners run with `LUA "..."`. ✘ `ReloadPlugins` does **not** refresh
edited files: import again over the same slot (see "Corrections" in section 6).

**Known gap.** There is no Lua call that returns the current selection or programmer values. Work around
it with system variables (`$SELECTEDFIXTURESCOUNT` etc. via `gma.show.getvar`), the object tree
(`getobj` / `property`), or by `Export`-ing objects to XML and parsing the file.

**Telnet remote.** ✔ Enable in *Setup → Console → Global Settings → Telnet = Login Enabled*. Port **30000**
accepts commands and returns the command-line feedback as text (with ANSI colour codes); port **30001** is
read-only. First line must be `Login "user" "password"`. This is the Python side's transport: unlike
`gma.cmd`, it lets you read the output of `List`.

**Web remote.** ? Port 80 WebSocket remote (*Global Settings → Remotes*), needs a user with a password.
Optional fallback only; do not build on it unless Telnet proves insufficient. *Not checked: Telnet has
been sufficient so far.*

**XML import/export.** ◐ Checked on 3.9.61: export of groups, fixtures and patch layers; import of
plugins and macros (see `docs/03`). Not yet checked: presets, effects, sequences, layouts, MAtricks, and
importing a patch layer. Most pool objects (groups, presets, macros, effects, sequences, layouts, MAtricks)
and fixture layers (the patch) can be exported to and imported from XML. Generating XML and importing it
is usually faster and more reliable than hundreds of individual commands, and it is the standard route for
scripted patching.

**Pan/tilt settings.** ✔ (method found and written up in `docs/01` and `docs/03`; see 0.4.0 in section 6). Per-fixture patch columns in *Setup → Patch & Fixture Schedule* include Pan/Tilt DMX
invert, encoder invert, swap, and pan/tilt offset. Find out how to read and write them (object tree under
`EditSetup`, `Assign ... /property=value`, or fixture-layer XML round trip) and document the working method.

## 4. Safety rules (not negotiable)

1. **Real fixtures are connected.** Never send values, highlight, or run effects on fixtures without the
   owner present and confirming in that session. Moving heads can hit things and blind people.
2. **Develop against a dedicated test show**, never the owner's shows. Ask the owner to create/load it
   (suggested name `toolkit_dev`). Before any write session, run `SaveShow` and confirm it succeeded.
3. **Every tool action that changes the show has a dry-run mode** that prints the exact commands/XML it
   would send. Dry-run is the default; applying needs an explicit flag or confirmation.
4. **Destructive or patch-changing commands** (`Delete`, `NewShow`, `LoadShow`, anything under `EditSetup`,
   pool overwrites) require a per-action confirmation showing what will be affected. Never use `/nc`
   (no-confirm) on a delete outside the test show.
5. **Pool safety.** Never overwrite an occupied pool slot silently. Tools take a start index, check the range
   is empty first, and refuse otherwise.
6. **Do not change console settings yourself** (Telnet enable, users, passwords, network). Tell the owner the
   exact clicks. Suggest a dedicated MA user for the toolkit.
7. **Secrets.** Host, user and password go in a local config file that is in `.gitignore`. Ship only a
   `config.example.toml`.
8. Files you copy into `MA_ROOT` must be tracked by a manifest so they can be removed cleanly. Never edit or
   delete files in `MA_ROOT` that you did not create.

## 5. Goals

- **G1 Understand:** a written, verified model of how onPC 3.9.61 works for our purposes.
- **G2 Reference:** a Lua API reference and a command-line cheat sheet, both checked against this install.
- **G3 Script management:** one command to install, update, list and remove this repo's plugins and macros in a show.
- **G4 Utilities:** color picker builder, auto groups, effect helpers, patch helper, pan/tilt normalization wizard, behind one CLI.
- **G5 Documentation:** enough that the owner can use and extend it without you.
- **G6 Repository:** a clean Git repo in this folder with meaningful commits.

## 6. Work plan

**Progress (2026-11-11):** Phase 0 is done except the first commit (waiting on the owner's choice of
commit e-mail, since the repo will be public). Phase 2 is partly done: `ma2kit/client.py` (socket client,
ANSI/Telnet stripping, prompt detection, password masking, transcript, dry-run, risky-command check) and
`ma2kit doctor | cmd | shell`, with 18 offline tests. Verified live: login as `toolkit` (Admin rights),
`ListVar`, `List Group`, and the real echo/error/prompt reply formats, which the fake console now copies
(see `docs/04-remote-control.md`). onPC is **standalone** (`$HOSTSTATUS = Standalone`), so the old
question about sessions is answered. Still open in Phase 2: reconnect. Phase 1 docs: only
`docs/04-remote-control.md` exists.

**Phase 3 done** (`ma2kit/model.py`, `ma2kit show summary|fixtures|pool|group`): list-table parser, fixtures,
types, pools, group members and stage positions via temporary XML exports. **Phase 5 item 2 (auto groups)
done** (`ma2kit/groups.py`, `ma2kit groups auto`): created groups 500-514 in the test show. See
`docs/06-show-reader-and-groups.md`. 30 offline tests.

**0.2.0 (owner's direction: universal features first; connection, interface, functionality):**
Phase 2 finished (dialog handling, late output, echo normalisation, auto-reconnect), Phase 4 done
(`ma2kit plugins ...`, `lua/lib/ma2kit.lua`, `docs/07-plugins.md`), Phase 5 item 6 done (`backup`, `doctor`
checks `[safety] allowed_shows`), `monitor` added, Phase 6 menu done (`ma2kit` with no arguments).
50 offline tests.

**0.3.0:** menu keeps one session; `batch`; macro manager (`macros ...`, `docs/09-macros-batch-checks.md`);
`show check` (overlaps, overflow, unpatched, duplicate names); `show free`; doctor cleans temp exports.
62 offline tests. Phase 4 is complete.

**0.4.0:** reference docs `docs/01`–`03` and `05` written and checked live (Phase 1 docs done). Read-only
plugins `ma2kit_api_dump` and `ma2kit_inspect` gather the facts. Findings that matter for the remaining
utilities:
- Pan/tilt patch settings live on the **subfixture** (`child(fixture, 0)`): `PanDMXInvert`, `TiltDMXInvert`,
  `PanEnc.Invert`, `TiltEnc.Invert`, `PanOffset`, `TiltOffset`, `Swap`. Read them with
  `gma.show.property.get(sub, "PanOffset")` or `List` inside the fixture. Write them with
  `cd "EditSetup"; cd "Layers"; cd <layer>; cd <fixture index>; Assign 1 /PanOffset=...` (method verified
  with `PosX`; pan/tilt fields are ignored on fixtures without pan/tilt; on beam fixture 100 `PanOffset`, `TiltOffset` and
  `TiltDMXInvert` were stored and reset). **The Stage view does not show patch offset/invert**: the owner
  watched tilt 30 from the programmer move the beam there, but offset +20 and tilt invert changed nothing.
  They act on DMX output only.
- **No hardware right now (owner, 2026-11-12):** the Command Wing is not connected, universes show
  `Granted = No`, `gma.show.getdmx` reads 0. Work targets the software and the Stage view only. Programmer
  values are safe while no hardware is connected. Consequence for the pan/tilt wizard: its effect can be
  checked in the patch (`List`, `property.get`) but not visually until real fixtures are connected.
- The patch exports per layer from inside `EditSetup/Layers` (`Export 3 "name"` → `fixture_layers\name.xml`,
  absolute `<Address>`), which suits the patch helper.
- `cd` changes the prompt to a tree path; the client handles it. The location is per Telnet session.
68 offline tests. Remaining phases: color picker, effect helpers, patch helper (import from CSV),
pan/tilt wizard.

**Owner's rule: build generic features.** Never hard-code fixture types, IDs, group numbers, positions or
layouts from the test show; read everything from the loaded show at runtime. Rig-specific ideas wait
until the owner asks.

**Corrections to section 3 found on 3.9.61:** the show stores plugin code at import, so `ReloadPlugins`
does not load edited files (re-import over the slot instead); `Lua "..."` exists and runs one line;
`gma.cmd` returns nil or an error string; dialogs are answered by sending the option number.

**Test show:** the show currently loaded in onPC is the owner's designated test show. It is backed up,
holds nothing important, and uses the owner's usual fixture libraries and layout. You may store, delete,
re-patch or break anything in it without asking. Its name is deliberately not written here (public
repo); `ma2kit doctor` prints it, and the owner can confirm it. If a different show is loaded than the one
agreed with the owner, stop and ask. This permission
covers show data only: the Command Wing can output DMX, so moving or lighting fixtures still needs the
owner present (rule 1 below).

**Test rig (read live, 2026-11-11):** 32 fixtures, 2 universes.

| Fixture IDs | Type (library) | Mode | Patch |
|---|---|---|---|
| 100–111 | SUPER BRIGHT "BEAM 8R + RING" (moving head beam) | 24CH | 1.001–1.288, consecutive |
| 200–219 | SUPER BRIGHT "PAR280 SLIM" (LED PAR) | 9CH | 2.001–2.180, consecutive |

Existing pools: groups 1–6 (`ALL`, `ALL_ESC`, `8R_ESC`, `SYM_8R_ALL`, `PAR_ALL`, `SYM_PAR_ALL`); effects 1–4,
17, 18, 24, 25; layouts 1, 2, 3, 6; MAtricks 1; plugin 1 (`LUA`); no macros. Fixture-level positions (XYZ) are
all 0; the stage positions are stored on the subfixtures. Fixtures 108–111 reuse the names "BEAM8R_RING 1–4" of fixtures 100–103 (a naming slip the auto-tools
could detect). The beams are the targets for the pan/tilt normalization wizard.

Useful observations: `List Fixture` columns are `Name FixId ChaId FixtureType Patch ...` with patch as
`universe.address`; `List FixtureType` includes `DMXFootprint`, `Mode` and `Used`; `List Layer` lists the show's
top-level object tree (`EditSetup`, `Groups`, `Presets`, `Effects`, `Layouts`, ...); `List Macro` on an empty
pool replies `WARNING, NO OBJECTS FOUND FOR LIST`; `List Preset` with no type lists the current preset type only.

**After 0.4.0 (unreleased):** terminal screenshots of the menu and `doctor` in `docs/images/` (shown in the
README and `docs/08`), made by `tools/screenshots.py` from the real menu with private names replaced.

Do the phases in order. Each ends with a commit and a short status report to the owner. Stop and ask when
an acceptance check needs the owner (anything involving the running console).

### Status against this brief (2026-11-12)

✔ done · ◐ partly done or done differently · ✘ missing. Keep this table current.

| Item | State | Notes |
|---|---|---|
| **Goals** | | |
| G1 Understand | ✔ | `docs/01`, each statement marked checked or not |
| G2 Reference | ✔ | `docs/02` (Lua API), `docs/03` (commands) |
| G3 Script management | ✔ | `ma2kit plugins …`, `ma2kit macros …` |
| G4 Utilities | ◐ | Only auto groups, show checks, free slots and backup exist. Color picker, effect helpers, patch helper and pan/tilt wizard are missing |
| G5 Documentation | ◐ | Missing pages listed under Phase 6 |
| G6 Repository | ✔ | Public on GitHub, commits per feature |
| **Phase 0** | ✔ | Two deliberate differences from the layout: `lua/plugins/` holds flat `<name>.lua` files (the XML is generated at install), and `macros/` holds plain-text `<name>.txt` sources instead of XML |
| **Phase 1** | ◐ | Docs 01–04 written and checked live. ✘ No notes kept on the third-party ColorPicker plugin or on reading the official 3.9 help; do both before the color picker. ✘ Web remote and several XML imports not checked (section 3) |
| **Phase 2** | ◐ | Client, dry-run, transcript, reconnect, fake console all done. `shell` has only the Windows console's own line history (up arrow, F7), none kept between sessions |
| **Phase 3** | ◐ | `show summary`, `show fixtures --format table\|json\|csv`, `show pool`, `show group`, `show free` work. ✘ The fixture list has no **layer** column. ✘ Executors not checked (`show pool` is generic but untested on them) |
| **Phase 4** | ◐ | install / update / list / remove / run done; `lua/lib` is concatenated into each plugin. Instead of a manifest file, installed files go to their own subfolder (`plugins/ma2kit/`) and the show's pool is read for slots. Update re-imports, because `ReloadPlugins` does not reload files |
| **Phase 5.1** Color picker builder | ✘ | Not started; read the ColorPicker prior art first |
| **Phase 5.2** Auto groups | ◐ | Done: per fixture type, ALL / ODD / EVEN / halves, plus OUT>IN and IN>OUT, and a rig-wide ALL. ✘ Missing: per layer, thirds, left/right/center, every-Nth, configurable name pattern (names are fixed `<type> <variant>`) |
| **Phase 5.3** Effect helpers | ✘ | Not started. `docs/01` lists the effect-line properties found so far |
| **Phase 5.4** Patch helper | ✘ | Not started. Groundwork: `show check` already validates overlaps, overflow, unpatched and duplicate names on the loaded patch; the layer-export and subfixture-write methods are known (`docs/03`) |
| **Phase 5.5** Pan/tilt wizard | ✘ | Not started. Groundwork: read/write method for invert/offset verified. Blocked: the reference orientation (section 8) is unanswered, and with no wing the result can only be checked in the patch data, not seen (the Stage view ignores offset/invert). "Tried on two real heads" needs hardware |
| **Phase 5.6** Housekeeping | ✔ | `backup`, `doctor` (version, login, rights, show vs `allowed_shows`, leftover temp files) |
| **Phase 6** Menu | ✔ | Every menu entry is also a subcommand; screenshots in `docs/08` |
| **Phase 6** Docs | ◐ | ✔ `docs/05` (with the onPC clicks), `CHANGELOG.md`, pages for the existing utilities (06, 08, 09). ✘ `docs/troubleshooting.md` (a troubleshooting section exists inside `docs/05`). ✘ `docs/developing.md`: how to add a plugin is in `docs/07`, how to add a utility is not written. ✘ "Reach a working color picker from the README" cannot be met until 5.1 exists |
| **Safety rules** | | |
| 1 Real fixtures | ✔ | Live moves only with the owner present; no hardware connected at the moment |
| 2 Test show | ◐ | The owner's designated test show is used instead of a new `toolkit_dev`; `allowed_shows` guards writes. `SaveShow` before writing is not automatic: run `ma2kit backup` first |
| 3 Dry-run default | ◐ | `groups auto` and `batch` preview unless `--apply`, and there is a global `--dry-run`. ✘ `plugins install/update` and `macros install/update` act at once (they only add or replace ma2kit's own objects in free or own slots) |
| 4 Confirm destructive commands | ◐ | `cmd`, `shell` and `batch` ask before `Delete`, `/nc` and other risky commands; the menu asks before removing plugins or macros. No per-action listing yet for `EditSetup` changes, which no tool makes so far |
| 5 Pool safety | ✔ | Free-slot checks before storing; `show free` |
| 6 Console settings | ✔ | Never changed by the tool; the owner made them |
| 7 Secrets | ✔ | `config.toml` git-ignored, password masked in transcripts |
| 8 Track files in `MA_ROOT` | ◐ | No manifest file: everything ma2kit writes is in its own `ma2kit/` subfolders or named `ma2kit_tmp…`, and `doctor` removes leftovers |
| **Section 8 question** (reference orientation) | ✘ | Asked 2026-11-12; the owner chose to **decide later**. Work on the other utilities first and ask again before starting the pan/tilt wizard |

### Phase 0: Repository bootstrap
- `git init`, default branch `main`. Add `.gitignore` (Python, `config.toml`, `*.show.gz`, `*.backup`, exports, logs).
- Layout:
  ```
  README.md            overview + quick start
  AGENT_BRIEF.md       this file (keep; update the "verified" notes as you learn)
  docs/                all documentation (see Phase 6)
  ma2kit/              Python package (client, model, features, cli)
  lua/plugins/         one folder per plugin: <name>.lua (+ generated <name>.xml)
  lua/lib/             shared Lua helpers
  macros/              macro XML sources
  tests/               pytest (offline, against a fake Telnet server)
  config.example.toml
  pyproject.toml
  ```
- Python 3.12, a virtual environment in `.venv`, minimal dependencies. Note `telnetlib` is deprecated and
  removed in 3.13: use a plain socket / asyncio client.
- **Done when:** repo exists, `pip install -e .` works, `ma2kit --help` prints.

### Phase 1: Research and verification
- Read `plugin_1.lua`, `systemtests\api_test.lua`, a sample of `systemtests\test_*.lua`, `predefined.xml`, and
  the existing ColorPicker plugin. Read the official grandMA2 3.9 help for: command syntax, keyword list,
  plugins, Telnet remote, import/export, patch & fixture schedule, effects, MAtricks, system variables.
- With the owner: start onPC, load the test show, enable Telnet, then confirm each `?` item in section 3
  by actually doing it. Capture real `List` output samples (they become test fixtures).
- Write `docs/01-how-grandma2-works.md`, `docs/02-lua-api.md`, `docs/03-command-cheatsheet.md`,
  `docs/04-remote-control.md`. Mark every statement as *verified on 3.9.61* or *from docs, unverified*.
- **Done when:** a "hello" plugin from this repo has been imported and run, and a Python script has logged
  in over Telnet, sent `List Group`, and printed the parsed result.

### Phase 2: Connection layer (`ma2kit/client`)
- `MA2Client`: connect, login, `send(cmd) -> CommandResult(text, error)`, ANSI stripping, prompt detection,
  timeouts, reconnect, a transcript log of every command sent.
- Global `--dry-run` that records commands instead of sending.
- A fake Telnet server for tests, replaying the samples captured in Phase 1.
- **Done when:** tests pass offline; `ma2kit cmd "List Group"` works live; `ma2kit shell` gives an interactive
  command line with history.

### Phase 3: Show model reader (`ma2kit/model`)
- Read-only functions returning structured data: fixtures (ID, name, fixture type, universe.address, layer),
  fixture types, groups (+ members), preset pools, macros, plugins, effects, sequences, executors, free pool slots.
- Prefer XML export + parse where `List` output is ambiguous. Clean up exported temp files.
- **Done when:** `ma2kit show summary` and `ma2kit show fixtures --format table|json|csv` are correct on the test show.

### Phase 4: Script manager (G3)
- `ma2kit plugins list|install|update|remove|run <name>` and the same for `macros`.
- Install = generate the plugin XML from a small header in the `.lua` (name, description, default pool
  slot), copy both into `MA_ROOT\plugins\`, `Import ... At Plugin N` into a free or requested slot, record it
  in a manifest. Update = copy + `ReloadPlugins`. Remove = `Delete Plugin N` + remove copied files, with confirmation.
- A `lua/lib` helper module (logging, safe `cmd` wrapper that checks the error string, free-slot finder,
  confirm dialogs) concatenated into each plugin at install time, since `require` paths inside onPC are unreliable.
- **Done when:** a plugin edited in the repo is live in onPC after one command, and `remove` leaves no trace.

### Phase 5: Utilities (G4)
Each utility: a CLI subcommand, dry-run by default, start-index arguments for every pool it writes to,
a doc page, and tests for its command generation.

1. **Color picker builder.** For chosen groups and a color list (default: White, Red, Orange, Yellow, Green,
   Seagreen, Cyan, Blue, Lavender, Violet, Magenta, Pink; user-editable with RGB values), create color
   presets, per-group sequences/macros, an "All" row, and a layout view grid. Handle RGB, RGBW, CMY and
   color-wheel fixtures sensibly (report fixtures it cannot serve). Also offer an in-terminal picker:
   choose group + color → sends it to the programmer.
2. **Auto groups.** From the patch, generate groups: per fixture type, per layer, odd/even, halves,
   thirds, left/right/center by ID order, every-Nth, and "all of type". Names follow a configurable pattern.
3. **Effect helpers.** Template-driven creation of common effects into the effect pool for a group:
   dimmer chase/sine, pan/tilt circle, tilt wave, color fades between two presets (the "high/low" idea in
   the existing HighLowFX plugin), with rate/phase/wings/blocks parameters and MAtricks options.
4. **Patch helper.** Read a CSV (fixture ID, name, fixture type + mode, universe, address, layer, quantity),
   validate (address collisions, footprint overrun past 512, duplicate IDs, unknown fixture types), show
   a plan, then patch via fixture-layer XML import or commands. Also the reverse: export the current patch
   to CSV. Include `next-free-address` and `repatch --offset` helpers.
5. **Pan/tilt normalization wizard.** For a selected set of moving heads, one head at a time: highlight
   it, move to a small known test pose (pan only, then tilt only, limited range, slow), ask the operator
   which way the beam moved (stage left/right, up/downstage), compute the needed invert/swap, then ask
   them to nudge to a common home direction and compute pan/tilt offset. Show a summary table of proposed
   patch changes; apply only after confirmation; save a JSON report so a rig can be restored or re-applied.
   Must have an abort that releases the fixture and clears the programmer.
6. **Housekeeping.** `ma2kit backup` (SaveShow + timestamped copy of the show file into a local, git-ignored
   folder), `ma2kit doctor` (checks Telnet reachable, login OK, version is 3.9.61, test show vs. real show).

- **Done when:** each utility has been run dry and live on the test show with the owner watching, and
  item 5 has been tried on at least two different real moving heads.

### Phase 6: CLI polish and documentation (G5)
- `ma2kit` with no arguments opens a numbered menu covering every feature; every menu action is also a
  plain subcommand for scripting.
- Docs: `docs/05-install-and-setup.md` (including the exact onPC clicks to enable Telnet and create the
  toolkit user), one page per utility with examples, `docs/troubleshooting.md`, `docs/developing.md` (how
  to add a plugin or a utility), and a `CHANGELOG.md`.
- **Done when:** the owner can follow the README on a clean checkout and reach a working color picker
  without asking you anything.

## 7. Working conventions

- Small commits per feature; never commit show files, exports, logs, or credentials.
- English for code, comments and docs.
- Lua: no globals except the entry functions, `local` everything, every `gma.cmd` goes through the checked wrapper.
- Python: type hints, `pytest`, no network needed for tests.
- When a fact in this brief turns out wrong for 3.9.61, fix the brief and note it in the docs.

## 8. Questions to put to the owner when you start

1. For normalization: what is the reference orientation ("pan positive = stage left, tilt positive = upstage", or another convention)?
