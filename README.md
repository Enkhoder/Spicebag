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
- Jupyter Notebook (to run the `.ipynb`)

### Dependencies

```
pillow
mnemonic
shamir-mnemonic
argon2-cffi
```

Install all at once:

```bash
pip install pillow mnemonic shamir-mnemonic argon2-cffi
```

---

## Usage

1. Open the notebook in Jupyter:

   ```bash
   jupyter notebook spicebag.ipynb
   ```

2. Run all cells. A menu will appear:

   ```
   Spicebag by E14118
   ——————————————————
   1) Generate image from seed phrase
   2) Generate image from seed phrase (bulk)
   3) Decode seed phrase from image
   0) Exit
   ```

3. Follow the interactive prompts. Seed phrases are entered via hidden input (`getpass`) and file paths are selected through native OS dialogs.

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

This project is licensed under the [MIT License](LICENSE).
