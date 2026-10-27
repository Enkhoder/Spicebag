######## LIBRARIES ########

from spicebag.frontend.theme import (
    COMMANDS, BANNER_META_PREFIX, AppState, OUTPUT_DIR, IMAGES_DIR, SCREENSHOTS_DIR, DEFAULT_CELL_PX, PROGRESS_BAR_LENGTH,
    C_SUCC, C_FAIL, C_INP, C_IMG, C_WC, C_WHITE, C_DIM, getBannerMeta, metaHoverFrameCount, INPUT_FLASH_WIDGETS,
    parseHueRange, HOVERED_CELL_ROWS, MASKED_INPUT_STATES,
    blendHexColors, getMascotBanner, gradientColor, bannerGradientHex, ASCII_ART_BANNER, getNetworkText, getVersion,
    bannerHoverFrameCount, formatElapsed, matchCommand, SCREENSHOT_KEY, EXIT_ESC_WINDOW, LIMITED_TERMINAL_NOTICE
)
from spicebag.frontend.widgets.stripLog import StripLog, renderStrips, renderRenderable
from spicebag.frontend.screenshot import generateScreenshotPath, executePrint
from spicebag.frontend.tree import RootNode, TreeNode, renderBlocks
from spicebag.frontend.handlers.decode import DecodeHandlerMixin
from spicebag.frontend.handlers.encode import EncodeHandlerMixin
from spicebag.frontend.widgets.secureInput import SecureInput
from spicebag.frontend.widgets.optionsBar import OptionsBar
from spicebag.backend.defaults import GRID_SIZES
from spicebag.backend.paths import tildePath
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Rule
from textual.app import ComposeResult
from textual.reactive import reactive
from rich.measure import Measurement
from textual.screen import Screen
from rich.padding import Padding
from textual import events, work
from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
import asyncio
import json
import time



######## CLICKABLE LOG ########

class ClickableLog(StripLog):
    """Strip log that forwards cell clicks (in virtual content coordinates) to the
    screen so the interactive image sample can re-roll the clicked cell."""

    def on_click(self, event: events.Click) -> None:
        event.stop()
        line = event.y + self.scroll_offset.y
        col = event.x + self.scroll_offset.x

        sampleClick = getattr(self.screen, "_handleSampleClick", None)
        if sampleClick is not None:
            sampleClick(line, col)

        seedClick = getattr(self.screen, "_handleSeedClick", None)

        if seedClick is not None:
            seedClick(line, col)


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



######## MAIN SCREEN ########

class MainScreen(EncodeHandlerMixin, DecodeHandlerMixin, Screen):
    """Single keyboard-driven screen for all Spicebag operations."""

    can_focus = False
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        (SCREENSHOT_KEY, "printSvg", "Screenshot"),
        ("pageup", "pageUp", "Page up"),
        ("pagedown", "pageDown", "Page down")
    ]

    _wordCountFlashRatio = reactive(0.0)

    def __init__(self) -> None:
        self._state = AppState.IDLE
        self._wordCount = 0
        self._encodePassphrase = ""
        self._encodePhrase = ""
        self._encodeSeedType = ""
        self._encodeCount = 1
        self._encodeCellPx = DEFAULT_CELL_PX
        self._encodeSavePath = ""
        self._encodeFileStem = ""
        self._decodePath = ""
        self._decodePassphrase = ""
        self._decodeWordCount = 0
        self._decodeValidating = False
        self._decodeInProgress = False
        self._decodeAbortHandled = False
        self._decodeToken = 0
        self._readyAt = 0.0
        self._tabIndex = -1
        self._processing = False
        self._lastIdentifiedCommand = ""
        self._takingScreenshot = False
        self._justCleared = False
        self._useMascotBanner = True
        self._netState = (False, False, False)
        self._loadConfig()

        self._blocks: list[RootNode] = []
        self._welcome: list = []
        self._curRoot: RootNode | None = None
        self._curStep: TreeNode | None = None
        self._encodingNode: TreeNode | None = None
        self._typeClearNode: TreeNode | None = None

        self._shownPassphraseWarning = False
        self._anyCommandRun = False
        self._inputErrorTimer: asyncio.TimerHandle | None = None
        self._wordCountWarnTimer: asyncio.TimerHandle | None = None
        self._exitArmTimer: asyncio.TimerHandle | None = None
        self._loaderBaseMsgPlain = ""
        self._cancelFlag = False
        self._lastProgressRebuild: float = 0.0
        self._branchFlickerTimer: asyncio.TimerHandle | None = None
        self._branchFlickerState: bool = True
        self._branchFlickerPercent: float = 0.0
        self._encodeStartTime: float = 0.0
        self._encodeFinalElapsedMs: float | None = None

        self._mascotColPhases: list[int] = [0] * 10
        self._mascotAnimTimer: asyncio.TimerHandle | None = None
        self._mascotAnimActive: bool = False

        self._activeSeedNode: TreeNode | None = None
        self._activeInvalidNodes: list[TreeNode] = []
        self._seedRevealTimer: asyncio.TimerHandle | None = None
        self._hoverIdleTimer: asyncio.TimerHandle | None = None
        self._hoverRegions: list = []

        self._bannerHoverPhase: int = -1
        self._bannerHoverTimer: asyncio.TimerHandle | None = None

        self._colorSpace = None
        self._activeSampleNode: TreeNode | None = None
        self._precomputePending = False
        self._precomputeToken = 0
        self._confirmStepNode: TreeNode | None = None
        self._confirmBaseMarkup = ""
        self._spinnerFrame = 0
        self._spinnerTimer = None
        self._sampleStartLine = -1
        self._sampleBlockCol = 0
        self._sampleCols = 0
        self._sampleRows = 0
        self._hueCell: tuple[int, int] | None = None
        self._hueErrorText = ""
        self._hueErrorTimer: asyncio.TimerHandle | None = None
        self._hueBlinkTimer = None
        self._hueBlinkText = ""
        self._selectSweepTimer = None
        self._cellNav = False
        self._lastClickOnCell = False

        self._welcomeKey: tuple | None = None
        self._welcomeCache: list = []

        super().__init__()


    def compose(self) -> ComposeResult:
        with Vertical(id="app-container"):
            log = ClickableLog(id="terminal-log")
            log.can_focus = False
            yield log
            yield Rule(id="sep-bot")

            with Horizontal(id="input-bar"):
                yield Static("●", id="input-prompt")
                yield SecureInput(id="cmd-input", placeholder="")

            yield Rule(id="sep-status")
            yield OptionsBar(id="status-bar")


    def on_mount(self) -> None:
        from spicebag.frontend.utils.networkDetect import getNetworkState
        import threading

        self._netState = getNetworkState()
        threading.Thread(target=self._pollNetworkState, daemon=True).start()

        self._readyAt = time.time() + 0.5
        self._showWelcome()

        warningShots = getattr(self.app, "_warningScreenshots", [])
        if warningShots:
            self._addShotsBlock(warningShots, "during warning confirmation:")

        self._rebuild()
        self._updateStatusBar()
        self.query_one("#cmd-input", SecureInput).focus()


    def on_screen_resume(self) -> None:
        helpShots = getattr(self.app, "_helpScreenshots", [])
        if helpShots:
            self._attachHelpShots(helpShots)
            setattr(self.app, "_helpScreenshots", [])
            self._rebuild()



    ######## CONFIG ########

    def _loadConfig(self) -> None:
        configPath = OUTPUT_DIR / "bannerConfig"
        if configPath.exists():
            try:
                with open(configPath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._useMascotBanner = data.get("useMascotBanner", True)

            except Exception:
                pass


    def _saveConfig(self) -> None:
        configPath = OUTPUT_DIR / "bannerConfig"
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(configPath, "w", encoding="utf-8") as f:
                json.dump({"useMascotBanner": self._useMascotBanner}, f)

        except Exception:
            pass


    def watch__wordCountFlashRatio(self, value: float) -> None:
        try:
            self._updateStatusBar()

        except Exception:
            pass



    ######## ERROR / WARN FLASH ########

    def _setInputFlash(self, cssClass: str, ratio: str, on: bool) -> None:
        self.query(INPUT_FLASH_WIDGETS).set_class(on, cssClass)
        self.query_one("#cmd-input", SecureInput).animate(
            ratio,
            1.0 if on else 0.0,
            duration=0.1,
            easing="in_out_cubic"
        )


    def _clearInputError(self) -> None:
        """End a red flash now instead of when its timer runs out."""
        if self._inputErrorTimer is not None:
            self._inputErrorTimer.cancel()
            self._inputErrorTimer = None
            self._setInputFlash("input-error", "_errRatio", False)


    def _triggerInputError(self) -> None:
        if self._inputErrorTimer is not None:
            self._inputErrorTimer.cancel()

        self._setInputFlash("input-error", "_errRatio", True)
        self._inputErrorTimer = asyncio.get_event_loop().call_later(
            0.5,
            lambda: self._setInputFlash("input-error", "_errRatio", False)
        )


    def _triggerWordCountWarn(self) -> None:
        self.animate("_wordCountFlashRatio", 1.0, duration=0.1)

        if self._wordCountWarnTimer is not None:
            self._wordCountWarnTimer.cancel()

        def clearWarn() -> None:
            self.animate("_wordCountFlashRatio", 0.0, duration=0.1)

        self._wordCountWarnTimer = asyncio.get_event_loop().call_later(0.5, clearWarn)



    ######## PROGRESS LOADER ########

    def _progressText(self, percent: float) -> Text:
        barLen = PROGRESS_BAR_LENGTH
        out = Text()
        out.append(self._loaderBaseMsgPlain, style=C_WHITE)
        out.append("  ")

        totalLit = int(percent * barLen)
        for i in range(barLen):
            if i < totalLit:
                out.append("━", style=gradientColor(i / max(1, barLen - 1)))

            else:
                out.append("─", style=C_DIM)

        pctColor = gradientColor(percent)

        if self._encodeFinalElapsedMs is not None:
            elapsedMs = self._encodeFinalElapsedMs
            isFinal = True

        else:
            elapsedMs = (time.monotonic() - self._encodeStartTime) * 1000
            isFinal = False

        out.append("  ")

        out.append(f"{int(percent * 100)}%", style=pctColor)
        out.append("  ·  ", style=C_DIM)
        out.append(f"{formatElapsed(elapsedMs, isFinal)}", style=C_DIM)
        return out


    def _startLoader(self, baseMsgPlain: str) -> None:
        self._loaderBaseMsgPlain = baseMsgPlain
        self._lastProgressRebuild = 0.0
        self._cancelFlag = False
        self._encodeStartTime = time.monotonic()
        self._encodeFinalElapsedMs = None
        self._encodingNode = TreeNode(
            kind="branch", connStyle=C_DIM, text=self._progressText(0.0)
        )
        if self._curRoot is not None:
            self._curRoot.children.append(self._encodingNode)
            self._curStep = self._encodingNode

        self._startBranchFlicker()
        self._rebuild()
        self._updateUI()


    def _workerHooks(self):
        """Progress and cancel callbacks for a worker thread. Progress hops back to the UI thread; cancel reads
        the flag that typing cancel sets."""
        def progressCb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)


        def cancelCheck() -> bool:
            return self._cancelFlag

        return progressCb, cancelCheck


    def _updateProgress(self, percent: float) -> None:
        if not self._processing or self._encodingNode is None:
            return

        self._branchFlickerPercent = percent
        self._encodingNode.text = self._progressText(percent)

        now = time.monotonic()
        if now - self._lastProgressRebuild < 0.05:
            return

        self._lastProgressRebuild = now
        self._rebuild(scrollToEnd=False)


    def _stopLoader(self, warn: bool = False) -> None:
        self._stopBranchFlicker()
        if self._cancelFlag:
            return

        if self._encodingNode is None:
            return

        self._encodeFinalElapsedMs = (time.monotonic() - self._encodeStartTime) * 1000
        self._encodingNode.connStyle = C_DIM
        if not warn:
            self._encodingNode.text = self._progressText(1.0)

        self._rebuild()


    def _startBranchFlicker(self) -> None:
        self._branchFlickerState = True
        self._branchFlickerPercent = 0.0
        self._doFlicker()


    def _doFlicker(self) -> None:
        if self._encodingNode is None or not self._processing:
            return

        if self._branchFlickerState:
            color = gradientColor(self._branchFlickerPercent)

        else:
            color = C_DIM

        self._encodingNode.connStyle = color
        self._rebuild(scrollToEnd=False)

        self._branchFlickerState = not self._branchFlickerState
        self._branchFlickerTimer = asyncio.get_event_loop().call_later(0.5, self._doFlicker)


    def _stopBranchFlicker(self) -> None:
        if self._branchFlickerTimer is not None:
            self._branchFlickerTimer.cancel()
            self._branchFlickerTimer = None


    def _abortProcessing(self) -> None:
        self._cancelFlag = True

        if self._encodeFinalElapsedMs is None and self._encodeStartTime > 0:
            self._encodeFinalElapsedMs = (time.monotonic() - self._encodeStartTime) * 1000
            if self._encodingNode is not None:
                self._encodingNode.text = self._progressText(self._branchFlickerPercent)

        self.query_one("#cmd-input", SecureInput).value = ""

        if self._decodeInProgress:
            self._finalizeDecodeAbort()


    def _finalizeDecodeAbort(self) -> None:
        if self._decodeAbortHandled:
            return

        self._decodeAbortHandled = True

        self._stopBranchFlicker()
        if self._encodingNode is not None:
            self._encodingNode.connStyle = C_DIM

        self._processing = False
        self._decodeInProgress = False
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""

        self._addResult(Text("Operation aborted.", style=f"bold {C_FAIL}"), C_FAIL)

        self._encodingNode = None
        self._decodePath = ""
        self._decodePassphrase = ""
        self._setState(AppState.IDLE)

        try:
            self.query_one("#cmd-input", SecureInput).value = ""

        except Exception:
            pass

        self._rebuild()



    ######## RENDER ########

    def on_resize(self, event: events.Resize) -> None:
        if self.is_mounted:
            self._debouncedRender()


    @work(exclusive=True)
    async def _debouncedRender(self) -> None:
        """A resize keeps the view where it was. Only a view already at the bottom stays pinned there."""
        await asyncio.sleep(0)
        if not self.is_mounted:
            return

        log = self.query_one("#terminal-log", ClickableLog)
        prevY = log.scroll_offset.y
        atBottom = prevY >= log.max_scroll_y
        self._rebuild(scrollToEnd=atBottom)
        if not atBottom:
            log.scroll_to(y=prevY, animate=False)


    def _logWidth(self) -> int:
        try:
            w = self.query_one("#terminal-log", ClickableLog).size.width

        except Exception:
            w = 0

        if w <= 0:
            w = self.app.size.width if self.app.size.width > 0 else 80

        return w


    def _welcomeStrips(self, width: int) -> list:
        """Rasterize the banner once per distinct frame. The mascot sweep and the hover highlight
        change it ten times a second, and nothing else in the document moves with it. The ASCII art keeps
        its natural width in a narrow window, running off the right edge instead of wrapping into broken
        rows; everything else wraps as usual. The natural width is measured against a wide canvas, since
        Rich caps a measurement at the console's current width."""
        key = (
            width,
            self._useMascotBanner,
            tuple(self._mascotColPhases),
            self._bannerHoverPhase,
            self._netState
        )

        if self._welcomeKey != key:
            strips: list = []
            console = self.app.console
            for index, item in enumerate(self._welcome):
                renderable = Text.from_markup(item) if isinstance(item, str) else item
                itemWidth = width
                if index == 0 and not self._useMascotBanner:
                    natural = Measurement.get(console, console.options.update_width(10_000), renderable).maximum
                    itemWidth = max(width, natural)

                strips.extend(renderRenderable(renderable, itemWidth, console))

            self._welcomeKey = key
            self._welcomeCache = strips

        return self._welcomeCache


    def _freezeHistory(self) -> None:
        """Turn every block already on screen into a fixed picture.

        A finished block never changes again: its decoded words, invalid-word notes and image sample
        are masked for good by the time it gets here. Rendering it once and keeping the Strips means
        the history is never re-rendered on a later frame, and dropping the node tree means the
        masked content is no longer held in memory where a later read could recover it."""
        width = self._logWidth()
        console = self.app.console

        for block in self._blocks:
            if block.frozenLines is not None:
                continue

            lines, _, _ = renderBlocks([block], width, console)
            block.frozenLines = lines
            block.frozenStrips = renderStrips(lines, console)
            block.frozenWidth = width
            block.label = Text()
            block.children = []


    def _blockStrips(self, block: RootNode, width: int) -> list:
        """Strips for a frozen block, re-wrapped only when the terminal grew narrower than the width
        the block was captured at."""
        if block.frozenStrips is not None and block.frozenWidth == width:
            return block.frozenStrips

        lines: list[Text] = []
        for line in block.frozenLines or []:
            lines.extend(line.wrap(self.app.console, width) if line.cell_len > width else [line])

        block.frozenStrips = renderStrips(lines, self.app.console)
        block.frozenWidth = width
        return block.frozenStrips


    def _rebuild(self, scrollToEnd: bool = True) -> None:
        try:
            log = self.query_one("#terminal-log", ClickableLog)

        except Exception:
            return

        width = self._logWidth()
        strips = list(self._welcomeStrips(width))
        live = []

        for block in self._blocks:
            if block.frozenLines is None:
                live.append(block)

            else:
                strips.extend(self._blockStrips(block, width))

        offset = len(strips)
        lines, sampleHit, hoverRegions = renderBlocks(live, width, self.app.console)
        strips.extend(renderStrips(lines, self.app.console))

        self._hoverRegions = [
            (lineIdx + offset, colStart, colEnd, node, wordIdx)
            for (lineIdx, colStart, colEnd, node, wordIdx) in hoverRegions
        ]

        if sampleHit is not None:
            firstBlockLine, blockCol, cols, rows = sampleHit
            self._sampleStartLine = offset + firstBlockLine
            self._sampleBlockCol = blockCol
            self._sampleCols = cols
            self._sampleRows = rows

        else:
            self._sampleStartLine = -1

        log.setLines(strips, max((strip.cell_length for strip in strips), default=0))

        if scrollToEnd:
            log.scrollToEnd()



    ######## INTERACTIVE SAMPLE ########

    def _sampleCellAt(self, line: int, col: int) -> tuple[int, int] | None:
        """The clickable sample cell under a document position, if any."""
        node = self._activeSampleNode
        if node is None or self._colorSpace is None:
            return None

        if not node.sampleClickable or node.sampleMasked or self._sampleStartLine < 0:
            return None

        rowOff = line - self._sampleStartLine
        colOff = col - self._sampleBlockCol
        if rowOff < 0 or colOff < 0 or rowOff >= self._sampleRows * 3 or colOff >= self._sampleCols * 6:
            return None

        return rowOff // 3, colOff // 6


    def _handleSampleClick(self, line: int, col: int) -> None:
        """The first click on a cell only selects it, and with a valid hue range in the input bar keeps that range
        for it and restarts the blink. Clicks on the selected cell reroll it, inside its range if it has one."""
        cell = self._sampleCellAt(line, col)
        if cell is None:
            return

        from spicebag.backend.generator import rerollCell

        self._cellNav = True
        self._lastClickOnCell = True
        if cell != self._hueCell:
            self._selectSampleCell(cell)
            return

        text = self.query_one("#cmd-input", SecureInput).value
        hueRange = parseHueRange(text, final=True) if text.strip() else None
        if isinstance(hueRange, tuple) and self._colorSpace.hueRanges.get(cell) != hueRange:
            self._initHueRange(cell, hueRange, text)
            return

        if not rerollCell(self._colorSpace, *cell):
            return

        self._rebuild(scrollToEnd=False)


    def _selectSampleCell(self, cell: tuple[int, int]) -> None:
        """Select a cell without recoloring it. With a valid hue range in the input bar, the cell keeps that range
        and the blink restarts."""
        text = self.query_one("#cmd-input", SecureInput).value
        hueRange = parseHueRange(text, final=True) if text.strip() else None

        self._stopHueBlink()
        self._hueCell = cell
        self._setSampleSelection(cell)
        if isinstance(hueRange, tuple) and self._colorSpace.hueRanges.get(cell) == hueRange:
            self._startHueBlink(text)

        elif isinstance(hueRange, tuple):
            self._initHueRange(cell, hueRange, text)

        self._rebuild(scrollToEnd=False)


    def _onInputBarClick(self) -> None:
        """Clicking the bar hands the arrow keys back to the text and drops the cell selection, so the cells return
        to normal until one is selected again."""
        self._cellNav = False
        self._lastClickOnCell = False
        if self._hueCell is not None:
            self._hueCell = None
            self._stopHueBlink()
            self._setSampleSelection(None)
            self._rebuild(scrollToEnd=False)

        else:
            self._updateUI()


    def _moveSampleSelection(self, rowStep: int, colStep: int) -> None:
        """Arrow keys step the selection one cell, wrapping around each edge of the grid."""
        if self._hueCell is None or self._colorSpace is None:
            return

        row, col = self._hueCell
        self._selectSampleCell(
            ((row + rowStep) % self._colorSpace.rows, (col + colStep) % self._colorSpace.cols)
        )


    def _setSampleSelection(self, cell: tuple[int, int] | None) -> None:
        """Show the selected cell over a brand gradient that sweeps back and forth once a second."""
        node = self._activeSampleNode
        if node is not None:
            node.sampleSelected = cell

        self._updateUI()
        if cell is None:
            if self._selectSweepTimer is not None:
                self._selectSweepTimer.stop()
                self._selectSweepTimer = None

            return

        if self._selectSweepTimer is None:
            frames = 2 * (len(HOVERED_CELL_ROWS[0]) - 1)
            self._selectSweepTimer = self.set_interval(1.0 / frames, self._tickSampleSelection)


    def _tickSampleSelection(self) -> None:
        node = self._activeSampleNode
        if node is None or node.sampleSelected is None:
            return

        node.sampleSelectPhase = (node.sampleSelectPhase + 1) % (2 * (len(HOVERED_CELL_ROWS[0]) - 1))
        self._rebuild(scrollToEnd=False)


    def _hueInputActive(self) -> bool:
        """A hue range can be typed at the single-image confirm step once its sample is shown and clickable."""
        node = self._activeSampleNode
        return (
            self._state == AppState.ENCODE_CONFIRM
            and not self._processing
            and node is not None
            and node.sampleClickable
            and not node.sampleMasked
        )


    def _showHueError(self, message: str) -> None:
        """Flash the input bar and swap the image stats in the status bar for the message for one second."""
        self._triggerInputError()
        self._hueErrorText = message
        if self._hueErrorTimer is not None:
            self._hueErrorTimer.cancel()

        self._hueErrorTimer = asyncio.get_event_loop().call_later(1.0, self._clearHueError)
        self._updateStatusBar()


    def _clearHueError(self) -> None:
        if self._hueErrorTimer is not None:
            self._hueErrorTimer.cancel()
            self._hueErrorTimer = None

        if self._hueErrorText:
            self._hueErrorText = ""
            self._updateStatusBar()


    def _startHueBlink(self, text: str) -> None:
        self._stopHueBlink()
        self._clearHueError()
        self._clearInputError()
        self._hueBlinkText = text
        self._setInputFlash("hue-accepted", "_hueRatio", True)
        self._hueBlinkTimer = self.set_interval(0.5, self._toggleHueBlink)


    def _toggleHueBlink(self) -> None:
        on = not self.query_one("#cmd-input", SecureInput).has_class("hue-accepted")
        self._setInputFlash("hue-accepted", "_hueRatio", on)


    def _stopHueBlink(self) -> None:
        if self._hueBlinkTimer is None:
            return

        self._hueBlinkTimer.stop()
        self._hueBlinkTimer = None
        self._hueBlinkText = ""
        self._setInputFlash("hue-accepted", "_hueRatio", False)


    def _maskActiveSample(self, dropColorSpace: bool = True) -> None:
        node = self._activeSampleNode
        self._activeSampleNode = None
        if dropColorSpace:
            self._colorSpace = None

        self._sampleStartLine = -1
        self._hueCell = None
        self._cellNav = False
        self._lastClickOnCell = False
        self._setSampleSelection(None)
        self._stopHueBlink()

        if node is not None:
            node.sampleMasked = True
            node.sampleClickable = False
            self._rebuild(scrollToEnd=False)



    ######## DECODED SEED GRID / MASKED WORDS ########

    def _showSeedGrid(self, words: list[str], seedType: str = "") -> None:
        cols, rows = GRID_SIZES.get(len(words), (1, len(words)))
        typeLabel = f" {seedType}" if seedType else ""
        header = Text(f"{len(words)}-word{typeLabel} seed phrase recovered:", style=f"bold {C_SUCC}")
        resultBranch = TreeNode(kind="branch", text=header, connStyle=C_SUCC)
        seedNode = TreeNode(
            kind="seedgrid", words=list(words), cols=cols, rows=rows,
            connStyle=C_DIM, interactive=True, revealAll=True, hoverIdx=-1,
        )

        parent = self._encodingNode if self._encodingNode is not None else self._curStep
        if parent is not None:
            parent.children.append(resultBranch)
            parent.children.append(seedNode)

        self._activeSeedNode = seedNode
        self._rebuild()
        self._scheduleSeedMask(seedNode)


    def _scheduleSeedMask(self, node: TreeNode) -> None:
        if self._seedRevealTimer is not None:
            self._seedRevealTimer.cancel()

        self._seedRevealTimer = asyncio.get_event_loop().call_later(
            3.0, lambda: self._endSeedReveal(node)
        )


    def _endSeedReveal(self, node: TreeNode) -> None:
        self._seedRevealTimer = None
        if node.interactive and node.revealAll:
            node.revealAll = False
            self._rebuild(scrollToEnd=False)


    def _addInvalidWordsNote(self, words: list[str], prefix: str = "") -> None:
        if self._curStep is not None:
            node = TreeNode(
                kind="invalidnote", words=list(words), prefixMsg=prefix,
                interactive=True, hoverIdx=-1,
            )
            self._curStep.children.append(node)
            self._activeInvalidNodes.append(node)

        self._rebuild()


    def _maskActiveSeed(self) -> None:
        changed = False

        if self._activeSeedNode is not None:
            self._activeSeedNode.interactive = False
            self._activeSeedNode.revealAll = False
            self._activeSeedNode.hoverIdx = -1
            self._activeSeedNode = None
            changed = True

        if self._maskActiveInvalidNode():
            changed = True

        if changed:
            if self._seedRevealTimer is not None:
                self._seedRevealTimer.cancel()
                self._seedRevealTimer = None

            self._rebuild(scrollToEnd=False)


    def _maskActiveInvalidNode(self) -> bool:
        if not self._activeInvalidNodes:
            return False

        for node in self._activeInvalidNodes:
            node.interactive = False
            node.hoverIdx = -1

        self._activeInvalidNodes = []
        return True


    def _handleSeedClick(self, line: int, col: int) -> None:
        node = self._activeSeedNode
        if node is None or not node.interactive:
            return

        hit = any(
            r[3] is node and r[0] == line and r[1] <= col < r[2]
            for r in self._hoverRegions
        )
        if not hit:
            return

        node.revealAll = True
        self._scheduleSeedMask(node)
        self._rebuild(scrollToEnd=False)


    def _uniqueHoverNodes(self) -> list[TreeNode]:
        nodes: list[TreeNode] = []
        seen: set[int] = set()
        for region in self._hoverRegions:
            node = region[3]
            if id(node) not in seen:
                seen.add(id(node))
                nodes.append(node)

        return nodes


    def _handleWordHover(self, line: int, col: int) -> None:
        """The idle timer restarts on every movement over a word, even when the hovered word stays the same."""
        target: tuple[TreeNode, int] | None = None

        for regionLine, colStart, colEnd, node, wordIdx in self._hoverRegions:
            if line == regionLine and colStart <= col < colEnd:
                target = (node, wordIdx)
                break

        timer = self._hoverIdleTimer
        if timer is not None:
            try:
                timer.cancel()

            except Exception:
                pass

            self._hoverIdleTimer = None

        if target is not None:
            self._hoverIdleTimer = asyncio.get_event_loop().call_later(3.0, self._clearWordHover)

        versionStr = getVersion()
        if self._useMascotBanner:
            bannerLine = 1
            startCol = 16
            endCol = 25 + len(versionStr)

        else:
            bannerLine = len(ASCII_ART_BANNER.strip("\n").split("\n"))
            startCol = 2 + len(BANNER_META_PREFIX)
            endCol = startCol + len(versionStr) + (2 if self._bannerHoverPhase != -1 else 0)

        self._setBannerHover(line == bannerLine and startCol <= col <= endCol)

        changed = self._setSampleHover(self._sampleCellAt(line, col))

        for node in self._uniqueHoverNodes():
            want = target[1] if (target is not None and target[0] is node) else -1
            if node.hoverIdx != want:
                node.hoverIdx = want
                changed = True

        if changed:
            self._rebuild(scrollToEnd=False)


    def _setSampleHover(self, cell: tuple[int, int] | None) -> bool:
        """Mark the hovered sample cell. Returns whether it changed."""
        node = self._activeSampleNode
        if node is None or node.sampleHover == cell:
            return False

        node.sampleHover = cell
        return True


    def _clearWordHover(self) -> None:
        self._setBannerHover(False)
        changed = self._setSampleHover(None)

        for node in self._uniqueHoverNodes():
            if node.hoverIdx != -1:
                node.hoverIdx = -1
                changed = True

        if changed:
            self._rebuild(scrollToEnd=False)


    def _onAppBlur(self) -> None:
        timer = self._hoverIdleTimer
        if timer is not None:
            try:
                timer.cancel()

            except Exception:
                pass

            self._hoverIdleTimer = None

        self._clearWordHover()



    ######## WELCOME ########

    def _showWelcome(self) -> None:
        from spicebag.frontend.utils.limitedTerminal import getLimitedTerminal

        if self._useMascotBanner:
            self._mascotColPhases = [0] * 10
            self._welcome = [getMascotBanner(self._netState, self._mascotColPhases, self._bannerHoverPhase)]
            self._startMascotAnimation()

        else:
            self._stopMascotAnimation()
            self._welcome = [
                self._getGradientBanner(),
                self._indented(getBannerMeta(self._bannerHoverPhase)),
                self._indented(getNetworkText(self._netState)),
            ]

        limitedTerminal = getLimitedTerminal()
        if limitedTerminal is not None:
            name = f" ({limitedTerminal})" if limitedTerminal else ""
            notice = Padding(Text(LIMITED_TERMINAL_NOTICE.format(terminal=name), style=C_DIM), (0, 0, 0, 2))
            self._welcome += ["", notice]


    def _pollNetworkState(self) -> None:
        from spicebag.frontend.utils.networkDetect import getNetworkState
        import sys

        netState = getNetworkState()
        self.app.call_from_thread(self._updateNetworkState, netState)

        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            iphlpapi = ctypes.windll.Iphlpapi

            while True:
                handle = wintypes.HANDLE()
                iphlpapi.NotifyAddrChange(ctypes.byref(handle), None)
                netState = getNetworkState()
                try:
                    self.app.call_from_thread(self._updateNetworkState, netState)

                except Exception:
                    pass

        else:
            while True:
                time.sleep(2)
                netState = getNetworkState()
                try:
                    self.app.call_from_thread(self._updateNetworkState, netState)

                except Exception:
                    pass


    def _updateNetworkState(self, netState: tuple[bool, bool, bool]) -> None:
        if self._netState != netState:
            self._netState = netState

            if not self._welcome:
                return

            if self._useMascotBanner:
                self._welcome[0] = getMascotBanner(netState, self._mascotColPhases, self._bannerHoverPhase)

            elif len(self._welcome) > 2:
                self._welcome[2] = self._indented(getNetworkText(netState))

            self._rebuild(scrollToEnd=False)


    @staticmethod
    def _indented(markup: str) -> Padding:
        """A two-cell left margin that wrapped lines keep as well."""
        return Padding(Text.from_markup(markup), (0, 0, 0, 2))


    def _getGradientBanner(self) -> str:
        lines = ASCII_ART_BANNER.strip("\n").split("\n")
        maxW = max(len(l) for l in lines)
        result = []

        for line in lines:
            styledLine = "  "
            for x, char in enumerate(line):
                if char.isspace():
                    styledLine += char
                    continue

                styledLine += f"[{bannerGradientHex(x / max(1, maxW - 1))}]{char}[/]"

            result.append(styledLine)

        return "\n".join(result)



    ######## MASCOT ANIMATION ########

    def _startMascotAnimation(self) -> None:
        self._stopMascotAnimation()
        self._mascotAnimActive = True
        self._scheduleMascotStep(3.0, True, 9)


    def _stopMascotAnimation(self) -> None:
        self._mascotAnimActive = False
        if self._mascotAnimTimer is not None:
            self._mascotAnimTimer.cancel()
            self._mascotAnimTimer = None


    def _scheduleMascotStep(self, delay: float, toInverted: bool, col: int) -> None:
        loop = asyncio.get_event_loop()
        self._mascotAnimTimer = loop.call_later(delay, self._mascotStep, toInverted, col)


    def _mascotStep(self, toInverted: bool, col: int) -> None:
        if not self._mascotAnimActive:
            return

        self._mascotColPhases[col] = 1 if toInverted else 0
        self._refreshMascotBanner()
        if toInverted:
            if col > 0:
                self._scheduleMascotStep(0.1, True, col - 1)

            else:
                self._scheduleMascotStep(3.0, False, 0)

        else:
            if col < 9:
                self._scheduleMascotStep(0.1, False, col + 1)

            else:
                self._scheduleMascotStep(3.0, True, 9)


    def _refreshMascotBanner(self) -> None:
        if not self._welcome or not self._useMascotBanner:
            return

        self._welcome[0] = getMascotBanner(self._netState, self._mascotColPhases, self._bannerHoverPhase)
        self._rebuild(scrollToEnd=False)


    def _refreshBanner(self) -> None:
        if self._useMascotBanner:
            self._refreshMascotBanner()
            return

        if len(self._welcome) < 2:
            return

        self._welcome[1] = self._indented(getBannerMeta(self._bannerHoverPhase))
        self._rebuild(scrollToEnd=False)


    def _setBannerHover(self, hovered: bool) -> None:
        if hovered:
            if self._bannerHoverPhase == -1:
                self._bannerHoverPhase = 0
                self._refreshBanner()
                if self._bannerHoverTimer is None:
                    self._bannerHoverTimer = asyncio.get_event_loop().call_later(0.1, self._bannerHoverTick)

        else:
            if self._bannerHoverPhase != -1:
                self._bannerHoverPhase = -1
                self._refreshBanner()
                if self._bannerHoverTimer is not None:
                    self._bannerHoverTimer.cancel()
                    self._bannerHoverTimer = None


    def _bannerHoverTick(self) -> None:
        if self._bannerHoverPhase != -1:
            frameCount = bannerHoverFrameCount() if self._useMascotBanner else metaHoverFrameCount()
            self._bannerHoverPhase = (self._bannerHoverPhase + 1) % frameCount
            self._refreshBanner()
            self._bannerHoverTimer = asyncio.get_event_loop().call_later(0.05, self._bannerHoverTick)



    ######## TREE API ########

    def _newRoot(self, label: Text, bullet: str = C_WHITE, kind: str = "command") -> RootNode:
        root = RootNode(label=label, bullet=bullet, kind=kind)
        self._blocks.append(root)
        self._curRoot = root
        self._curStep = None
        return root


    def _addStep(self, markup: str, connStyle: str = C_DIM) -> TreeNode:
        node = TreeNode(kind="branch", text=Text.from_markup(markup), connStyle=connStyle)
        if self._curRoot is not None:
            self._curRoot.children.append(node)

        self._curStep = node
        self._rebuild()
        return node


    def _addAnswer(self, value: str, style: str = f"bold {C_INP}", connStyle: str = C_DIM) -> None:
        if self._curStep is not None:
            self._curStep.children.append(
                TreeNode(kind="branch", text=Text(value, style=style), connStyle=connStyle)
            )

        self._rebuild()


    def _addDashbar(self, connStyle: str = C_INP) -> None:
        if self._curStep is not None:
            inquiryLen = cell_len(self._curStep.text.plain.rstrip())
            barWidth = inquiryLen
            self._curStep.children.append(
                TreeNode(kind="dashbar", connStyle=connStyle, barWidth=barWidth)
            )

        self._rebuild()


    def _addNote(self, content: str | Text) -> None:
        if self._curStep is not None:
            text = Text.from_markup(content) if isinstance(content, str) else content
            self._curStep.children.append(TreeNode(kind="note", text=text))

        self._rebuild()


    def _addResult(self, text: str | Text, connStyle: str, body: list[Text] | None = None) -> None:
        """Append a result branch (Success / error / Decoded …) under the active
        encoding/decoding node, or the current step as a fallback."""
        parent = self._encodingNode if self._encodingNode is not None else self._curStep
        if parent is not None:
            t = Text.from_markup(text) if isinstance(text, str) else text
            parent.children.append(TreeNode(
                kind="branch", text=t, connStyle=connStyle, body=body or []
            ))

        self._rebuild()


    def _promptMarkup(self, state: AppState) -> str:
        if state == AppState.ENCODE_COUNT:
            return (f"[{C_WHITE}]How many images to generate? "
                    f"([bold]ENTER[/] for one)[/]")

        if state == AppState.ENCODE_PHRASE:
            return f"[{C_WHITE}]Seed phrase goes here.[/]"

        if state == AppState.ENCODE_PASSPHRASE:
            return (f"[{C_WHITE}]Enter image passphrase. "
                    f"(highly recommended, [bold]ENTER[/] for none)[/]")

        if state == AppState.ENCODE_PASSPHRASE_CONFIRM:
            return f"[{C_WHITE}]Confirm image passphrase.[/]"

        if state == AppState.ENCODE_CELL:
            return (f"[{C_WHITE}]Set cell size in pixels. "
                    f"([bold]ENTER[/] for 100×100px)[/]")

        if state == AppState.ENCODE_SAVE_PATH:
            return (f"[{C_WHITE}]Save path goes here. "
                    f"([bold]ENTER[/] for default)[/]")

        if state == AppState.ENCODE_CONFIRM:
            if self._encodeCount == 1:
                return (f"[{C_WHITE}]Proceed to generate this image?")

            return (f"[{C_WHITE}]Proceed to generate {self._encodeCount} images?")

        if state == AppState.DECODE_PATH:
            return f"[{C_WHITE}]Enter path to encoded image.[/]"

        if state == AppState.DECODE_PASSPHRASE:
            return (f"[{C_WHITE}]Image passphrase goes here. "
                    f"([bold]ENTER[/] if none were given)[/]")

        if state == AppState.DECODE_CONFIRM:
            return (f"[{C_WHITE}]Proceed to recover image?")

        if state == AppState.BANNER_CONFIRM:
            nextLabel = "mascot" if not self._useMascotBanner else "ASCII"
            return (f"[{C_WHITE}]Switch to {nextLabel} banner? "
                    f"Contents will be cleared.[/]")

        return ""



    ######## SCREENSHOT BLOCKS ########

    def _fileNode(self, filename: str) -> TreeNode:
        fileUri = (SCREENSHOTS_DIR / filename).as_uri()
        text = Text(filename, style=Style(color=C_IMG, link=fileUri))
        return TreeNode(kind="branch", text=text)


    def _clearTypeClearHint(self) -> None:
        if self._typeClearNode is not None:
            self._typeClearNode.hints = []
            self._typeClearNode = None


    def _addShotsBlock(self, shots: list[str], suffix: str) -> None:
        plural = "Screenshots" if len(shots) > 1 else "Screenshot"
        root = self._newRoot(
            Text.from_markup(f"[{C_WHITE}]{plural} taken {suffix}[/]"),
            bullet=C_IMG, kind="screenshot",
        )
        for shot in shots:
            node = self._fileNode(shot)
            node.connStyle = C_IMG
            root.children.append(node)

        root.children[-1].hints = [
            Text.from_markup(f"[{C_DIM}]Type [bold]clear[/] to remove this message.[/]")
        ]
        self._typeClearNode = root.children[-1]
        self._curRoot = None


    def _attachHelpShots(self, shots: list[str]) -> None:
        if not self._blocks:
            return

        helpRoot = self._blocks[-1]
        plural = "Screenshots" if len(shots) > 1 else "Screenshot"
        header = TreeNode(
            kind="branch",
            text=Text.from_markup(f"[{C_WHITE}]{plural} taken in help page:[/]"),
        )
        for shot in shots:
            node = self._fileNode(shot)
            node.connStyle = C_IMG
            header.children.append(node)

        helpRoot.children.append(header)
        self._curRoot = None
        self._curStep = None


    def _emitScreenshotSaved(self, filename: str, inline: bool) -> None:
        """Mid-operation, the shot attaches inline under the active step. Consecutive shots merge into one group
        there, and into one block at the idle menu."""
        self._clearTypeClearHint()

        if inline:
            step = self._curStep
            if step is None:
                return

            last = step.children[-1] if step.children else None
            if last is not None and last.kind == "shotgroup":
                last.children.append(self._fileNode(filename))
                last.text = Text.from_markup(f"[{C_WHITE}]Screenshots taken and saved:[/]")

            else:
                group = TreeNode(
                    kind="shotgroup",
                    text=Text.from_markup(f"[{C_WHITE}]Screenshot taken and saved:[/]"),
                )
                group.children.append(self._fileNode(filename))
                step.children.append(group)

            self._rebuild()
            return

        def _objFileNode(name: str) -> TreeNode:
            node = self._fileNode(name)
            node.connStyle = C_IMG
            return node

        last = self._blocks[-1] if self._blocks else None
        if last is not None and last.kind == "shortcut" and last.frozenLines is None:
            last.children.append(_objFileNode(filename))
            last.label = Text.from_markup(f"[{C_WHITE}]Screenshots taken and saved:[/]")

        else:
            root = self._newRoot(
                Text.from_markup(f"[{C_WHITE}]Screenshot taken and saved:[/]"),
                bullet=C_IMG, kind="shortcut",
            )
            root.children.append(_objFileNode(filename))
            self._curRoot = None

        self._rebuild()


    def _emitScreenshotError(self, message: str) -> None:
        self._newRoot(Text(message, style=f"bold {C_FAIL}"), bullet=C_FAIL, kind="screenshot")
        self._curRoot = None
        self._rebuild()



    ######## STATUS / UI ########

    def _statusText(self) -> str | Text:
        if self._state == AppState.BANNER_CONFIRM:
            currentStyle = "Spicebag mascot" if self._useMascotBanner else "ASCII art"
            return (
                f"[{C_DIM}]Current banner style: [{C_WHITE}]{currentStyle}[/]  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to cancel[/]"
            )

        if self._state == AppState.ENCODE_COUNT:
            return (
                f"[{C_DIM}]Enter number of images to generate  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to cancel[/]"
            )

        if self._state == AppState.ENCODE_PHRASE:
            try:
                typed = self.query_one("#cmd-input", SecureInput).value
                n = len(typed.split()) if typed.strip() else 0

            except Exception:
                n = 0

            nColor = blendHexColors(C_WHITE, C_FAIL, self._wordCountFlashRatio)
            return (
                f"[{C_DIM}]Word [{nColor}]{n}[/]  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state in (AppState.ENCODE_PASSPHRASE, AppState.ENCODE_PASSPHRASE_CONFIRM):
            return (
                f"[{C_DIM}]Passphrase adds significant entropy to raw images  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state == AppState.DECODE_PASSPHRASE:
            return (
                f"[{C_DIM}]Image cannot be decoded if the passphrase is lost  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state == AppState.ENCODE_CELL:
            return (
                f"[{C_DIM}]Tip: Cell size as small as 1px can be hidden among high-res photo noises  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state in (AppState.ENCODE_SAVE_PATH, AppState.DECODE_PATH):
            return Text.assemble(
                ("Press ", C_DIM),
                ("help", Style(color=C_DIM, bold=True)),
                (" on the menu navbar later for a guide to custom saves  ", C_DIM),
                ("·", C_DIM),
                ("  ", ""),
                ("ESC", f"bold {C_FAIL}"),
                (" to undo", C_FAIL)
            )

        if self._state == AppState.ENCODE_CONFIRM:
            if self._hueErrorText:
                return f"[{C_FAIL}]{self._hueErrorText}[/]"

            cols, rows = GRID_SIZES.get(self._wordCount, (4, 6))
            imgW = cols * self._encodeCellPx
            imgH = rows * self._encodeCellPx
            passphraseStr = "true" if self._encodePassphrase else "false"
            passphraseColor = C_SUCC if self._encodePassphrase else C_FAIL

            base = (
                f"[{C_DIM}]Seed type: [/][{C_IMG}]{self._encodeSeedType}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Seed words: [/][{C_WC}]{self._wordCount}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Passphrase: [/][{passphraseColor}]{passphraseStr}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Size: [/][{C_INP}]{imgW}×{imgH}[/]"
            )
            if self._processing:
                return base

            return base + f"  [{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"

        if self._state == AppState.DECODE_CONFIRM:
            wordCount = self._decodeWordCount
            passphraseStr = "true" if self._decodePassphrase else "false"
            passphraseColor = C_SUCC if self._decodePassphrase else C_FAIL

            base = (
                f"[{C_DIM}]Seed words: [/][{C_WC}]{wordCount}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Passphrase: [/][{passphraseColor}]{passphraseStr}[/]"
            )
            if self._processing:
                return base

            return base + f"  [{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"

        return ""


    def _updateStatusBar(self) -> None:
        try:
            bar = self.query_one("#status-bar", OptionsBar)

        except Exception:
            return

        if self._state == AppState.IDLE:
            if self._exitArmTimer is not None:
                bar.setStatic(f"[{C_FAIL}][bold]ESC[/] again to exit[/]")
                return

            bar.setInteractive(COMMANDS, self._tabIndex)
            return

        bar.setStatic(self._statusText())


    def cycleCommands(self) -> None:
        """Cycle through the main commands using TAB. At a seed phrase or passphrase prompt TAB shows or hides the
        input instead, leaving its text and cursor untouched."""
        inp: SecureInput = self.query_one("#cmd-input", SecureInput)

        if self._state in MASKED_INPUT_STATES:
            inp.password = not inp.password
            self._updateUI()
            return

        if self._state in (AppState.ENCODE_SAVE_PATH, AppState.DECODE_PATH):
            if not inp.value:
                defaultStr = tildePath(IMAGES_DIR)
                if self._state == AppState.DECODE_PATH:
                    defaultStr += "//"

                inp.value = defaultStr
                inp.cursor_position = len(defaultStr)

            return

        if self._state != AppState.IDLE:
            return

        if not self._lastIdentifiedCommand and inp.value.strip():
            return

        val = inp.value.lower().strip()

        if self._tabIndex != -1 and val == COMMANDS[self._tabIndex]:
            self._tabIndex = (self._tabIndex + 1) % len(COMMANDS)

        else:
            if self._lastIdentifiedCommand:
                self._tabIndex = COMMANDS.index(self._lastIdentifiedCommand)

            else:
                self._tabIndex = 0

        selected = COMMANDS[self._tabIndex]

        prefixLen = len(inp.value) - len(inp.value.lstrip())
        prefix = inp.value[:prefixLen]

        inp.value = prefix + selected
        inp.cursor_position = len(inp.value)
        self._updateUI()


    def _syncInputPrompt(self) -> None:
        """Hidden input holding text turns the bullet to the input color, one bar per character after the space. The
        color switches at once, skipping the bullet's CSS transition, so it lands with the bars on the same frame."""
        inp = self.query_one("#cmd-input", SecureInput)
        masked = inp.password and bool(inp.value)

        prompt = self.query_one("#input-prompt", Static)
        if prompt.has_class("masked") != masked:
            prompt.set_class(masked, "masked", update=False)
            self.app.stylesheet.update_nodes([prompt], animate=False)


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle real-time input changes for highlighting."""
        if event.input.id != "cmd-input":
            return

        self._syncInputPrompt()

        if self._hueBlinkTimer is not None and event.input.value != self._hueBlinkText:
            self._stopHueBlink()

        typed = event.value.lower().strip()

        if self._state == AppState.ENCODE_PHRASE:
            try:
                self._updateStatusBar()

            except Exception:
                pass

        if self._state != AppState.IDLE or not typed:
            if not typed:
                self._lastIdentifiedCommand = ""
                self._tabIndex = -1
                try:
                    self._updateStatusBar()

                except Exception:
                    pass

            return

        best = matchCommand(typed)
        self._lastIdentifiedCommand = best or ""
        self._tabIndex = COMMANDS.index(typed) if best == typed else -1
        self._updateUI()


    def _updateUI(self) -> None:
        inp = self.query_one("#cmd-input", SecureInput)
        self._syncInputPrompt()

        if self._processing:
            verb = "decoding" if self._decodeInProgress else "encoding"
            inp.placeholder = f"Type [bold]cancel[/] to abort seed image {verb}"
            self._updateStatusBar()
            return

        if self._state == AppState.IDLE:
            inp.placeholder = ""

        elif self._state == AppState.ENCODE_SAVE_PATH:
            inp.placeholder = tildePath(IMAGES_DIR)

        elif self._state == AppState.DECODE_PATH:
            inp.placeholder = f"{tildePath(IMAGES_DIR)}//..."

        elif self._hueInputActive() and self._hueCell is None:
            inp.placeholder = "Enter desired hue range for any cell, or [bold]ENTER[/] to generate image"

        elif self._hueInputActive():
            inp.placeholder = "Enter desired hue range for any cell, or click here and [bold]ENTER[/] to generate image"

        elif self._state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM, AppState.BANNER_CONFIRM):
            inp.placeholder = "[bold]ENTER[/] to confirm"

        elif self._state in MASKED_INPUT_STATES:
            action = "show" if inp.password else "hide"
            secret = "seed phrase" if self._state == AppState.ENCODE_PHRASE else "passphrase"
            inp.placeholder = f"[bold]TAB[/] to {action} {secret}"

        else:
            inp.placeholder = ""

        self._updateStatusBar()


    def _setState(self, state: AppState) -> None:
        if self._exitArmTimer is not None:
            self._exitArmTimer.cancel()
            self._exitArmTimer = None

        self._state = state
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""
        self._cellNav = False
        self._lastClickOnCell = False
        self._stopHueBlink()
        self._clearHueError()
        self.query_one("#cmd-input", SecureInput).password = state in MASKED_INPUT_STATES
        if state == AppState.IDLE:
            self._curRoot = None
            self._curStep = None

        self._updateUI()



    ######## ESC ########

    def action_cancel(self) -> None:
        """At the idle menu ESC is the exit shortcut. Elsewhere it aborts the first step of a flow, or steps back
        one state and shows the previous prompt again."""
        if self._processing:
            return

        if self._state == AppState.IDLE:
            self._exitShortcut()
            return

        inp = self.query_one("#cmd-input", SecureInput)
        if self._hueInputActive() and inp.value.strip():
            inp.value = ""
            return

        inp.value = ""
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""

        if self._state == AppState.BANNER_CONFIRM:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._setState(AppState.IDLE)
            return

        if self._state == AppState.ENCODE_COUNT:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._wordCount = 0
            self._encodePassphrase = ""
            self._encodePhrase = ""
            self._encodeCount = 1
            self._encodeCellPx = DEFAULT_CELL_PX
            self._setState(AppState.IDLE)

        elif self._state == AppState.DECODE_PATH:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._decodePath = ""
            self._setState(AppState.IDLE)

        else:
            backMap = {
                AppState.ENCODE_PHRASE: AppState.ENCODE_COUNT,
                AppState.ENCODE_PASSPHRASE: AppState.ENCODE_PHRASE,
                AppState.ENCODE_PASSPHRASE_CONFIRM: AppState.ENCODE_PASSPHRASE,
                AppState.ENCODE_CELL: AppState.ENCODE_PASSPHRASE,
                AppState.ENCODE_SAVE_PATH: AppState.ENCODE_CELL,
                AppState.ENCODE_CONFIRM: AppState.ENCODE_SAVE_PATH,
                AppState.DECODE_PASSPHRASE: AppState.DECODE_PATH,
                AppState.DECODE_CONFIRM: AppState.DECODE_PASSPHRASE,
            }
            prev = backMap.get(self._state)
            if prev is None:
                return

            self._addAnswer("Stepped back.", C_DIM)

            if self._state in (AppState.ENCODE_PHRASE, AppState.ENCODE_PASSPHRASE):
                self._maskActiveInvalidNode()

            if self._state == AppState.ENCODE_CELL:
                self._cancelPrecompute()

            elif self._state in (AppState.ENCODE_SAVE_PATH, AppState.ENCODE_CONFIRM):
                self._stopConfirmSpinner()
                self._confirmStepNode = None

            if self._state == AppState.ENCODE_CONFIRM:
                self._maskActiveSample(dropColorSpace=False)

            if self._state == AppState.ENCODE_PHRASE:
                self._encodeCount = 1
                self._wordCount = 0
                self._encodePhrase = ""
                self._encodeSeedType = ""

            elif self._state in (AppState.ENCODE_PASSPHRASE, AppState.ENCODE_PASSPHRASE_CONFIRM):
                self._encodePassphrase = ""

            elif self._state == AppState.ENCODE_CELL:
                self._encodeCellPx = DEFAULT_CELL_PX

            elif self._state in (AppState.ENCODE_SAVE_PATH, AppState.ENCODE_CONFIRM):
                self._encodeSavePath = ""
                self._encodeFileStem = ""

            self._setState(prev)
            self._addStep(self._promptMarkup(prev))


    def _exitShortcut(self) -> None:
        """A second ESC within EXIT_ESC_WINDOW of an arming one exits. An ESC that follows any other ESC within
        EXIT_ESC_BURST, such as the tail of a burst that stepped back to the menu, neither arms nor exits."""
        if self._exitArmTimer is not None:
            self.app.exit()
            return

        if getattr(self.app, "escInBurst", False):
            return

        self._exitArmTimer = asyncio.get_event_loop().call_later(EXIT_ESC_WINDOW, self._disarmExit)
        self._updateStatusBar()


    def _disarmExit(self) -> None:
        self._exitArmTimer = None
        self._updateStatusBar()


    def action_pageUp(self) -> None:
        self.query_one("#terminal-log", ClickableLog).scroll_page_up(animate=False)


    def action_pageDown(self) -> None:
        self.query_one("#terminal-log", ClickableLog).scroll_page_down(animate=False)



    ######## SCREENSHOTS ########

    async def action_printSvg(self) -> None:
        if self._takingScreenshot:
            return

        self._takingScreenshot = True
        try:
            path = generateScreenshotPath()

            if self._processing or self._state != AppState.IDLE:
                await executePrint(self, path, inline=True)
                return

            self._processing = True
            await asyncio.sleep(0)
            await executePrint(self, path)
            self._processing = False

        finally:
            self._takingScreenshot = False





    ######## SUBMIT ########

    async def on_options_bar_selected(self, event: OptionsBar.Selected) -> None:
        if self._processing or self._state != AppState.IDLE:
            return

        inp = self.query_one("#cmd-input", SecureInput)

        inp.value = event.value
        await self.on_input_submitted(Input.Submitted(inp, event.value))


    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd-input":
            return

        if self._processing:
            event.stop()
            event.prevent_default()
            return

        if time.time() < self._readyAt and not event.value.strip():
            return

        rawValue = event.value
        value = rawValue.strip()
        self.query_one("#cmd-input", SecureInput).value = ""

        if self._state == AppState.IDLE:
            best = matchCommand(value.lower()) if value else None
            if best:
                await self._handleCommand(rawValue.rstrip() + best[len(value):], best)

            else:
                await self._handleCommand(rawValue, None)

        elif self._state == AppState.ENCODE_COUNT:
            self._handleEncodeCount(value)

        elif self._state == AppState.ENCODE_PHRASE:
            self._handlePhrase(value)

        elif self._state == AppState.ENCODE_PASSPHRASE:
            self._encodePassphrase = rawValue
            self._addDashbar(C_INP)
            self._setState(AppState.ENCODE_PASSPHRASE_CONFIRM)
            self._addStep(self._promptMarkup(AppState.ENCODE_PASSPHRASE_CONFIRM))

        elif self._state == AppState.ENCODE_PASSPHRASE_CONFIRM:
            self._handlePassphraseConfirm(rawValue)

        elif self._state == AppState.ENCODE_SAVE_PATH:
            self._handleSavePath(rawValue)

        elif self._state == AppState.ENCODE_CELL:
            self._handleEncodeCell(value)

        elif self._state == AppState.ENCODE_CONFIRM:
            self._handleEncodeConfirm(rawValue)

        elif self._state == AppState.DECODE_PATH:
            await self._handleDecodePath(rawValue)

        elif self._state == AppState.DECODE_PASSPHRASE:
            self._decodePassphrase = rawValue
            self._addDashbar(C_INP)
            self._setState(AppState.DECODE_CONFIRM)
            self._addStep(self._promptMarkup(AppState.DECODE_CONFIRM))

        elif self._state == AppState.DECODE_CONFIRM:
            self._handleDecodeConfirm()

        elif self._state == AppState.BANNER_CONFIRM:
            self._handleBannerConfirm()

        if value and not self._justCleared:
            self._anyCommandRun = True

        self._justCleared = False


    async def _handleCommand(self, raw: str, executedCmd: str | None = None) -> None:
        self._maskActiveSeed()

        cmd = (executedCmd if executedCmd is not None else raw).strip().lower()
        display = raw.strip()

        if not cmd:
            return

        self._clearTypeClearHint()

        if cmd == "clear":
            self._resetHistory()
            return

        if cmd == "banner":
            if not self._anyCommandRun:
                self._handleBannerConfirm()

            else:
                self._newRoot(Text("banner", style=f"bold {C_INP}"))
                self._rebuild()
                self._addStep(self._promptMarkup(AppState.BANNER_CONFIRM))
                self._setState(AppState.BANNER_CONFIRM)

            return

        if cmd == "exit":
            self.app.exit()
            return

        self._freezeHistory()
        self._newRoot(Text(display, style=f"bold {C_INP}"))
        self._rebuild()

        if cmd == "encode":
            self._encodeCount = 1
            self._encodePhrase = ""
            self._encodeCellPx = DEFAULT_CELL_PX
            self._setState(AppState.ENCODE_COUNT)
            self._addStep(self._promptMarkup(AppState.ENCODE_COUNT))

        elif cmd == "decode":
            self._setState(AppState.DECODE_PATH)
            self._addStep(self._promptMarkup(AppState.DECODE_PATH))

        elif cmd == "help":
            self._showHelp()
            self._tabIndex = -1
            self._lastIdentifiedCommand = ""
            self._updateUI()

        else:
            displayCmd = cmd[:100] + "..." if len(cmd) > 100 else cmd
            if self._curRoot is not None:
                self._curRoot.bullet = C_FAIL

            self._addStep(f"[bold {C_FAIL}]No such command: {displayCmd}[/]", connStyle=C_FAIL)
            self._curRoot = None
            self._curStep = None
            self._tabIndex = -1
            self._lastIdentifiedCommand = ""
            self._updateUI()


    def _showHelp(self) -> None:
        from spicebag.frontend.screens.help import HelpScreen

        self._curRoot = None
        self._curStep = None
        self.app.push_screen(HelpScreen())


    def _handleBannerConfirm(self) -> None:
        self._useMascotBanner = not self._useMascotBanner
        self._saveConfig()
        self._resetHistory()


    def _resetHistory(self) -> None:
        """Empty the history and redraw the banner, for clear and for a banner switch."""
        self._blocks.clear()
        self._typeClearNode = None
        self._shownPassphraseWarning = False
        self._anyCommandRun = False
        self._setState(AppState.IDLE)
        self._showWelcome()
        self._rebuild()
        self._justCleared = True