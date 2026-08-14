# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bat
run.bat                          # launch TUI (creates/activates .venv automatically)
run.bat encode "<phrase>" <path> [--salt <s>] [--cell-px <n>]
run.bat decode <path> [--salt <s>]
```

Option names in `cli.py` are pinned explicitly (`typer.Option(100, "--cell-px", ...)`). Do not rely on Typer's implicit derivation from the parameter identifier: it lowercased `cellPx` to `--cellpx` in Typer 0.25 and preserves it as `--cellPx` in 0.27, so an unpinned camelCase parameter produces a different flag depending on which version the user installed.

For development without `run.bat`, set `PYTHONPATH=.` first — all imports use `from spicebag.xxx import yyy` (no relative imports):

```powershell
$env:PYTHONPATH = "."
python spicebag/app/cli.py
```

Install dependencies into the venv: `pip install -r requirements.txt` (Python 3.10+). Alternatively `pip install -e .` installs the package from `pyproject.toml` and puts the `spicebag` console script on PATH, which removes the need for `PYTHONPATH`.

There are no tests in this project. `pyrightconfig.json` points Pyright at `.venv`; there is no linter or formatter configuration.

## Architecture

The codebase has five layers that call downward:

**CLI → TUI → Handlers → Core → Utils/Constants**

### CLI (`spicebag/app/cli.py`)
Typer app with `encode` and `decode` subcommands. When invoked with no subcommand it launches the Textual TUI directly. `pyproject.toml` exposes it as the `spicebag` console script via `[project.scripts]`.

### TUI (`spicebag/app/tui.py`, `spicebag/app/screens/`)
`SpicebagApp` (Textual `App`) opens a `WarningScreen` on mount, then navigates to `MainScreen`. `MainScreen` is a state machine (`AppState` enum from `spicebag/constants/theme.py`) with states like `IDLE → ENCODE_COUNT → ENCODE_WORD_COUNT → ENCODE_PHRASE → ENCODE_SALT → ENCODE_CELL → ENCODE_SAVE_PATH → ENCODE_CONFIRM`. Encode/decode logic is injected via mixins: `EncodeHandlerMixin` and `DecodeHandlerMixin` (in `spicebag/app/handlers/`). The screen rebuilds its `RichLog` history on every terminal resize.

### Core (`spicebag/core/`)
- `generator.py` — `identifySeedType()` validates the mnemonic against all three wordlists and returns `(indices, standard, wordCount, maxIdx)`. `encodeMnemonic()` builds a 1-pixel-per-cell image then scales it. `bulkEncodeMnemonic()` decouples color computation from upscaling and writes results into a ZIP.
- `decoder.py` — `validateImage()` checks PNG chunks (no `PLTE`, `tRNS`, etc.) and verifies every pixel within a cell is identical. `decodeImage()` then reverses the encoding to recover word indices, and `resolveMnemonic()` walks `SEED_TYPE_STANDARDS` in declaration order, returning the first phrase that passes its own checksum. `getGridDimensions()` recovers `(cols, rows, wordCount, maxIdx)` from the aspect ratio by scanning `GRID_SIZES` with a cross-multiplied integer comparison.

### Encoding algorithm (`spicebag/utils/colors.py`)
Each word index is transformed to an RGB color through four reversible steps:
1. **XOR mask** — `deriveMask(maskKey, wordPosition, maxIdx)` via HMAC-SHA512; skipped if no salt.
2. **Block offset** — `maskedIndex * blockSize + offset` packs the index into the upper bits of a 24-bit number and randomizes the lower bits. The offset is the only free variable in the whole encoding, so it must always come from `secrets.SystemRandom()` — never from the salt-seeded `random.Random`, which would make every encode of a given phrase+salt byte-identical. Decoding discards the offset (`index = value // blockSize`), so it is never reproduced.
3. **Channel shift** — per-position `(ΔR, ΔG, ΔB)` tuples from `RGB_VALUE_SHIFTS` in `spicebag/constants/defaults.py`.
4. **Channel permutation** — one of 6 fixed permutations selected by `(R+G+B) % 6`.

`deriveMasterKey()` uses Argon2id (`time_cost=4`, `memory_cost=256 MB`) on the salt, then `deriveSubkeys()` expands it via HKDF-SHA512 into three 128-byte keys (`maskKey`, `permKey`, `offsetKey`). `permKey[:8]` seeds a `random.Random` used for one purpose only: deterministic grid-cell position shuffling, which `decoder.py` mirrors to un-shuffle. `offsetKey` is currently unused.

### Constants (`spicebag/constants/`)
- `defaults.py` — wordlists (BIP39 via `mnemonic`, Electrum from bundled `.txt`, SLIP39 via `shamir-mnemonic`), validators, `SEED_TYPE_STANDARDS`, `WORD_COUNT_MAX_INDEX`, `FORBIDDEN_CHUNKS`, `RGB_VALUE_SHIFTS`, `PERMUTATIONS`.
- `theme.py` — `AppState` enum, `OUTPUT_DIR` (`~/Spicebag/`), `GRID_SIZES`, color palette constants, banner ASCII art.

Three tables are single-sourced and must stay that way, because every consumer derives from them rather than restating them:

- `SEED_TYPE_STANDARDS` — `(name, wordCounts, wordList, maxIdx, validator)` per standard. Both `generator.identifySeedType()` and `decoder.resolveMnemonic()` iterate it, so adding a standard needs no edit in either. Every validator is a real checksum function, including `validateSLIP39` — none is a stub, so neither call site special-cases a standard by name. The `name` field is also the label shown in the UI on both the encode confirm screen and the decode result, which is why it is `"Electrum"` and not `"ELECTRUM"`.
- `WORD_COUNT_MAX_INDEX` — derived from `SEED_TYPE_STANDARDS`, never written by hand.
- `GRID_SIZES` — word count to `(cols, rows)`, the single source for grid geometry in `generator.py`, `decoder.py`, and the TUI. Word counts do not overlap between standards (SLIP-39 owns 20 and 33; BIP-39/Electrum own 12, 15, 18, 21, 24), so keying on word count alone is unambiguous, and every ratio `cols/rows` is distinct, so the decoder's reverse lookup can never match two entries.

### Output location
All generated images and screenshots go to `~/Spicebag/` (`Path.home() / "Spicebag"`). A `bannerConfig` JSON file is persisted there to remember the user's banner preference across sessions.