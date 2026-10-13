Every image now proves its own seed phrase, so a wrong salt is rejected instead of quietly decoding to a different valid phrase. Spicebag also runs straight from the terminal: `spicebag --encode`, `--decode` and `--palette` work through plain prompts, with native masking for the seed phrase and salt. The TUI app itself gains a salt confirmation step and stops dragging the history to the bottom while a progress bar runs.

```bash
pip install --upgrade spicebag
```

### Breaking changes

> **4.0.0 changes the image format, and images made by 3.x no longer decode.** They are not lost: they still decode on 3.x, so keep `pip install "spicebag<4"` in a separate virtual environment for as long as you rely on them, and re-encode them here.

- **Proof-of-phrase.** Until now a wrong salt was only caught by the seed phrase's own checksum, which a random 12-word phrase passes about one time in fifteen. A mistyped salt, even a single stray keystroke, could decode an image to a different phrase that looked perfectly valid. Each cell now carries 3 bits of an HMAC-SHA256 over the whole phrase, keyed by a third HKDF subkey of the salt, in the top of its random block offset. The decoder recomputes it and rejects any mismatch: a wrong salt now slips through a 12-word image about one time in 10¹², and far less often for longer phrases.
- **Clearer decode errors.** A wrong salt reads `Salt is incorrect.`, a salted image decoded without its salt reads `Image is salted or predates v4.0.0.`, since an image made before 4.0.0 fails the same way, and an unsalted image decoded with a salt reads `Salt is incorrect.` instead of sometimes producing a phrase: the decoder handles it exactly like a wrong salt, so it never reveals that an image is unsalted.
- **Altered images are caught.** Swapping two cells, even two holding the same word, or changing a cell's word breaks the proof. Mixing cells between images of the same phrase and salt still decodes, since they carry the same proof.
- **Fewer free colors per cell.** The proof takes 3 of each offset's bits, so once a phrase and salt are fixed a cell can take 1,024 colors (2,048 for SLIP39) instead of 8,192 (16,384). A 12-word phrase still has about 1.3×10³⁶ distinct images per salt. Manual decoding of unsalted images is unchanged, because the proof lives in bits it already ignores.
- **Salts are normalized to Unicode NFC** before key derivation, so an accented salt typed as one composed character or as a letter plus a combining mark is the same salt. A salt made only of such decomposed characters encodes differently than it did on 3.x.

### CLI mode

- **`spicebag --encode` / `-e`** asks for the image count, seed phrase, salt, salt confirmation, cell size and save path, then writes the image or ZIP and prints its filename as a clickable link to the file.
- **`spicebag --decode` / `-d`** asks for the image path and salt, reports the recovered seed phrase's length and standard, then asks whether to copy it to the clipboard. The phrase is never printed, and answering `N` checks an image and salt without exposing the phrase anywhere. If the clipboard cannot be written, the run fails rather than showing it.
- **`spicebag --palette` / `-p`** asks for the seed phrase, salt and cells, then offers to copy every color each chosen cell can take, sorted ascending under `Cell [row][col]` headers counted from 0. Cells are row and column pairs, each index a number or a range like `0-2` or `3-1`, with `*` or a blank answer for every cell. The list identifies the phrase as surely as the phrase itself, so it is never printed and goes through the same one-paste clipboard as decode.
- The seed phrase, the salt and its confirmation are read with native terminal masking, so nothing appears while typing.
- A rejected answer repeats the prompt with a short reason in front of it, such as `Invalid word count`, `Checksum failed`, `Salt does not match`, `Dir not found`, `PNG only` or `Dirty cells`. Three mismatched salt confirmations start the salt over. The image is fully validated before the salt is asked for.
- Encode and decode end with `Proceed? (y/n)`. `y` or `yes` continues, in any case. `n` or `no` ends the run without writing anything, as do three answers that are neither, a plain ENTER included. Every abort prints `Operation aborted.` A blank answer where none is accepted is asked again without a message, and the third in a row ends the run.
- Typed answers keep the terminal's default color, like any native prompt. Errors use its bright red, and the progress bar steps through the brand gradient while encoding and its inverse while decoding, in 256 colors, with a live stopwatch. In a window narrower than the line, the bar wraps at full length and each redraw still replaces the last.
- Pasting into any prompt clears the clipboard once the answer is read, so a pasted seed phrase or salt does not stay behind.
- <kbd>Ctrl</kbd>+<kbd>C</kbd> aborts at any step with exit status 130. An encode interrupted mid-write removes its unfinished file.
- Save paths follow the TUI app's rules, including the `//` separator, and **a leading `~` is the home folder** in every save and image path, in the TUI app too.
- On Windows the clipboard copy is kept out of clipboard history and cloud sync. macOS uses `pbcopy` and Linux uses `wl-copy`. Under WSL, whose clipboard mirror would use up the one paste, decode and palette report `Clipboard unavailable for WSL.` instead of asking to copy.

### TUI app

- **Double ESC exits.** At the main menu, ESC shows `Press ESC again to exit`, and a second ESC within a second closes Spicebag. An ESC less than half a second after the previous one never arms it, so a burst of ESC that steps back out of a flow or closes the help screen cannot quit by accident.
- **Limited/legacy terminal notice.** In the classic Windows console host, or in a terminal that does not advertise truecolor, the header names the terminal and its version and recommends CLI mode instead.
- **No word count step.** Encode goes straight from the image count to the seed phrase, whose length decides the standard. The status bar counts words as `Word n`, typing and pasting stop at 33 words, and a phrase of an unsupported length reads `Invalid word count.`, stacked in front of the masked words as `Invalid word count, invalid seed words: ···` when some are not in any wordlist.
- **Image salt is confirmed.** After entering an image salt, encode asks to confirm it, masked like the first entry and with the same status bar. A mismatch reads `Salt does not match.` and asks again. This happens with no salt as well, where confirming means pressing ENTER again.
- **Progress no longer scrolls the screen.** While an encode or decode runs, scrolling up through the history stays put. The view jumps to the bottom only when the run reaches 100%, fails, or is stopped with `cancel`.
- **Resizing keeps your place.** Changing the window size no longer jumps to the bottom unless the view was already there, and the ASCII art banner keeps its shape in a narrow window, running off the right edge instead of wrapping into broken rows.
- **Paths are shown in the history.** The save path and the image path are logged as typed, minus surrounding spaces, with ENTER on the save path logging the default folder, and screenshots no longer blank them. The seed phrase and salts stay masked.
- **Pasting clears the clipboard.** Any paste into the TUI app empties the system clipboard, so a pasted seed phrase or salt does not stay behind.
- **Default filenames no longer describe their contents.** A single image saves as `20260930_123456.png` and a bulk archive as `x1000_20260930_123456.zip`, instead of names that announced a seed image and its word count. The output folders are now `~/Spicebag/images` and `~/Spicebag/screenshots`, renamed from `encoded-images` and `app-screenshots`. Files already in the old folders stay there.
- Minor UX and quality-of-life updates and fixes.

### Flags

- `spicebag --help` lists `--encode`, `--decode` and `--palette` and adds short Save paths, Decode paths and Palette cells sections.
- `python -m spicebag` runs Spicebag when the `spicebag` command is not on PATH.
- A mistyped flag gets a suggestion: `spicebag --encofe` prints `Did you mean --encode?`, and a bare `spicebag encode` points at `--encode` too. Nothing runs until the flag is typed correctly. The error no longer lists the two help invocations after it.

### Installation

- Every GitHub Release from 4.0.0 on carries a standalone `spicebag.exe` for Windows that needs no Python. It is not code-signed, so SmartScreen may warn on first launch.
- A source checkout runs with `python -m spicebag`, and so does `run.bat`, so `PYTHONPATH` no longer needs setting.
- Python 3.14 is supported.

### Privacy hardening

- A crash prints its traceback without the values of local variables, which could hold the seed phrase or salt. Textual's crash output showed them, and so does Typer's on versions that default to it.
- Every `TEXTUAL*` environment variable is cleared at startup. `TEXTUAL_LOG` made Textual write every keystroke and input change to a file, and `TEXTUAL_SCREENSHOT` saved an unmasked screenshot.

### Examples and tests

- Every decodable image in [`examples/images/`](examples/images) is re-encoded in the new format from the same phrases and salts, and `24-interchanged-seed-Enkhoder.png` is rebuilt from cells of two images of one phrase and salt.
- `Previous-format-3.0-undecodable.png` keeps a 3.0 image as a regression case that must be rejected.
- `tests/smoke.py` checks that wrong salts, a missing salt and a superfluous salt are all rejected, and round-trips 15, 18 and 21-word phrases, which no fixture covers.

### Platform testing

The TUI app and CLI mode are verified on Windows, and under WSL on Ubuntu, Fedora and Arch. WSL exercises neither the Linux clipboard nor the Linux network detection. The CLI mode clipboard on macOS (`pbcopy`) and Linux (`wl-copy`) has not run on real hardware, and neither has the per-OS code disclosed in earlier releases: the POSIX half of the palette probe in `frontend/utils/terminalColors.py`, the OSC 0 window-title fallback in `frontend/entry.py`, and the Linux and macOS network detection in `frontend/utils/networkDetect.py`. The same goes for the `COLORTERM` check behind the limited terminal notice in `frontend/utils/limitedTerminal.py`. Reports from macOS and Linux users close that gap fastest: [open an issue](https://github.com/Enkhoder/Spicebag/issues).

### Documentation

- [`README.md`](README.md): a CLI mode section under Usage, why every block offset gives a distinct color under the salted permutation, what to do when `spicebag` is not on PATH, and the Windows executable
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the proof-of-phrase and its place in the file format, CLI mode and the clipboard writer, the new flags, and the salt confirmation state