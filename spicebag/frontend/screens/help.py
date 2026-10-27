######## LIBRARIES ########

from spicebag.frontend.theme import (
    invertedGradientHex,
    bannerGradientHex,
    C_WHITE, C_DIM, C_INP, C_IMG, C_WC, C_SUCC, C_FAIL,
    SCREENSHOT_KEY, MODIFIER_KEYS, HOVERED_CELL_ROWS, ARROW_STEPS,
)
from spicebag.backend.generator import ColorSpace, precomputeColorSpace, rerollCell
from spicebag.frontend.widgets.stripLog import StripLog, renderStrips
from spicebag.frontend.tree import RootNode, TreeNode, renderBlocks
from spicebag.backend.defaults import GRID_SIZES
from textual.app import ComposeResult
from typing import Optional, Sequence
from textual.geometry import Region
from textual.screen import Screen
from textual.strip import Strip
from rich.style import Style
from rich.text import Text
from textual import events
import webbrowser
import time
import re



######## PAGE CONTENT ########

HELP_DEMO_SEED = (
    "grape monster husband desert city near blast brown pigeon normal tired stem "
    "spot increase real simple slim word shell glove tortoise luggage meat castle"
)

PROSE = [
    "Spicebag conceals your seed phrase inside colored PNG cell grid. Colors can be interchanged, "
    "scattered, and reassembled, yet they would still be perfectly decodable to raw string, given "
    "another compatible images of the same seed phrase and passphrase.",
]

MANUAL_DECODE_SINCE = "v3.0.0"

VERSION_HOVER_TEXT = f" {MANUAL_DECODE_SINCE} "

ENCODE_LINK = "ENCODE"

SAMPLE_INTRO = "Try the unencrypted image sample below."

HOW_THIS_WORKS_ROWS = [
    [
        ("One cell represents one seed word. All 24-bit = 16,777,216 colors are split in order, one chunk "
         "per word: ", C_DIM),
        ("2,048 chunks of 8,192 colors", C_DIM),
        (" for BIP39 and Electrum, ", C_DIM),
        ("1,024 chunks of 16,384 colors", C_DIM),
        (" for SLIP39. Chunk size = block size.", C_DIM),
    ],
    [
        ("Starting from ", C_DIM),
        (MANUAL_DECODE_SINCE, C_DIM),
        (", you can decode unencrypted images yourself. Example: Word #1 abandon covers #000000-#001FFF, "
         "word #2 ability covers #002000-#003FFF, and so on. Unencrypted sample on ", C_DIM),
        (ENCODE_LINK, C_IMG),
        (" works this way. Read in standard horizontal-left-to-right direction. Translate color values to "
         "decimal first if referring from raw hex codes #RRGGBB.", C_DIM),
    ],
    (
        [
            ("A = 10", C_WHITE),
            ("  ·  ", C_DIM),
            ("B = 11", C_WHITE),
            ("  ·  ", C_DIM),
            ("C = 12", C_WHITE),
            ("  ·  ", C_DIM),
            ("D = 13", C_WHITE),
            ("  ·  ", C_DIM),
            ("E = 14", C_WHITE),
            ("  ·  ", C_DIM),
            ("F = 15", C_WHITE),
        ],
        [
            ("#XY···· or #··XY·· -> 16X + Y = ", C_WHITE),
            ("R", f"bold {C_FAIL}"),
            (" or ", C_WHITE),
            ("G", f"bold {C_SUCC}"),
            (" in decimal", C_WHITE),
        ],
    ),
    (
        [
            ("8", C_WHITE),
            ("R", f"bold {C_FAIL}"),
            (" + floor(", C_WHITE),
            ("G", f"bold {C_SUCC}"),
            (" / 32) + 1", C_WHITE),
            (" = nth BIP39 / Electrum word", C_WHITE),
        ],
        [
            ("4", C_WHITE),
            ("R", f"bold {C_FAIL}"),
            (" + floor(", C_WHITE),
            ("G", f"bold {C_SUCC}"),
            (" / 64) + 1", C_WHITE),
            (" = nth SLIP39 word", C_WHITE),
        ],
    ),
    [
        ("Passphrase goes through ", C_DIM),
        ("Argon2id + HKDF + HMAC", C_DIM),
        (". Each word's colors scatter across the whole color space, cells shuffle, and raw hex codes mean "
         "nothing anymore. Every cell also hides 3 bits of proof, so an incorrect passphrase gets rejected instead "
         "of being wrongfully decoded as some other phrase.", C_DIM),
    ],
    [
        ("Result: one phrase, one passphrase, and ", C_DIM),
        ("10^36 to 10^109", C_DIM),
        (" possible images. Math: ", C_DIM),
        ("(blockSize / 2^3)^wordCount = (blockSize / 8)^wordCount", C_DIM),
        (", since proof takes 3 bits of every block.", C_DIM),
    ],
    [
        ("This project was named after the iconic Irish-Chinese takeaway dish. You throw seasoning and ", C_DIM),
        ("salt", f"italic {C_DIM}"),
        (" into a paper bag and shake it. That's more or less what the encoder does.", C_DIM),
    ],
]

LICENSE_PREFIX = "(c) 2026 "
LICENSE_NAME = "Enkhoder"
LICENSE_SEPARATOR = "  ·  "
LICENSE_SUFFIX = "Licensed under the MIT License."
LICENSE_HOVER_ACTION = "CTRL+click"
LICENSE_HOVER_TAIL = " to view GitHub profile"
NAME_HOVER_TEXT = f" {LICENSE_NAME} "
NAME_GITHUB_URL = f"https://github.com/{LICENSE_NAME}"
RETURN_LINE = "Press any key to return to main menu."

SEE_FILE_PATHS = [("See ", C_DIM), ("FILE PATHS", C_WHITE), (".", C_DIM)]

COMMAND_ROWS = [
    ("encode", C_IMG,   "Seed phrase -> encoded image"),
    ("decode", C_WC,    "Encoded image -> seed phrase"),
    ("clear",  C_WHITE, "Wipe the screen"),
    ("banner", C_WHITE, "Toggle banner styles"),
    ("help",   C_SUCC,  "Open this guide"),
    ("exit",   C_FAIL,  "Close Spicebag"),
    ("ESC",    C_DIM,   "Spicebag's back button"),
    ("F12",    C_DIM,   "Secure SVG screenshot, anywhere"),
]

ENCODE_ROWS = [
    ("Image count", [("1-2000", C_INP)]),
    ("Seed phrase", [("Accepted standards: BIP39, Electrum, SLIP39", C_DIM)]),
    ("Passphrase",  [("Further masks your image. Optional but recommended, all Unicode allowed, "
                      "no character limit, no rules.", C_DIM)]),
    ("Cell size",   [("1-2000", C_INP)]),
    ("Save path",   SEE_FILE_PATHS),
    ("Hue range",   [("20 120", C_INP),
                     (" after clicking a cell of a single-image preview keeps its color between hues 20 and 120. "
                      "A hyphen makes a hue negative, so ", C_DIM),
                     ("-20 -50", C_INP),
                     (" runs from 340 up to 310.", C_DIM)]),
]

ENCODE_PATH_ROWS = [
    ("(blank)", C_DIM,
     [("Default Spicebag folder inside user home directory, default name", C_DIM)]),
    ("safe/image", C_INP,
     [("image", C_WHITE), (".png in folder safe", C_DIM)]),
    ("safe/image.png", C_INP,
     [("image.png", C_WHITE), (".png in folder safe", C_DIM)]),
    ("safe/myFolder", C_INP,
     [("If myFolder is a folder, save with default name inside it; else myFolder.png in folder safe "
       "(flexible)", C_DIM)]),
    ("safe/myFolder/", C_INP,
     [("Trailing slash, save with default name inside folder myFolder; ", C_DIM),
      ("else directory not found", C_FAIL)]),
    ("safe//myFolder", C_INP,
     [("Double slash forces myFolder.png, folder or not", C_DIM)]),
    ("//image", C_INP,
     [("image.png in default directory", C_DIM)]),
    ("myFolder", C_INP,
     [("Bare name is treated as directory. Save with default name inside folder myFolder if it "
       "exists. Spicebag does not create custom folders for you.", C_DIM)]),
    ("myFolder/", C_INP,
     [("Trailing slash is tolerable, same treatment as above", C_DIM)]),
    ("myFolder//", C_INP,
     [("Trailing double slash error: custom filename cannot be blank", C_FAIL)]),
]

DECODE_PATH_ROWS = [
    ("(blank)", C_DIM,
     [("This one is not autofilled, you choose the image yourself", C_FAIL)]),
    ("safe/image.png", C_INP,
     [("Reads image.png inside folder safe", C_DIM)]),
    ("safe//image.png", C_INP,
     [("Same treatment as above", C_DIM)]),
    ("//image.png", C_INP,
     [("Reads image.png from default directory", C_DIM)]),
    ("image.png", C_INP,
     [("Treated as directory. Directory not found, or missing file if folder image.png exists.",
       C_FAIL)]),
    ("safe/image", C_INP,
     [("Missing file if there is a folder named image, else missing extension, both cannot proceed",
       C_FAIL)]),
    ("safe/image.jpg", C_INP,
     [("Wrong extension, only PNG is accepted", C_FAIL)]),
]



######## TREE BUILDERS ########

def _mk(segments: Sequence[tuple[str, str | None]]) -> Text:
    text = Text(end="")
    for body, style in segments:
        text.append(body, style=style)

    return text


def _branch(segments: Sequence[tuple[str, str | None]], children: list[TreeNode] | None = None) -> TreeNode:
    return TreeNode(kind="branch", text=_mk(segments), connStyle=C_DIM, children=children or [])


def _note(segments: Sequence[tuple[str, str | None]]) -> TreeNode:
    return TreeNode(kind="note", text=_mk(segments))


def _spacer() -> TreeNode:
    """Blank continuation line. The renderer only auto-spaces root-level
    branches, so notes and nested siblings need one of these between them."""
    return TreeNode(kind="note", text=Text(""))


def _pathChildren(rows: list) -> list[TreeNode]:
    children: list[TreeNode] = []
    for i, (example, exampleStyle, meaning) in enumerate(rows):
        if i > 0:
            children.append(_spacer())

        children.append(_branch([(example, exampleStyle)], [_branch(meaning)]))

    return children


def _commandsBlock() -> RootNode:
    root = RootNode(label=_mk([("COMMANDS", f"bold {C_INP}")]), bullet=C_WHITE)
    root.children = [
        _branch([(name, color)], [_branch([(desc, C_DIM)])])
        for name, color, desc in COMMAND_ROWS
    ]
    return root


def _encodeBlock(
    colorSpace: Optional[ColorSpace],
    masked: bool,
    hoverCell: Optional[tuple[int, int]],
    selectedCell: Optional[tuple[int, int]],
    selectPhase: int
) -> RootNode:
    root = RootNode(label=_mk([("ENCODE", f"bold {C_IMG}")]), bullet=C_WHITE)
    root.children = [
        _note([("Writes a PNG file for 1 image by default, or a ZIP file containing bulk PNGs for "
                "multiple images.", C_DIM)]),
        _spacer(),
    ]

    for label, meaning in ENCODE_ROWS:
        root.children.append(_branch([(label, C_WHITE)], [_branch(meaning)]))

    if colorSpace is not None:
        sample = TreeNode(
            kind="imagesample",
            connStyle=C_DIM,
            sampleSpace=colorSpace,
            sampleMasked=masked,
            sampleClickable=True,
            sampleHover=hoverCell,
            sampleSelected=selectedCell,
            sampleSelectPhase=selectPhase,
        )
        root.children.append(_branch(
            [(f"{SAMPLE_INTRO} Click on a cell to reroll its color within its word's chunk.", C_DIM)],
            [sample],
        ))

    return root


def _decodeBlock(words: Sequence[str], revealAll: bool, hoverIdx: int) -> RootNode:
    cols, rows = GRID_SIZES.get(len(words), (4, (len(words) + 3) // 4))
    seedGrid = TreeNode(
        kind="seedgrid",
        connStyle=C_DIM,
        words=list(words),
        cols=cols,
        rows=rows,
        interactive=True,
        revealAll=revealAll,
        hoverIdx=hoverIdx,
    )

    root = RootNode(label=_mk([("DECODE", f"bold {C_WC}")]), bullet=C_WHITE)
    root.children = [
        _note([("For extra security, you can only view your decoded seed phrases without saving or "
                "downloading them. No sensitive information ever leaves the CLI.", C_DIM)]),
        _spacer(),
        _branch([("Image file path", C_WHITE)], [_branch(SEE_FILE_PATHS)]),
        _branch([("Passphrase used to encode the image", C_WHITE)]),
        _spacer(),
        _branch([("Decoded seed phrase from the image sample on ", C_DIM), (ENCODE_LINK, C_IMG), (":", C_DIM)],
                [seedGrid]),
    ]
    return root


def _filePathsBlock() -> RootNode:
    root = RootNode(label=_mk([("FILE PATHS", f"bold {C_WHITE}")]), bullet=C_WHITE)
    root.children = [
        _note([("Standard file path. ", C_DIM), ("/", C_WHITE), (" or ", C_DIM), ("\\", C_WHITE),
               (" as separators are acceptable.", C_DIM)]),
        _spacer(),
        _note([("Filename containing illegal characters or using reserved names will be first "
                "rejected by your PC.", C_DIM)]),
        _spacer(),
        _note([("Let ", C_DIM), ("safe", C_WHITE), (" be a folder, and ", C_DIM),
               ("image", C_WHITE), (" be the encoded image:", C_DIM)]),
        _spacer(),
        _branch([("Encode", C_IMG), (" paths (where to save)", C_WHITE)],
                _pathChildren(ENCODE_PATH_ROWS)),
        _branch([("Decode", C_WC), (" paths (which image to read)", C_WHITE)],
                _pathChildren(DECODE_PATH_ROWS)),
    ]
    return root


def versionHoverFrameCount() -> int:
    return 2 * (len(VERSION_HOVER_TEXT) - 1)


def _versionSweep(hoverPhase: int) -> list[tuple[str, str]]:
    """The mascot banner title's hover sweep: a back-and-forth brand gradient, drawn reversed and italic like the
    title's version, over the version padded by one cell on each side, so the text around it moves aside."""
    half = len(VERSION_HOVER_TEXT) - 1
    period = 2 * half
    segments = []
    for i, char in enumerate(VERSION_HOVER_TEXT):
        p = (i - hoverPhase) % period
        colorIdx = p if p <= half else period - p
        segments.append((char, f"italic reverse {bannerGradientHex(colorIdx / half)}"))

    return segments


def _howThisWorksBlock(versionPhase: int) -> RootNode:
    """A list in HOW_THIS_WORKS_ROWS is one paragraph. A tuple holds lines that stay together, with no blank
    line between them."""
    root = RootNode(label=_mk([("HOW THIS WORKS & MANUAL DECODE", f"bold {C_WHITE}")]), bullet=C_WHITE)
    children: list[TreeNode] = []
    for i, row in enumerate(HOW_THIS_WORKS_ROWS):
        if i > 0:
            children.append(_spacer())

        for segments in (row if isinstance(row, tuple) else (row,)):
            if versionPhase != -1:
                segments = [
                    part
                    for body, style in segments
                    for part in (_versionSweep(versionPhase) if body == MANUAL_DECODE_SINCE else [(body, style)])
                ]

            children.append(_note(segments))

    root.children = children
    return root


def nameHoverFrameCount() -> int:
    return 2 * (len(NAME_HOVER_TEXT) - 1)


def licenseLine(hoverPhase: int) -> Text:
    """License credit, with the author name swept by a back-and-forth highlight
    of the inverted brand gradient while hovered, and the suffix
    swapped to a ctrl+click hint. The name text stays a fixed C_WHITE against
    the moving gradient background, so it never blends with it. The highlight
    opens on the column the name starts at, so only the name slides one cell
    right; the separator's leading space is kept in full (on top of the
    name's own trailing pad), giving the dot one extra space of breathing
    room while hovered."""
    text = Text(end="")
    if hoverPhase == -1:
        text.append(LICENSE_PREFIX, style=C_WHITE)
        text.append(LICENSE_NAME, style=f"bold {C_WHITE}")
        text.append(LICENSE_SEPARATOR + LICENSE_SUFFIX, style=C_WHITE)
        return text

    text.append(LICENSE_PREFIX, style=C_WHITE)

    half = len(NAME_HOVER_TEXT) - 1
    period = 2 * half
    for i, char in enumerate(NAME_HOVER_TEXT):
        p = (i - hoverPhase) % period
        colorIdx = p if p <= half else period - p
        bgHex = invertedGradientHex(colorIdx / half)
        text.append(char, style=f"bold {C_WHITE} on {bgHex}")

    text.append(LICENSE_SEPARATOR, style=C_WHITE)
    text.append(LICENSE_HOVER_ACTION, style=C_WHITE)
    text.append(LICENSE_HOVER_TAIL, style=C_DIM)
    return text


def gradientRule(width: int) -> Text:
    """Full-width divider, re-colored across the banner gradient on every
    rebuild so a resize re-spreads it over the new width."""
    text = Text(end="")
    for x in range(width):
        text.append("─", style=bannerGradientHex(x / max(1, width - 1)))

    return text



######## CLICKABLE LOG ########

BLANK_STRIP = Strip.blank(0)


class HelpLog(StripLog):
    """Strip log that forwards cell clicks and hovers, in virtual content coordinates, to the screen
    so the encode sample can re-roll a tile and the decode grid can reveal a word."""

    def on_click(self, event: events.Click) -> None:
        event.stop()
        line = event.y + self.scroll_offset.y
        col = event.x + self.scroll_offset.x

        releaser = getattr(self.screen, "_releaseSampleOnClick", None)
        if releaser is not None:
            releaser(line, col)

        hitWord = getattr(self.screen, "_hitSeedWord", None)
        wordIdx = hitWord(line, col) if hitWord is not None else None
        if wordIdx is not None:
            seedHandler = getattr(self.screen, "_handleSeedClick", None)
            if seedHandler is not None:
                seedHandler(wordIdx)

            return

        nameHandler = getattr(self.screen, "_handleNameClick", None)
        if nameHandler is not None and nameHandler(line, col, event.ctrl):
            return

        linkHandler = getattr(self.screen, "_handleEncodeLinkClick", None)
        if linkHandler is not None and linkHandler(line, col):
            return

        handler = getattr(self.screen, "_handleSampleClick", None)

        if handler is not None:
            handler(line, col)


    def on_mouse_move(self, event: events.MouseMove) -> None:
        handler = getattr(self.screen, "_handleWordHover", None)
        if handler is None:
            return

        line = event.y + self.scroll_offset.y
        col = event.x + self.scroll_offset.x
        handler(line, col)


    def on_leave(self) -> None:
        handler = getattr(self.screen, "_clearWordHover", None)
        if handler is not None:
            handler()


    def watch_scroll_x(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_x(old_value, new_value)
        self._releaseHiddenSelection()


    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self._releaseHiddenSelection()


    def _releaseHiddenSelection(self) -> None:
        handler = getattr(self.screen, "_releaseHiddenSelection", None)
        if handler is not None:
            handler()



######## HELP SCREEN ########

class HelpScreen(Screen):
    """Self-contained, single-column guide shown over the menu. Any key returns,
    leaving the menu underneath exactly as it was, except F12 which takes an
    unmasked screenshot without closing the guide, and ENTER and the arrow keys
    while a sample cell is selected. The encode sample and decode
    grid are live and behave like their real counterparts on the main menu. The
    log fills the screen with no padding or margin, so every line runs edge to edge."""

    can_focus = False

    DEFAULT_CSS = """
    HelpScreen #help-log {
        width: 100%;
        height: 100%;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        scrollbar-size: 0 0;
    }
    """

    def __init__(self) -> None:
        """_imgPausedUntil suspends the auto-reshuffle until that time, _imgMasked is the frozen, fully masked
        beat after the grace window, and _imgRevision, bumped on every reroll, keys the sample's cache entry.
        The decode grid shows every word until the first click, then only the word under the cursor. A
        _namePhase or _versionPhase of -1 means the author name or the version is not hovered."""
        super().__init__()
        self._readyAt = 0.0
        self._words = HELP_DEMO_SEED.split()

        try:
            self._imgColorSpace: Optional[ColorSpace] = precomputeColorSpace(HELP_DEMO_SEED, "")

        except Exception:
            self._imgColorSpace = None

        self._imgTimer = None
        self._imgPausedUntil = 0.0
        self._imgMasked = False
        self._imgRevision = 0
        self._graceTimer = None
        self._maskTimer = None
        self._sampleStartLine = -1
        self._sampleBlockCol = 0
        self._sampleCols = 0
        self._sampleRows = 0
        self._sampleHoverCell: Optional[tuple[int, int]] = None
        self._sampleSelectedCell: Optional[tuple[int, int]] = None
        self._sampleSelectPhase = 0
        self._selectTimer = None
        self._seedRevealAll = True
        self._seedHoverIdx = -1
        self._hoverRegions: list = []
        self._namePhase = -1
        self._nameTimer = None
        self._nameRegion: Optional[tuple[int, int, int]] = None
        self._versionPhase = -1
        self._versionTimer = None
        self._versionRegion: Optional[tuple[int, int, int]] = None
        self._encodeLinks: list[tuple[int, int, int]] = []
        self._hoveredLink: Optional[tuple[int, int, int]] = None
        self._sampleIntroLine = 0
        self._segCache: dict[str, tuple] = {}
        self._cacheWidth = -1


    def compose(self) -> ComposeResult:
        log = HelpLog(id="help-log")
        log.can_focus = False
        yield log


    def on_mount(self) -> None:
        """The whole sample reshuffles once a second, paused for 3 seconds after a click."""
        self._readyAt = time.time() + 0.25
        self._rebuild()
        self._imgTimer = self.set_interval(1.0, self._imgTick)


    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()

        if event.key == SCREENSHOT_KEY:
            from spicebag.frontend.screenshot import generateScreenshotPath, executePrint
            import os
            path = generateScreenshotPath()

            if not hasattr(self.app, "_helpScreenshots"):
                setattr(self.app, "_helpScreenshots", [])

            basename = os.path.basename(path + ".svg")
            shots = getattr(self.app, "_helpScreenshots")
            if basename not in shots:
                shots.append(basename)

            self.run_worker(executePrint(self, path))
            return

        if event.key in ("pageup", "pagedown"):
            log = self.query_one("#help-log", HelpLog)
            if event.key == "pageup":
                log.scroll_page_up(animate=False)

            else:
                log.scroll_page_down(animate=False)

            return

        if event.key in MODIFIER_KEYS or time.time() < self._readyAt:
            return

        if self._sampleSelectedCell is not None and (event.key == "enter" or event.key in ARROW_STEPS):
            self._handleSampleKey(event.key)
            return

        if self._imgTimer is not None:
            self._imgTimer.stop()
            self._imgTimer = None

        self._stopTimer("_graceTimer")
        self._stopTimer("_maskTimer")
        self._stopTimer("_nameTimer")
        self._stopTimer("_versionTimer")
        self._stopTimer("_selectTimer")

        self.app.pop_screen()


    def on_resize(self) -> None:
        if self.is_mounted:
            self._rebuild()
            self.call_after_refresh(self._releaseHiddenSelection)



    ######## ANIMATION ########

    def _stopTimer(self, attr: str) -> None:
        timer = getattr(self, attr, None)
        if timer is not None:
            timer.stop()
            setattr(self, attr, None)


    def _reshuffleAll(self) -> None:
        cs = self._imgColorSpace
        if cs is None:
            return

        for (r, c) in list(cs.cellToWord.keys()):
            rerollCell(cs, r, c)

        self._imgRevision += 1


    def _imgTick(self) -> None:
        """Reshuffle the entire image once a second, unless a recent click has
        paused auto-reshuffling or the post-grace masked beat is on screen."""
        cs = self._imgColorSpace
        if cs is None or self._imgMasked:
            return

        if time.time() < self._imgPausedUntil:
            return

        self._reshuffleAll()
        self._rebuild()


    def _enterMaskFreeze(self) -> None:
        """Grace window expired: freeze the sample fully masked for two seconds
        before letting the reshuffle loop take over again."""
        self._graceTimer = None
        if self._imgColorSpace is None:
            return

        self._imgMasked = True
        self._imgPausedUntil = 0.0
        self._setSampleSelection(None)
        self._maskTimer = self.set_timer(2.0, self._exitMaskFreeze)
        self._rebuild()


    def _exitMaskFreeze(self) -> None:
        """Masked beat over: reshuffle once and hand the sample back to the
        ambient loop. The loop restarts from this moment, so the next tick is a steady
        second away rather than wherever the on_mount phase happens to land."""
        self._maskTimer = None
        self._imgMasked = False
        if self._imgColorSpace is None:
            return

        self._reshuffleAll()
        self._rebuild()
        self._stopTimer("_imgTimer")
        self._imgTimer = self.set_interval(1.0, self._imgTick)



    ######## INTERACTIVE SAMPLE ########

    def _setSampleSelection(self, cell: Optional[tuple[int, int]]) -> None:
        """Show the clicked cell over the brand gradient sweep, until a click lands outside the sample, the cell scrolls
        fully out of the window or the sample masks. Clicking the selected cell again keeps the sweep running where it is."""
        if cell == self._sampleSelectedCell:
            return

        self._sampleSelectedCell = cell
        self._sampleSelectPhase = 0
        if cell is None:
            self._stopTimer("_selectTimer")

        elif self._selectTimer is None:
            self._selectTimer = self.set_interval(1.0 / (2 * (len(HOVERED_CELL_ROWS[0]) - 1)), self._tickSampleSelection)


    def _tickSampleSelection(self) -> None:
        if self._sampleSelectedCell is None:
            return

        self._sampleSelectPhase = (self._sampleSelectPhase + 1) % (2 * (len(HOVERED_CELL_ROWS[0]) - 1))
        self._rebuild()


    def _sampleCellAt(self, line: int, col: int) -> Optional[tuple[int, int]]:
        """The sample cell under a document position, if the sample is shown unmasked."""
        if self._imgColorSpace is None or self._imgMasked or self._sampleStartLine < 0:
            return None

        rowOff = line - self._sampleStartLine
        colOff = col - self._sampleBlockCol
        if rowOff < 0 or colOff < 0 or rowOff >= self._sampleRows * 3 or colOff >= self._sampleCols * 6:
            return None

        return rowOff // 3, colOff // 6


    def _handleSampleClick(self, line: int, col: int) -> None:
        """A click re-rolls only the clicked tile (same next-color logic as the
        real confirm-step preview) and pauses auto-reshuffle for 3 seconds."""
        cell = self._sampleCellAt(line, col)
        if cell is None or not rerollCell(self._imgColorSpace, *cell):
            return

        self._setSampleSelection(cell)

        self._imgRevision += 1
        self._holdSample()
        self._rebuild()


    def _handleSampleKey(self, key: str) -> None:
        """ENTER rerolls the selected cell and the arrow keys step the selection, wrapping around each edge of the
        grid and scrolling the new cell into view, as in the real confirm-step preview."""
        row, col = self._sampleSelectedCell
        if key == "enter":
            if rerollCell(self._imgColorSpace, row, col):
                self._imgRevision += 1

        else:
            rowStep, colStep = ARROW_STEPS[key]
            self._setSampleSelection(((row + rowStep) % self._sampleRows, (col + colStep) % self._sampleCols))

        self._holdSample()
        self._rebuild()
        self.query_one("#help-log", HelpLog).scroll_to_region(
            self._sampleCellRegion(self._sampleSelectedCell),
            animate=False,
            immediate=True
        )


    def _holdSample(self) -> None:
        """Pause the auto-reshuffle for 3 seconds, then mask the sample unless another click or key comes first."""
        self._imgPausedUntil = time.time() + 3.0
        self._stopTimer("_graceTimer")
        self._graceTimer = self.set_timer(3.0, self._enterMaskFreeze)


    def _sampleCellRegion(self, cell: tuple[int, int]) -> Region:
        return Region(self._sampleBlockCol + cell[1] * 6, self._sampleStartLine + cell[0] * 3, 6, 3)


    def _releaseSampleOnClick(self, line: int, col: int) -> None:
        if self._sampleSelectedCell is not None and self._sampleCellAt(line, col) is None:
            self._setSampleSelection(None)
            self._rebuild()


    def _releaseHiddenSelection(self) -> None:
        """Drop the selection once its cell is fully out of the window. It stays dropped if the cell scrolls back."""
        cell = self._sampleSelectedCell
        if cell is None:
            return

        log = self.query_one("#help-log", HelpLog)
        if not log.scrollable_content_region.at_offset(log.scroll_offset).overlaps(self._sampleCellRegion(cell)):
            self._setSampleSelection(None)
            self._rebuild()



    ######## DECODED SEED GRID / MASKED WORDS ########

    def _hitSeedWord(self, line: int, col: int) -> Optional[int]:
        for lineIdx, colStart, colEnd, wordIdx in self._hoverRegions:
            if line == lineIdx and colStart <= col < colEnd:
                return wordIdx

        return None


    def _handleSeedClick(self, wordIdx: int) -> None:
        """With every word shown, a click masks the rest and shows just this word, exactly like hovering it.
        Otherwise a click reveals everything."""
        if self._seedRevealAll:
            self._seedRevealAll = False
            self._seedHoverIdx = wordIdx

        else:
            self._seedRevealAll = True
            self._seedHoverIdx = -1

        self._rebuild()


    def _handleWordHover(self, line: int, col: int) -> None:
        target = self._hitSeedWord(line, col)
        want = target if target is not None else -1
        changed = False

        if self._seedHoverIdx != want:
            self._seedHoverIdx = want
            changed = True

        region = self._nameRegion
        overName = region is not None and line == region[0] and region[1] <= col < region[2]
        if self._setNameHover(overName):
            changed = True

        region = self._versionRegion
        overVersion = region is not None and line == region[0] and region[1] <= col < region[2]
        if self._setVersionHover(overVersion):
            changed = True

        link = self._encodeLinkAt(line, col)
        if self._hoveredLink != link:
            self._hoveredLink = link
            changed = True

        cell = self._sampleCellAt(line, col)
        if self._sampleHoverCell != cell:
            self._sampleHoverCell = cell
            changed = True

        if changed:
            self._rebuild()


    def _clearWordHover(self) -> None:
        changed = self._setNameHover(False)
        if self._setVersionHover(False):
            changed = True

        if self._hoveredLink is not None:
            self._hoveredLink = None
            changed = True

        if self._seedHoverIdx != -1:
            self._seedHoverIdx = -1
            changed = True

        if self._sampleHoverCell is not None:
            self._sampleHoverCell = None
            changed = True

        if changed:
            self._rebuild()



    ######## HOVERED AUTHOR NAME ########

    def _setNameHover(self, hovered: bool) -> bool:
        """Start/stop the gradient sweep over the name. Returns whether the
        rendered state changed."""
        if hovered:
            if self._namePhase != -1:
                return False

            self._namePhase = 0
            self._nameTimer = self.set_timer(0.1, self._nameTick)
            return True

        if self._namePhase == -1:
            return False

        self._namePhase = -1
        self._stopTimer("_nameTimer")
        return True


    def _handleNameClick(self, line: int, col: int, ctrlHeld: bool) -> bool:
        """Ctrl+click on the author name opens their GitHub profile. Returns
        whether the click landed on the name, so callers can swallow it either
        way instead of falling through to the sample-click handler."""
        region = self._nameRegion
        if region is None or line != region[0] or not (region[1] <= col < region[2]):
            return False

        if ctrlHeld:
            webbrowser.open(NAME_GITHUB_URL)

        return True


    def _nameTick(self) -> None:
        self._nameTimer = None
        if self._namePhase == -1:
            return

        self._namePhase = (self._namePhase + 1) % nameHoverFrameCount()
        self._nameTimer = self.set_timer(0.05, self._nameTick)
        self._rebuild()



    ######## ENCODE LINK ########

    def _encodeLinkAt(self, line: int, col: int) -> Optional[tuple[int, int, int]]:
        for region in self._encodeLinks:
            if line == region[0] and region[1] <= col < region[2]:
                return region

        return None


    def _handleEncodeLinkClick(self, line: int, col: int) -> bool:
        """A click on any ENCODE in body text scrolls the image sample's intro line to the second row of the
        screen, with the line above it still in view. Returns whether the click landed on a link."""
        if self._encodeLinkAt(line, col) is None:
            return False

        self.query_one("#help-log", HelpLog).scroll_to(y=max(0, self._sampleIntroLine - 1), animate=False)
        return True


    def _linkEncodes(self, strips: list[Strip]) -> None:
        """Every ENCODE outside a heading links to the image sample. The section headings start with their
        bullet, so they are left out. The hovered link is bolded on its rendered line, so no section needs to
        know about it."""
        self._encodeLinks = []
        for i, strip in enumerate(strips):
            plain = strip.text
            if plain.startswith("●"):
                continue

            if SAMPLE_INTRO in plain:
                self._sampleIntroLine = i

            for match in re.finditer(rf"\b{ENCODE_LINK}\b", plain):
                self._encodeLinks.append((i, match.start(), match.end()))

        if self._hoveredLink not in self._encodeLinks:
            self._hoveredLink = None
            return

        line, start, end = self._hoveredLink
        before, word, after = strips[line].divide([start, end, strips[line].cell_length])
        strips[line] = Strip.join([before, word.apply_style(Style(bold=True)), after])



    ######## HOVERED VERSION ########

    def _setVersionHover(self, hovered: bool) -> bool:
        """Start/stop the gradient sweep over the version. Returns whether the rendered state changed."""
        if hovered:
            if self._versionPhase != -1:
                return False

            self._versionPhase = 0
            self._versionTimer = self.set_interval(1.0 / versionHoverFrameCount(), self._versionTick)
            return True

        if self._versionPhase == -1:
            return False

        self._versionPhase = -1
        self._stopTimer("_versionTimer")
        return True


    def _versionTick(self) -> None:
        """One frame of the sweep. A fixed-rate interval keeps a full back-and-forth cycle at one second."""
        if self._versionPhase == -1:
            return

        self._versionPhase = (self._versionPhase + 1) % versionHoverFrameCount()
        self._rebuild()



    ######## ASSEMBLY ########

    def _logWidth(self) -> int:
        try:
            w = self.query_one("#help-log", HelpLog).size.width

        except Exception:
            w = 0

        if w <= 0:
            w = self.app.size.width if self.app.size.width > 0 else 80

        return max(8, w)


    def _prose(self, lines: list, body: str, width: int, style: str = C_WHITE) -> None:
        text = Text(body, style=style)
        for wrapped in text.wrap(self.app.console, max(1, width)):
            lines.append(wrapped)


    def _section(self, name: str, key: tuple, build):
        """Rasterize a section of the document once per distinct key.

        Most of the page (the command list, the path tables, the closing prose)
        depends on nothing but the width, so a hover that only repaints one word
        of the decode grid must not re-wrap and re-rasterize all of it. Sections
        that do change carry their mutable state in the key: the encode sample on
        a reroll counter, the decode grid on its reveal/hover indices, the license
        line on the gradient phase."""
        cached = self._segCache.get(name)
        if cached is not None and cached[0] == key:
            return cached[1]

        value = build()
        self._segCache[name] = (key, value)
        return value


    def _blockSection(self, name: str, key: tuple, makeRoot, width: int):
        """Cache one tree block as (strips, sampleHit, hoverRegions), with the two
        region lists still relative to the block's own first line."""
        def build():
            console = self.app.console
            lines, sampleHit, hoverRegions = renderBlocks([makeRoot()], width, console)
            return renderStrips(lines, console), sampleHit, hoverRegions

        return self._section(name, key, build)


    def _licenseSection(self, width: int):
        """Cache the license line as (strips, plains). The plain strings are kept
        because the name's hot zone is located by searching the rendered text."""
        def build():
            console = self.app.console
            lines = list(licenseLine(self._namePhase).wrap(console, max(1, width)))
            return renderStrips(lines, console), [line.plain for line in lines]

        return self._section("license", (width, self._namePhase), build)


    def _worksSection(self, width: int):
        """Cache the HOW THIS WORKS & MANUAL DECODE block as (strips, plains). The plain strings locate the version's hot zone,
        which anchors on the highlight block like the author name's, so it stays put while the version shifts."""
        def build():
            console = self.app.console
            lines, _, _ = renderBlocks([_howThisWorksBlock(self._versionPhase)], width, console)
            return renderStrips(lines, console), [line.plain for line in lines]

        return self._section("works", (width, self._versionPhase), build)


    def _headSection(self, width: int) -> list[Strip]:
        def build():
            lines: list = [gradientRule(width)]
            for i, paragraph in enumerate(PROSE):
                if i > 0:
                    lines.append(Text(""))

                self._prose(lines, paragraph, width)

            return renderStrips(lines, self.app.console)

        return self._section("head", (width,), build)


    def _footSection(self, width: int) -> list[Strip]:
        def build():
            lines: list = []
            self._prose(lines, RETURN_LINE, width, C_DIM)

            return renderStrips(lines, self.app.console)

        return self._section("foot", (width,), build)


    def _composeStrips(self, width: int) -> list[Strip]:
        """Assemble the whole document from its cached sections, re-deriving the
        click and hover geometry as each section lands at its final offset. The
        blank rows around the license reuse BLANK_STRIP rather than new strips, so
        they keep their identity between rebuilds, which is how the view tells an
        unchanged line from a stale one. The name's hot zone anchors on the
        highlight block, not the name, so it stays put while the hovered name sits
        one cell to the right."""
        strips: list[Strip] = list(self._headSection(width))

        strips.extend(self._blockSection("commands", (width,), _commandsBlock, width)[0])

        offset = len(strips)
        sampleStrips, sampleHit, _ = self._blockSection(
            "encode",
            (width, self._imgMasked, self._imgRevision, self._sampleHoverCell, self._sampleSelectedCell,
             self._sampleSelectPhase),
            lambda: _encodeBlock(
                self._imgColorSpace,
                self._imgMasked,
                self._sampleHoverCell,
                self._sampleSelectedCell,
                self._sampleSelectPhase
            ),
            width,
        )
        strips.extend(sampleStrips)

        if sampleHit is not None:
            firstBlockLine, blockCol, cols, rows = sampleHit
            self._sampleStartLine = offset + firstBlockLine
            self._sampleBlockCol = blockCol
            self._sampleCols = cols
            self._sampleRows = rows

        else:
            self._sampleStartLine = -1

        offset = len(strips)
        gridStrips, _, hoverRegions = self._blockSection(
            "decode",
            (width, self._seedRevealAll, self._seedHoverIdx),
            lambda: _decodeBlock(self._words, self._seedRevealAll, self._seedHoverIdx),
            width,
        )
        strips.extend(gridStrips)

        self._hoverRegions = [
            (lineIdx + offset, colStart, colEnd, wordIdx)
            for (lineIdx, colStart, colEnd, _, wordIdx) in hoverRegions
        ]

        strips.extend(self._blockSection("paths", (width,), _filePathsBlock, width)[0])
        offset = len(strips)
        worksStrips, worksPlains = self._worksSection(width)
        strips.extend(worksStrips)

        self._versionRegion = None
        for i, plain in enumerate(worksPlains):
            hit = plain.find(MANUAL_DECODE_SINCE)
            if hit >= 0:
                start = hit - 1 if self._versionPhase != -1 else hit
                self._versionRegion = (offset + i, start, start + len(VERSION_HOVER_TEXT))
                break

        strips.append(BLANK_STRIP)
        offset = len(strips)
        licenseStrips, licensePlains = self._licenseSection(width)
        strips.extend(licenseStrips)

        self._nameRegion = None
        for i, plain in enumerate(licensePlains):
            hit = plain.find(LICENSE_NAME)
            if hit >= 0:
                start = hit - 1 if self._namePhase != -1 else hit
                self._nameRegion = (offset + i, start, start + len(NAME_HOVER_TEXT))
                break

        strips.append(BLANK_STRIP)
        strips.extend(self._footSection(width))
        self._linkEncodes(strips)

        return strips


    def _rebuild(self) -> None:
        """Every section is wrapped to the width, so a resize invalidates all of them at once."""
        try:
            log = self.query_one("#help-log", HelpLog)

        except Exception:
            return

        width = self._logWidth()
        if width != self._cacheWidth:
            self._segCache.clear()
            self._cacheWidth = width

        prevY = log.scroll_offset.y
        strips = self._composeStrips(width)
        widest = max((strip.cell_length for strip in strips), default=0)

        log.setLines(strips, widest)
        log.scroll_to(y=prevY, animate=False)