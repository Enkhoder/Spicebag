# Spicebag

**Visual Mnemonic Encoder / Decoder** by [E14118](https://github.com/E14118)

Spicebag encodes cryptocurrency wallet seed phrases into color-coded PNG images and decodes them back. Each word in the mnemonic maps to a unique RGB color cell, producing a compact grid image that visually represents the seed — optionally encrypted with a user-provided salt.

---

## Features

- **Encode** a seed phrase into a single PNG image or **bulk-generate** multiple variants into a ZIP archive.
- **Decode** a color-coded PNG back into the original seed phrase, with optional `.txt` export.
- **Salt-based encryption** — an optional passphrase processed through **Argon2id** key derivation adds XOR masking and grid shuffling, making the image unreadable without the salt.
- **Multi-standard support**:

  | Standard | Word Counts | Wordlist Size |
  |----------|-------------|---------------|
  | BIP-39   | 12, 15, 18, 21, 24 | 2048 |
  | Electrum | 12, 24 | 2048 |
  | SLIP-39  | 20, 33 | 1024 |

- **PNG integrity checks** — rejects images with forbidden chunks (e.g. `PLTE`, `tRNS`, `iCCP`) and verifies cell-level monochromatic consistency to detect lossy compression.
- **Checksum validation** on decode ensures the recovered mnemonic is valid before output.

---

## How It Works

1. **Word → Index** — Each seed word is looked up in its standard's wordlist.
2. **XOR Masking** — If a salt is provided, an Argon2id-derived master key is expanded via HKDF into subkeys. A per-word mask is computed and XORed with the word index.
3. **Index → RGB** — The masked index is packed into a 24-bit value, split into R/G/B channels, shifted by a per-word constant, and the channels are permuted.
4. **Grid Layout** — Each color fills a square cell in a grid whose dimensions match the word count (e.g. 3×4 for 12 words, 4×6 for 24 words). When a salt is used, cell positions are deterministically shuffled.
5. **Decoding** reverses all steps: un-permute, un-shift, un-mask, and look up the word by index.

---

## Configuration Space

How many visually distinct images can encode the *same* seed phrase under the *same* salt?

Once the salt is fixed, almost everything is deterministic:

| Component | Source | Free? |
|-----------|--------|-------|
| Cell positions | Grid shuffled by `random.Random(permKey[:8])` | ❌ Fixed — one layout per salt |
| XOR mask | `deriveMask(maskKey, wordPosition, maxIdx)` | ❌ Fixed |
| Channel shift | `RGB_VALUE_SHIFTS[wordPosition]` | ❌ Fixed |
| Channel permutation | Selected by `(R+G+B) % 6` | ❌ Derived |
| **Block offset** | `secrets.randbelow(blockSize)` | ✅ **Free** |

The block offset is the only free variable. It occupies the low bits of the 24-bit value left over after the word
index is packed into the high bits:

```
blockSize = 1 << (24 - (maxIdx.bit_length() - 1))
```

| Standard | Wordlist Size | Block Size | Colors per Word |
|----------|---------------|------------|-----------------|
| BIP-39, Electrum | 2048 | 2¹³ | 8,192 |
| SLIP-39 | 1024 | 2¹⁴ | 16,384 |

Every offset produces a distinct color: the channel shift is a bijective mod-256 addition, and the permutation only
reorders an already-distinct triple. No two offsets collide.

Since each grid holds exactly one cell per word, the total is `blockSize ^ wordCount`:

| Phrase | Entropy | Distinct Images per Salt |
|--------|---------|--------------------------|
| 12-word BIP-39 / Electrum | 156 bits | 9.13 × 10⁴⁶ |
| 15-word BIP-39 | 195 bits | 5.02 × 10⁵⁸ |
| 18-word BIP-39 | 234 bits | 2.76 × 10⁷⁰ |
| 20-word SLIP-39 | 280 bits | 1.94 × 10⁸⁴ |
| 21-word BIP-39 | 273 bits | 1.52 × 10⁸² |
| 24-word BIP-39 / Electrum | 312 bits | 8.34 × 10⁹³ |
| 33-word SLIP-39 | 462 bits | 1.19 × 10¹³⁹ |

Notes:

- **Positions across salts** — the layout dimension only opens up when the salt changes, contributing up to
  `wordCount!` arrangements (4.79 × 10⁸ for 12 words, 6.20 × 10²³ for 24). Within a single salt it collapses to one.
- **Interactive preview** — the clickable color-space editor rejects any color matching an orthogonal neighbour,
  trimming at most 4 of 8,192 candidates per cell. The reduction is under 0.05%.
- **No salt** — the grid is left in natural reading order and all masks are zero, but the per-word color count is
  unchanged.

---

## Valid PNG Requirements

To successfully decode, a PNG must pass all of the following checks:

### Aspect Ratio

The image's width-to-height ratio determines the grid size and expected word count:

| Aspect Ratio (W:H) | Grid (cols × rows) | Word Count | Standard |
|---------------------|---------------------|------------|----------|
| 3:4 | 3 × 4 | 12 | BIP-39, Electrum |
| 3:5 | 3 × 5 | 15 | BIP-39 |
| 1:2 | 3 × 6 | 18 | BIP-39 |
| 4:5 | 4 × 5 | 20 | SLIP-39 |
| 3:7 | 3 × 7 | 21 | BIP-39 |
| 2:3 | 4 × 6 | 24 | BIP-39, Electrum |
| 3:11 | 3 × 11 | 33 | SLIP-39 |

Image dimensions must be evenly divisible by their grid's column and row count (i.e. every cell must be the same whole-pixel size).

### PNG Chunks

| Status | Chunk Types |
|--------|-------------|
| ✅ Allowed | `IHDR`, `IDAT`, `IEND`, `tIME`, `tEXt`, `iTXt`, `zTXt`, `sRGB`, `gAMA`, `pHYs` |
| ❌ Forbidden | `PLTE`, `tRNS`, `bKGD`, `sBIT`, `iCCP` |

Any forbidden chunk causes immediate rejection. This ensures the image uses a direct RGB color model with no palette, transparency, or embedded ICC profile.

### Color Mode

- Must be **RGB** (3 channels) or **RGBA** (4 channels) with alpha fixed at `255`.
- **Bit Depth**: Varying bit depths are acceptable only if they are semantically/exactly identical to standard 8-bit channels upon extraction.
- **Strictly Prohibited**:
  - Custom color models or color profiles (e.g., **Adobe RGB**).
  - **Monochromatic** / Grayscale images.
- All channel values must be integers in the range `0–255`.

### Cell Integrity

Every pixel within a single grid cell must be **exactly the same color**. Any variation (e.g. from JPEG re-compression, anti-aliasing, or screenshot artifacts) will fail validation.

---

## Requirements

- Python 3.10+
- A terminal with 24-bit color support (Windows Terminal, iTerm2, or any modern Linux terminal)

### Dependencies

```
typer
rich
textual
pillow
mnemonic
shamir-mnemonic
argon2-cffi
setuptools
```

---

## Installation

```bash
pip install spicebag
```

This installs the `spicebag` command on your PATH. Run it with no arguments for the TUI, or pass a
subcommand for one-shot use.

### From source

Clone the repository, then let the launcher build the virtual environment for you:

```bat
git clone https://github.com/E14118/Spicebag.git
cd Spicebag
run.bat
```

`run.bat` creates `.venv/`, installs `requirements.txt`, verifies dependencies, and launches the app.

To set it up by hand instead — required on Linux and macOS, where `run.bat` does not apply:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PYTHONPATH=.              # Windows: set PYTHONPATH=.
python spicebag/app/cli.py
```

All imports are absolute (`from spicebag.xxx import yyy`), so `PYTHONPATH` must include the repository
root. For editor integration, copy `.env.example` to `.env`.

---

## Usage

### Interactive TUI

Run with no arguments to open the full-screen interface:

```bash
spicebag            # installed via pip
run.bat             # from a source checkout on Windows
```

Type a command at the prompt:

| Command | Action |
|---------|--------|
| `encode` | Walk through encoding a seed phrase into a PNG, or bulk-generate a ZIP of variants |
| `decode` | Recover a seed phrase from a PNG, with optional `.txt` export |
| `help` | Open the in-app reference |
| `banner` | Toggle the ASCII banner (preference persists across sessions) |
| `clear` | Clear the scrollback |
| `exit` | Quit |

The encode flow prompts in order for word count, phrase, salt, cell size, and save path, then shows
a clickable color-space preview before writing the file.

### Command line

Pass a subcommand to skip the TUI entirely:

```bash
spicebag encode "<phrase>" <path> [--salt <s>] [--cell-px <n>]
spicebag decode <path> [--salt <s>]
```

From a source checkout, substitute `run.bat` for `spicebag`.

| Option | Default | Applies to | Meaning |
|--------|---------|------------|---------|
| `--salt` | *(empty)* | both | Passphrase for Argon2id key derivation |
| `--cell-px` | `100` | encode | Pixel width of each square color cell |

Try it against the sample images in
[`examples/`](https://github.com/E14118/Spicebag/tree/main/examples):

```bash
spicebag decode examples/images/12-seedless.png
spicebag decode examples/images/12-seed-Z3wjBTmDso1eLQ.png --salt Z3wjBTmDso1eLQ
```

### Output location

Images, ZIP archives, screenshots, and the banner preference file are written to `~/Spicebag/`.

---

## Security Considerations

> [!CAUTION]
> Spicebag provides **no protection** against malware, keyloggers, screen capture, coercion, or any form of surveillance. Use it only in a secure, private environment.

- **Salt** is processed with **Argon2id** (`time_cost`=4, `memory_cost`=256 MB) making brute-force infeasible.
- All randomness for color offsets uses Python's `secrets` module (CSPRNG).
- The salt is **not stored** anywhere — losing it means the image cannot be decoded.

---

## Performance & Bulk Generation

- **Algorithmic Separation**: Bulk image generation (`bulkEncodeMnemonic`) decouples the color space calculations from the resolution upscaling. This minimizes memory overhead during logic generation.
- **Strictly Unique Colors**: Offsets for cells are sampled without replacement using `random.sample` (out of the 8192 available colors for BIP-39) to mathematically guarantee that all bulk-generated images use unique cell colors.
- **Optimized PNG Encoding**: High-resolution cell scaling (e.g. 2000px per cell) processes massive amounts of pixel data. The bulk encoder uses a fast compression level (`compress_level=1`) to yield a ~43% execution speedup, dropping bulk generation times significantly.

---

## License

This project is licensed under the
[MIT License](https://github.com/E14118/Spicebag/blob/main/LICENSE).