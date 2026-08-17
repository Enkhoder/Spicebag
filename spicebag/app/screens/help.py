######## LIBRARIES ########

from spicebag.constants.theme import (
    invertedGradientHex,
    bannerGradientHex,
    GRID_SIZES,
    C_WHITE, C_DIM, C_INP, C_IMG, C_WC, C_SUCC, C_FAIL,
    SCREENSHOT_KEY,
)
from spicebag.core.generator import ColorSpace, precomputeColorSpace, rerollCell
from spicebag.app.tree import RootNode, TreeNode, renderBlocks
from textual.scroll_view import ScrollView
from textual.app import ComposeResult
from typing import Optional, Sequence
from rich.console import Console
from textual.geometry import Size
from textual.screen import Screen
from rich.segment import Segment
from textual.strip import Strip
from rich.text import Text
from textual import events
import webbrowser
import time



######## PAGE CONTENT ########

HELP_DEMO_SEED = (
    "grape monster husband desert city near blast brown pigeon normal tired stem "
    "spot increase real simple slim word shell glove tortoise luggage meat castle"
)

PROSE = [
    "Spicebag conceals your seed phrase inside colored PNG cell grid. Colors can be interchanged, "
    "scattered, and reassembled, yet they would still be perfectly decodable to raw string, given "
    "another compatible images of the same seed phrase and salt.",
]

HOW_THIS_WORKS_ROWS = [
    [
        ("Each cell/tile is one word and has 8,192 possible colors", C_DIM),
        (" (16,777,216 colors / 2,048 words)", C_WHITE),
        (" for BIP39 and Electrum standards, or 16,384", C_DIM),
        (" (16,777,216 colors / 1,024 words)", C_WHITE),
        (" for SLIP39 standard.", C_DIM),
    ],
    [
        ("Additionally, image salting is possible through thick layers of encryption: ", C_DIM),
        ("Argon2id + HKDF + HMAC", C_WHITE),
        (". Different salts produce different possible color combinations per word. The number of "
         "possible colors per cell is called the block size.", C_DIM),
    ],
    [
        ("As a result, one seed phrase has ", C_DIM),
        ("~10^47 to 10^139", C_WHITE),
        (" possible configurations per unique salt, derived from ", C_DIM),
        ("blockSize^wordCount", C_WHITE),
        (".", C_DIM),
    ],
    [
        ("Remember that image encoding uses Argon2id? That means even if someone reverse-engineered "
         "this tool to brute-force image decoding, reaching sufficient FLOPS is impossible without "
         "wrecking their RAM; the hardware Argon2id heavily taxes per operation.", C_DIM),
    ],
    [
        ("TL;DR: barely noticeable for honest users, devastating for attackers trying to crack "
         "stolen images. RAMs are expensive, please don't try it on your PC. Peace.", C_DIM),
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
    ("F12",    C_DIM,   "Take SVG screenshot, anywhere"),
]

ENCODE_ROWS = [
    ("Image count", [("1-2000", C_INP)]),
    ("Word count",  [("12, 15, 18, 20, 21, 24, 33", C_INP)]),
    ("Seed phrase", [("Accepted standards: BIP39, Electrum, SLIP39", C_DIM)]),
    ("Salt",        [("Further masks your image. Optional but recommended, all Unicode allowed, "
                      "no character limit, no rules.", C_DIM)]),
    ("Cell size",   [("1-2000", C_INP)]),
    ("Save path",   SEE_FILE_PATHS),
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
    """Blank continuation line — the renderer only auto-spaces root-level
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


def _encodeBlock(colorSpace: Optional[ColorSpace], masked: bool) -> RootNode:
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
        )
        root.children.append(_branch(
            [("Try the image sample below. Click on a cell to reroll its color.", C_DIM)],
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
        _branch([("Salt used to encode the image", C_WHITE)]),
        _spacer(),
        _branch([("Decoded seed phrase from the image sample on ", C_DIM), ("ENCODE", C_IMG), (":", C_DIM)],
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


def _howThisWorksBlock() -> RootNode:
    root = RootNode(label=_mk([("HOW THIS WORKS", f"bold {C_WHITE}")]), bullet=C_WHITE)
    children: list[TreeNode] = []
    for i, segments in enumerate(HOW_THIS_WORKS_ROWS):
        if i > 0:
            children.append(_spacer())

        children.append(_note(segments))

    root.children = children
    return root


def nameHoverFrameCount() -> int:
    return 2 * (len(NAME_HOVER_TEXT) - 1)


def licenseLine(hoverPhase: int) -> Text:
    """License credit, with the author name swept by the same gradient
    highlight the mascot banner title uses while hovered, and the suffix
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
    """Full-width divider, re-coloured across the banner gradient on every
    rebuild so a resize re-spreads it over the new width."""
    text = Text(end="")
    for x in range(width):
        text.append("─", style=bannerGradientHex(x / max(1, width - 1)))

    return text




######## CLICKABLE LOG ########

# Shared separator line. Reused rather than rebuilt so the two blank rows around
# the license keep their identity between rebuilds, which is how the view tells
# an unchanged line from a stale one.
BLANK_STRIP = Strip.blank(0)


def renderStrips(lines: Sequence[Text], console: Console) -> list[Strip]:
    """Rasterize pre-wrapped lines into Strips, exactly one Strip per input line.

    Every line the tree renderer emits is already wrapped to the target width and
    carries no_wrap, so rendering each at its own cell length neither truncates
    nor pads it. The 1:1 mapping is load-bearing: hover and click regions address
    the document by line index, so a line that rasterized to two Strips (or none)
    would silently shift every region below it."""
    options = console.options.update(overflow="ignore", no_wrap=True)
    out: list[Strip] = []

    for line in lines:
        segments = console.render(line, options.update_width(max(1, line.cell_len)))
        strips = Strip.from_lines(list(Segment.split_lines(segments)))
        out.append(strips[0] if strips else Strip.blank(0))

    return out


class HelpLog(ScrollView):
    """Scrolling view over a pre-rasterized document, which forwards cell clicks
    and hovers (in virtual content coordinates) to the screen so the encode
    sample can re-roll a tile and the decode grid can reveal a word.

    A RichLog stood here until the document outgrew it. RichLog only appends, so
    every hover meant clearing it and re-writing all ~160 lines, and each write
    re-measured its line and reassigned virtual_size — 47ms per hover, which is
    what made the cursor stutter. Holding the Strips instead lets the screen swap
    in only the lines that changed."""

    ALLOW_SELECT = False

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._strips: list[Strip] = []
        self._lineCache: dict[tuple[int, int, int], Strip] = {}


    def setLines(self, strips: list[Strip], widest: int) -> None:
        """Swap in a new document, dropping only the cropped lines that moved.

        The screen hands back the identical Strip objects for every section it
        did not rebuild, so identity is enough to tell which lines are stale. A
        hover changes about ten of them, and the rest stay cropped and ready."""
        previous = self._strips

        if len(previous) != len(strips):
            self._lineCache.clear()

        else:
            stale = {i for i, (old, new) in enumerate(zip(previous, strips)) if old is not new}
            for key in [key for key in self._lineCache if key[0] in stale]:
                del self._lineCache[key]

        self._strips = strips
        self.virtual_size = Size(widest, len(strips))
        self.refresh()


    def notify_style_update(self) -> None:
        self._lineCache.clear()
        super().notify_style_update()


    def render_line(self, y: int) -> Strip:
        scrollX, scrollY = self.scroll_offset
        width = self.scrollable_content_region.width
        idx = scrollY + y

        key = (idx, scrollX, width)
        cached = self._lineCache.get(key)
        if cached is not None:
            return cached

        richStyle = self.rich_style
        if 0 <= idx < len(self._strips):
            strip = self._strips[idx].crop_extend(scrollX, scrollX + width, richStyle).apply_style(richStyle)

        else:
            strip = Strip.blank(width, richStyle)

        self._lineCache[key] = strip
        return strip


    def on_click(self, event: events.Click) -> None:
        event.stop()
        line = event.y + self.scroll_offset.y
        col = event.x + self.scroll_offset.x

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


    def on_leave(self, event: events.Leave) -> None:
        handler = getattr(self.screen, "_clearWordHover", None)
        if handler is not None:
            handler()



######## HELP SCREEN ########

class HelpScreen(Screen):
    """Self-contained, single-column guide shown over the menu. Any key returns,
    leaving the menu underneath exactly as it was, except F12 which takes an
    unmasked screenshot without closing the guide. The encode sample and decode
    grid are live and behave like their real counterparts on the main menu."""

    can_focus = False

    # Full-bleed: the log fills the screen with no padding/margin, so every line
    # starts at the window's left edge and runs to its right edge.
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
        super().__init__()
        self._readyAt = 0.0
        self._words = HELP_DEMO_SEED.split()

        # Interactive encode sample
        try:
            self._imgColorSpace: Optional[ColorSpace] = precomputeColorSpace(HELP_DEMO_SEED, "")

        except Exception:
            self._imgColorSpace = None

        self._imgTimer = None
        self._imgPausedUntil = 0.0      # auto-reshuffle suspended until this time
        self._imgMasked = False         # frozen, fully masked beat after the grace window
        self._imgRevision = 0           # bumped on every reroll, keys the sample's cache entry
        self._graceTimer = None
        self._maskTimer = None
        self._sampleStartLine = -1
        self._sampleBlockCol = 0
        self._sampleCols = 0
        self._sampleRows = 0

        # Interactive decode grid
        self._seedRevealAll = True      # everything shown until the first click
        self._seedHoverIdx = -1         # word revealed by cursor (hover or click)
        self._hoverRegions: list = []   # (lineIdx, colStart, colEnd, wordIdx)

        # Hovered author name in the license line
        self._namePhase = -1            # -1 = not hovered
        self._nameTimer = None
        self._nameRegion: Optional[tuple[int, int, int]] = None

        # Rasterized document, cached per section (see _section)
        self._segCache: dict[str, tuple] = {}
        self._cacheWidth = -1


    def compose(self) -> ComposeResult:
        log = HelpLog(id="help-log")
        log.can_focus = False
        yield log


    def on_mount(self) -> None:
        self._readyAt = time.time() + 0.25
        self._rebuild()
        # Whole-image reshuffle once per second (paused for 3s after a click).
        self._imgTimer = self.set_interval(1.0, self._imgTick)


    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()

        if event.key == SCREENSHOT_KEY:
            from spicebag.app.handlers.screenshot import generateScreenshotPath, executePrint
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

        if time.time() < self._readyAt:
            return

        if self._imgTimer is not None:
            self._imgTimer.stop()
            self._imgTimer = None

        self._stopTimer("_graceTimer")
        self._stopTimer("_maskTimer")
        self._stopTimer("_nameTimer")

        self.app.pop_screen()


    def on_resize(self, event: events.Resize) -> None:
        if self.is_mounted:
            self._rebuild()



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
        self._maskTimer = self.set_timer(2.0, self._exitMaskFreeze)
        self._rebuild()


    def _exitMaskFreeze(self) -> None:
        """Masked beat over: reshuffle once and hand the sample back to the
        ambient loop."""
        self._maskTimer = None
        self._imgMasked = False
        if self._imgColorSpace is None:
            return

        self._reshuffleAll()
        self._rebuild()

        # Re-anchor the ambient reshuffle clock to this moment, so the next
        # tick is a steady 1s away instead of wherever _imgTimer's on_mount
        # phase happens to land.
        self._stopTimer("_imgTimer")
        self._imgTimer = self.set_interval(1.0, self._imgTick)



    ######## INTERACTIVE SAMPLE ########

    def _handleSampleClick(self, line: int, col: int) -> None:
        """A click re-rolls only the clicked tile (same next-colour logic as the
        real confirm-step preview) and pauses auto-reshuffle for 3 seconds."""
        cs = self._imgColorSpace
        if cs is None or self._imgMasked or self._sampleStartLine < 0:
            return

        rowOff = line - self._sampleStartLine
        colOff = col - self._sampleBlockCol
        if rowOff < 0 or colOff < 0:
            return

        if rowOff >= self._sampleRows * 3 or colOff >= self._sampleCols * 6:
            return

        if not rerollCell(cs, rowOff // 3, colOff // 6):
            return

        self._imgRevision += 1
        self._imgPausedUntil = time.time() + 3.0
        self._stopTimer("_graceTimer")
        self._graceTimer = self.set_timer(3.0, self._enterMaskFreeze)
        self._rebuild()



    ######## DECODED SEED GRID / MASKED WORDS ########

    def _hitSeedWord(self, line: int, col: int) -> Optional[int]:
        for lineIdx, colStart, colEnd, wordIdx in self._hoverRegions:
            if line == lineIdx and colStart <= col < colEnd:
                return wordIdx

        return None


    def _handleSeedClick(self, wordIdx: int) -> None:
        if self._seedRevealAll:
            # All revealed → click masks the rest, showing just this word
            # (behaves exactly like hovering it).
            self._seedRevealAll = False
            self._seedHoverIdx = wordIdx

        else:
            # Masked → click reveals everything.
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

        if changed:
            self._rebuild()


    def _clearWordHover(self) -> None:
        changed = self._setNameHover(False)

        if self._seedHoverIdx != -1:
            self._seedHoverIdx = -1
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

        Most of the page — the command list, the path tables, the closing prose —
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
        click and hover geometry as each section lands at its final offset."""
        strips: list[Strip] = list(self._headSection(width))

        strips.extend(self._blockSection("commands", (width,), _commandsBlock, width)[0])

        offset = len(strips)
        sampleStrips, sampleHit, _ = self._blockSection(
            "encode",
            (width, self._imgMasked, self._imgRevision),
            lambda: _encodeBlock(self._imgColorSpace, self._imgMasked),
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
        strips.extend(self._blockSection("works", (width,), _howThisWorksBlock, width)[0])

        strips.append(BLANK_STRIP)
        offset = len(strips)
        licenseStrips, licensePlains = self._licenseSection(width)
        strips.extend(licenseStrips)

        # Anchor the hot zone on the highlight block, not the name, so it stays
        # put while the hovered name sits one cell to the right.
        self._nameRegion = None
        for i, plain in enumerate(licensePlains):
            hit = plain.find(LICENSE_NAME)
            if hit >= 0:
                start = hit - 1 if self._namePhase != -1 else hit
                self._nameRegion = (offset + i, start, start + len(NAME_HOVER_TEXT))
                break

        strips.append(BLANK_STRIP)
        strips.extend(self._footSection(width))

        return strips


    def _rebuild(self) -> None:
        try:
            log = self.query_one("#help-log", HelpLog)

        except Exception:
            return

        width = self._logWidth()
        if width != self._cacheWidth:
            # Every section is wrapped to the width, so a resize invalidates all
            # of them at once.
            self._segCache.clear()
            self._cacheWidth = width

        prevY = log.scroll_offset.y
        strips = self._composeStrips(width)
        widest = max((strip.cell_length for strip in strips), default=0)

        log.setLines(strips, widest)
        log.scroll_to(y=prevY, animate=False)