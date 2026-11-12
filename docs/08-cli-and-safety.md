# Using ma2kit: menu, backup, monitor and safety

## Interactive menu

Run `ma2kit` with no arguments (or `ma2kit menu`) for a numbered menu:

```
ma2kit - grandMA2 toolkit
  127.0.0.1:30000  user toolkit  show my_test_show (may be changed)
   1  Status check (connection, login, show)
   2  Show summary
   3  List fixtures
   4  Browse a pool
   5  Group members
   6  Check the show (patch, names)
   7  Find free pool slots
   8  Auto groups
   9  Plugins
  10  Macros
  11  Run a command file (batch)
  12  Backup the show
  13  System monitor (Ctrl+C to stop)
  14  Command shell
   0  Quit
```

Every entry runs the same code as the matching subcommand, so anything in the menu can also be scripted.
The menu keeps **one logged-in session** for all actions (the command shell included), reconnecting by
itself if the console drops it; the header line shows the connection, user and loaded show on every
redraw. `Status check` deliberately tests a fresh connection. Invalid input is reported and the menu
carries on.

## Backup

`ma2kit backup` sends `SaveShow` (the console confirms with `Show successfully saved as "<name>"`) and copies
`<MA data folder>/shows/<name>.show.gz` to `backups/<name>_<YYYYMMDD-HHMMSS>.show.gz`. Only the newest
`[backup] keep` copies per show are kept. `backups/` is git-ignored.

## System monitor

`ma2kit monitor [--filter REGEX]` follows Telnet port 30001 (no login, read-only). It shows `gma.echo` output
from plugins, every command typed by any user (`toolkit 3 CMD INPUT : List Plugin`), Lua engine messages,
imports and show saves. Example: `ma2kit monitor --filter ma2kit`.

## Safety

| Protection | Details |
|---|---|
| Allowed shows | `[safety] allowed_shows = ["my_test_show"]` in `config.toml`: commands that change the show (`groups auto --apply`, `plugins`/`macros install/update/remove`, `batch --apply`) refuse to run on any other show. `doctor` reports whether the loaded show may be changed. Empty list = no restriction. |
| Previews | `groups auto` only shows its plan and commands unless `--apply` is given. `--dry-run` (global) prints commands instead of sending them. |
| Occupied slots | Group and plugin slots are checked before writing; the console itself overwrites silently. |
| Console dialogs | If a command opens a confirmation dialog, ma2kit answers **Cancel** unless a person chooses otherwise (`shell` and interactive `cmd` ask you). Nothing is confirmed by accident. |
| Risky commands | `cmd`/`shell` ask before `Delete`, `NewShow`, `LoadShow`, `Shutdown`, `Reboot`, `Restart` and anything with `/nc`. |
| Transcript | Every command is logged to `logs/transcript.log` with the password masked. |
| Reconnect | If the console closed the connection, the next command reconnects and logs in again. A command is only resent when it is certain it never reached the console. |
| Leftover files | `doctor` removes temporary `ma2kit_tmp_*` export files left by an interrupted run. |

Light output: reading the show, storing groups and installing plugins send no DMX changes. Anything that
selects with highlight, sets values or runs effects will move real fixtures when a Command Wing or node
is connected.
