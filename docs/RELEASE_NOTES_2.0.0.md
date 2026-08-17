# Draft: v2.0.0 release body

Paste into the GitHub release at tag time. Not published anywhere; this file exists so the notes
survive until the tag does.

---

## Spicebag v2.0.0

The interface is now the only way in. The `encode` and `decode` subcommands are gone, screenshots
render against your real terminal colors instead of a fixed palette, and the in-app guide redraws
from cached strips rather than rewriting itself.

```bash
pip install --upgrade spicebag
```

### Breaking changes

- **`spicebag encode` and `spicebag decode` are removed.** Encoding and decoding happen in the TUI
  and nowhere else. A seed phrase passed as a command-line argument lands in shell history, in the
  process table, and in any shell integration that records commands. The application can clear none
  of that afterwards. Scripts that called either subcommand will need rewriting; there is no
  drop-in replacement, by design.
- The command line now accepts flags only: `--version` / `-V` and `--help` / `-h`.
- Everything that shelled out to those subcommands was rewritten to match: CI smoke-tests
  `spicebag --help`, the release job decodes the example images through `decodeImage` directly, and
  [`examples/README.md`](examples/README.md) walks through the interface instead.

### Screenshots match your terminal

Exports used to be re-rendered through Rich's `SVG_EXPORT_THEME` and Textual's `MONOKAI`, so every
capture came out with a `#292929` frame and a `#0C0C0C` body regardless of how the terminal was
configured. Spicebag now queries the terminal for its real background, foreground, and all sixteen
ANSI slots (OSC 11, OSC 10, OSC 4) at startup and renders the SVG against those.

Terminals that do not answer fall back to the previous fixed dark theme, so nothing regresses. On
Windows, legacy `conhost.exe` answers no queries and is read from its console color table instead.

### Interface

- Screenshots are bound to <kbd>F12</kbd>. The previous <kbd>Ctrl</kbd>+<kbd>S</kbd> is intercepted
  as XOFF by legacy console hosts, which made the security warning screen impossible to capture.
- The window title is set through the Win32 console API on Windows, so legacy hosts no longer print
  the raw escape sequence as a stray line at startup.
- `--help` is hand-written rather than generated, and no longer advertises framework defaults.
- The help screen renders from cached strips instead of rewriting the whole log on every frame. It
  lists F12 alongside the typed commands, and Ctrl-clicking the author credit in its footer opens
  the GitHub profile.

### Platform testing

> **The encoding core is covered on all three platforms. The interface is verified on Windows only.**
> CI runs the encode and decode round trip on Linux, Windows and macOS for every change, so the
> cryptography and the PNG path are exercised everywhere. What CI cannot drive is a full-screen
> interface, and what it never touches is the per-OS probing code. Nothing below is known to be
> broken; treat it as unverified rather than as unsupported.

| OS | Status |
|---|---|
| Windows 11 | Fully exercised: interface, screenshots, Windows Terminal and legacy `conhost.exe` |
| macOS | Core green in CI; interface exercised only in a VMware guest, never on real hardware |
| Linux | Core green in CI; interface not exercised |

The code that branches on platform, and therefore carries the most risk:

- **`utils/terminalColors.py`**: the POSIX half of the palette probe (`termios`, `tty`, `select`)
  has never run. The Windows half and the fallback theme are covered.
- **`app/cli.py`**: `setTerminalTitle` falls back to an OSC 0 escape sequence off Windows.
- **`utils/networkDetect.py`**: the Linux `/sys/class/net` and `rfkill` reads, and the macOS
  `networksetup` and `ifconfig` shell-outs plus the Bluetooth plist read, are unverified.

Each of these degrades to a safe default rather than raising, so a failure should cost a single
feature rather than the session. Reports from macOS and Linux users are the fastest way to close
the gap: [open an issue](https://github.com/Enkhoder/Spicebag/issues).

### Supply chain

Publishing still runs through [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
No long-lived API token exists on any machine or in any repository secret.
[`release.yml`](.github/workflows/release.yml) fires on a `v*` tag, refuses to build unless the tag
matches the version in `pyproject.toml`, builds and `twine check`s the wheel and sdist, then holds
publishing behind the `pypi` environment for manual approval.

Before that gate it installs the freshly built wheel into a clean virtualenv and decodes two example
images. That step used to call the `decode` subcommand this release removes, so it now calls
`decodeImage` directly, and still proves a clean install can decode a real PNG.

[`ci.yml`](.github/workflows/ci.yml) runs the encode/decode round trip in `tests/smoke.py` across
Linux, Windows and macOS on Python 3.10 through 3.13, and fails the build if the wheel ever contains
a file that must not ship.

### Documentation

- [`README.md`](README.md): usage, the encoding algorithm, the configuration-space math, and a new
  terminal-compatibility section covering 24-bit color, mouse reporting, OSC 8 hyperlinks, and
  palette queries per OS
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): module map and the invariants that aren't visible
  from any single file
- [`SECURITY.md`](SECURITY.md): threat model and scope