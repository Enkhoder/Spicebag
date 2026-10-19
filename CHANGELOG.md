A minor release: a single-image encode lets you steer any cell of the preview toward a range of hues, and the Windows build ships as a zip with `Spicebag.exe` inside. Images and the image format are unchanged from 4.0.0.

```bash
pip install --upgrade spicebag
```

### Hue ranges

- **Pick a cell's hues.** At the single-image confirm step, select a cell, type a hue range and press <kbd>ENTER</kbd>: the cell rerolls to a color of its word inside the range and keeps the range for later rerolls.
- **Selecting.** The first click on a cell selects it without recoloring. Each further click, or <kbd>ENTER</kbd> while the last click was on a cell, rerolls it. With a range typed, selecting a cell also gives it that range. The arrow keys move the selection, wrapping at the edges. Clicking the input bar drops the selection.
- **Writing the image.** Click the input bar, then press <kbd>ENTER</kbd> on it blank. <kbd>ESC</kbd> with a range typed clears the bar first.
- **Syntax.** Two whole hues from -360 to 360, separated by spaces, with a hyphen only ever a minus sign. The range runs upward and wraps past 360: `20 120` is 20 to 120, `-20 -50` is 340 to 310, `10 -10` is 10 to 350. Grays have no hue and fit every range.
- **Feedback.** An accepted range stays in the input bar while its bullet, cursor, background and borders blink green. Characters other than digits, hyphens and spaces are never typed and flash the bar red. Other invalid input also shows its reason in the status bar for a second:
  - `Too many hyphens.`
  - `Hyphen is misplaced.`
  - `Hue out of range.`
  - `Too many hues.`
  - `Two hues are needed.`
  - `Click a cell first.`
  - `No color in this hue range.`
- **Unsalted images** reach only a narrow arc of hues per cell, so many ranges have no color for them. Salted cells cover the whole color wheel: a 60° range keeps about a sixth of a cell's colors.

### TUI app

- Hovering a preview cell, in the encode preview or the help page sample, shrinks it to a rounded block.
- The last clicked cell keeps that shape over a brand gradient sweeping back and forth once a second: in the encode preview while it stays selected, and in the help page sample until a click lands outside it, the cell scrolls out of the window or the sample masks.
- While a help page sample cell is selected, <kbd>ENTER</kbd> rerolls it and the arrow keys move the selection, as in the encode preview, instead of closing the page.
- The command suggestion in the input bar turns red with the placeholder during an error flash.
- <kbd>Ctrl</kbd>+<kbd>V</kbd> and <kbd>Shift</kbd>+<kbd>Insert</kbd> paste the system clipboard in terminals that pass them through, filtered for the prompt like any paste, and the clipboard is wiped afterwards. A hue range can be pasted too, under the same rules as typing it.
- The default save and decode paths in the input bar's placeholder, its <kbd>TAB</kbd> autofill and the answer shown for a blank save path are shortened to `~`, as in CLI mode.

### Fixes

- **Autoscroll on the first overflow.** The prompt that first made the history taller than the window stayed below the visible area until the next prompt. It now scrolls into view like every later one.
- **Help page in the Windows console host.** Pressing <kbd>Ctrl</kbd> or <kbd>Alt</kbd> alone, as in <kbd>Alt</kbd>+<kbd>TAB</kbd> or <kbd>Ctrl</kbd>+click on the author credit, closed the help page, since the console host reports a bare modifier as a key of its own.
- **Red flashes from system keys.** At a confirm step, a bare <kbd>Ctrl</kbd>, <kbd>Alt</kbd>, <kbd>Shift</kbd> or Windows key, <kbd>TAB</kbd>, the lock keys, media keys and window shortcuts such as <kbd>Alt</kbd>+<kbd>TAB</kbd> no longer flash the input bar red.
- **First command after the warning screen.** A command typed and entered within half a second of the menu appearing was ignored, so `e` followed at once by <kbd>ENTER</kbd> did nothing.

### Windows executable

- Each GitHub Release carries `Spicebag-X.Y.Z-windows.zip` instead of a single exe. Extract it and run `Spicebag.exe` from inside the `Spicebag` folder, which must stay next to its `_internal` folder; pin it from there. The one-folder build starts faster than the old self-unpacking exe, which antivirus engines flagged more often.
- A redrawn icon, pixel-exact at 16, 32, 48, 64, 128 and 256 pixels.

### Documentation

- [`README.md`](README.md): hue ranges under Usage, and their effect on a cell's candidate colors under the configuration space notes.
- The in-app help page lists the hue range syntax under Encode.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): `applyHueRange()` and the stored ranges in `ColorSpace`.