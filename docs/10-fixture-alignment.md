# Fixture alignment: make the real rig match the 3D (design)

**Status: design, not built yet.** This page records what grandMA2 3.9.61 already offers, the method chosen
for `ma2kit align`, and what still has to be checked. Marks: **✔** checked on onPC 3.9.61 by this project,
**○** from MA's built-in help (`lang/en/help/` in the MA data folder), not tried yet, **?** to be checked.

## The goal

Positions are programmed against the 3D model (Stage view or MA 3D). On site, every moving head should land
exactly where the 3D says, so existing position presets work without re-focusing. Narrow beam fixtures
show every error: at 15 m throw, 0.1° is about 2.6 cm and 1° about 26 cm.

## Two directions, two tools

| | Direction | What changes | Exists? |
|---|---|---|---|
| **A. MA's auto-calibration** | 3D ← reality | Fixture position and rotation in the 3D | ○ built into grandMA2 3.x |
| **B. Offset alignment** (`ma2kit align`) | reality ← 3D | Pan/tilt offsets in the patch | to build |

**A. MA's auto-calibration** (○ help pages *Fixture Position Calibration Dialog* and *Auto-calibrate
fixture positions*; ✔ the dialog and its messages exist in this build). Opened from the Stage view
options, Calibration tab, button *Calibrate Fixture Pos*:

- You mark four floor points that form a rectangle and enter where it is.
- You focus every fixture on each corner and store each corner.
- *Do Calibration* then moves and rotates the fixtures in the 3D so that the stored pan/tilt values point at
  those corners.

It suits **XYZ programming** (grandMA2 can add virtual X/Y/Z, Flip, Mark and Dist channels per fixture
type, and recalculates XYZ cues after a recalibration). It does **not** make existing pan/tilt presets
land: it changes the model to fit the rig, not the rig to fit the model.

**B. Offset alignment** is what this project builds: keep the 3D as the truth and correct each fixture's
`PanOffset` / `TiltOffset` (and invert flags) so that the real fixture answers like its 3D twin.

## Method for `ma2kit align`

### 1. Define the target

You measure one spot on the stage (a tape cross) and enter its stage coordinates X, Y, Z in metres, in the
same system as the 3D. A spot in the middle of the area the fixtures normally play in gives the best
average. Fixtures can share one target or have their own.

### 2. Desired pan/tilt (what the 3D says)

The tool computes, per fixture, the pan/tilt that aims at the target. It uses the fixture's 3D position
and rotation (✔ on the subfixture: `PosX/Y/Z`, `RotX/Y/Z`) and the fixture type's pan/tilt ranges (✔ e.g.
the BEAM 8R type: pan −270…270°, tilt −135…135°, 16-bit). It stores the result as a position preset,
"desired", so you can see it in the Stage view: every beam should hit the target there.

Alternative for a cross-check: aim the fixtures at the target in the Stage view (MA's *Follow*) and store
that preset yourself. The tool can also just compare two presets you made.

### 3. Actual pan/tilt (what reality needs): guided focus

The tool walks through the fixtures **one at a time**:

1. It selects only that fixture.
2. With the operator present, it brings the dimmer up or highlights the fixture, and starts from the
   desired values.
3. The operator centres the beam on the tape cross:
   - with the console encoders, or
   - with keys in the ma2kit terminal: arrow keys nudge pan/tilt, a modifier changes the step
     (1° / 0.1° / 0.01°), so no wing is needed.
4. **Enter** stores that fixture's pan/tilt into the "actual" preset (`Store … /merge`).
5. **S** skips the fixture, **B** goes back, **Esc** aborts: release the fixture and clear the programmer.

✔ A preset's values can be read back from `Export Preset 2.N "name"`. The XML holds one `PresetValue` per
fixture and attribute, e.g. `PAN = 0.0041`, `TILT = 52.65`, in degrees.

### 4. Compute the corrections

Per fixture: correction = actual − desired, for pan and for tilt. Then:

- **Choose the same solution.** One spot can be reached by (pan, tilt), (pan ± 180°, −tilt), and pan ± 360°.
  Before subtracting, the desired solution closest to the actual one is chosen.
- **Turn the correction into an offset** in the fixture's own axes. Account for the invert and swap flags
  already set, and add it to any offset already there.
- **Flag a suspect fixture** when the correction is large (default > 10°). A large correction usually
  means one of these, and not an offset problem:
  - wrong invert or swap (it shows as a sign flip),
  - wrong 3D position or rotation,
  - the wrong fixture type or mode.

### 5. Review, apply, report

A table lists, per fixture, the old offsets, the new offsets and the correction. Nothing changes before
confirmation. Applying writes:

```
cd "EditSetup"; cd "Layers"; cd <layer>; cd <fixture index>
Assign 1 /PanOffset=<new> /TiltOffset=<new>
cd /
```

✔ This writes the patch the same way as the pan/tilt patch tests that worked (see `docs/03`). A JSON
report keeps the old and new values, so the change can be undone or applied again to the same rig.

### 6. Verify with a second spot (recommended)

Offsets correct a **constant angle error**: the fixture base turned on the truss (pure pan offset), or a
tilt zero error. They cannot fully correct:

- a fixture hung in a different **place** than in the 3D,
- a **tilted mount** (truss not level, clamp twisted),
- a pan/tilt **range** in the fixture type that differs from the real fixture (a scale error).

With one spot those errors vanish at that spot and grow away from it. So after applying, the tool aims all
fixtures at a second measured spot, using the computed "desired" values. If the beams miss, there is a
residual error in the 3D or the hang. The tool then:

- measures that spot too, and fits the offsets to both spots (least squares);
- reports the residual per fixture;
- above a threshold, says which fix is needed: correct the 3D position/rotation, use MA's calibration (A),
  or check the fixture type's ranges.

## Beam fixtures: practical points

- Make the spot as small as possible: no prism, no frost, smallest gobo or iris, sharp focus.
- Reset the fixtures before aligning (cheap beams lose steps), and approach the spot from the same
  direction every time (gear backlash).
- Use 16-bit pan/tilt (the BEAM 8R type has fine channels: ✔).
- Generic or home-made fixture types for budget beams often state pan/tilt ranges that differ from the real
  fixture (the library folder on this PC holds several variants of the same beam type). A wrong range is
  a scale error, which offsets cannot fix and which step 6 detects.

## What still has to be checked

| Item | How | Needs hardware |
|---|---|---|
| MA's geometry convention: rotation order, and where pan 0 / tilt 0 point for a hanging fixture | Compare computed aims with the Stage view (place a target, aim, look) | no |
| Pan/tilt from the 3D matches MA's own XYZ conversion | Enable XYZ on a copy of the fixture type in the test show, set X/Y/Z, store, export and compare | no |
| Unit and sign of `PanOffset` / `TiltOffset` (degrees? added or subtracted?) | Watch the real beam or the DMX output after setting an offset | **yes** (the Stage view ignores offsets ✔) |
| Offsets combined with `PanDMXInvert` / `TiltDMXInvert` / `Swap` | Same | **yes** |
| `Store Preset 2.N /merge` for one fixture keeps the others | Store, then export | no |

The parts that need no hardware come first: the geometry model, preset read/write, the guided-focus
screen (it works on the Stage view) and the report. The real alignment, and the checks marked **yes**,
need the wing reconnected and the operator present.
