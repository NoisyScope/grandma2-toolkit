# Macros, batch files and show checks

## Macros from text files

Macros live in the repo as plain text, `macros/<name>.txt`:

```text
# description: Save the show, then confirm on the command line.
SaveShow
wait 0.5
Lua "gma.feedback('ma2kit: show saved')"
```

- One command per line; `#` lines and blank lines are ignored.
- `wait N` sets the wait time (seconds) of the line **above** it: the macro line's `delay`, MA's "Wait" column.
- The first `# description:` line is shown by `ma2kit macros list`.
- The file name is the macro's name in the pool.

| Command | What it does |
|---|---|
| `ma2kit macros list` | Repo macros, their line count, and where each is installed. |
| `ma2kit macros install <name> [--slot N]` | Builds the macro XML and imports it into the first free macro slot from `[pools] macro_start` (default 500). |
| `ma2kit macros update [<name> ...]` | Imports edited macros again over their own slots. |
| `ma2kit macros remove <name> ...` | Deletes the macro from the pool and its XML file. |

Run an installed macro on the console, or with `ma2kit cmd "Macro 501"`.

**Verified on 3.9.61:** `Import "ma2kit/<name>.xml" At Macro N` reads from `<MA data folder>/macros/ma2kit/`.
Exporting an installed macro gives back the same lines and delays. The console normalises keywords in
stored lines (`Lua` is stored as `LUA`). Updating answers the "Overwrite Confirmation" dialog with Overwrite
for that one object.

## Batch files

A batch file is a list of commands to send once, with a preview:

```text
# make a test group
ClearSelection
Fixture 1 Thru 4
Store Group 600
wait 0.2
Label Group 600 "Test"
```

```powershell
ma2kit batch my_commands.txt            # preview: numbered table, nothing sent
ma2kit batch my_commands.txt --apply    # send
```

- Stops at the first error (`--keep-going` to continue).
- Console warnings such as `WARNING, NO OBJECTS FOUND FOR LABEL` (the command did nothing) are shown as
  `[WRN]` and counted; `--strict` treats them as errors.
- Dialogs are answered Cancel. Commands that delete or replace data (`Delete`, `NewShow`, `/nc`, ...) are
  marked in the preview and need a confirmation (`--yes` to skip it).
- `wait N` pauses N seconds (not sent to the console).
- Respects `[safety] allowed_shows`. `-` reads the commands from standard input.

## Show checks

`ma2kit show check` looks for problems in any show:

| Check | Severity | Meaning |
|---|---|---|
| `overlap` | error | Two fixtures share DMX addresses in the same universe. |
| `overflow` | error | A fixture's footprint runs past address 512. |
| `unpatched` | warning | Fixtures with no DMX address. |
| `duplicate-name` | warning | Several fixtures with the same name. |

Footprints come from `List FixtureType` (`DMXFootprint`). Exit code 2 when there are errors.

## Free slots

`ma2kit show free <Pool> [--count N] [--start S]` prints the first number from S where N slots in a row are
empty, e.g. `ma2kit show free Group --count 10 --start 500` gives `Group 515-524 is free`.
