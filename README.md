# Digit Dash — native Python conversion

A complete source conversion of the supplied `digit-dash.sb3`, using Python and
Pygame Community Edition. All 23 project scripts and 124 stored blocks are mapped
to readable Python. The game runs offline and does not load Scratch, a browser,
the SB3 archive, or `reference/project.json`.

## Install and play

Use **64-bit Python 3.12** (the tested version), or another Python version for
which pygame-ce supplies a compatible wheel. Open a terminal in this folder:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

With your Python environment already activated, the launch command is:

```sh
python main.py
```

On macOS/Linux, use `python3 -m venv .venv`, activate with
`source .venv/bin/activate`, then install and run as above. Those platforms have
not been tested here. Python 3.15 was also installed on the conversion machine;
use the explicit `py -3.12` commands to select the tested interpreter.

- **W/A/S/D:** move up/left/down/right, ten Scratch units per key event.
- **F5:** green flag/restart.
- **Escape:** Scratch stop-all; F5 resumes through the green-flag scripts.
- **Close the window:** quit.
- Resize freely; the stage keeps its 4:3 shape with letterboxing.

The window opens at 960 × 720, showing the logical 480 × 360 Scratch stage.
Key holding uses SDL repeats (500 ms initial delay, then 33 ms). Scratch receives
browser/OS key repeats, so the exact repeat cadence can differ by computer.

Collect Apple, Cake, Cheesy Puffs, and Muffin for one point each, or Watermelon
for ten. Points arrive when the eating sound finishes. Rocks become visible
after five seconds, move periodically, and reset the score on contact while
adding a death; the timer resets after the alert finishes. The original timer
continues below zero and clears the score each countdown tick. There is no
separate game-over screen in the source project.

F5 preserves properties that the original green-flag scripts do not reset.
For example, Rocks and Watermelon retain their current positions. This is
intentional Scratch behavior.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python -m compileall -q .
python main.py --headless --frames 180 --seed 10 --screenshot stage.png
python tools/verify.py
```

Additional launch options: `--mute`, `--seed INTEGER`, `--frames INTEGER`, and
`--screenshot PATH`. Headless mode uses SDL dummy video/audio drivers and advances
at a deterministic 30 steps per second without waiting for real time.

The tests include actual Scratch VM/WebGL reference snapshots and 5,346 collision
probes. Reference results are already included; running the Python tests requires
no JavaScript, Scratch, or network. See `conversion_report.md` for measured
coverage, results, and differences.

## Source layout

| File | Purpose |
| --- | --- |
| `main.py` | Window, events, scaling, command-line entry point |
| `scripts.py` | All translated project scripts; original block ID comments |
| `project_data.py` | Saved state and asset metadata; no executable blocks |
| `runtime.py` | Sprites, variables, events, cloning, restart |
| `scheduler.py` | Cooperative threads, waits and loop yielding |
| `graphics.py` | Costumes, pivots, fencing, collisions and monitors |
| `audio.py` | Concurrent original WAV playback and completion timing |
| `semantics.py` | Scratch coercion, comparison, rounding and randomness |
| `assets/` | Ready-to-run images, sounds, and precise collision masks |
| `coverage.json` | All 124 block IDs mapped to Python functions/source lines |
| `reference/analysis.json` | Full analyzed graph and script dependencies |
| `reference/` | Unmodified original assets and original `project.json` |
| `tests/`, `verification/` | Automated tests, evidence and comparison images |
| `tools/convert.py` | Build-time analysis, asset conversion and code generation |

Only the root Python modules and `assets/` are needed to play. The reference
materials are included for auditing, not runtime execution.

To regenerate Python source and SVG renders, install the development dependencies
and run `python tools/convert.py`. Optionally pass a path to the same original SB3.
The translator intentionally rejects unhandled block types rather than silently
omitting them. It is a converter for this project's opcode set, not a universal
SB3 converter. Existing precise collision masks and their metadata are retained.

`tools/scratch_reference/` records the optional JavaScript harness used for actual
Scratch comparison and exact mask export. Its README explains regeneration.

## Optional standalone Windows executable

Run on Windows in the activated Python environment:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DigitDash --add-data "assets;assets" main.py
```

The output is `dist\DigitDash.exe`. Assets are bundled inside the executable.
Scratch, Node.js, the SB3 and reference files are not included or required.
Build on the target OS; PyInstaller does not cross-compile. The executable build
has not been tested as part of this delivery.

Original project artwork/audio remain the supplied creator's materials; no new
license for those assets is asserted by this conversion.
