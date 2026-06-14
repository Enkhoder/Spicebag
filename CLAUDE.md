# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bat
run.bat                          # launch TUI (creates/activates .venv automatically)
run.bat encode "<phrase>" <path> [--salt <s>] [--cell-px <n>]
run.bat decode <path> [--salt <s>]
```

For development without `run.bat`, set `PYTHONPATH=.` first — all imports use `from src.xxx import yyy` (no relative imports):

```powershell
$env:PYTHONPATH = "."
python src/app/cli.py
```

Install dependencies into the venv: `pip install -r requirements.txt` (Python 3.10+).

There are no tests and no linter configuration in this project.

## Architecture

The codebase has four layers that call downward:

**CLI → TUI → Handlers → Core → Utils/Constants**

### CLI (`src/app/cli.py`)
Typer app with `encode` and `decode` subcommands. When invoked with no subcommand it launches the Textual TUI directly.

### TUI (`src/app/tui.py`, `src/app/screens/`)
`SpicebagApp` (Textual `App`) opens a `WarningScreen` on mount, then navigates to `MainScreen`. `MainScreen` is a state machine (`AppState` enum from `src/constants/theme.py`) with states like `IDLE → ENCODE_COUNT → ENCODE_WORD_COUNT → ENCODE_PHRASE → ENCODE_SALT → ENCODE_CELL → ENCODE_SAVE_PATH → ENCODE_CONFIRM`. Encode/decode logic is injected via mixins: `EncodeHandlerMixin` and `DecodeHandlerMixin` (in `src/app/handlers/`). The screen rebuilds its `RichLog` history on every terminal resize.

### Core (`src/core/`)
- `generator.py` — `identifySeedType()` validates the mnemonic against all three wordlists and returns `(indices, standard, numWords, maxIdx)`. `encodeMnemonic()` builds a 1-pixel-per-cell image then scales it. `bulkEncodeMnemonic()` decouples color computation from upscaling and writes results into a ZIP.
- `decoder.py` — `validateImage()` checks PNG chunks (no `PLTE`, `tRNS`, etc.) and verifies every pixel within a cell is identical. `decodeImage()` then reverses the encoding to recover word indices, tries BIP39/Electrum/SLIP39 validators in order, and returns the first valid mnemonic.

### Encoding algorithm (`src/utils/colors.py`)
Each word index is transformed to an RGB color through four reversible steps:
1. **XOR mask** — `deriveMask(maskKey, wordPosition, maxIdx)` via HMAC-SHA512; skipped if no salt.
2. **Block offset** — `maskedIndex * blockSize + offset` packs the index into the upper bits of a 24-bit number and randomizes the lower bits.
3. **Channel shift** — per-position `(ΔR, ΔG, ΔB)` tuples from `RGB_VALUE_SHIFTS` in `src/constants/defaults.py`.
4. **Channel permutation** — one of 6 fixed permutations selected by `(R+G+B) % 6`.

`deriveMasterKey()` uses Argon2id (`time_cost=4`, `memory_cost=256 MB`) on the salt, then `deriveSubkeys()` expands it via HKDF-SHA512 into three 128-byte keys (`maskKey`, `permKey`, `offsetKey`). `permKey[:8]` seeds a `random.Random` for deterministic grid-cell position shuffling.

### Constants (`src/constants/`)
- `defaults.py` — wordlists (BIP39 via `mnemonic`, Electrum from bundled `.txt`, SLIP39 via `shamir-mnemonic`), validators, `FORBIDDEN_CHUNKS`, `RGB_VALUE_SHIFTS`, `PERMUTATIONS`.
- `theme.py` — `AppState` enum, `OUTPUT_DIR` (`~/Spicebag/`), grid size mapping, color palette constants, banner ASCII art.

### Output location
All generated images and screenshots go to `~/Spicebag/` (`Path.home() / "Spicebag"`). A `bannerConfig` JSON file is persisted there to remember the user's banner preference across sessions.
