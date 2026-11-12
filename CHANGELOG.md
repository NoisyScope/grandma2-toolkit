# Changelog

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
