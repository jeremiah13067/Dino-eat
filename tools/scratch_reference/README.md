# Optional reference harness

This build-time utility runs the retained original project in the actual Scratch
VM/WebGL renderer, captures deterministic states and screenshots, probes 5,346
collision placements, and exports the original costumes' integer-lattice alpha
collision masks. None of this JavaScript is used by the Python application.

From this directory:

```sh
npm install
npx playwright install chromium
node run.cjs
```

Alternatively set `CHROME_PATH` to an existing Chrome executable. The utility
starts a temporary HTTP server bound only to 127.0.0.1 and closes it afterward.
It reconstructs the reference SB3 in memory from `reference/project.json` and the
original assets, so the downloaded SB3 path is unnecessary. Assets are served
locally to headless Chrome; they are not uploaded.

It refreshes `verification/scratch_vm_reference.json`, two Scratch screenshots,
`assets/collision/`, and `reference/collision_metadata.json`. Then run
`python tools/convert.py` from the project root to refresh metadata and source,
and run the Python tests.

The supplied evidence was generated using these same package versions and
locally installed Google Chrome on Windows. Scratch audio was disabled for the
reference sequence; native audio decoding and playback are verified separately
in the Python suite. Scratch GUI monitors are outside the WebGL stage renderer
and therefore absent from the Scratch reference screenshots.
