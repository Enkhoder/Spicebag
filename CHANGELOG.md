A patch release: the help page stays open when a modifier key is pressed on its own, the ASCII banner's version glows on hover, and the Windows executable carries the Spicebag icon. Images and the image format are unchanged from 4.0.0.

```bash
pip install --upgrade spicebag
```

### Fixes

- **Help page and modifier keys.** Pressing <kbd>Ctrl</kbd>, <kbd>Shift</kbd>, <kbd>Alt</kbd> or <kbd>Super</kbd> alone no longer closes the help page. Terminals that speak the kitty keyboard protocol, such as Alacritty 0.13 and later, report a bare modifier press as a key of its own, and the help page took it as the key that closes it. Every other key still closes it.

### TUI app

- Hovering the version under the ASCII banner sweeps it with the inverted brand gradient, white italic text over a highlight one cell wider on each side, the way the mascot banner's title and the help page's author name already respond.

### Windows executable

- `spicebag.exe` carries the Spicebag icon at 16, 32, 48, 64, 128 and 256 pixels.

### Documentation

- [`README.md`](README.md): installing with pipx through `python -m pipx`, so plain `spicebag` works even when neither `spicebag` nor `pipx` is on PATH.
- Proof-of-phrase is hyphenated throughout [`README.md`](README.md), [`examples/README.md`](examples/README.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).