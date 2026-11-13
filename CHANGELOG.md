# Changelog

## 0.5.0

- **MCP server** `ma2kit-mcp` (`ma2kit/mcp_server.py`, standard library only, stdio): tools `ma2_status`,
  `ma2_command`, `ma2_list`, `ma2_set`, `ma2_export`, `ma2_import`, `ma2_lua`, `ma2_help`, `ma2_guide`,
  `ma2_patch`, `ma2_backup`. See `docs/11-mcp-server.md`.
- Safety in the server: show allow-list, `allow_destructive`, `confirm_live` when DMX hardware is
  connected, dialogs cancelled by default, always back to the tree root.
- Checked on 3.9.61 and written into the cheat sheet and the server's guide: fixture type import, layers,
  fixtures, patching, `Move3D` / `Rotate3D`, presets, cues, executors, macros, layouts, views, timecode
  shows, import from any folder with `/path=`.
- Correction: `Assign <Object> N /property=value` at the root fails over Telnet (`Error #14`); it works
  from inside the object tree. The cheat sheet had marked the root form as verified.

- Screenshots of the menu and `doctor` in `docs/images/`, shown in the README and doc 08.
- `tools/screenshots.py` remakes them from the real menu with scripted input, with the show name,
  computer name and user folder replaced.
- `AGENT_BRIEF.md`: a status table marks every goal, phase and safety rule as done, partly done or
  missing; section 3 items now say which were checked on 3.9.61. The README links to it.
- `docs/10-fixture-alignment.md`: design for aligning the real rig to the 3D with pan/tilt offsets, and
  what grandMA2 3.9 already has (4-point auto-calibration, XYZ).

## 0.4.0

- Reference docs: `01-how-grandma2-works`, `02-lua-api`, `03-command-cheatsheet`, `05-install-and-setup`,
  each statement marked as checked on 3.9.61 or not.
- Read-only plugins `ma2kit_api_dump` (lists the Lua environment and every `gma.*` function) and
  `ma2kit_inspect` (class, children and properties of any object, chosen with `$MA2KIT_INSPECT`).
- Client: recognises the tree-path prompt after `cd` (`EditSetup/Layers 4 >`); before, any command after a
  `cd` timed out. New `MA2Client.poll()` returns feedback that arrives after a reply.
- Batch runs print late feedback (from `Lua` or plugin lines) under the step that caused it.
- `cmd` and `batch` no longer print each console error twice.

## 0.3.0

- Menu keeps one logged-in session for all actions and shows connection, user and loaded show in its
  header; invalid input no longer exits the menu.
- `ma2kit batch FILE [--apply]`: preview, stop on first error, `wait N`, `--keep-going`, `--strict`.
- Macro manager: `ma2kit macros list | install | update | remove` from plain-text `macros/*.txt`
  (`wait N` sets the line delay). Example macros `ma2kit_clear_all`, `ma2kit_save_show`.
- `ma2kit show check`: DMX overlaps, overflow past 512, unpatched fixtures, duplicate names.
- `ma2kit show free <Pool> --count N`: first free run of pool slots.
- `doctor` removes leftover temporary export files.
- Client: `CommandResult.warnings` for console warnings such as `NO OBJECTS FOUND`.
- Config: `[pools] macro_start`.

## 0.2.0

- Interactive menu (`ma2kit` with no arguments, or `ma2kit menu`).
- Plugin manager: `ma2kit plugins list | install | update | run | remove`, Lua helper library
  (`lua/lib/ma2kit.lua`), example plugin `ma2kit_info`. Plugin errors point at the source file and line.
- `ma2kit backup`: save the show and keep timestamped, rotated copies.
- `ma2kit monitor`: follow the console's system monitor (port 30001).
- Client: handles console confirmation dialogs (Cancel unless a person chooses), output that arrives after
  the prompt, keyword-normalised echoes, and reconnects automatically when the console closed the connection.
- Safety: `[safety] allowed_shows` stops show-changing commands on any other show; `doctor` reports it.
- Config: `[pools]`, `[backup]`, `[monitor]`, `[safety]` sections.

## 0.1.0

- Telnet client, `doctor`, `cmd`, `shell`.
- Show reader: `show summary | fixtures | pool | group`.
- `groups auto`.
