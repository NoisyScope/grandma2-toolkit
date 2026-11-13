# MCP server: let an AI agent drive grandMA2

`ma2kit-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server. An AI agent (Claude Code,
Claude Desktop, or any MCP client) connects to it and can then read and change the show in grandMA2 onPC:
anything the console's Telnet command line allows.

- **Lightweight:** one Python module on top of the existing Telnet client, standard library only, MCP over
  stdio. It starts in well under a second and opens the Telnet session on first use.
- **Self-describing:** the tool `ma2_status` reports the state of the connection and lists every tool and
  guide topic, so an agent can orient itself with one call.
- **Grounded:** `ma2_guide` serves command recipes that were checked on onPC 3.9.61, and `ma2_help` searches
  MA Lighting's own help pages installed with onPC (829 pages, one per command keyword).

## Set up

1. Do the normal setup in [05](05-install-and-setup.md): Telnet = *Login Enabled*, an MA user for the tool,
   `config.toml` with its password, and `pip install -e .`.
2. Tell your MCP client how to start the server. For Claude Code, from the repository folder:

   ```powershell
   claude mcp add grandma2 -- "C:\path\to\grandma2-toolkit\.venv\Scripts\python.exe" -m ma2kit.mcp_server
   ```

   Or as JSON (Claude Desktop's `claude_desktop_config.json`, or a project `.mcp.json`):

   ```json
   {
     "mcpServers": {
       "grandma2": {
         "command": "C:\\path\\to\\grandma2-toolkit\\.venv\\Scripts\\python.exe",
         "args": ["-m", "ma2kit.mcp_server"],
         "env": { "MA2KIT_CONFIG": "C:\\path\\to\\grandma2-toolkit\\config.toml" }
       }
     }
   }
   ```

   The password stays in `config.toml` (or `MA2KIT_PASSWORD`); it is never passed through the agent and is
   masked in every reply and in the transcript log.
3. Ask the agent to run `ma2_status`.

## Tools

| Tool | What it does | Changes the show |
|---|---|---|
| `ma2_status` | Connection probes: reachable, Telnet enabled, login, version, loaded show and whether it may be changed, DMX hardware, plus the list of tools and guide topics | no |
| `ma2_command` | Sends command lines in one session and returns each one's output, errors and warnings. `cd` lasts for the call, then the session returns to the root | yes |
| `ma2_list` | Lists a pool or a place in the object tree as structured rows | no |
| `ma2_set` | Sets object properties from inside the tree (the form that works over Telnet) and shows the result | yes |
| `ma2_export` | Returns an object's full XML: preset values, cue contents, layouts, macros, timecode shows, executors | no |
| `ma2_import` | Imports XML content you give it, or a file from the console's folders (fixture types from the library) | yes |
| `ma2_lua` | Runs Lua inside the console and returns what it prints or returns | can |
| `ma2_help` | Searches MA's official help pages on this PC; works without a connection | no |
| `ma2_guide` | Verified recipes: basics, patch, position, presets, sequences, executors, macros, layouts, views, timecode, effects, lua, safety | no |
| `ma2_patch` | Creates fixtures in a new layer in one step: fixture type from the library, IDs, DMX addresses, 3D positions | yes |
| `ma2_backup` | `SaveShow` plus a timestamped copy of the show file | no |

### What `ma2_status` returns

```json
{
 "server": "ma2kit-mcp 0.5.0",
 "console": "127.0.0.1:30000",
 "reachable": true,
 "connected": true,
 "logged_in_as": "toolkit",
 "user_rights": "Admin",
 "software_version": "3.9.61.5",
 "show": "demo_show",
 "show_may_be_changed": true,
 "hardware": { "fader_modules": 0, "granted_universes": [], "live_output": false },
 "output_note": "No DMX hardware: nothing reaches real fixtures; results show in the Stage view only.",
 "official_help": "829 pages",
 "tools": { "ma2_command": "Send command lines to the console …", "…": "…" },
 "guide_topics": { "patch": "Import a fixture type from the library …", "…": "…" }
}
```

When something is wrong it says what and how to fix it: console not running, Telnet disabled, or a failed
login.

## What an agent can set up

Checked on onPC 3.9.61 through this server (**✔** worked, **◐** partly, **✘** no working command found):

| Task | State | How |
|---|---|---|
| Add a fixture type from the library | ✔ | `ma2_patch library_file=…`, or `Import "name"` in `EditSetup/FixtureTypes` |
| Create and patch fixtures | ✔ | `ma2_patch`: new layer, fixtures, IDs, consecutive addresses; refuses ID or address clashes and addresses past 512 |
| Position fixtures on the stage | ✔ | `positions` / `rotations` in `ma2_patch`, or `Move3D At x y z` and `Rotate3D At x y z` on a selection |
| Pan/tilt patch settings (invert, offset, swap) | ✔ | `ma2_set` on the subfixture |
| Presets | ✔ | Select, set values, `Store Preset type.n`, `Label`. Checked for dimmer, position and color; gobo, beam, focus and control use the same commands with other attributes |
| Groups | ✔ | `Store Group n`, `Label` |
| Sequences and cues | ✔ | `Store Cue n Sequence m`, labels; cue properties with `ma2_set` |
| Executors | ◐ | Assigning a sequence to an executor and setting its options works from inside the tree. ✘ No command was found to change a button's or fader's function; the values are visible in the executor's XML |
| Macros | ✔ | `Store Macro`, lines with `ma2_set` (`CMD`, `Wait`), or whole macros by `ma2_import` |
| Views | ◐ | `Store View n /screen=s` saves what a screen shows now, and labels work. Windows cannot be opened or arranged by command |
| Layout views | ◐ | `Store Layout n` from a selection, add group and macro buttons at x/y. Exact element positions and looks are in the layout XML; importing edited XML is not verified |
| Timecode | ◐ | Timecode shows can be created and their properties set (name, slot, length, …). ✘ No command adds single events; the route is XML (`ma2_export` an example, generate, `ma2_import`), not verified yet |
| Effects | ◐ | Reading works; creating by command is not verified |

The recipes behind this table are what `ma2_guide` returns. Each line is marked verified, documented only,
or failed, so the agent knows what to trust.

### Telnet differences found on 3.9.61

- `Assign <Object> N /property=value` typed at the root answers `Error #14`, for every object type tried.
  The same assignment works after `cd` to the object's parent. `ma2_set` does this.
- The keyword `Executor page.number` at the root answers `Error #14`; executors are reached through
  `ExecutorPages / 1 / <page>`.
- MA's help warns that a Telnet session inside `EditSetup` locks the patch for other users. Every tool
  returns to the root (`cd /`) when it finishes.

## Safety

- **Show allow-list.** With `[safety] allowed_shows` set, commands that change the show are refused on any
  other show. Reading always works.
- **Destructive commands** (`Delete`, `NewShow`, `LoadShow`, `Shutdown`, `Reboot`, `Restart`, anything with
  `/nc`) need `allow_destructive=true`. `Login` and `Logout` are refused.
- **Live output.** `ma2_status` reports fader modules and granted DMX universes. When hardware is connected,
  every changing call needs `confirm_live=true`: values, highlight, playbacks and patch changes then move and
  light real fixtures, so a person must be at the rig.
- **Dialogs** are answered *Cancel* unless the call sets `answer_dialogs`.
- **Lua** can run any command, so `ma2_lua` is treated as a changing call.
- Everything sent is written to the transcript log with the password masked.

## Limits

- Files (`ma2_export`, `ma2_import` with XML, `ma2_lua`) need onPC on the same PC as the server.
- One console per server, set in `config.toml`.
- Not tried: MA-Net sessions with several consoles, and the web remote.

## Development

The server is `ma2kit/mcp_server.py`; the recipes are `ma2kit/mcp_guide.py`. It implements MCP directly
(JSON-RPC 2.0, one message per line on stdin/stdout: `initialize`, `ping`, `tools/list`, `tools/call`), so
there is nothing to install. `tests/test_mcp.py` covers the handshake, the catalogue, the refusals and the
command building against the fake console.
