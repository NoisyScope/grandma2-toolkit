# Reading the show and auto groups

## Reading the show (read-only)

| Command | Output |
|---|---|
| `ma2kit show summary` | Loaded show, software version, fixtures per type with IDs and patch span, and which numbers are used in the Group, Effect, Sequence, Macro, Layout, Plugin and MAtricks pools. |
| `ma2kit show fixtures [--format table\|json\|csv] [--positions]` | Every fixture: ID, name, fixture type, patch. `--positions` adds the 3D stage position (X, Y, Z). |
| `ma2kit show pool Group` | Any pool by name: `Group`, `Effect`, `Macro`, `Layout`, `Sequence`, `Plugin`, `MAtricks`, ... |
| `ma2kit show group 4` | The members of a group, in their stored order. |

Example: export the patch to a spreadsheet:

```powershell
ma2kit show fixtures --format csv --positions > patch.csv
```

### How it works (verified on 3.9.61)

- `List <pool>` prints a fixed-width table. The header row's column starts line up with the values, and
  each row begins with `<Class> <number>`, so the parser slices rows at the header's column positions.
  An empty pool prints `WARNING, NO OBJECTS FOUND FOR LIST`.
- `List Fixture` shows `PosX/PosY/PosZ` as `0.00` even when fixtures have stage positions. The real
  positions, group members and their order are only in XML exports: `Export Group 4 "name"` writes
  `importexport/name.xml`, `Export Fixture 100 Thru 111 "name"` writes `fixtures/name.xml` under the MA data
  folder (`$PATH` from `ListVar`). `ma2kit` exports to a temporary `ma2kit_tmp_*` file, reads it and deletes it.
  This only works when onPC runs on the same PC.
- Fixture XML holds the absolute DMX address (`<Address>` 1 to 512 per universe in sequence) and
  `<Location x y z>` in metres.

## Auto groups

```powershell
ma2kit groups auto                 # preview: table of groups + exact commands, changes nothing
ma2kit groups auto --apply         # create them
ma2kit groups auto --start 600 --types BEAM8R_RING --variants all,odd,even --apply
```

For each fixture type (in fixture ID order), plus one `ALL FIXTURES` group when the rig has several types:

| Variant | Contents |
|---|---|
| `all` | every fixture of the type |
| `odd` / `even` | 1st, 3rd, 5th ... / 2nd, 4th, 6th ... |
| `halves` | first half and second half by ID (4+ fixtures) |
| `outin` | outside to inside: first, last, second, second-to-last ... (useful for symmetric effects) |
| `inout` | the reverse of `outin` |

Groups are named `<fixture type short name> <VARIANT>`, e.g. `BEAM8R_RING ODD`, and numbered from
`--start` (default 500). The selection order is kept, which matters for effects and MAtricks.

**Safety:** the whole range is checked first; if any slot is used, nothing is created. `Store` into an
occupied group slot gives no error or prompt on the console, so this check is the only protection.
Creating groups only selects fixtures and stores; it sends no light output. The selection is cleared at the end.

### Commands sent per group (verified)

```
ClearSelection                  (replies Error #72 if nothing was selected; ignored)
Fixture 100 + 111 + 101 + 110   (ascending runs of 3+ become "a Thru b")
Store Group 513
Label Group 513 "BEAM8R_RING OUT>IN"
```

## Ideas not done yet

- Position-aware groups (by side, front to back, mirror pairs) using the X/Y/Z from `--positions`. In the
  test rig the beams are two lines of six at X = -4.5 and X = +4.5, so "by side" would be meaningful.
- Detecting duplicate fixture names (the test rig reuses `BEAM8R_RING 1-4` for fixtures 108-111).
