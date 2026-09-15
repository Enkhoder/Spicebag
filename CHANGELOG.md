Image encoding starts over. An unsalted image now stores every word as a literal chunk of the 24-bit color space, so a seed phrase can be read back from its PNG with a color picker and a wordlist, without Spicebag installed.

```bash
pip install --upgrade spicebag
```

### Breaking changes

> **3.0.0 is a fresh start for images.** Every image encoded or decoded from this version on follows the new color rules, and images made by 1.x or 2.x do not decode here. Those images are not lost: they still decode on 2.x, so keep `pip install "spicebag<3"` in a separate virtual environment for as long as you rely on them.

- **Unsalted words map onto literal hex chunks.** The 16,777,216 colors are split in order into one chunk per word, and a word's color always falls inside its own chunk. Word 1 of a 2048-word list (abandon) owns `#000000` to `#001FFF`, word 2 owns `#002000` to `#003FFF`, and the last word owns `#FFE000` to `#FFFFFF`. The 1024-word SLIP39 list uses chunks of 16,384. Cells still run left to right, top to bottom.
- **`RGB_VALUE_SHIFTS` and `PERMUTATIONS` are removed.** The fixed per-position channel shifts and the six channel permutations sat between the word index and the color, hiding the chunk structure. `encodeWord` and `decodeColor` take `colorTables` in place of `shift` and `mask`, and `ColorSpace` carries `colorTables` in place of `shifts` and `masks`.
- **Salted colors scatter across the whole color space.** With a salt, the 24-bit value passes through a salt-keyed permutation before it becomes the color: a 10-round Feistel network whose round keys come from the Argon2id master key through HKDF. Each word still owns exactly 8,192 colors (16,384 for SLIP39) and no color belongs to two words, but those colors are spread pseudo-randomly over all 16,777,216 instead of sitting in one slice, so rerolling a salted cell can land on any hue. The per-position XOR mask is gone: within one salt a word keeps the same color set in every cell, and the salt-seeded cell shuffle still hides word positions. The number of colors per word is unchanged, so every phrase and salt still has as many distinct images as before.

### Manual decoding

The README has a new [Manual Decoding](README.md#manual-decoding) section that walks through reading an unsalted image by hand: find the wordlist from the aspect ratio, read each cell's hex code, and compute the word number from red and green alone (`R × 8 + ⌊G ÷ 32⌋ + 1`, or `R × 4 + ⌊G ÷ 64⌋ + 1` for SLIP39). An unsalted image no longer depends on Spicebag, or on any software at all, still being around to read it.

### Interface

- The help screen explains the color chunks under HOW THIS WORKS, with abandon and ability as worked ranges, and labels the ENCODE image sample as unsalted: rerolling a cell keeps its color inside the same word's chunk. Its salting paragraph explains that a salt scatters each word's colors across the whole color space.
- An unknown command in the main menu reads `No such command: <input>`.

### Command line

- `spicebag --help` and `spicebag -h` print a compact usage block with no blank lines.
- Any argument that is not one of the four flags stops the run before the interface starts. It prints `No such option: <input>` for a token starting with `-` and `No such command: <input>` for anything else, followed by `spicebag --help` and `spicebag -h`, and exits with status 2. Whole tokens are checked, so a stray word after `-h` is an error instead of being ignored, and combined short flags such as `-hV` are rejected.

### Examples and tests

- Every decodable image in [`examples/images/`](examples/images) is re-encoded from the same phrases and salts, so `tests/smoke.py` and the release job's decode check both run against the new format.
- `24-seed-0x59756E-interchanged.png` is rebuilt as a 3.0.0 encode with five cells swapped, so it still fails for the reason its name gives.

### Platform testing

CI runs the encode and decode round trip on every change on Linux (Python 3.10 and 3.13), Windows (3.12) and macOS (3.12), so the new color transform is covered on all three platforms. The interface is verified on Windows only. The per-OS code that 2.0.0 disclosed as unverified is unchanged and still has not run on real macOS or Linux hardware: the POSIX half of the palette probe in `utils/terminalColors.py`, the OSC 0 window-title fallback in `app/cli.py`, and the Linux and macOS network detection in `utils/networkDetect.py`. Each degrades to a safe default rather than raising. Reports from macOS and Linux users close that gap fastest: [open an issue](https://github.com/Enkhoder/Spicebag/issues).

### Documentation

- [`README.md`](README.md): the Manual Decoding section, a Security Considerations warning that an unsalted image protects nothing, How It Works and Configuration Space rewritten around the two-step color transform, and the banner mascot's belt split between the brand gradient and its inversion
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the color transform with its salted Feistel permutation, why the unsalted path takes no transform after the block offset, and the command line's input check
- [`SECURITY.md`](SECURITY.md): reading an unsalted image by hand is listed as out of scope, since it is intentional by design