<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Spicebag">
</p>

<p align="center"><strong>Visual Mnemonic Encoder / Decoder</strong></p>

<p align="center">
  <a href="https://github.com/Enkhoder/Spicebag/stargazers"><img src="https://img.shields.io/github/stars/Enkhoder/Spicebag?style=for-the-badge&logo=github&logoColor=white&label=Stars&color=ECD251" alt="Stars"></a>
  <a href="https://github.com/Enkhoder/Spicebag/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Enkhoder/Spicebag/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI" alt="CI"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-88A4E9?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/.github/workflows/ci.yml"><img src="https://img.shields.io/badge/OS-Windows%20%7C%20macOS%20%7C%20Linux-D787EF?style=for-the-badge" alt="OS"></a>
  <a href="https://github.com/Enkhoder/Spicebag/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enkhoder/Spicebag?style=for-the-badge&color=909090" alt="License"></a>
</p>

<p align="center">
  <a href="https://www.producthunt.com/products/spicebag?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-spicebag" target="_blank" rel="noopener noreferrer"><img alt="Spicebag - Compress crypto seed phrases into secure visual artifacts. | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1246937&amp;theme=light&amp;t=1789065380333"></a>
</p>

**Spicebag** encodes cryptocurrency wallet seed phrases into color-coded PNG images and decodes them back. Each word in the mnemonic maps to a unique RGB color cell, producing a compact grid image that visually represents the seed, and can be optionally encrypted with a user-provided passphrase.

---

## Features

- **Encode** a seed phrase into a single PNG image or **bulk-generate** multiple variants into a ZIP archive.
- **Decode** a color-coded PNG back into the original seed phrase.
- **Passphrase encryption**: an optional passphrase processed through **Argon2id** key derivation scatters each word's colors across the whole color space and shuffles the grid, making the image unreadable without the passphrase.
- **Proof-of-phrase**: every image carries an HMAC of its own phrase, so a wrong passphrase or an altered image is rejected instead of decoding to a different valid phrase.
- **CLI mode**: `spicebag --encode`, `--decode` and `--palette` run as plain prompts, without the full-screen TUI app.
- **Multi-standard support**:

  | Standard | Word Counts | Wordlist Size |
  |----------|-------------|---------------|
  | BIP39   | 12, 15, 18, 21, 24 | 2048 |
  | Electrum | 12, 24 | 2048 |
  | SLIP39  | 20, 33 | 1024 |

- **PNG integrity checks**: rejects images with forbidden chunks (e.g. `PLTE`, `tRNS`, `iCCP`) and verifies cell-level monochromatic consistency to detect lossy compression.

---

## How It Works

1. **Word → Index**: Each seed word is looked up in its standard's wordlist.
2. **Passphrase Keys**: If a passphrase is provided, an Argon2id-derived master key is expanded via HKDF into a color key, a grid-shuffle key and a proof key.
3. **Index → RGB**: The word index fills the high bits of a 24-bit value and a block offset fills the low bits. The offset's top 3 bits carry a slice of the proof-of-phrase, an HMAC of the whole phrase under the proof key, and the rest is random. Without a passphrase, that value, split into R/G/B channels, is the cell's color. With a passphrase, a passphrase-keyed permutation first scatters it across the whole color space.
4. **Grid Layout**: Each color fills a square cell in a grid whose dimensions match the word count (e.g. 3×4 for 12 words, 4×6 for 24 words). When a passphrase is used, cell positions are deterministically shuffled.
5. **Decoding**: reverses all steps: undo the permutation, look up each word by index, and check the proof slices against the rebuilt phrase. A wrong passphrase fails the proof instead of decoding to a different valid phrase.

---

## Manual Decoding

An image encoded without a passphrase can be decoded by hand, with nothing but a color picker and the wordlist. Manually decoding encrypted images is impossible.

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

How many visually distinct images can encode the *same* seed phrase under the *same* passphrase?

Once the passphrase is fixed, almost everything is deterministic:

| Component | Source | Free? |
|-----------|--------|-------|
| Cell positions | Grid shuffled by `random.Random(permKey[:8])` | ❌ Fixed, one layout per passphrase |
| Color permutation | 10-round Feistel network keyed by the passphrase | ❌ Fixed |
| Proof-of-phrase | Top 3 bits of each block offset, from an HMAC of the phrase | ❌ Fixed |
| **Rest of the block offset** | `secrets.SystemRandom().randrange(blockSize >> 3)` | ✅ **Free** |

The block offset occupies the low bits of the 24-bit value left over after the word index is packed into the high bits. Its top 3 bits carry the proof-of-phrase, so the rest of it is the only free variable:

```
blockSize = 1 << (24 - (maxIdx.bit_length() - 1))
```

| Standard | Wordlist Size | Block Size | Colors per Word | Free Colors per Cell |
|----------|---------------|------------|-----------------|----------------------|
| BIP39, Electrum | 2048 | 2¹³ | 8,192 | 1,024 |
| SLIP39 | 1024 | 2¹⁴ | 16,384 | 2,048 |

Every offset produces a distinct color: the offset fills the low bits of the 24-bit value, and the encrypted color permutation is a bijection, so no two offsets collide.

Since each grid holds exactly one cell per word, the total is `(blockSize / 8) ^ wordCount`:

| Phrase | Entropy | Distinct Images per Passphrase |
|--------|---------|--------------------------|
| 12-word BIP39 / Electrum | 120 bits | 1.33 × 10³⁶ |
| 15-word BIP39 | 150 bits | 1.43 × 10⁴⁵ |
| 18-word BIP39 | 180 bits | 1.53 × 10⁵⁴ |
| 20-word SLIP39 | 220 bits | 1.68 × 10⁶⁶ |
| 21-word BIP39 | 210 bits | 1.65 × 10⁶³ |
| 24-word BIP39 / Electrum | 240 bits | 1.77 × 10⁷² |
| 33-word SLIP39 | 363 bits | 1.88 × 10¹⁰⁹ |

Notes:

- **Positions across passphrases**: the layout dimension only opens up when the passphrase changes, contributing up to `wordCount!` arrangements (4.79 × 10⁸ for 12 words, 6.20 × 10²³ for 24). Within a single passphrase it collapses to one.
- **Interactive preview**: the clickable color-space editor rejects any color matching the cell's current color or an orthogonal neighbor, trimming at most 5 of 1,024 candidates per cell. The reduction is under 0.5%. A hue range typed for a cell narrows its candidates further, by choice, to its word's colors inside that arc: about a sixth of an encrypted cell's colors for a 60° arc.
- **No passphrase**: the grid is left in natural reading order and no color permutation is applied, but the per-word color count is unchanged.

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

- **RGB** or **RGBA** with every alpha value at `255`. Grayscale, palette and other color models are rejected, and so is an embedded color profile such as **Adobe RGB**.
- Other bit depths pass only if they read back as exactly the same 8-bit values.

### Cell Integrity

Every pixel within a single grid cell must be **exactly the same color**. Any variation (e.g. from JPEG re-compression, anti-aliasing, or screenshot artifacts) will fail validation.

---

## Requirements

- Python 3.10+
- A terminal with 24-bit color support. See [Terminal](#terminal)

### Terminal

The TUI app draws a full-screen interface and leans on four terminal capabilities. Each one degrades on its own, so a terminal missing some of them still runs the app:

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

- **macOS Terminal.app** caps out at 256 colors, so gradients band and neighboring cells can render as the same color, which matters because cell colors carry the encoded data. It has no OSC 8 either, so saved files are not clickable. Use one of the macOS entries above instead.
- **Windows legacy console host (`conhost.exe`)** handles 24-bit color but answers no palette queries, so screenshots use the fallback, and it has no OSC 8, so saved files are not clickable. It also intercepts some control keys, which is why the screenshot shortcut is <kbd>F12</kbd>.
- **tmux and screen** hide palette queries from the terminal underneath and need explicit configuration for 24-bit color. Under tmux, set `terminal-features` for your terminal and enable `allow-passthrough`.

In the legacy console host, or in any terminal that does not advertise 24-bit color through `COLORTERM`, a notice under the header names the terminal and its version and recommends [CLI mode](#cli-mode), which needs none of the capabilities above.

Block glyphs (`█ ▀ ▂ ░`) and box-drawing characters are used throughout, so pick a monospace font that includes the Block Elements range. Cascadia Code, JetBrains Mono, Fira Code, and any Nerd Font patch all qualify.

---

## Installation

```bash
pip install spicebag
```

This installs the `spicebag` command on your PATH. Run it with no arguments to open the TUI app, or with a flag such as `--encode` to use [CLI mode](#cli-mode).

If `spicebag` is not recognized after installing, pip placed it in a Scripts folder that is not on your PATH, which is common with the Microsoft Store Python and `--user` installs. `python -m spicebag` runs the same program without it. To run it as plain `spicebag`, install it with [pipx](https://pipx.pypa.io), which puts it on your PATH:

```bash
python -m pip install --user pipx
python -m pipx install spicebag
python -m pipx ensurepath
```

Open a new terminal once afterwards.

### Windows executable

Every [GitHub Release](https://github.com/Enkhoder/Spicebag/releases) from 4.2.0 on carries three zips that need no Python: `Spicebag-X.Y.Z-windows-x64.zip` for most PCs, `Spicebag-X.Y.Z-windows-arm64.zip` for ARM devices such as Snapdragon laptops, and `Spicebag-X.Y.Z-windows-x86.zip` for 32-bit Windows only. Extract it, keep the `Spicebag` folder somewhere permanent, and run `Spicebag.exe` inside it, from a terminal as `.\Spicebag.exe` or `.\Spicebag.exe --encode`, or pinned to the taskbar or Start menu. The exe needs the `_internal` folder beside it, so move the whole folder, never the exe alone; add the folder to your PATH to run `spicebag` from any terminal. It is not code-signed, so Windows SmartScreen may warn the first time it runs.

### From source

Clone the repository, then let the launcher build the virtual environment for you:

```bat
git clone https://github.com/Enkhoder/Spicebag.git
cd Spicebag
run.bat
```

`run.bat` creates `.venv/`, installs `requirements.txt`, checks for missing dependencies, and launches the app.

To set it up on Linux and macOS, where `run.bat` does not apply:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spicebag
```

Run it from the repository root. `pip install -e .` instead installs the `spicebag` command against the checkout.

---

## Usage

### TUI app

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

Pressing <kbd>ESC</kbd> twice within a second at the menu also quits.

The encode flow prompts in order for image count, phrase, passphrase, passphrase confirmation, cell size, and save path. The seed phrase and passphrase are hidden as a line of bars while you type; press <kbd>TAB</kbd> to show or hide them without losing what you typed. A single-image encode then shows a clickable color-space preview before writing the file.

Clicking a cell in the preview selects it, and each further click on the selected cell rerolls its color. To steer a cell toward a hue, click it, then type a hue range in degrees and press <kbd>ENTER</kbd>: two whole numbers from -360 to 360 separated by spaces, such as `20 120`. The range runs upward from the first hue to the second and wraps past 360, so `-20 -50` covers 340 to 310 and `10 -10` covers 10 to 350. The cell rerolls to a color of its word inside the range, with grays, which have no hue, fitting every range. Later clicks on it stay inside it, and the accepted range blinks green in the input bar. With a range already typed, selecting a cell keeps the range for it without recoloring it, and each later click on it rerolls inside the range. After a click, or after <kbd>ENTER</kbd> on a valid range, the arrow keys move the selection between cells. Unencrypted cells reach only a narrow arc of hues, so many ranges have no color for them. To write the image, click the input bar, then press <kbd>ENTER</kbd> on it blank.

### CLI mode

Encode, decode and list cell colors straight from the shell, without opening the TUI app:

```bash
spicebag --encode   # or -e
spicebag --decode   # or -d
spicebag --palette  # or -p
```

Encode asks for the image count, seed phrase, passphrase, passphrase confirmation, cell size and save path. Decode asks for the image path and passphrase. Palette asks for the seed phrase, passphrase and cells. The seed phrase, the passphrase and its confirmation use native terminal masking, so nothing appears while you type. A rejected answer repeats the prompt with the reason in front of it.

Encode and decode then ask `Proceed? (y/n)` before doing any work. `y` or `yes` continues. <kbd>Ctrl</kbd>+<kbd>C</kbd> aborts at any step. Save paths follow the TUI app's rules, with `~` as your home folder, and `spicebag --help` lists them.

A decoded seed phrase is never printed. Decode reports what it recovered and asks before copying the phrase to the clipboard, so answering `N` checks an image and passphrase without exposing the phrase. On Windows the copy is kept out of clipboard history and cloud sync. macOS uses `pbcopy` and Linux uses `wl-copy` (Wayland), and neither can opt out of clipboard managers or Universal Clipboard, so clear the clipboard once you are done. Under WSL, the clipboard is mirrored to Windows and the mirror reads the phrase the moment it is offered, using up the one paste before you can make it, so decode and palette skip the copy question and report `Clipboard unavailable for WSL.` instead.

Palette lists every color each chosen cell can take for that phrase and passphrase, sorted ascending under headers like `Cell [0][2]` (row, then column, counted from 0), and asks before copying the list. Cells are row and column pairs, such as `0 2 3 1` for `[0][2]` and `[3][1]`, and either index can be a range, so `0-2 1-2` covers rows 0 to 2 in columns 1 and 2. `*` or plain ENTER takes every cell. The list gives away the seed phrase as surely as the phrase itself, so it is never printed and takes the same clipboard path as decode.

### Output location

Images, ZIP archives, screenshots, and the banner preference file are written to `~/Spicebag/`.

---

## Security Considerations

> [!CAUTION]
> Spicebag provides **no protection** against malware, keyloggers, screen capture, coercion, or any form of surveillance. Use it only in a secure, private environment.

- **An unencrypted image protects nothing.** Anyone who gets hold of it can read the seed phrase back with a color picker and the public wordlist (see [Manual Decoding](#manual-decoding)). Treat it exactly like the phrase written on paper, and use a passphrase for any image you cannot keep physically secure.
- **Passphrase** is processed with **Argon2id** (`time_cost=4`, `memory_cost=256 MiB`), which makes every guess slow but cannot rescue a guessable passphrase. Use a long, random one.
- All randomness for color offsets uses Python's `secrets` module (CSPRNG).
- The passphrase is the secret Argon2id derives every key from. Argon2id's own salt is the fixed constant `SpicebagDomain`, the same for every image, so a passphrase guess costs one Argon2id run however many images it is tested against. It is unrelated to a wallet's BIP39 passphrase (the "25th word").
- The passphrase is **not stored** anywhere. Losing it means the image cannot be decoded.

---

## Bulk Generation

- A bulk encode builds every image at one pixel per cell first, and scales each one to the cell size only as it is written into the ZIP.
- The free bits of each cell's offset are drawn without replacement (`secrets.SystemRandom().sample`), so up to 1,024 images per archive (2,048 for SLIP39) never repeat a cell's color. Past that, cell colors can repeat, though two identical images remain vanishingly unlikely.
- PNGs are written with the fast `compress_level=1`, trading file size for speed at large cell sizes.

---

## Contributing

[`docs/ARCHITECTURE.md`](https://github.com/Enkhoder/Spicebag/blob/main/docs/ARCHITECTURE.md) maps the codebase layer-by-layer and documents the invariants that are not obvious from reading a single file, such as randomness source, single-sourced tables, and seed phrase handling in logs. Read it before changing anything in `spicebag/backend/`.

---

## Trivia

This project was named after the iconic Irish-Chinese [takeaway dish](https://en.wikipedia.org/wiki/Spice_bag). You throw seasoning and *salt* into a paper bag and shake it. That's more or less what the encoder does.

---

## License

This project is licensed under the [MIT License](https://github.com/Enkhoder/Spicebag/blob/main/LICENSE).