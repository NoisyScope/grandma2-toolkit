# grandma2-toolkit

An **MCP server for grandMA2 onPC v3.9.61**: it lets an AI agent (Claude Code, Claude Desktop, or any
[MCP](https://modelcontextprotocol.io) client) read and set up a show through the console's Telnet command
line. A command-line toolkit (`ma2kit`) built on the same connection comes with it.

> **Safety:** with an MA Command Wing or node connected, commands act on real fixtures. The server refuses
> changes in that case unless the call confirms a person is at the rig. Set `[safety] allowed_shows` to a
> test show while experimenting.

## The MCP server

`ma2kit-mcp` is one Python module with no dependencies beyond the standard library. It speaks MCP over stdio.

| Tool | What it does |
|---|---|
| `ma2_status` | Connection probes (reachable, Telnet enabled, login, version, loaded show, DMX hardware) plus the list of every tool and guide topic. An agent calls this first |
| `ma2_command` | Sends any command lines, as typed at the console, and returns output, errors and warnings |
| `ma2_list` | Lists a pool or a place in the object tree as structured rows |
| `ma2_set` | Sets object properties (from inside the object tree, the form that works over Telnet) |
| `ma2_export` / `ma2_import` | Reads an object's full XML; imports XML or a library file |
| `ma2_lua` | Runs Lua inside the console and returns the result |
| `ma2_help` | Searches MA Lighting's official help installed with onPC (829 pages, one per keyword) |
| `ma2_guide` | Command recipes checked on onPC 3.9.61, each line marked verified, documented only, or failed |
| `ma2_patch` | Creates fixtures in one step: fixture type from the library, IDs, DMX addresses, 3D positions |
| `ma2_backup` | Saves the show and keeps a timestamped copy |

What an agent can set up with it, as checked on onPC 3.9.61:

| Task | State |
|---|---|
| Fixture types from the library, new fixtures, patching, 3D positions, pan/tilt patch settings | works |
| Groups, presets (dimmer, color, position checked), sequences and cues, macros | works |
| Executors | assigning sequences and options works; no command found for button and fader functions |
| Layout views | create, add fixtures, group and macro buttons; exact placement by XML not verified |
| Views | saves what a screen shows; cannot open or arrange windows |
| Timecode | creates timecode shows and sets their properties; no command found for single events |

Details, setup for each MCP client, and the safety rules: **[docs/11-mcp-server.md](docs/11-mcp-server.md)**.

### Quick start (Windows, Python 3.11+)

1. In onPC: **Setup → Console → Global Settings → Telnet = Login Enabled**, and create an MA user for
   the tool (**Setup → Console → User & Profiles Setup**). Details: [docs/05](docs/05-install-and-setup.md).
2. Install:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```
3. Configure: copy `config.example.toml` to `config.toml` and set the user and password.
   `config.toml` is git-ignored. Alternatively set the `MA2KIT_PASSWORD` environment variable.
4. Register the server with your MCP client. Copy the entry from [mcp.example.json](mcp.example.json) into
   the client's settings and replace the paths, or with the Claude Code CLI:
   ```powershell
   claude mcp add grandma2 -- "C:\path\to\grandma2-toolkit\.venv\Scripts\python.exe" -m ma2kit.mcp_server
   ```
5. Start a new session in the client and ask the agent to run `ma2_status`.

## The command-line toolkit

The same connection is also available to a person at a terminal. `ma2kit` with no arguments opens a menu:

![The ma2kit menu](docs/images/menu-summary.svg)

| Command | What it does |
|---|---|
| `ma2kit` / `ma2kit menu` | Interactive numbered menu for everything below. Screenshots: [docs/08](docs/08-cli-and-safety.md#screenshots) |
| `ma2kit doctor` | Checks config, connection, Telnet, login, version, user rights, loaded show, plugin folder |
| `ma2kit cmd "List Group"` | Sends one command line and prints the reply |
| `ma2kit shell` | Interactive command line; asks you when the console opens a dialog |
| `ma2kit monitor [--filter REGEX]` | Follows the console's system monitor (plugin output, command log) |
| `ma2kit backup` | Saves the show and keeps a timestamped copy in `backups/` |
| `ma2kit show summary` | Fixtures per type, patch span, and pool usage |
| `ma2kit show fixtures` | All fixtures as a table, JSON or CSV; `--positions` adds stage X/Y/Z |
| `ma2kit show pool <Pool>` / `show group <n>` | Any pool's contents; a group's members in order |
| `ma2kit show check` | Finds DMX overlaps, patches past 512, unpatched fixtures, duplicate names |
| `ma2kit show free <Pool> --count N` | First run of N free slots in a pool |
| `ma2kit groups auto [--apply]` | Previews, then creates, ALL/ODD/EVEN/halves/out-in groups per fixture type |
| `ma2kit plugins list / install / update / run / remove` | Puts this repo's Lua plugins into the show and runs them |
| `ma2kit macros list / install / update / remove` | Turns plain-text `macros/*.txt` into macros in the show |
| `ma2kit batch FILE [--apply]` | Previews, then sends, a file of commands; stops at the first error |
| `--dry-run` (global) | Prints what would be sent, sends nothing |

## Status

| Part | State |
|---|---|
| MCP server: 11 tools, safety checks, recipes, official help search | working; gaps listed in [docs/11](docs/11-mcp-server.md#what-an-agent-can-set-up) |
| Telnet client: dialogs, late output, tree-path prompts, auto-reconnect, transcript with masked password | working |
| CLI: menu, `doctor`, `cmd`, `shell`, `monitor`, `backup`, show reader, checks, auto groups, batch | working |
| Plugin manager with Lua helper library; macro manager | working |
| Reference docs on grandMA2 (concepts, Lua API, commands), checked on 3.9.61 | written |
| Fixture alignment to the 3D ([design](docs/10-fixture-alignment.md)), color picker, effect helpers | not started |

All "working" parts are tested offline and against onPC 3.9.61. The full checklist of the project plan is in
[AGENT_BRIEF.md → Status against this brief](AGENT_BRIEF.md#status-against-this-brief-2026-11-12).

## Documentation

For agents and their operators:

- [11 MCP server](docs/11-mcp-server.md): setup, tools, what an agent can set up, safety
- [05 Install and setup](docs/05-install-and-setup.md): onPC settings, install, config, troubleshooting

grandMA2 reference (each statement marked as checked on 3.9.61 or not):

- [01 How grandMA2 works](docs/01-how-grandma2-works.md): the object tree, fixtures and patch, pools, files on disk
- [02 Lua API](docs/02-lua-api.md): every `gma.*` function on 3.9.61, object classes, properties
- [03 Command cheat sheet](docs/03-command-cheatsheet.md): syntax, reading, storing, import/export, patch editing
- [04 Remote control](docs/04-remote-control.md): Telnet setup, reply formats, dialogs

The command-line toolkit:

- [06 Show reader and auto groups](docs/06-show-reader-and-groups.md)
- [07 Lua plugins](docs/07-plugins.md): writing plugins, the helper library, how install/update work
- [08 Menu, backup, monitor and safety](docs/08-cli-and-safety.md)
- [09 Macros, batch files and show checks](docs/09-macros-batch-checks.md)

Plans and history:

- [10 Fixture alignment to the 3D](docs/10-fixture-alignment.md) (design, not built)
- [CHANGELOG](CHANGELOG.md)

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests run offline against a fake console (`tests/fake_ma2.py`) built from replies captured on onPC 3.9.61.
The MCP server is `ma2kit/mcp_server.py`, its recipes are `ma2kit/mcp_guide.py`.
`tools/screenshots.py` remakes the images in `docs/images/` from the real menu (needs the console).

## Licence

MIT, see [LICENSE](LICENSE). grandMA2 is a product of MA Lighting; this project is not affiliated with it.
