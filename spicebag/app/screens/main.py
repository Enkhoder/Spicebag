######## LIBRARIES ########

from spicebag.constants.theme import (
    COMMANDS, WORD_COUNTS, GRID_SIZES, BANNER_META, AppState, G_START, G_END,
    C_BG, C_SUCC, C_FAIL, C_INP, C_IMG, C_WC, C_WHITE, C_DIM,
    blendHexColors, getMascotBanner, gradientColor, ASCII_ART_BANNER, bannerHoverFrameCount
)
import json

from spicebag.app.handlers.screenshot import generateScreenshotPath, executePrint
from spicebag.app.tree import RootNode, TreeNode, renderBlocks
from spicebag.app.handlers.decode import DecodeHandlerMixin
from spicebag.app.handlers.encode import EncodeHandlerMixin
from spicebag.app.widgets.secureInput import SecureInput
from textual.widgets import Static, Input, RichLog, Rule
from spicebag.app.widgets.optionsBar import OptionsBar
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual import events, work
from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
import colorsys
import asyncio
import time



######## CLICKABLE LOG ########

class ClickableLog(RichLog):
    """RichLog that forwards cell clicks (in virtual content coordinates) to the
    screen so the interactive image sample can re-roll the clicked cell."""

    ALLOW_SELECT = False

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
        ("ctrl+s", "printSvg", "Screenshot")
    ]

    _wordCountFlashRatio = reactive(0.0)

    def __init__(self) -> None:
        self._state = AppState.IDLE
        self._words: list[str] = []
        self._wordCount = 0
        self._currentWordIdx = 0
        self._encodeSalt = ""
        self._encodePhrase = ""
        self._encodeSeedType = ""
        self._encodeCount = 1
        self._encodeCellPx = 100
        self._encodeSavePath = ""
        self._encodeFileStem = ""
        self._decodePath = ""
        self._decodeSalt = ""
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
        self._useMascotBanner = True
        self._loadConfig()

        # Conversation tree model
        self._blocks: list[RootNode] = []
        self._welcome: list = []
        self._curRoot: RootNode | None = None
        self._curStep: TreeNode | None = None
        self._encodingNode: TreeNode | None = None
        self._typeClearNode: TreeNode | None = None

        self._shownSaltWarning = False
        self._anyCommandRun = False
        self._inputBarErrorActive = False
        self._inputErrorTimer: asyncio.TimerHandle | None = None
        self._wordCountWarnTimer: asyncio.TimerHandle | None = None
        self._loaderBaseMsgPlain = ""
        self._cancelFlag = False
        self._lastProgressRebuild: float = 0.0
        self._branchFlickerTimer: asyncio.TimerHandle | None = None
        self._branchFlickerState: bool = True
        self._branchFlickerPercent: float = 0.0
        self._encodeStartTime: float = 0.0
        self._encodeFinalElapsedMs: float | None = None

        # Mascot animation
        self._mascotColPhases: list[int] = [0] * 10
        self._mascotAnimTimer: asyncio.TimerHandle | None = None
        self._mascotAnimActive: bool = False

        # Interactive masked-word output (decoded grid / invalid words)
        self._activeSeedNode: TreeNode | None = None
        self._activeInvalidNodes: list[TreeNode] = []
        self._seedRevealTimer: asyncio.TimerHandle | None = None
        self._hoverIdleTimer: asyncio.TimerHandle | None = None
        self._hoverRegions: list = []

        # Mascot hover animation
        self._bannerHoverPhase: int = -1
        self._bannerHoverTimer: asyncio.TimerHandle | None = None

        # Interactive image sample
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

        super().__init__()


    def compose(self) -> ComposeResult:
        with Vertical(id="app-container"):
            log = ClickableLog(id="terminal-log", wrap=False, highlight=False, markup=True)
            log.can_focus = False
            yield log
            yield Rule(id="sep-bot")

            with Horizontal(id="input-bar"):
                yield Static("●", id="input-prompt")
                yield SecureInput(id="cmd-input", placeholder="")

            yield Rule(id="sep-status")
            yield OptionsBar(id="status-bar")


    def on_mount(self) -> None:
        from spicebag.utils.networkDetect import getNetworkState
        import threading

        self._airplaneMode = getNetworkState()
        threading.Thread(target=self._pollAirplaneMode, daemon=True).start()

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
        from spicebag.constants.theme import OUTPUT_DIR
        configPath = OUTPUT_DIR / "bannerConfig"
        if configPath.exists():
            try:
                with open(configPath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._useMascotBanner = data.get("useMascotBanner", True)

            except Exception:
                pass


    def _saveConfig(self) -> None:
        from spicebag.constants.theme import OUTPUT_DIR
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

    def _triggerInputError(self) -> None:
        inputBar = self.query_one("#input-bar")
        inputPrompt = self.query_one("#input-prompt")
        cmdInput = self.query_one("#cmd-input", SecureInput)
        sepBot = self.query_one("#sep-bot")
        sepStatus = self.query_one("#sep-status")

        if self._inputBarErrorActive:
            if self._inputErrorTimer is not None:
                self._inputErrorTimer.cancel()

        else:
            self._inputBarErrorActive = True
            inputBar.add_class("input-error")
            inputPrompt.add_class("input-error")
            cmdInput.add_class("input-error")
            sepBot.add_class("input-error")
            sepStatus.add_class("input-error")

        cmdInput.animate("_errRatio", 1.0, duration=0.1, easing="in_out_cubic")

        def clearError() -> None:
            self._inputBarErrorActive = False
            inputBar.remove_class("input-error")
            inputPrompt.remove_class("input-error")
            cmdInput.remove_class("input-error")
            sepBot.remove_class("input-error")
            sepStatus.remove_class("input-error")
            cmdInput.animate("_errRatio", 0.0, duration=0.1, easing="in_out_cubic")

        self._inputErrorTimer = asyncio.get_event_loop().call_later(0.5, clearError)


    def _triggerWordCountWarn(self) -> None:
        self.animate("_wordCountFlashRatio", 1.0, duration=0.1)

        if self._wordCountWarnTimer is not None:
            self._wordCountWarnTimer.cancel()

        def clearWarn() -> None:
            self.animate("_wordCountFlashRatio", 0.0, duration=0.1)

        self._wordCountWarnTimer = asyncio.get_event_loop().call_later(0.5, clearWarn)



    ######## PROGRESS LOADER ########

    def _progressText(self, percent: float) -> Text:
        barLen = 36
        out = Text()
        out.append(self._loaderBaseMsgPlain, style=C_WHITE)
        out.append("  ")

        totalLit = int(percent * barLen)
        for i in range(barLen):
            if i < totalLit:
                out.append("━", style=gradientColor(i / max(1, barLen - 1)))

            else:
                out.append("━", style=C_BG)

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
        out.append(f"{self._formatElapsed(elapsedMs, isFinal)}", style=C_DIM)
        return out


    def _formatElapsed(self, elapsedMs: float, isFinal: bool) -> str:
        if isFinal and elapsedMs < 1000:
            return f"{int(elapsedMs)}ms"

        elapsedS = elapsedMs / 1000
        h = int(elapsedS // 3600)
        m = int((elapsedS % 3600) // 60)
        s = int(elapsedS % 60)
        if h > 0:
            return f"{h}h {m}m {s}s"

        if m > 0:
            return f"{m}m {s}s"

        return f"{s}s"


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


    def _updateProgress(self, percent: float) -> None:
        if not getattr(self, "_processing", False) or self._encodingNode is None:
            return

        self._branchFlickerPercent = percent
        self._encodingNode.text = self._progressText(percent)

        now = time.monotonic()
        if now - self._lastProgressRebuild < 0.05:
            return

        self._lastProgressRebuild = now
        self._rebuild()


    def _stopLoader(self, warn: bool = False) -> None:
        self._stopBranchFlicker()
        if getattr(self, "_cancelFlag", False):
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
        if self._encodingNode is None or not getattr(self, "_processing", False):
            return

        if self._branchFlickerState:
            color = gradientColor(self._branchFlickerPercent)

        else:
            color = C_DIM

        self._encodingNode.connStyle = color
        self._rebuild()

        self._branchFlickerState = not self._branchFlickerState
        self._branchFlickerTimer = asyncio.get_event_loop().call_later(0.5, self._doFlicker)


    def _stopBranchFlicker(self) -> None:
        if self._branchFlickerTimer is not None:
            self._branchFlickerTimer.cancel()
            self._branchFlickerTimer = None


    def _abortProcessing(self) -> None:
        self._cancelFlag = True

        if self._encodeFinalElapsedMs is None and getattr(self, "_encodeStartTime", 0) > 0:
            self._encodeFinalElapsedMs = (time.monotonic() - self._encodeStartTime) * 1000
            if self._encodingNode is not None:
                self._encodingNode.text = self._progressText(getattr(self, "_branchFlickerPercent", 0.0))

        inp = self.query_one("#cmd-input", SecureInput)
        inp.value = ""
        inp.isFilled = False

        if getattr(self, "_decodeInProgress", False):
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
        self._decodeSalt = ""
        self._setState(AppState.IDLE)

        try:
            inp = self.query_one("#cmd-input", SecureInput)
            inp.value = ""
            inp.isFilled = False

        except Exception:
            pass

        self._rebuild()



    ######## RENDER ########

    def on_resize(self, event: events.Resize) -> None:
        if self.is_mounted:
            self._debouncedRender()


    @work(exclusive=True)
    async def _debouncedRender(self) -> None:
        await asyncio.sleep(0)
        if not self.is_mounted:
            return

        self._rebuild()


    def _logWidth(self) -> int:
        try:
            w = self.query_one("#terminal-log", RichLog).size.width

        except Exception:
            w = 0

        if w <= 0:
            w = self.app.size.width if self.app.size.width > 0 else 80

        return w


    def _rebuild(self, scrollToEnd: bool = True) -> None:
        try:
            log = self.query_one("#terminal-log", RichLog)

        except Exception:
            return

        sampleHit = None
        lines: list = []

        with self.app.batch_update():
            log.auto_scroll = False
            log.clear()

            for item in self._welcome:
                if isinstance(item, str):
                    log.write(Text.from_markup(item))

                else:
                    log.write(item)

            lines, sampleHit, hoverRegions = renderBlocks(self._blocks, self._logWidth(), self.app.console)
            for line in lines:
                log.write(line)

        welcomeOffset = len(log.lines) - len(lines)

        self._hoverRegions = [
            (lineIdx + welcomeOffset, colStart, colEnd, node, wordIdx)
            for (lineIdx, colStart, colEnd, node, wordIdx) in hoverRegions
        ]

        if sampleHit is not None:
            firstBlockLine, blockCol, cols, rows = sampleHit
            self._sampleStartLine = welcomeOffset + firstBlockLine
            self._sampleBlockCol = blockCol
            self._sampleCols = cols
            self._sampleRows = rows

        else:
            self._sampleStartLine = -1

        if scrollToEnd:
            log.auto_scroll = True
            log.scroll_end(animate=False)



    ######## INTERACTIVE SAMPLE ########

    def _handleSampleClick(self, line: int, col: int) -> None:
        node = self._activeSampleNode
        if node is None or self._colorSpace is None:
            return

        if not node.sampleClickable or node.sampleMasked or self._sampleStartLine < 0:
            return

        rowOff = line - self._sampleStartLine
        colOff = col - self._sampleBlockCol
        if rowOff < 0 or colOff < 0:
            return

        if rowOff >= self._sampleRows * 3 or colOff >= self._sampleCols * 6:
            return

        from spicebag.core.generator import rerollCell

        if not rerollCell(self._colorSpace, rowOff // 3, colOff // 6):
            return

        self._rebuild(scrollToEnd=False)


    def _maskActiveSample(self, dropColorSpace: bool = True) -> None:
        node = self._activeSampleNode
        self._activeSampleNode = None
        if dropColorSpace:
            self._colorSpace = None

        self._sampleStartLine = -1

        if node is not None:
            node.sampleMasked = True
            node.sampleClickable = False
            self._rebuild(scrollToEnd=False)



    ######## DECODED SEED GRID / MASKED WORDS ########

    def _showSeedGrid(self, words: list[str], seedType: str = "") -> None:
        from spicebag.constants.theme import GRID_SIZES

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
        target: tuple[TreeNode, int] | None = None

        for regionLine, colStart, colEnd, node, wordIdx in self._hoverRegions:
            if line == regionLine and colStart <= col < colEnd:
                target = (node, wordIdx)
                break

        # Reset idle timer on every movement while over a word, even if the
        # hovered word didn't change.
        timer = getattr(self, "_hoverIdleTimer", None)
        if timer is not None:
            try:
                timer.cancel()

            except Exception:
                pass

            self._hoverIdleTimer = None

        if target is not None:
            self._hoverIdleTimer = asyncio.get_event_loop().call_later(3.0, self._clearWordHover)

        from spicebag.constants.theme import getVersion

        versionStr = getVersion()
        startCol = 16
        endCol = 25 + len(versionStr)

        if self._useMascotBanner and line == 1 and startCol <= col <= endCol:
            self._setBannerHover(True)

        else:
            self._setBannerHover(False)

        changed = False

        for node in self._uniqueHoverNodes():
            want = target[1] if (target is not None and target[0] is node) else -1
            if node.hoverIdx != want:
                node.hoverIdx = want
                changed = True

        if changed:
            self._rebuild(scrollToEnd=False)


    def _clearWordHover(self) -> None:
        self._setBannerHover(False)
        changed = False

        for node in self._uniqueHoverNodes():
            if node.hoverIdx != -1:
                node.hoverIdx = -1
                changed = True

        if changed:
            self._rebuild(scrollToEnd=False)


    def _onAppBlur(self) -> None:
        timer = getattr(self, "_hoverIdleTimer", None)
        if timer is not None:
            try:
                timer.cancel()

            except Exception:
                pass

            self._hoverIdleTimer = None

        self._clearWordHover()



    ######## WELCOME ########

    def _showWelcome(self) -> None:
        from spicebag.constants.theme import getNetworkText

        if self._useMascotBanner:
            self._mascotColPhases = [0] * 10
            self._welcome = [getMascotBanner(self._airplaneMode, self._mascotColPhases, self._bannerHoverPhase)]
            self._startMascotAnimation()

        else:
            self._stopMascotAnimation()
            self._welcome = [
                self._getGradientBanner(),
                "  " + BANNER_META,
                "  " + getNetworkText(self._airplaneMode),
            ]


    def _pollAirplaneMode(self) -> None:
        from spicebag.utils.networkDetect import getNetworkState
        import sys

        netState = getNetworkState()
        self.app.call_from_thread(self._updateAirplaneMode, netState)

        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            iphlpapi = ctypes.windll.Iphlpapi

            while True:
                handle = wintypes.HANDLE()
                iphlpapi.NotifyAddrChange(ctypes.byref(handle), None)
                netState = getNetworkState()
                try:
                    self.app.call_from_thread(self._updateAirplaneMode, netState)

                except Exception:
                    pass

        else:
            while True:
                time.sleep(2)
                netState = getNetworkState()
                try:
                    self.app.call_from_thread(self._updateAirplaneMode, netState)

                except Exception:
                    pass


    def _updateAirplaneMode(self, netState: tuple[bool, bool, bool]) -> None:
        if getattr(self, "_airplaneMode", None) != netState:
            self._airplaneMode = netState

            if not self._welcome:
                return

            from spicebag.constants.theme import getNetworkText

            if self._useMascotBanner:
                self._welcome[0] = getMascotBanner(netState, self._mascotColPhases, self._bannerHoverPhase)

            elif len(self._welcome) > 2:
                self._welcome[2] = "  " + getNetworkText(netState)

            self._rebuild(scrollToEnd=False)


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

                t = x / max(1, maxW - 1)
                h = (G_START[0] + (G_END[0] - G_START[0]) * t) % 1.0
                light = G_START[1] + (G_END[1] - G_START[1]) * t
                s = G_START[2] + (G_END[2] - G_START[2]) * t

                r, g, b = colorsys.hls_to_rgb(h, light, s)
                hexColor = f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"
                styledLine += f"[{hexColor}]{char}[/]"

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

        self._welcome[0] = getMascotBanner(self._airplaneMode, self._mascotColPhases, self._bannerHoverPhase)
        self._rebuild(scrollToEnd=False)


    def _setBannerHover(self, hovered: bool) -> None:
        if hovered:
            if self._bannerHoverPhase == -1:
                self._bannerHoverPhase = 0
                self._refreshMascotBanner()
                if self._bannerHoverTimer is None:
                    self._bannerHoverTimer = asyncio.get_event_loop().call_later(0.1, self._bannerHoverTick)

        else:
            if self._bannerHoverPhase != -1:
                self._bannerHoverPhase = -1
                self._refreshMascotBanner()
                if self._bannerHoverTimer is not None:
                    self._bannerHoverTimer.cancel()
                    self._bannerHoverTimer = None


    def _bannerHoverTick(self) -> None:
        if self._bannerHoverPhase != -1:
            self._bannerHoverPhase = (self._bannerHoverPhase + 1) % bannerHoverFrameCount()
            self._refreshMascotBanner()
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


    def _addResult(self, text: str | Text, connStyle: str,
                   body: list[Text] | None = None, hints: list[Text] | None = None) -> None:
        """Append a result branch (Success / error / Decoded …) under the active
        encoding/decoding node, or the current step as a fallback."""
        parent = self._encodingNode if self._encodingNode is not None else self._curStep
        if parent is not None:
            t = Text.from_markup(text) if isinstance(text, str) else text
            parent.children.append(TreeNode(
                kind="branch", text=t, connStyle=connStyle,
                body=body or [], hints=hints or [],
            ))

        self._rebuild()


    def _promptMarkup(self, state: AppState) -> str:
        if state == AppState.ENCODE_COUNT:
            return (f"[{C_WHITE}]How many images to generate? "
                    f"([bold]ENTER[/] for single-image generation)[/]")

        if state == AppState.ENCODE_WORD_COUNT:
            return (f"[{C_WHITE}]Select seed word count.")

        if state == AppState.ENCODE_PHRASE:
            return f"[{C_WHITE}]{self._wordCount}-word seed phrase goes here.[/]"

        if state == AppState.ENCODE_SALT:
            return (f"[{C_WHITE}]Enter image salt. "
                    f"(highly recommended, [bold]ENTER[/] for none)[/]")

        if state == AppState.ENCODE_CELL:
            return (f"[{C_WHITE}]Set cell size in pixels. "
                    f"([bold]ENTER[/] for default 100×100px)[/]")

        if state == AppState.ENCODE_SAVE_PATH:
            return (f"[{C_WHITE}]Save path and filename goes here. "
                    f"([bold]ENTER[/] for default)[/]")

        if state == AppState.ENCODE_CONFIRM:
            if self._encodeCount == 1:
                return (f"[{C_WHITE}]Proceed to generate this image?")

            return (f"[{C_WHITE}]Proceed to generate {self._encodeCount} images?")

        if state == AppState.DECODE_PATH:
            return f"[{C_WHITE}]Enter path to encoded image.[/]"

        if state == AppState.DECODE_SALT:
            return (f"[{C_WHITE}]Image salt goes here. "
                    f"([bold]ENTER[/] if none were given)[/]")

        if state == AppState.DECODE_CONFIRM:
            return (f"[{C_WHITE}]Proceed to decode image?")

        if state == AppState.BANNER_CONFIRM:
            nextLabel = "mascot" if not self._useMascotBanner else "ASCII"
            return (f"[{C_WHITE}]Switch to {nextLabel} banner? "
                    f"Terminal contents will be cleared.[/]")

        return ""



    ######## SCREENSHOT BLOCKS ########

    def _fileNode(self, filename: str, subdir: str) -> TreeNode:
        from spicebag.constants.theme import OUTPUT_DIR
        fileUri = (OUTPUT_DIR / subdir / filename).as_uri()
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
            node = self._fileNode(shot, "app-screenshots")
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
            node = self._fileNode(shot, "app-screenshots")
            node.connStyle = C_IMG
            header.children.append(node)

        helpRoot.children.append(header)
        self._curRoot = None
        self._curStep = None


    def _emitScreenshotSaved(self, filename: str, inline: bool) -> None:
        self._clearTypeClearHint()

        # Mid-operation: attach the shot inline under the active step, merging
        # consecutive shots into one "Screenshots taken and saved:" group.
        if inline:
            step = self._curStep
            if step is None:
                return

            last = step.children[-1] if step.children else None
            if last is not None and last.kind == "shotgroup":
                last.children.append(self._fileNode(filename, "app-screenshots"))
                last.text = Text.from_markup(f"[{C_WHITE}]Screenshots taken and saved:[/]")

            else:
                group = TreeNode(
                    kind="shotgroup",
                    text=Text.from_markup(f"[{C_WHITE}]Screenshot taken and saved:[/]"),
                )
                group.children.append(self._fileNode(filename, "app-screenshots"))
                step.children.append(group)

            self._rebuild()
            return

        # CTRL+S at the idle main menu — merge consecutive shots into one block.
        def _objFileNode(name: str) -> TreeNode:
            node = self._fileNode(name, "app-screenshots")
            node.connStyle = C_IMG
            return node

        last = self._blocks[-1] if self._blocks else None
        if last is not None and last.kind == "shortcut":
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
                f"[{C_DIM}]Word [{nColor}]{n}[/] of {self._wordCount}  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state == AppState.ENCODE_SALT:
            return (
                f"[{C_DIM}]Salt adds significant entropy to raw images  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state == AppState.DECODE_SALT:
            return (
                f"[{C_DIM}]Image cannot be decoded if the salt is lost  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state == AppState.ENCODE_CELL:
            return (
                f"[{C_DIM}]Tip: Cell size as small as 1px can be hidden among high-res photo noises  "
                f"[{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"
            )

        if self._state in (AppState.ENCODE_SAVE_PATH, AppState.DECODE_PATH):
            return Text.assemble(
                ("Type ", C_DIM),
                ("help", Style(color=C_DIM, bold=True)),
                (" on the main menu later for a guide to custom saves  ", C_DIM),
                ("·", C_DIM),
                ("  ", ""),
                ("ESC", f"bold {C_FAIL}"),
                (" to undo", C_FAIL)
            )

        if self._state == AppState.ENCODE_CONFIRM:
            cols, rows = GRID_SIZES.get(self._wordCount, (4, 6))
            imgW = cols * self._encodeCellPx
            imgH = rows * self._encodeCellPx
            saltStr = "true" if self._encodeSalt else "false"
            saltColor = C_SUCC if self._encodeSalt else C_FAIL

            base = (
                f"[{C_DIM}]Seed type: [/][{C_IMG}]{self._encodeSeedType}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Seed words: [/][{C_WC}]{self._wordCount}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Salt: [/][{saltColor}]{saltStr}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Size: [/][{C_INP}]{imgW}×{imgH}[/]"
            )
            if getattr(self, "_processing", False):
                return base

            return base + f"  [{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"

        if self._state == AppState.DECODE_CONFIRM:
            wordCount = getattr(self, "_decodeWordCount", 0)
            saltStr = "true" if self._decodeSalt else "false"
            saltColor = C_SUCC if self._decodeSalt else C_FAIL

            base = (
                f"[{C_DIM}]Seed words: [/][{C_WC}]{wordCount}[/]"
                + f"  [{C_DIM}]·[/]  [{C_DIM}]Salt: [/][{saltColor}]{saltStr}[/]"
            )
            if getattr(self, "_processing", False):
                return base

            return base + f"  [{C_DIM}]·[/]  [{C_FAIL}][bold]ESC[/] to undo[/]"

        return ""


    def _updateStatusBar(self) -> None:
        try:
            bar = self.query_one("#status-bar", OptionsBar)

        except Exception:
            return

        if self._state == AppState.IDLE:
            bar.setInteractive(COMMANDS, self._tabIndex)
            return

        if self._state == AppState.ENCODE_WORD_COUNT:
            try:
                typed = self.query_one("#cmd-input", SecureInput).value.strip()

            except Exception:
                typed = ""

            opts = [str(wc) for wc in WORD_COUNTS]
            selected = opts.index(typed) if typed in opts else -1
            suffix = Text()
            suffix.append("  ·  ", style=C_DIM)
            suffix.append("ESC", style=f"bold {C_FAIL}")
            suffix.append(" to undo", style=C_FAIL)
            bar.setInteractive(opts, selected, suffix)
            return

        bar.setStatic(self._statusText())


    def cycleCommands(self) -> None:
        """Cycle through the main commands using TAB."""
        inp: SecureInput = self.query_one("#cmd-input", SecureInput)

        if self._state in (AppState.ENCODE_SAVE_PATH, AppState.DECODE_PATH):
            if not inp.value:
                from spicebag.constants.theme import OUTPUT_DIR
                defaultStr = str(OUTPUT_DIR / "encoded-images").replace("\\", "/")
                if self._state == AppState.DECODE_PATH:
                    defaultStr += "//"

                inp.value = defaultStr
                inp.cursor_position = len(defaultStr)
                inp.isFilled = True

            return

        if self._state == AppState.ENCODE_WORD_COUNT:
            if self._tabIndex == -1:
                val = inp.value.strip()
                if not val:
                    self._tabIndex = 0

                elif val == "1":
                    self._tabIndex = WORD_COUNTS.index(12)

                elif val == "2":
                    self._tabIndex = WORD_COUNTS.index(24)

                elif val == "3":
                    self._tabIndex = WORD_COUNTS.index(33)

                elif val.isdigit() and int(val) in WORD_COUNTS:
                    self._tabIndex = (WORD_COUNTS.index(int(val)) + 1) % len(WORD_COUNTS)

                else:
                    return

            else:
                self._tabIndex = (self._tabIndex + 1) % len(WORD_COUNTS)

            selected = str(WORD_COUNTS[self._tabIndex])
            inp.value = selected
            inp.cursor_position = len(selected)
            inp.isFilled = True
            self._updateStatusBar()
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
        inp.isFilled = True
        self._updateUI()


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle real-time input changes for highlighting."""
        if event.input.id != "cmd-input":
            return

        typedRaw = event.value
        typed = typedRaw.lower().strip()
        inp: SecureInput = event.input  # type: ignore

        if self._state in (AppState.ENCODE_WORD_COUNT, AppState.ENCODE_PHRASE):
            try:
                self._updateStatusBar()

            except Exception:
                pass

        if self._state != AppState.IDLE or not typed:
            if not typed:
                self._lastIdentifiedCommand = ""
                self._tabIndex = -1
                inp.isFilled = False
                try:
                    self._updateStatusBar()

                except Exception:
                    pass

            return

        matches = [c for c in COMMANDS if c.startswith(typed)]

        if matches:
            best = "encode" if "encode" in matches else matches[0]
            self._lastIdentifiedCommand = best

            if typed == best:
                inp.isFilled = True
                self._tabIndex = COMMANDS.index(best)

            else:
                inp.isFilled = False
                self._tabIndex = -1

            self._updateUI()

        else:
            self._lastIdentifiedCommand = ""
            inp.isFilled = False
            self._tabIndex = -1
            self._updateUI()


    def _updateUI(self) -> None:
        inp = self.query_one("#cmd-input", SecureInput)
        inp.password = False

        if getattr(self, "_processing", False):
            verb = "decoding" if getattr(self, "_decodeInProgress", False) else "encoding"
            inp.placeholder = f"Type [bold]cancel[/] to abort seed image {verb}"
            self._updateStatusBar()
            return

        if self._state == AppState.IDLE:
            inp.placeholder = ""

        elif self._state == AppState.ENCODE_SAVE_PATH:
            from spicebag.constants.theme import OUTPUT_DIR
            defaultStr = str(OUTPUT_DIR / "encoded-images").replace("\\", "/")
            inp.placeholder = f"{defaultStr}"

        elif self._state == AppState.DECODE_PATH:
            from spicebag.constants.theme import OUTPUT_DIR
            defaultStr = str(OUTPUT_DIR / "encoded-images").replace("\\", "/")
            inp.placeholder = f"{defaultStr}//..."

        elif self._state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM):
            if getattr(self, "_processing", False):
                verb = "decoding" if getattr(self, "_decodeInProgress", False) else "encoding"
                inp.placeholder = f"Type [bold]cancel[/] to abort seed image {verb}"

            else:
                inp.placeholder = "Press [bold]ENTER[/] to confirm"

        elif self._state == AppState.BANNER_CONFIRM:
            inp.placeholder = "Press [bold]ENTER[/] to confirm"

        else:
            inp.placeholder = ""

        self._updateStatusBar()


    def _setState(self, state: AppState) -> None:
        self._state = state
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""
        if state == AppState.IDLE:
            self._curRoot = None
            self._curStep = None

        self._updateUI()



    ######## ESC ########

    def action_cancel(self) -> None:
        if self._processing:
            return

        if self._state == AppState.IDLE:
            return

        inp = self.query_one("#cmd-input", SecureInput)
        inp.value = ""

        inp.isFilled = False
        inp._suggestion = ""
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""

        if self._state == AppState.BANNER_CONFIRM:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._setState(AppState.IDLE)
            return

        if self._state == AppState.ENCODE_COUNT:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._words = []
            self._wordCount = 0
            self._currentWordIdx = 0
            self._encodeSalt = ""
            self._encodePhrase = ""
            self._encodeCount = 1
            self._encodeCellPx = 100
            self._setState(AppState.IDLE)

        elif self._state == AppState.DECODE_PATH:
            self._addAnswer("Operation aborted.", f"bold {C_FAIL}", connStyle=C_FAIL)
            self._decodePath = ""
            self._setState(AppState.IDLE)

        else:
            # Step back one state, re-showing the previous prompt as a new step.
            backMap = {
                AppState.ENCODE_WORD_COUNT: AppState.ENCODE_COUNT,
                AppState.ENCODE_PHRASE: AppState.ENCODE_WORD_COUNT,
                AppState.ENCODE_SALT: AppState.ENCODE_PHRASE,
                AppState.ENCODE_CELL: AppState.ENCODE_SALT,
                AppState.ENCODE_SAVE_PATH: AppState.ENCODE_CELL,
                AppState.ENCODE_CONFIRM: AppState.ENCODE_SAVE_PATH,
                AppState.DECODE_SALT: AppState.DECODE_PATH,
                AppState.DECODE_CONFIRM: AppState.DECODE_SALT,
            }
            prev = backMap.get(self._state)
            if prev is None:
                return

            self._addAnswer("User stepped back.", C_DIM)

            if self._state == AppState.ENCODE_PHRASE:
                self._maskActiveInvalidNode()

            elif self._state == AppState.ENCODE_SALT:
                self._maskActiveInvalidNode()

            if self._state == AppState.ENCODE_CELL:
                self._cancelPrecompute()

            elif self._state in (AppState.ENCODE_SAVE_PATH, AppState.ENCODE_CONFIRM):
                self._stopConfirmSpinner()
                self._confirmStepNode = None

            if self._state == AppState.ENCODE_CONFIRM:
                self._maskActiveSample(dropColorSpace=False)

            if self._state == AppState.ENCODE_WORD_COUNT:
                self._encodeCount = 1

            elif self._state == AppState.ENCODE_PHRASE:
                self._wordCount = 0
                self._words = []
                self._currentWordIdx = 0
                self._encodePhrase = ""
                self._encodeSeedType = ""

            elif self._state == AppState.ENCODE_SALT:
                self._encodeSalt = ""

            elif self._state == AppState.ENCODE_CELL:
                self._encodeCellPx = 100

            elif self._state in (AppState.ENCODE_SAVE_PATH, AppState.ENCODE_CONFIRM):
                self._encodeSavePath = ""
                self._encodeFileStem = ""

            self._setState(prev)
            self._addStep(self._promptMarkup(prev))



    ######## SCREENSHOTS ########

    async def action_printSvg(self) -> None:
        if getattr(self, "_takingScreenshot", False):
            return

        self._takingScreenshot = True
        try:
            path = generateScreenshotPath()

            if self._processing or self._state != AppState.IDLE:
                await self._executePrint(path, inline=True)
                return

            self._processing = True
            await asyncio.sleep(0)
            await self._executePrint(path, inline=False)
            self._processing = False

        finally:
            self._takingScreenshot = False


    async def _executePrint(self, path: str, inline: bool = False) -> None:
        await executePrint(self, path, inline=inline)



    ######## SUBMIT ########

    async def on_options_bar_selected(self, event: OptionsBar.Selected) -> None:
        if self._processing or self._state not in (AppState.IDLE, AppState.ENCODE_WORD_COUNT):
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

        if time.time() < self._readyAt:
            return

        rawValue = event.value
        value = rawValue.strip()
        self.query_one("#cmd-input", SecureInput).value = ""

        if self._state == AppState.IDLE:
            if value:
                matches = [c for c in COMMANDS if c.startswith(value.lower())]
                if matches:
                    best = "encode" if "encode" in matches else matches[0]
                    autofilledRaw = rawValue.rstrip() + best[len(value):]
                    await self._handleCommand(autofilledRaw, best)

                else:
                    await self._handleCommand(rawValue, None)

            else:
                await self._handleCommand(rawValue, None)

        elif self._state == AppState.ENCODE_COUNT:
            self._handleEncodeCount(value)

        elif self._state == AppState.ENCODE_WORD_COUNT:
            self._handleWordCount(value)

        elif self._state == AppState.ENCODE_PHRASE:
            self._handlePhrase(value)

        elif self._state == AppState.ENCODE_SALT:
            self._encodeSalt = rawValue
            self._addDashbar(C_INP)
            self._setState(AppState.ENCODE_CELL)
            self._addStep(self._promptMarkup(AppState.ENCODE_CELL))

            if self._encodeCount == 1:
                self._beginColorSpacePrecompute()

        elif self._state == AppState.ENCODE_SAVE_PATH:
            self._handleSavePath(rawValue)

        elif self._state == AppState.ENCODE_CELL:
            self._handleEncodeCell(value)

        elif self._state == AppState.ENCODE_CONFIRM:
            self._handleEncodeConfirm(value)

        elif self._state == AppState.DECODE_PATH:
            await self._handleDecodePath(rawValue)

        elif self._state == AppState.DECODE_SALT:
            self._decodeSalt = rawValue
            self._addDashbar(C_INP)
            self._setState(AppState.DECODE_CONFIRM)
            self._addStep(self._promptMarkup(AppState.DECODE_CONFIRM))

        elif self._state == AppState.DECODE_CONFIRM:
            self._handleDecodeConfirm(value)

        elif self._state == AppState.BANNER_CONFIRM:
            self._handleBannerConfirm()

        if not getattr(self, "_justCleared", False):
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
            self._blocks.clear()
            self._typeClearNode = None
            self._curRoot = None
            self._curStep = None
            self._shownSaltWarning = False
            self._anyCommandRun = False
            self._showWelcome()
            self._rebuild()
            self._tabIndex = -1
            self._lastIdentifiedCommand = ""
            self._updateUI()
            self._justCleared = True
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

        self._newRoot(Text(display, style=f"bold {C_INP}"))
        self._rebuild()

        if cmd == "encode":
            self._encodeCount = 1
            self._encodePhrase = ""
            self._encodeCellPx = 100
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

            self._addStep(f"[bold {C_FAIL}]Unrecognized command: {displayCmd}[/]", connStyle=C_FAIL)
            self._curRoot = None
            self._curStep = None
            self._tabIndex = -1
            self._lastIdentifiedCommand = ""
            self._updateUI()


    def _showHelp(self) -> None:
        from spicebag.app.screens.help import HelpScreen

        self._curRoot = None
        self._curStep = None
        self.app.push_screen(HelpScreen())


    def _handleBannerConfirm(self) -> None:
        self._useMascotBanner = not self._useMascotBanner
        self._saveConfig()

        self._blocks.clear()
        self._typeClearNode = None
        self._curRoot = None
        self._curStep = None
        self._shownSaltWarning = False
        self._anyCommandRun = False
        self._setState(AppState.IDLE)
        self._showWelcome()
        self._rebuild()
        self._tabIndex = -1
        self._lastIdentifiedCommand = ""
        self._justCleared = True