######## LIBRARIES ########

from spicebag.constants.theme import (
    invertedGradientHex,
    bannerGradientHex,
    GRID_SIZES,
    C_WHITE, C_DIM, C_INP, C_IMG, C_WC, C_SUCC, C_FAIL,
)
from spicebag.core.generator import ColorSpace, precomputeColorSpace, rerollCell
from spicebag.app.tree import RootNode, TreeNode, renderBlocks
from textual.app import ComposeResult
from typing import Optional, Sequence
from textual.widgets import RichLog
from textual.screen import Screen
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
LICENSE_SEPARATOR = " · "
LICENSE_SUFFIX = "Licensed under the MIT License."
LICENSE_HOVER_SUFFIX = "CTRL+click to view GitHub profile"
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
    ("ESC",    C_WHITE, "Spicebag's back button"),
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
    ("blank", C_DIM,
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
    ("blank", C_DIM,
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
    """License credit, with the author name swept by the same reverse-video
    gradient highlight the mascot banner title uses while hovered, and the
    suffix swapped to a ctrl+click hint. The highlight opens on the column the
    name starts at, so only the name slides one cell right — one of its two
    pad cells is taken out of the separator's leading space, keeping the dot."""
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
        text.append(char, style=f"bold reverse {bgHex}")

    text.append(LICENSE_SEPARATOR[1:] + LICENSE_HOVER_SUFFIX, style=C_WHITE)
    return text


def gradientRule(width: int) -> Text:
    """Full-width divider, re-coloured across the banner gradient on every
    rebuild so a resize re-spreads it over the new width."""
    text = Text(end="")
    for x in range(width):
        text.append("─", style=bannerGradientHex(x / max(1, width - 1)))

    return text


def buildBlocks(
    colorSpace: Optional[ColorSpace],
    masked: bool,
    words: Sequence[str],
    revealAll: bool,
    hoverIdx: int,
) -> list[RootNode]:
    return [
        _commandsBlock(),
        _encodeBlock(colorSpace, masked),
        _decodeBlock(words, revealAll, hoverIdx),
        _filePathsBlock(),
        _howThisWorksBlock(),
    ]



######## CLICKABLE LOG ########

class HelpLog(RichLog):
    """RichLog that forwards cell clicks / hovers (in virtual content
    coordinates) to the screen, so the encode sample can re-roll a tile and the
    decode grid can reveal a word."""

    ALLOW_SELECT = False

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
    leaving the menu underneath exactly as it was, except ctrl+s which takes an
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


    def compose(self) -> ComposeResult:
        log = HelpLog(id="help-log", wrap=False, highlight=False, markup=False)
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

        if event.key == "ctrl+s":
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
        """Grace window expired: freeze the sample fully masked for one second
        before letting the reshuffle loop take over again."""
        self._graceTimer = None
        if self._imgColorSpace is None:
            return

        self._imgMasked = True
        self._imgPausedUntil = 0.0
        self._maskTimer = self.set_timer(1.0, self._exitMaskFreeze)
        self._rebuild()


    def _exitMaskFreeze(self) -> None:
        # BUG: this reshuffle fires on the click-relative grace/mask timers, but
        # _imgTimer keeps ticking on its own phase from on_mount and is never
        # restarted here. The gap to the next ambient reshuffle can land anywhere
        # from ~0s to just under 1s depending on when the click happened, instead
        # of a steady 1s cadence. Cosmetic only, no functional impact — fix by
        # stopping and recreating _imgTimer at the end of this method so the
        # ambient clock re-anchors to the moment the sample becomes visible again.
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
            w = self.query_one("#help-log", RichLog).size.width

        except Exception:
            w = 0

        if w <= 0:
            w = self.app.size.width if self.app.size.width > 0 else 80

        return max(8, w)


    def _prose(self, lines: list, body: str, width: int, style: str = C_WHITE) -> None:
        text = Text(body, style=style)
        for wrapped in text.wrap(self.app.console, max(1, width)):
            lines.append(wrapped)


    def _composeLines(self, width: int) -> list:
        lines: list = [gradientRule(width)]
        for i, paragraph in enumerate(PROSE):
            if i > 0:
                lines.append(Text(""))

            self._prose(lines, paragraph, width)

        blocks = buildBlocks(
            self._imgColorSpace,
            self._imgMasked,
            self._words,
            self._seedRevealAll,
            self._seedHoverIdx,
        )
        blockLines, sampleHit, hoverRegions = renderBlocks(blocks, width, self.app.console)
        offset = len(lines)
        lines.extend(blockLines)

        if sampleHit is not None:
            firstBlockLine, blockCol, cols, rows = sampleHit
            self._sampleStartLine = offset + firstBlockLine
            self._sampleBlockCol = blockCol
            self._sampleCols = cols
            self._sampleRows = rows

        else:
            self._sampleStartLine = -1

        self._hoverRegions = [
            (lineIdx + offset, colStart, colEnd, wordIdx)
            for (lineIdx, colStart, colEnd, _, wordIdx) in hoverRegions
        ]

        lines.append(Text(""))
        licenseStart = len(lines)
        for wrapped in licenseLine(self._namePhase).wrap(self.app.console, max(1, width)):
            lines.append(wrapped)

        # Anchor the hot zone on the highlight block, not the name, so it stays
        # put while the hovered name sits one cell to the right.
        self._nameRegion = None
        for idx in range(licenseStart, len(lines)):
            hit = lines[idx].plain.find(LICENSE_NAME)
            if hit >= 0:
                start = hit - 1 if self._namePhase != -1 else hit
                self._nameRegion = (idx, start, start + len(NAME_HOVER_TEXT))
                break

        lines.append(Text(""))

        self._prose(lines, RETURN_LINE, width, C_DIM)

        return lines


    def _rebuild(self) -> None:
        try:
            log = self.query_one("#help-log", RichLog)

        except Exception:
            return

        prevY = log.scroll_offset.y
        lines = self._composeLines(self._logWidth())

        with self.app.batch_update():
            log.auto_scroll = False
            log.clear()
            for line in lines:
                log.write(line)

        log.scroll_to(y=prevY, animate=False)