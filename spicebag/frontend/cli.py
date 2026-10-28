######## LIBRARIES ########

from spicebag.frontend.theme import (
    IMAGES_DIR, MAX_IMAGE_COUNT, MAX_CELL_PX, DEFAULT_CELL_PX, PROGRESS_BAR_LENGTH,
    formatElapsed
)
from spicebag.backend.generator import identifySeedType, bulkEncodeMnemonic, encodeMnemonic, cellPalettes, InvalidSeedWordsError
from spicebag.backend.decoder import decodeImage, imageError, validatePNGStructure, PNG_SIGNATURE, BAD_PNG_TEXT
from spicebag.frontend.utils.clipboard import pasteOnce, clearClipboard, clipboardBlocker, readClipboard
from spicebag.frontend.utils.terminalColors import STD_OUTPUT_HANDLE, ENABLE_VIRTUAL_TERMINAL_PROCESSING
from spicebag.backend.paths import parseSavePath, locateImage, tildePath
from spicebag.backend.defaults import WORD_COUNTS, GRID_SIZES
from spicebag.backend.colors import normalizePassphrase
from rich.console import Console
from rich.control import Control
from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from pathlib import Path
import threading
import tempfile
import getpass
import time
import sys
import os
import re



######## CONSTANTS ########

ERASE_BELOW = "\x1b[J"

INTEGER_PATTERN = re.compile(r"[+-]?\d+", re.ASCII)

INDEX_PATTERN = re.compile(r"(-?\d+)(?:-(-?\d+))?", re.ASCII)

ANSI_FAIL = "bright_red"

MAX_ATTEMPTS = 3

IMAGE_PATH_ERRORS = {
    "filename": "Filename required",
    "folder": "PNG only",
    "noDir": "Dir not found",
    "noExtension": "PNG only",
    "notPng": "PNG only",
    "missing": "Image not found"
}

ABORT_MESSAGE = "Operation aborted."

PASTE_OUTCOMES = {
    "pasted": "Clipboard cleared.",
    "replaced": "Clipboard replaced before any paste.",
    "copied": "{what} copied to clipboard."
}

ANSI_UNFILLED = "bright_black"

ANSI_ENCODE_GRADIENT = (
    "color(226)",
    "color(220)",
    "color(214)",
    "color(208)",
    "color(202)",
    "color(203)",
    "color(204)",
    "color(168)",
    "color(169)"
)

ANSI_DECODE_GRADIENT = (
    "color(63)",
    "color(27)",
    "color(33)",
    "color(39)",
    "color(45)",
    "color(81)",
    "color(87)",
    "color(86)",
    "color(85)"
)



######## CONSOLE ########

def _enableVirtualTerminal() -> None:
    """Turn on VT sequences for this console on Windows, where the classic console host leaves them off, so
    Rich draws the progress bar in its 256 colors and the saved path as a link instead of falling back to the
    legacy console API."""
    if sys.platform != "win32":
        return

    from ctypes import wintypes
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    handle = kernel32.GetStdHandle(wintypes.DWORD(STD_OUTPUT_HANDLE & 0xFFFFFFFF))
    mode = wintypes.DWORD()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)


_enableVirtualTerminal()

console = Console(highlight=False, soft_wrap=True)



######## PROMPTS ########

class Aborted(Exception):
    """Ends the run with the given status and ABORT_MESSAGE."""

    def __init__(self, code: int = 1) -> None:
        super().__init__()
        self.code = code


def _wipePasted(raw: str) -> None:
    """Clear the clipboard when the answer holds its text, so nothing pasted into a prompt lingers there."""
    pasted = readClipboard()

    if pasted and any(line.strip() and line.strip() in raw for line in pasted.splitlines()):
        clearClipboard()


def _ask(prompt: str, prefix: str = "", masked: bool = False) -> str:
    if prefix:
        console.print(Text(f"{prefix} ", style=ANSI_FAIL), end="")

    raw = getpass.getpass(prompt) if masked else input(prompt)

    _wipePasted(raw)
    return raw


def _fillBlank(prompt: str, prefix: str, raw: str, shown: str) -> None:
    """Rewrite the line a blank answer left behind so it shows the default that was used."""
    if not (console.is_terminal and sys.stdin.isatty()):
        return

    head = f"{prefix} " if prefix else ""
    rows = max(1, -(-cell_len(head + prompt + raw) // console.width))
    console.control(Control.move(0, -rows), Control.move_to_column(0))
    console.print(Text(head, style=ANSI_FAIL), end="")
    console.print(Text(prompt + shown))


def _prompt(prompt: str, check, masked: bool = False, fill=None):
    """Ask until check(raw) returns a value with no error. A None value with no error is a blank answer that
    cannot proceed: it re-asks silently, and the MAX_ATTEMPTS-th in a row aborts the run. A blank answer
    accepted as a default is written back into its line through fill(value)."""
    error = ""
    blanks = 0

    while True:
        prefix = error
        raw = _ask(prompt, prefix, masked)
        value, error = check(raw)

        if value is None and not error:
            blanks += 1
            if blanks == MAX_ATTEMPTS:
                raise Aborted()

            continue

        blanks = 0

        if value is not None and not error:
            if fill is not None and not raw.strip():
                _fillBlank(prompt, prefix, raw, fill(value))

            return value


def _askPassphrase() -> str:
    """MAX_ATTEMPTS mismatched confirmations start the passphrase over, since a masked first entry may be the typo."""
    while True:
        passphrase = _ask("Passphrase: ", masked=True)
        error = ""

        for _ in range(MAX_ATTEMPTS):
            if normalizePassphrase(_ask("Confirm passphrase: ", error, True)) == normalizePassphrase(passphrase):
                return passphrase

            error = "No match"


def _confirm(prompt: str) -> bool:
    """True on y or yes, case ignored. Anything else, a blank answer included, is No, the default the capital N
    advertises."""
    return _ask(prompt).strip().lower() in ("y", "yes")


def _proceed() -> None:
    """Returns on y or yes, case ignored, and aborts on n or no. Anything else, a blank answer included,
    repeats the prompt silently, and the MAX_ATTEMPTS-th aborts."""
    for _ in range(MAX_ATTEMPTS):
        answer = _ask("Proceed? (y/n): ").strip().lower()

        if answer in ("y", "yes"):
            return

        if answer in ("n", "no"):
            raise Aborted()

    raise Aborted()



######## INPUT CHECKS ########

def _checkNumber(raw: str, default: int, maximum: int, unit: str) -> tuple[int | None, str]:
    raw = raw.strip()
    if not raw:
        return default, ""

    if not INTEGER_PATTERN.fullmatch(raw):
        return None, "Int only"

    value = int(raw)
    if value < 1:
        return None, f"Min 1{unit}"

    if value > maximum:
        return None, f"Max {maximum}{unit}"

    return value, ""


def _checkPhrase(raw: str) -> tuple[str | None, str]:
    phrase = " ".join(raw.split())
    if not phrase:
        return None, ""

    if len(phrase.split()) not in WORD_COUNTS:
        return None, "Invalid word count"

    try:
        identifySeedType(phrase)

    except InvalidSeedWordsError as e:
        return None, f"{len(e.words)} invalid words" if len(e.words) > 1 else "Invalid word"

    except ValueError:
        return None, "Checksum failed"

    return phrase, ""


def _checkCells(raw: str, rows: int, cols: int) -> tuple[set[tuple[int, int]] | None, str]:
    """Blank or * selects every cell. Otherwise indices pair up as row then column, each an integer or an
    inclusive range in either direction, and a pair selects every cell its two ranges cross. Out of bounds
    counts every index a range covers, so 3-5 past row 3 is two."""
    tokens = raw.replace(",", " ").split()
    if not tokens or tokens == ["*"]:
        return {(r, c) for r in range(rows) for c in range(cols)}, ""

    spans = []
    for token in tokens:
        match = INDEX_PATTERN.fullmatch(token)
        if not match:
            return None, "Valid ints only"

        start, end = sorted((int(match[1]), int(match[2] or match[1])))
        spans.append(range(start, end + 1))

    outside = sum(
        len(span) - max(0, min(span.stop, cols if n % 2 else rows) - max(span.start, 0))
        for n, span in enumerate(spans)
    )
    if outside:
        return None, "Out of bounds"

    if len(spans) % 2:
        return None, "Last col missing"

    return {(r, c) for rowSpan, colSpan in zip(spans[::2], spans[1::2]) for r in rowSpan for c in colSpan}, ""


def _canWrite(directory: Path) -> bool:
    try:
        with tempfile.TemporaryFile(dir=directory):
            return True

    except OSError:
        return False


def _checkSavePath(raw: str) -> tuple[tuple[Path, str] | None, str]:
    result = parseSavePath(raw.strip(), IMAGES_DIR)

    if isinstance(result, str):
        if result in ("Directory not found.", "Path is not a directory."):
            return None, "Dir not found"

        if "reserved system name" in result:
            return None, "Filename reserved"

        return None, "Invalid filename"

    dirStr, stem = result
    targetDir = Path(dirStr) if dirStr else IMAGES_DIR

    if os.path.isdir(targetDir) and not _canWrite(targetDir):
        return None, "Permission denied"

    return (targetDir, stem), ""


def _inspectImage(path: str) -> str:
    """The interface's image checks, worded without the final period since the reason runs into the prompt. A
    file that is not a PNG, a forbidden chunk and a bad color space each get their own short reason, where the
    interface words the last two alike."""
    try:
        with open(path, "rb") as f:
            if f.read(8) != PNG_SIGNATURE:
                return "PNG only"

        validatePNGStructure(path)

    except ValueError:
        return "Forbidden chunks"

    except OSError:
        pass

    error = imageError(path) or ""
    return "Bad color space" if error == BAD_PNG_TEXT else error.rstrip(".")


def _checkImagePath(raw: str) -> tuple[str | None, str]:
    if not raw.strip():
        return None, ""

    fullPath, reason = locateImage(raw, IMAGES_DIR)
    if fullPath is None:
        return None, IMAGE_PATH_ERRORS[reason]

    error = _inspectImage(fullPath)
    return (None, error) if error else (fullPath, "")



######## PROGRESS BAR ########

class ProgressBar:
    """The interface's loader without the tree, in 256-color steps: heavy segments for done, light ones for the
    rest, the percent, and a stopwatch. A background thread keeps the stopwatch ticking while the work blocks, such as
    during Argon2. Leaving the block freezes the time, ends the line, and turns Ctrl+C into an abort."""

    def __init__(self, label: str, gradient: tuple[str, ...]) -> None:
        self._label = label
        self._gradient = gradient
        self._percent = 0.0
        self._start = time.monotonic()
        self._finalMs: float | None = None
        self._shown: tuple | None = None
        self._shownCells = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ticker = threading.Thread(target=self._tick, daemon=True)


    def __enter__(self) -> "ProgressBar":
        self._draw()
        self._ticker.start()
        return self


    def __exit__(self, excType, exc, traceback) -> None:
        self._stop.set()
        self._ticker.join()
        self._finalMs = (time.monotonic() - self._start) * 1000
        self._draw()
        console.print()

        if excType is KeyboardInterrupt:
            raise Aborted(130) from None


    def update(self, percent: float) -> None:
        self._percent = percent
        self._draw()


    def _tick(self) -> None:
        while not self._stop.wait(0.1):
            self._draw()


    def _draw(self) -> None:
        """A line wider than the window wraps, and a carriage return only reaches the start of its last row. So
        each redraw first climbs to the row the previous line began on, counted at the current width since the
        terminal reflows on resize, then erases whatever the old line left below the new one."""
        with self._lock:
            width = console.width
            isFinal = self._finalMs is not None
            elapsedMs = self._finalMs if self._finalMs is not None else (time.monotonic() - self._start) * 1000
            lit = int(self._percent * PROGRESS_BAR_LENGTH)
            percent = int(self._percent * 100)
            state = (width, lit, percent, formatElapsed(elapsedMs, isFinal))
            if state == self._shown:
                return

            self._shown = state
            line = Text(f"{self._label}  ")
            step = PROGRESS_BAR_LENGTH // len(self._gradient)
            for i, color in enumerate(self._gradient):
                line.append("━" * max(0, min(step, lit - i * step)), style=color)

            line.append("─" * (PROGRESS_BAR_LENGTH - lit), style=ANSI_UNFILLED)
            line.append(f"  {percent}%")
            line.append(f"  ·  {state[3]}")

            if console.is_terminal and self._shownCells > width:
                console.control(Control.move(0, -((self._shownCells - 1) // width)))

            console.file.write("\r")
            console.print(line, end="")
            if console.is_terminal:
                console.file.write(ERASE_BELOW)

            self._shownCells = line.cell_len



######## FLOWS ########

def _fileState(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
        return (stat.st_mtime_ns, stat.st_size)

    except OSError:
        return None


def _encodeFlow() -> int:
    count = _prompt("Image count: ", lambda raw: _checkNumber(raw, 1, MAX_IMAGE_COUNT, ""), fill=str)
    phrase = _prompt("Seed phrase: ", _checkPhrase, masked=True)
    passphrase = _askPassphrase()
    cellPx = _prompt("Cell size: ", lambda raw: _checkNumber(raw, DEFAULT_CELL_PX, MAX_CELL_PX, "px"), fill=str)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    extension = ".png" if count == 1 else ".zip"
    defaultStem = timestamp if count == 1 else f"x{count}_{timestamp}"
    targetDir, stem = _prompt(
        "Save path: ",
        _checkSavePath,
        fill=lambda value: tildePath(value[0] / (defaultStem + extension))
    )

    _proceed()

    finalPath = os.path.abspath(targetDir / ((stem or defaultStem) + extension))
    before = _fileState(finalPath)

    try:
        with ProgressBar("Encoding", ANSI_ENCODE_GRADIENT) as bar:
            os.makedirs(targetDir, exist_ok=True)

            if count == 1:
                encodeMnemonic(phrase, finalPath, cellPx=cellPx, passphrase=passphrase, progressCallback=bar.update)

            else:
                bulkEncodeMnemonic(phrase, finalPath, count, cellPx=cellPx, passphrase=passphrase, progressCallback=bar.update)

    except BaseException as exc:
        if _fileState(finalPath) != before:
            try:
                os.remove(finalPath)

            except OSError:
                pass

        if not isinstance(exc, Exception) or isinstance(exc, Aborted):
            raise

        console.print(Text(f"{type(exc).__name__}: {exc}. Unable to write image.", style=ANSI_FAIL))
        return 1

    saved = Text("Image saved: ")
    saved.append(os.path.basename(finalPath), style=Style(underline=True, link=Path(finalPath).as_uri()))
    console.print(saved)
    return 0


def _decodeFlow() -> int:
    path = _prompt("Image path: ", _checkImagePath)
    passphrase = _ask("Image passphrase: ", masked=True)

    _proceed()

    try:
        with ProgressBar("Decoding", ANSI_DECODE_GRADIENT) as bar:
            mnemonic, seedType = decodeImage(path, passphrase=passphrase, progressCallback=bar.update, validate=False)

    except Aborted:
        raise

    except Exception:
        console.print(Text("Passphrase is incorrect." if passphrase else "Image is encrypted or predates v4.0.0.", style=ANSI_FAIL))
        return 1

    typeLabel = f" {seedType}" if seedType else ""
    console.print(Text(f"{len(mnemonic.split())}-word{typeLabel} seed phrase recovered."))

    if _clipboardBlocked():
        return 1

    if not _confirm("Copy to clipboard? (y/N): "):
        raise Aborted(0)

    return _copyOnce(mnemonic, "Seed phrase")


def _paletteFlow() -> int:
    phrase = _prompt("Seed phrase: ", _checkPhrase, masked=True)
    passphrase = _ask("Passphrase: ", masked=True)
    cols, rows = GRID_SIZES[len(phrase.split())]
    cells = _prompt("Cells: ", lambda raw: _checkCells(raw, rows, cols), fill=lambda _: "*")
    if _clipboardBlocked():
        return 1

    palettes = cellPalettes(phrase, passphrase, cells)

    if not _confirm("Copy to clipboard? (y/N): "):
        raise Aborted(0)

    text = "\n\n".join(
        f"Cell [{r}][{c}]\n" + " ".join(f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in colors)
        for (r, c), colors in palettes.items()
    )
    return _copyOnce(text, "Palette")


def _clipboardBlocked() -> bool:
    """Under a subsystem that spends the one-time paste itself, say so in place of the copy question."""
    blocker = clipboardBlocker()
    if blocker:
        console.print(Text(f"Clipboard unavailable for {blocker}.", style=ANSI_FAIL))

    return blocker is not None


def _copyOnce(text: str, what: str) -> int:
    """Hand text to the clipboard for exactly one paste, waiting silently for it. If the clipboard cannot be
    written the run fails instead of falling back to the screen. Ctrl+C while waiting aborts without a blank
    line, since the cursor already sits on a fresh one."""
    try:
        outcome = pasteOnce(text)

    except KeyboardInterrupt:
        raise Aborted(130) from None

    if outcome == "unavailable":
        console.print(Text("Clipboard unavailable", style=ANSI_FAIL))
        return 1

    console.print(Text(PASTE_OUTCOMES[outcome].format(what=what)))
    return 0


def _run(flow) -> int:
    """Ctrl+C ends any step with status 130 and ABORT_MESSAGE, EOF with status 1 and no message, both on a fresh
    line."""
    try:
        return flow()

    except KeyboardInterrupt:
        console.print()
        console.print(Text(ABORT_MESSAGE))
        return 130

    except EOFError:
        console.print()
        return 1

    except Aborted as e:
        console.print(Text(ABORT_MESSAGE))
        return e.code


def runEncode() -> int:
    return _run(_encodeFlow)


def runDecode() -> int:
    return _run(_decodeFlow)


def runPalette() -> int:
    return _run(_paletteFlow)