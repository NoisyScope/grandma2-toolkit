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
| DMX output | onPC is used with **MA hardware (wing/node)**, so commands can move and light **real fixtures**. Treat every command as live. |
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
the command's output. ? The embedded interpreter is Lua 5.3 (check by echoing `_VERSION`).
? Plugins are loaded with `Import "name.xml" At Plugin N` (file in `MA_ROOT\plugins\`), run with
`Plugin N` or `Plugin "Name"`, refreshed with `ReloadPlugins`; one-liners run with `LUA "..."`.

**Known gap.** There is no Lua call that returns the current selection or programmer values. Work around
it with system variables (`$SELECTEDFIXTURESCOUNT` etc. via `gma.show.getvar`), the object tree
(`getobj` / `property`), or by `Export`-ing objects to XML and parsing the file.

**Telnet remote.** ? Enable in *Setup → Console → Global Settings → Telnet = Login Enabled*. Port **30000**
accepts commands and returns the command-line feedback as text (with ANSI colour codes); port **30001** is
read-only. First line must be `Login "user" "password"`. This is the Python side's transport: unlike
`gma.cmd`, it lets you read the output of `List`.

**Web remote.** ? Port 80 WebSocket remote (*Global Settings → Remotes*), needs a user with a password.
Optional fallback only; do not build on it unless Telnet proves insufficient.

**XML import/export.** ? Most pool objects (groups, presets, macros, effects, sequences, layouts, MAtricks)
and fixture layers (the patch) can be exported to and imported from XML. Generating XML and importing it
is usually faster and more reliable than hundreds of individual commands, and it is the standard route for
scripted patching.

**Pan/tilt settings.** ? Per-fixture patch columns in *Setup → Patch & Fixture Schedule* include Pan/Tilt DMX
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

**Test show:** when this was checked, the owner's real show was loaded, not a test show. Before any
command that writes to the show, confirm with `ma2kit doctor` (it prints the loaded show) that a test show
is loaded, and ask the owner if not.

Do the phases in order. Each ends with a commit and a short status report to the owner. Stop and ask when
an acceptance check needs the owner (anything involving the running console).

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

1. Which fixtures (make/model/mode) are in the usual rig? These decide color-mixing handling and the test set for the wizard.
2. For normalization: what is the reference orientation ("pan positive = stage left, tilt positive = upstage", or another convention)?
