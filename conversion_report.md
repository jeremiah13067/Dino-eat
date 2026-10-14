# Digit Dash conversion audit

The complete executable block graph in the supplied `digit-dash.sb3` has been
translated into Python. This is project-specific coverage, not a claim of 100%
compatibility with every Scratch project or pixel-identical presentation.

## Coverage

| Target | Scripts translated / original | Stored blocks translated / original | Costumes retained | Sound references retained |
| --- | ---: | ---: | ---: | ---: |
| Stage | 0 / 0 | 0 / 0 | 3 | 1 |
| Dinosaur1 | 7 / 7 | 21 / 21 | 4 | 1 |
| Apple | 2 / 2 | 12 / 12 | 1 | 1 |
| Cake | 2 / 2 | 12 / 12 | 2 | 2 |
| Cheesy Puffs | 2 / 2 | 12 / 12 | 1 | 2 |
| Muffin | 2 / 2 | 12 / 12 | 2 | 1 |
| Rocks | 4 / 4 | 22 / 22 | 2 | 2 |
| . | 2 / 2 | 18 / 18 | 1 | 2 |
| Watermelon | 2 / 2 | 15 / 15 | 1 | 1 |
| **Total** | **23 / 23** | **124 / 124** | **17** | **13** |

There are eight sprites plus the Stage, 31 distinct stored opcodes, and no
unreachable or discarded stored blocks. Coverage comprises 23 event hats,
69 command/control blocks, and 32 reporter/menu blocks. Inline literals and
inline variable reporters are translated as expression inputs as well.

`coverage.json` maps each original block ID to its target, opcode, Python
function, role and source line. Statement lines point to the source annotation
immediately preceding their implementation; reporters/menus point to the
containing Python expression. `reference/analysis.json` contains the full
pre-translation graph, reachable block sets, variable accesses, collision target
dependencies, clone dependencies, and all original comments and metadata.

All original four Stage variables and Rocks' local `Game over` variable are
retained. `my variable` and `Game over` are unused by executable source logic;
they are preserved without inventing new behavior. All four monitor definitions
are retained, with three initially visible.

## Assets

- 21 distinct original assets retained byte-for-byte, with SHA-256 hashes in
  `coverage.json`: 13 SVGs, two PNGs, and six WAVs.
- All 17 costume/backdrop references retained, including three references to the
  same genuinely empty 0 × 0 SVG. Empty images intentionally produce no pixels
  or collisions; the one-pixel transparent PNG is only a loadable representation.
- 13 SVGs converted to PNG (nonempty SVGs at 2× resolution); original bitmap
  resolution factors, floating-point rotation centers, costume names and layers
  remain in `project_data.py`. Both original PNG assets are reused unchanged.
- 11 additional collision-mask PNGs derived from the original costumes using
  Scratch's actual WebGL renderer and CPU silhouette sampler. All project motion
  uses integer positions, size 100 and direction 90; these masks preserve the
  exact sampled contact behavior for those states, independently of display
  antialiasing. Transparent costumes need no collision mask.
- All six distinct WAVs, including two ADPCM files, are reused unchanged. Unused
  costumes and sounds remain available and are tested for loading.

## Implemented behavior

The generated scripts use ordinary Python conditions, loops and generators.
There is no runtime Scratch block dispatcher, embedded VM, browser, or loading
of `project.json`. The shared runtime implements every opcode used by this
project: green flag, key hats, clone-start hats; x/y movement and random position;
forever/repeat/if/wait; comparison, random and y reporters; variable assignment
and numeric change; show/hide and costume selection; sprite touching; cloning
and deletion; and play-sound-until-done.

Scheduling follows reverse executable-layer event order and original intra-target
hat order. Scripts run until waits, audio waits, or loop boundaries. New clone
threads can execute during the creating frame. Multiple scheduling passes within
a frame are allowed until a visual change requests redraw. Green flag stops
threads/audio, deletes clones, and runs the original reset scripts; it does not
restore unrelated saved positions. Key hats avoid duplicate simultaneously
running instances, as Scratch does.

Food relocates immediately on contact and adds points after the sound. Rocks
start in the empty `rocks2` costume, move every wait cycle, and switch to visible
rocks after five seconds. A rock collision clears Score and adds one Death;
Time left becomes 270 only when Alert finishes. The timer continues below zero,
clearing Score on each countdown tick below one. These source behaviors remain
intact.

The hidden `.` helper makes one clone. The clone shows its empty costume, starts
at y=160 and a random x, and repeats moving left 50 times with 0.25-second waits.
Its condition tests **y < -100**, while its movement changes **x**. Therefore
the original delete/replacement branch never happens naturally and its blank
clone persists after the script ends. The branch is nevertheless translated and
tested by deliberately setting the clone's y below -100 in a test.

No extensions, broadcasts, custom procedures, lists, sprite-click hats,
backdrop-change hats, speech bubbles, color sensing, graphical effects, glides,
asks, sound effect blocks, or hardware/network features occur in this project.
Their absence was verified from the full graph; no executable feature was
silently dropped. This runtime does not claim support for those unused opcodes
in arbitrary other projects.

## Executed verification

Test environment: Windows, CPython 3.12.10, pygame-ce 2.5.8 / SDL 2.32.10.

| Check | Actual result |
| --- | --- |
| Python compilation | All delivered Python source compiled successfully |
| Automated suite | **30 passed**, including six collision-grid cases |
| Asset integrity/loading | All original hashes match; all costume references load |
| Audio | All six WAVs decode; every sound reference starts a real SDL mixer channel using the dummy device; concurrent playback/restarts and wait timing tested |
| Gameplay | All five foods and their point values, rock delay/death/reset, negative countdown, WASD, restart, cancellation, clone scope/cap/deletion tested |
| Original Scratch execution | scratch-vm 5.0.300 + scratch-render 2.2.84, actual WebGL renderer in headless Chrome; five deterministic state snapshots captured |
| State comparison | Startup, five key events, ~1.1 s, ~5.13 s, and green-flag restart all match target positions, costume, visibility, variables, clone state and active script hats |
| Collision comparison | **5,346 / 5,346** WebGL reference probes match (891 each for six collectible/hazard costumes against Dinosaur1) |
| Startup visual comparison | Scratch and Python screenshots inspected side by side; image mean absolute channel error approximately **0.99 / 255**, excluding Python monitor area |
| Sustained native run | 1,800 frames (60 simulated seconds), with rendering and SDL dummy audio, completed without exception |
| Independence/portability | Tests copied Python modules and assets into a fresh directory without reference files or SB3 and launched successfully |

Evidence is in `verification/`: JUnit test results, five original Scratch state
snapshots, all original collision probes, measured collision comparisons, native
screenshots and the side-by-side visual comparison. The optional reference/mask
export harness and exact package versions are in `tools/scratch_reference/`.

## Remaining differences and verification limits

1. SVG display antialiasing, fractional pivot raster placement, and scaling use
   resvg plus Pygame rather than the browser/WebGL drawing path. Small visual
   edge differences remain; collisions at project-reachable states use the
   exported precise masks. Resizing scales the logical rendered stage rather
   than rerasterizing vectors at arbitrary window resolutions.
2. Monitor widgets are drawn with Pygame's available Helvetica/Arial-compatible
   font and native rounded rectangles. Their font metrics and border/padding can
   differ from Scratch's browser GUI. The WebGL reference screenshots exclude
   Scratch GUI widgets, so monitor pixels were excluded from the numerical image
   comparison.
3. OS/browser keyboard repeat timing is not portable. The Python window uses
   an explicit 500 ms delay and 33 ms repeat interval; each key event still moves
   exactly ten units. Key-event scripts are tested, but no physical human keyboard
   session was used as a verification claim.
4. Audio decoding, SDL channel playback and logical sound completion timing are
   tested with dummy audio. Physical speakers were not listened to. Device
   buffering/resampling can add audible latency. Audio-device failure retains
   sound wait durations and prints the device error instead of breaking gameplay.
5. The original reference sequence has no sound-triggering collision; its audio
   engine was disabled. Audio-triggered score/death sequencing is verified in
   native tests against the source block order and original sample durations.
6. The scheduler skips repeated polling passes once they make no observable
   progress, instead of busy-spinning until Scratch's work budget expires. Its
   pass safeguard is 100. This preserves the tested project states but is not a
   general proof of every possible Scratch concurrency ordering.
7. The 5,346 collision probes cover all active food/hazard costumes on a 10-unit
   grid against Dinosaur1 at the origin. They are strong sampled evidence, not
   exhaustive proof of every coordinate/renderer history. Non-project fractional
   positions, arbitrary rotations or size changes use the ordinary Pygame alpha
   fallback rather than the exported fixed-state masks.
8. PyInstaller instructions are included; an EXE build and other operating
   systems were not tested. The delivered Python application and ZIP are the
   verified deliverables.

There are no known omitted or partially implemented **source operations**.
The presentation/platform differences above are disclosed rather than claiming
universal or pixel-perfect compatibility.

## Semantics references

Primary sources inspected during translation:

- [Scratch VM control, waits and clones](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/src/blocks/scratch3_control.js)
- [Scratch VM motion and random positions](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/src/blocks/scratch3_motion.js)
- [Scratch VM coercion](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/src/util/cast.js)
- [Scratch runtime event ordering and green flag](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/src/engine/runtime.js)
- [Scratch script sequencing](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/src/engine/sequencer.js)
- [Scratch rendering, fencing and touching](https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-render/src/RenderWebGL.js)

Read-only copies of the inspected sources are retained under
`reference/semantics/`; executable tests additionally used the pinned package
versions recorded by the reference harness.
