# Changelog

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
