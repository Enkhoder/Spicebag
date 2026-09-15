<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Spicebag">
</p>

<p align="center"><strong>Visual Mnemonic Encoder / Decoder</strong></p>

<p align="center">
  <a href="https://github.com/Enkhoder/Spicebag/stargazers"><img src="https://img.shields.io/github/stars/Enkhoder/Spicebag?style=for-the-badge&logo=github&logoColor=white&label=Stars&color=ECD251" alt="Stars"></a>
  <a href="https://github.com/Enkhoder/Spicebag/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Enkhoder/Spicebag/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI" alt="CI"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-88A4E9?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/.github/workflows/ci.yml"><img src="https://img.shields.io/badge/OS-Windows%20%7C%20macOS%20%7C%20Linux-D787EF?style=for-the-badge" alt="OS"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enkhoder/Spicebag?style=for-the-badge&color=909090" alt="License"></a>
</p>

<p align="center">
  <a href="https://www.producthunt.com/products/spicebag?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-spicebag" target="_blank" rel="noopener noreferrer"><img alt="Spicebag - Compress crypto seed phrases into secure visual artifacts. | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1246937&amp;theme=light&amp;t=1789065380333"></a>
</p>

**Spicebag** encodes cryptocurrency wallet seed phrases into color-coded PNG images and decodes them back. Each word in the mnemonic maps to a unique RGB color cell, producing a compact grid image that visually represents the seed, and can be optionally encrypted with a user-provided salt.

---

## Features

- **Encode** a seed phrase into a single PNG image or **bulk-generate** multiple variants into a ZIP archive.
- **Decode** a color-coded PNG back into the original seed phrase.
- **Salt-based encryption**: an optional passphrase processed through **Argon2id** key derivation scatters each word's colors across the whole color space and shuffles the grid, making the image unreadable without the salt.
- **Multi-standard support**:

  | Standard | Word Counts | Wordlist Size |
  |----------|-------------|---------------|
  | BIP39   | 12, 15, 18, 21, 24 | 2048 |
  | Electrum | 12, 24 | 2048 |
  | SLIP39  | 20, 33 | 1024 |

- **PNG integrity checks**: rejects images with forbidden chunks (e.g. `PLTE`, `tRNS`, `iCCP`) and verifies cell-level monochromatic consistency to detect lossy compression.
- **Checksum validation** on decode ensures the recovered mnemonic is valid before output.

---

## How It Works

1. **Word → Index**: Each seed word is looked up in its standard's wordlist.
2. **Salt Keys**: If a salt is provided, an Argon2id-derived master key is expanded via HKDF into a color key and a grid-shuffle key.
3. **Index → RGB**: The word index fills the high bits of a 24-bit value and a random block offset fills the low bits. Without a salt, that value, split into R/G/B channels, is the cell's color. With a salt, a salt-keyed permutation first scatters it across the whole color space.
4. **Grid Layout**: Each color fills a square cell in a grid whose dimensions match the word count (e.g. 3×4 for 12 words, 4×6 for 24 words). When a salt is used, cell positions are deterministically shuffled.
5. **Decoding**: reverses all steps: undo the permutation, drop the offset, and look up the word by index.

---

## Manual Decoding

An image encoded without a salt can be decoded by hand, with nothing but a color picker and the wordlist. Manually decoding salted images is impossible.

### 1. Find the wordlist

Match the image's width-to-height ratio against the [Aspect Ratio](#aspect-ratio) table to get the grid and word count. The word count decides the wordlist:

| Word Count | Wordlist | Colors per Word |
|------------|----------|-----------------|
| 12, 15, 18, 21, 24 | [BIP39 English](https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt), 2048 words, shared by Electrum | 8,192 |
| 20, 33 | [SLIP39](https://github.com/satoshilabs/slips/blob/master/slip-0039/wordlist.txt), 1024 words | 16,384 |

### 2. Read the cells in order

Words run left-to-right first, top-to-bottom, the same way you read most texts. Write down the hex code of each cell from the PNG file itself.

### 3. Turn each hex code into a word

The 16,777,216 colors from `#000000` to `#FFFFFF` are split in order into equal chunks, one per word. The first word of the list owns the first chunk, the second word the next one, and so on:

| Word Number | BIP39 / Electrum Chunk | SLIP39 Chunk |
|-------------|-------------------------|---------------|
| 1 | `#000000` to `#001FFF` (abandon) | `#000000` to `#003FFF` (academic) |
| 2 | `#002000` to `#003FFF` (ability) | `#004000` to `#007FFF` (acid) |
| 3 | `#004000` to `#005FFF` (able) | `#008000` to `#00BFFF` (acne) |
| Last | `#FFE000` to `#FFFFFF` (zoo, 2048) | `#FFC000` to `#FFFFFF` (zero, 1024) |

Only red and green decide the word. Convert both to decimal (0 to 255), then:

| Standard | Word Number |
|----------|-------------|
| BIP39, Electrum | `R × 8 + ⌊G ÷ 32⌋ + 1` |
| SLIP39 | `R × 4 + ⌊G ÷ 64⌋ + 1` |

`⌊ ⌋` = rounded down. Blue is random filler and never changes the word. The word number is the line number in the wordlist file.

For example, a cell colored `#65DFCD` in a 24-word image has R = `0x65` = 101 and G = `0xDF` = 223. That gives 101 × 8 + ⌊223 ÷ 32⌋ + 1 = 808 + 6 + 1 = **815**, and line 815 of the BIP39 list is **grape**.

If a calculator is closer to hand, convert the whole hex code to decimal instead, divide by the colors per word from step 1, drop the remainder, and add 1: `0x65DFCD` = 6,676,429, and ⌊6,676,429 ÷ 8,192⌋ + 1 = 815.

### 4. Check the phrase

The last word carries the phrase's checksum, so a misread cell almost always produces a phrase that fails validation.

---

## Configuration Space

How many visually distinct images can encode the *same* seed phrase under the *same* salt?

Once the salt is fixed, almost everything is deterministic:

| Component | Source | Free? |
|-----------|--------|-------|
| Cell positions | Grid shuffled by `random.Random(permKey[:8])` | ❌ Fixed, one layout per salt |
| Color permutation | 10-round Feistel network keyed by the salt | ❌ Fixed |
| **Block offset** | `secrets.SystemRandom().randrange(blockSize)` | ✅ **Free** |

The block offset is the only free variable. It occupies the low bits of the 24-bit value left over after the word index is packed into the high bits:

```
blockSize = 1 << (24 - (maxIdx.bit_length() - 1))
```

| Standard | Wordlist Size | Block Size | Colors per Word |
|----------|---------------|------------|-----------------|
| BIP39, Electrum | 2048 | 2¹³ | 8,192 |
| SLIP39 | 1024 | 2¹⁴ | 16,384 |

Every offset produces a distinct color: the offset is written straight into the low bits of the 24-bit value, so no two offsets collide.

Since each grid holds exactly one cell per word, the total is `blockSize ^ wordCount`:

| Phrase | Entropy | Distinct Images per Salt |
|--------|---------|--------------------------|
| 12-word BIP39 / Electrum | 156 bits | 9.13 × 10⁴⁶ |
| 15-word BIP39 | 195 bits | 5.02 × 10⁵⁸ |
| 18-word BIP39 | 234 bits | 2.76 × 10⁷⁰ |
| 20-word SLIP39 | 280 bits | 1.94 × 10⁸⁴ |
| 21-word BIP39 | 273 bits | 1.52 × 10⁸² |
| 24-word BIP39 / Electrum | 312 bits | 8.34 × 10⁹³ |
| 33-word SLIP39 | 462 bits | 1.19 × 10¹³⁹ |

Notes:

- **Positions across salts**: the layout dimension only opens up when the salt changes, contributing up to `wordCount!` arrangements (4.79 × 10⁸ for 12 words, 6.20 × 10²³ for 24). Within a single salt it collapses to one.
- **Interactive preview**: the clickable color-space editor rejects any color matching the cell's current color or an orthogonal neighbor, trimming at most 5 of 8,192 candidates per cell. The reduction is under 0.07%.
- **No salt**: the grid is left in natural reading order and no color permutation is applied, but the per-word color count is unchanged.

---

## Valid PNG Requirements

To successfully decode, a PNG must pass all of the following checks:

### Aspect Ratio

The image's width-to-height ratio determines the grid size and expected word count:

| Aspect Ratio (W:H) | Grid (cols × rows) | Word Count | Standard |
|---------------------|---------------------|------------|----------|
| 3:4 | 3 × 4 | 12 | BIP39, Electrum |
| 3:5 | 3 × 5 | 15 | BIP39 |
| 1:2 | 3 × 6 | 18 | BIP39 |
| 4:5 | 4 × 5 | 20 | SLIP39 |
| 3:7 | 3 × 7 | 21 | BIP39 |
| 2:3 | 4 × 6 | 24 | BIP39, Electrum |
| 3:11 | 3 × 11 | 33 | SLIP39 |

Image dimensions must be evenly divisible by their grid's column and row count (i.e. every cell must be the same whole-pixel size).

### PNG Chunks

| Status | Chunk Types |
|--------|-------------|
| ❌ Forbidden | `PLTE`, `tRNS`, `bKGD`, `sBIT`, `iCCP` |
| ✅ Allowed | Everything else, including `IHDR`, `IDAT`, `IEND`, `tIME`, `tEXt`, `iTXt`, `zTXt`, `sRGB`, `gAMA`, `pHYs` |

Validation is a blocklist, not an allowlist: any forbidden chunk causes immediate rejection, and every other chunk type passes. This ensures the image uses a direct RGB color model with no palette, transparency, or embedded ICC profile.

### Color Mode

- Must be **RGB** (3 channels) or **RGBA** (4 channels) with alpha fixed at `255`.
- **Bit Depth**: Varying bit depths are acceptable only if they are semantically/exactly identical to standard 8-bit channels upon extraction.
- **Strictly Prohibited**:
  - Custom color models or color profiles (e.g., **Adobe RGB**).
  - **Monochromatic** / Grayscale images.
- All channel values must be integers from `0` to `255`.

### Cell Integrity

Every pixel within a single grid cell must be **exactly the same color**. Any variation (e.g. from JPEG re-compression, anti-aliasing, or screenshot artifacts) will fail validation.

---

## Requirements

- Python 3.10+
- A terminal with 24-bit color support. See [Terminal](#terminal)

### Terminal

Spicebag draws a full-screen interface and leans on four terminal capabilities. Each one degrades on its own, so a terminal missing some of them still runs the app:

| Capability | Used for | Without it |
|---|---|---|
| 24-bit color | Color-space grids, seed cells, gradients | Colors quantize to 256 and distinct cells can look identical |
| Mouse reporting | Clicking a sample cell to reroll it, hover states | Unreachable; keyboard still works |
| OSC 8 hyperlinks | Ctrl/Cmd-clicking a saved PNG or ZIP to open it | Filenames print as plain text; browse to `~/Spicebag` |
| OSC 10/11/4 queries | Screenshots that match your real terminal colors | Screenshots fall back to a fixed dark palette |

Every terminal below covers all four. The versions listed are where the full set is reliably present, not the oldest build that runs the app at all.

| OS | Terminal | Minimum |
|---|---|---|
| Windows | Windows Terminal | 1.18 |
| macOS | Ghostty | 1.0 |
| macOS | iTerm2 | 3.4 |
| Linux | Ghostty | 1.0 |
| Linux | Kitty | 0.21 |
| Linux | Konsole | 20.04 |
| Linux | GNOME Terminal | VTE 0.50 |
| Any | WezTerm | recent stable |
| Any | Alacritty | 0.12 |

On Windows, 1.18 is the release where Windows Terminal began answering palette queries. Earlier builds render identically but export screenshots against the fallback palette.

**Known limitations.** Spicebag still runs on all of these. They cost comfort, not function:

- **macOS Terminal.app** caps out at 256 colors. Gradients band and neighboring cells can render as the same color, which matters because cell colors carry the encoded data. It also does not implement OSC 8, so saved files are not clickable: Terminal.app linkifies literal URLs for <kbd>Cmd</kbd>-click, but Spicebag shows the filename with the `file://` target behind it, leaving no visible URL to detect. Use one of the macOS entries above instead.
- **Windows legacy console host (`conhost.exe`)** handles 24-bit color but answers no palette queries, so screenshots use the fallback. It has no OSC 8 support either, so <kbd>Ctrl</kbd>-clicking a saved file does nothing. It also intercepts some control keys before the app sees them, which is why the screenshot shortcut is <kbd>F12</kbd> rather than a Ctrl combination.
- **tmux and screen** hide palette queries from the terminal underneath and need explicit configuration for 24-bit color. Under tmux, set `terminal-features` for your terminal and enable `allow-passthrough`.

Block glyphs (`█ ▀ ▂ ░`) and box-drawing characters are used throughout, so pick a monospace font that includes the Block Elements range. Cascadia Code, JetBrains Mono, Fira Code, and any Nerd Font patch all qualify.

### Dependencies

```
typer
rich
textual
pillow
mnemonic
shamir-mnemonic
argon2-cffi
```

---

## Installation

```bash
pip install spicebag
```

This installs the `spicebag` command on your PATH. Run it with no arguments to open the TUI, which is the only interface to encoding and decoding.

### From source

Clone the repository, then let the launcher build the virtual environment for you:

```bat
git clone https://github.com/Enkhoder/Spicebag.git
cd Spicebag
run.bat
```

`run.bat` creates `.venv/`, installs `requirements.txt`, verifies dependencies, and launches the app.

To set it up on Linux and macOS, where `run.bat` does not apply:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PYTHONPATH=.              # Windows: set PYTHONPATH=.
python spicebag/app/cli.py
```

All imports are absolute (`from spicebag.xxx import yyy`), so `PYTHONPATH` must include the repository root. Editors that do not read `PYTHONPATH` need the repository root added to their own analysis path, or you can `pip install -e .` and skip the variable entirely.

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
| `decode` | Recover a seed phrase from a PNG, shown on screen only and never saved |
| `help` | Open the in-app reference |
| `banner` | Toggle the ASCII banner (preference persists across sessions) |
| `clear` | Clear the scrollback |
| `exit` | Quit |

The encode flow prompts in order for image count, word count, phrase, salt, cell size, and save path. A single-image encode then shows a clickable color-space preview before writing the file.

### Output location

Images, ZIP archives, screenshots, and the banner preference file are written to `~/Spicebag/`.

---

## Security Considerations

> [!CAUTION]
> Spicebag provides **no protection** against malware, keyloggers, screen capture, coercion, or any form of surveillance. Use it only in a secure, private environment.

- **An unsalted image protects nothing.** Anyone who gets hold of it can read the seed phrase back with a color picker and the public wordlist (see [Manual Decoding](#manual-decoding)). Treat it exactly like the phrase written on paper, and use a salt for any image you cannot keep physically secure.
- **Salt** is processed with **Argon2id** (`time_cost` = 4, `memory_cost` = 256 MB) making brute-force infeasible.
- All randomness for color offsets uses Python's `secrets` module (CSPRNG).
- The salt is **not stored** anywhere. Losing it means the image cannot be decoded.

---

## Performance & Bulk Generation

- **Algorithmic Separation**: Bulk image generation (`bulkEncodeMnemonic`) decouples the color space calculations from the resolution upscaling. This minimizes memory overhead during logic generation.
- **Strictly Unique Colors**: Offsets for cells are sampled without replacement using `secrets.SystemRandom().sample` (out of the 8192 available colors for BIP39) to mathematically guarantee that all bulk-generated images use unique cell colors.
- **Optimized PNG Encoding**: High-resolution cell scaling (e.g. 2000px per cell) processes massive amounts of pixel data. The bulk encoder uses a fast compression level (`compress_level=1`) to yield a ~43% execution speedup, dropping bulk generation times significantly.

---

## Contributing

[`docs/ARCHITECTURE.md`](https://github.com/Enkhoder/Spicebag/blob/main/docs/ARCHITECTURE.md) maps the codebase layer-by-layer and documents the invariants that are not obvious from reading a single file, such as randomness source, single-sourced tables, and seed phrase handling in logs. Read it before changing anything in `spicebag/core/` or `spicebag/utils/colors.py`.

---

## License

This project is licensed under the [MIT License](https://github.com/Enkhoder/Spicebag/blob/main/LICENSE).