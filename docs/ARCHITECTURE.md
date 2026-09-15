# Architecture

How Spicebag is put together, for anyone modifying it. The [README](../README.md) covers what the encoding does and why the numbers are what they are; this document covers where the code lives and which parts you can break without noticing.

---

## Layers

Five layers, each calling only downward:

```
CLI  →  TUI  →  Handlers  →  Core  →  Utils / Constants
```

```
spicebag/
├── app/
│   ├── cli.py              Typer entry point
│   ├── tui.py              SpicebagApp, the Textual application root
│   ├── tui.tcss            stylesheet (shipped as package data)
│   ├── tree.py             tree rendering primitives, emits styled Text lines
│   ├── screens/
│   │   ├── warning.py      WarningScreen, the 4-key security confirmation
│   │   ├── main.py         MainScreen, the state machine
│   │   └── help.py         HelpScreen, the in-app reference
│   ├── handlers/
│   │   ├── encode.py       EncodeHandlerMixin
│   │   ├── decode.py       DecodeHandlerMixin
│   │   ├── savePath.py     path parsing and filename validation
│   │   └── screenshot.py   SVG export with secret masking
│   └── widgets/
│       ├── secureInput.py  Input with clipboard and key-repeat disabled
│       └── optionsBar.py   status bar
├── core/
│   ├── generator.py        encode, bulk encode, interactive ColorSpace
│   └── decoder.py          PNG validation, decode
├── utils/
│   ├── colors.py           key derivation and the color transform
│   ├── networkDetect.py    per-OS connection state, packet-free
│   ├── terminalColors.py   live terminal palette probe, per-OS
│   └── dependencyCheck.py  requirements.txt check for the run.bat path
└── constants/
    ├── defaults.py         wordlists, standards, forbidden PNG chunks, Feistel rounds
    └── theme.py            AppState, palette, grid sizes, banner art
```

### CLI (`app/cli.py`)

Typer app whose callback launches the TUI, alongside two eager flags: `--version` / `-V` prints the installed package version, and `--help` / `-h` prints the usage text. Both exit before the interface starts. `pyproject.toml` exposes the app as the `spicebag` console script through `[project.scripts]`.

The `version` parameter on the callback is never read in its body. Typer registers the flag from the signature and the eager callback does the work, so it looks unused to a linter and must stay. The same applies to `ctx` in `SpicebagGroup.get_help`, which the Click signature requires.

**The help output is hand-written.** `SpicebagGroup.get_help` returns the `HELP_TEXT` constant verbatim in place of the table Typer would assemble, so Typer never sees the flag list. It is returned as a plain string rather than rendered through Rich, which keeps the literal spacing at any terminal width and leaves the bracketed metavariable alone instead of parsing it as markup. Adding or renaming a flag means editing `HELP_TEXT` by hand, or it will not appear in `--help`. Click still owns the help option itself.

**Unknown input never reaches Click's error path.** `SpicebagGroup.parse_args` checks every argument against the registered flag spellings before Click parses anything, and stops at the first one that matches none of them. A token starting with `-` is reported as `No such option`, anything else as `No such command`, followed by the two help invocations, on stderr with exit status 2. Whole tokens are compared on purpose: `-Vx` and `--version=1` are echoed exactly as typed, and a stray word after `-h` is an error rather than silently ignored.

**No subcommand may accept a seed phrase or a salt.** An argument passed on the command line is recorded in the shell history file and is readable from the process list by any other process on the machine, and the tool cannot retract either one afterwards. `encode` and `decode` subcommands existed through v1.0.0 and were removed for this reason. Adding a subcommand that takes secret material reintroduces the leak, so encoding and decoding stay behind the interactive interface.

### TUI (`app/tui.py`, `app/screens/`)

`SpicebagApp` pushes `WarningScreen` on mount, which switches to `MainScreen` after four correct keypresses.

`MainScreen` is a state machine driven by the `AppState` enum in `constants/theme.py`:

```
IDLE → ENCODE_COUNT → ENCODE_WORD_COUNT → ENCODE_PHRASE → ENCODE_SALT
     → ENCODE_CELL → ENCODE_SAVE_PATH → ENCODE_CONFIRM
```

Encode and decode behavior is injected as mixins (`EncodeHandlerMixin` and `DecodeHandlerMixin`), so `MainScreen` holds the state and the handlers hold the flows. Each handler is a `_handleX(self, value: str)` method dispatched from `on_input_submitted`. Two of them ignore `value` (`_handleEncodeConfirm`, `_handleDecodeConfirm`); the parameter stays for a uniform dispatch signature.

The screen rebuilds its entire `RichLog` history on every terminal resize.

### Core (`core/`)

`generator.py`

- `identifySeedType()`: validates a phrase against every standard admitting its word count, returns `(indices, standard, wordCount, maxIdx)`.
- `encodeMnemonic()`: builds a one-pixel-per-cell image, then scales it with `NEAREST`.
- `bulkEncodeMnemonic()`: decouples color computation from upscaling and writes into a ZIP. Offsets are drawn without replacement so every image in a batch is distinct.
- `precomputeColorSpace()` / `rerollCell()` / `renderColorSpaceToFile()`: the interactive preview. Single-image encodes from the TUI go through this path, not through `encodeMnemonic`.

`decoder.py`

- `validatePNGStructure()`: walks the chunk stream and rejects any forbidden chunk. This is a **blocklist**, not an allowlist: anything not in `FORBIDDEN_CHUNKS` passes.
- `validateImage()`: derives the grid from the aspect ratio and verifies every pixel inside each cell is identical.
- `getGridDimensions()`: recovers `(cols, rows, wordCount, maxIdx)` from the image dimensions by scanning `GRID_SIZES` with a cross-multiplied integer comparison, so the ratio test stays exact.
- `resolveMnemonic()`: walks `SEED_TYPE_STANDARDS` in declaration order and returns the first phrase that passes its own checksum.

### Utils (`utils/`)

`colors.py` holds the key derivation and the color transform (below).

`networkDetect.py` reports `(isEthernet, isWifi, isBluetooth)` and is **deliberately packet-free**: it never opens a socket, because the app is meant to run air-gapped. Detection is per-OS and local: Windows uses `GetAdaptersAddresses` + `GetIfEntry2` and `Bthprops.cpl`; Linux reads `/sys/class/net` and `/sys/class/rfkill`; macOS reads the Bluetooth plist and shells out to `networksetup`/`ifconfig`. `MainScreen` polls it on a daemon thread (blocking on `NotifyAddrChange` on Windows, on a 2-second sleep elsewhere) to keep the connection indicator live. The macOS path is untested on real hardware.

`terminalColors.py` resolves the terminal's real palette, so an exported screenshot matches what was on screen. It queries OSC 11, OSC 10 and OSC 4 for the background, the foreground and the sixteen ANSI slots, reading the replies in raw mode under a short deadline. Two details are load-bearing: the probe runs from `cli.py` **before** the app starts, because Textual owns stdin once it does; and the reader counts terminated replies, then drains whatever is left, because a reply cut mid-sequence leaks its tail into the first keypress the app sees. A terminal that does not answer falls back to the `HKCU\Console` color table on Windows, then to a fixed dark theme identical to Textual's `MONOKAI`, so a silent terminal reproduces the pre-2.0.0 output exactly. The POSIX reader is untested on real hardware.

`dependencyCheck.py` is only meaningful on the source checkout; it no-ops when `requirements.txt` is absent, which is the case for an installed package.

---

## The color transform

Each word index becomes one RGB triple through two reversible steps, in `utils/colors.py`:

1. **Block offset**: `wordIndex * blockSize + offset` packs the index into the high bits of a 24-bit value and fills the low bits with randomness.
2. **Color permutation**: with a salt, `permuteColor()` runs the value through a 10-round balanced Feistel network over its two 12-bit halves, keyed by the salt. Without a salt this step is skipped.

Without a salt the 24-bit value is the color itself, split into R, G and B, so word index `n` always lands in `[n * blockSize, (n + 1) * blockSize)` and a cell can be read back by hand from its hex code. Keep it that way: the unsalted path must never gain a transform after step 1, or manual decoding of unsalted images breaks.

With a salt, the permutation scatters each word's `blockSize` colors pseudo-randomly across all 16,777,216, so a salted cell's hex code says nothing about its word and a reroll can land on any hue. The permutation is a bijection over the whole color space, so no color ever belongs to two words. The set depends only on the word and the salt, never on the cell: a repeated word reuses one set wherever it appears, and the cell shuffle is what hides word positions.

Every step is a bijection, so `offset → color` is injective: 8,192 distinct colors per word for BIP39 and Electrum, 16,384 for SLIP39, with no collisions. Several things depend on that property, including the termination guarantee for the `while` loop in `rerollCell()`.

### Key derivation

`deriveMasterKey()` runs Argon2id (`time_cost=4`, `memory_cost=256 MB`) over the salt. `deriveSubkeys()` expands the result via HKDF-SHA512 into two 128-byte keys:

| Key | Used for |
|-----|----------|
| `colorKey` | `deriveColorTables()` turns it into the Feistel round tables, which `deriveSubkeys()` returns in its place |
| `permKey` | `permKey[:8]` seeds a `random.Random` that shuffles grid-cell positions |

Each Feistel round function is the first 12 bits of HMAC-SHA256 over the round number and a 12-bit half. A half has only 4,096 possible values, so every round output is precomputed once per salt into a 4,096-entry table, and a permutation costs ten lookups instead of ten HMACs. That keeps a 2,000-image salted bulk encode within a few seconds.

The cell shuffle is the **only** consumer of the seeded RNG, and `decoder.py` mirrors it exactly to un-shuffle. It must stay deterministic.

---

## Invariants

Things that look like cleanup opportunities and are not.

### Block offsets must come from `secrets.SystemRandom()`

The offset is the encoding's only free variable: the index and the color permutation are both fixed once the phrase and salt are chosen. Deriving the offset from the salt in any form collapses every encode of a given phrase and salt to one byte-identical image, which turns file equality into proof that two images share a phrase *and* a salt.

There is deliberately **no third subkey** for offsets. An `offsetKey` used to exist and was never wired up; it was removed rather than left as an invitation to reintroduce the bug.

Decoding undoes the permutation when salted and then discards the offset (`index = value // blockSize`), so the offset is never reproduced and never needs to be.

### The salted color permutation is part of the file format

`FEISTEL_ROUNDS`, the HMAC-SHA256 round function, the 12-bit split and the `colorDomain` HKDF label together define where every salted color lands. Changing any of them, even to speed things up, silently makes every existing salted image undecodable.

### Three tables are single-sourced

Every consumer derives from these rather than restating them. Adding a standard or a word count should require exactly one edit.

- **`SEED_TYPE_STANDARDS`**: `(name, wordCounts, wordList, maxIdx, validator)`. Both `generator.identifySeedType()` and `decoder.resolveMnemonic()` iterate it. Every validator is a real checksum function, `validateSLIP39` included, so neither call site special-cases a standard by name. The `name` field is also the label shown in the UI on the encode confirm screen and the decode result, which is why it reads `"Electrum"` and not `"ELECTRUM"`.
- **`WORD_COUNT_MAX_INDEX`**: derived from `SEED_TYPE_STANDARDS`. Never write it by hand.
- **`GRID_SIZES`**: word count to `(cols, rows)`, the single source of grid geometry for `generator.py`, `decoder.py` and the TUI. Word counts do not overlap between standards (SLIP39 owns 20 and 33; BIP39 and Electrum own 12, 15, 18, 21, 24), so keying on word count alone is unambiguous. Every `cols/rows` ratio is distinct, so the decoder's reverse lookup can never match two entries. Preserve that when adding a size.

### `ELECTRUM_LIST` is an alias, not a table

Electrum's English wordlist *is* the BIP39 English wordlist (the same 2048 words in the same order), so the word-to-index mapping is identical and the two standards are separated only by their checksum validators. A bundled `electrum-english.txt` used to sit in `constants/`; it was byte-identical to the `english.txt` inside the `mnemonic` package, so it pinned nothing that BIP39 decoding was not already depending on.

If Electrum ever forks its English list, give `ELECTRUM_LIST` its own sorted 2048-word source. `binarySearchWord` uses `bisect` and requires sorted input.

### Secrets never reach the log

The seed phrase and the salt are never echoed into the `RichLog` history. Both confirm their entry with `_addDashbar(C_INP)` instead of `_addAnswer(value)`, which is reserved for the word count, cell size and fixed strings. The status bar only reports whether a salt is present, never its value.

Screenshot export (`handlers/screenshot.py`) blanks the input, masks the sample grid and any decoded words, takes the capture, and restores everything in a `finally`. `cleanSvg()` then strips `<title>`, `<desc>`, `<metadata>` and comments from the SVG.

The capture goes through the local `exportScreenshot()` rather than Textual's `App.export_screenshot`, which hardcodes the export theme. Passing the probed terminal palette through to `export_svg` is what lets the frame and the body carry the real terminal background instead of Rich's fixed `#292929`, so `cleanSvg()` recolors from that palette rather than guessing at it. See `utils/terminalColors.py`.

`InvalidSeedWordsError` masks offending words as `·` characters, so word *lengths* leak but the words do not. This only applies to words absent from every wordlist: typos, not seed words.

The same rule covers the process boundary: no secret may arrive as a command-line argument. See [CLI](#cli-appclipy): the shell history file and the process list are outside the tool's control, which is why no subcommand accepts a phrase or a salt.

### `ASCII_ART_BANNER` has load-bearing trailing spaces

All 15 lines are padded to exactly 74 characters, including the blank first and last rows which are 74 spaces rather than empty. Stripping trailing whitespace there breaks the banner alignment.

---

## Output location

Everything the app writes goes to `~/Spicebag/` (`Path.home() / "Spicebag"`): generated PNGs, ZIP archives, and `app-screenshots/`. A `bannerConfig` JSON file is persisted there to remember the banner preference between sessions.

---

## Development

All imports are absolute (`from spicebag.xxx import yyy`), with no relative imports, so the repository root must be importable:

```bash
pip install -r requirements.txt
export PYTHONPATH=.              # Windows: set PYTHONPATH=.
python spicebag/app/cli.py
```

Or skip the variable entirely:

```bash
pip install -e .
spicebag
```

On Windows, `run.bat` handles the venv, the dependency check and `PYTHONPATH` for you.

`tests/smoke.py` is the only test. It decodes every fixture in `examples/images/`, confirms the four deliberately invalid ones still fail, round-trips each recovered phrase through `encodeMnemonic` and `bulkEncodeMnemonic` salted and unsalted, and asserts that three encodes of the same phrase and salt produce three different files. Run it from the repository root:

```bash
python tests/smoke.py
```

CI runs it on every push to `main` and every pull request against it, across Ubuntu (3.10, 3.13), Windows (3.12) and macOS (3.12), then builds the artifacts and rejects any wheel containing files that must never ship. Releases publish to PyPI from a `v*` tag via Trusted Publishing; see `.github/workflows/`.

There is no linter or formatter configuration. The house style is 128-character lines, `camelCase` functions and variables, `PascalCase` classes, `ALL_CAPS` constants, and `######## CLUSTER TITLE ########` section headers with three blank lines before and one after. Identifiers that come from Textual, Rich or the Win32 API keep their original casing (`on_mount`, `render_line`, `MIB_IF_ROW2`) and must not be renamed to fit the convention.