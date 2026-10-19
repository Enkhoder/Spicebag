######## LIBRARIES ########

from spicebag.frontend.theme import (
    C_SUCC, C_DIM, C_INP, C_FAIL, C_IMG, AppState,
    IMAGES_DIR, MAX_IMAGE_COUNT, MAX_CELL_PX, DEFAULT_CELL_PX, parseHueRange
)
from spicebag.backend.generator import identifySeedType, bulkEncodeMnemonic, encodeMnemonic, InvalidSeedWordsError
from spicebag.backend.paths import parseSavePath, tildePath
from spicebag.backend.colors import normalizeSalt
from rich.style import Style
from rich.text import Text
from textual import work
import typing
import time
import os



######## CONSTANTS ########

BRAILLE_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"



######## ENCODE HANDLER MIXIN ########

class EncodeHandlerMixin:
    if typing.TYPE_CHECKING:
        _encodeCount: int
        _wordCount: int
        _encodeSalt: str
        _encodePhrase: str
        _encodeSeedType: str
        _encodeCellPx: int
        _encodeSavePath: str
        _encodeFileStem: str
        _shownSaltWarning: bool
        _processing: bool
        _cancelFlag: bool
        _encodingNode: typing.Any
        _colorSpace: typing.Any
        _activeSampleNode: typing.Any
        _precomputePending: bool
        _precomputeToken: int
        _confirmStepNode: typing.Any
        _confirmBaseMarkup: str
        _spinnerFrame: int
        _spinnerTimer: typing.Any
        _hueCell: tuple[int, int] | None
        _cellNav: bool
        _lastClickOnCell: bool
        _tabIndex: int
        _lastIdentifiedCommand: str
        _state: AppState
        app: typing.Any
        def _rebuild(self, scrollToEnd: bool = ...) -> None: ...
        def _triggerInputError(self) -> None: ...
        def _maskActiveSample(self) -> None: ...
        def set_interval(self, interval: float, callback: typing.Any) -> typing.Any: ...
        def _addAnswer(self, value: str, style: str = ..., connStyle: str = ...) -> None: ...
        def _addDashbar(self, connStyle: str = ...) -> None: ...
        def _addNote(self, content: typing.Any) -> None: ...
        def _addInvalidWordsNote(self, words: list, prefix: str = ...) -> None: ...
        def _maskActiveInvalidNode(self) -> bool: ...
        def _addStep(self, markup: str) -> typing.Any: ...
        def _addResult(self, text: typing.Any, connStyle: str, body: typing.Any = ...) -> None: ...
        def _promptMarkup(self, state: AppState) -> str: ...
        def _setState(self, state: AppState) -> None: ...
        def _workerHooks(self) -> tuple[typing.Any, typing.Any]: ...
        def _startLoader(self, baseMsgPlain: str) -> None: ...
        def _stopLoader(self, warn: bool = ...) -> None: ...
        def _stopBranchFlicker(self) -> None: ...
        def _updateUI(self) -> None: ...
        def _hueInputActive(self) -> bool: ...
        def _showHueError(self, message: str) -> None: ...
        def _clearHueError(self) -> None: ...
        def _startHueBlink(self, text: str) -> None: ...
        def _stopHueBlink(self) -> None: ...
        def _setSampleSelection(self, cell: tuple[int, int] | None) -> None: ...
        def query_one(self, selector: str, expect_type: type = typing.Any) -> typing.Any: ...

    def _handleEncodeCount(self, value: str) -> None:
        self._addAnswer(value if value else "1", f"bold {C_INP}")

        if not value:
            self._encodeCount = 1

        else:
            try:
                n = int(value)

            except ValueError:
                self._addNote(f"[bold {C_FAIL}]Please enter a valid number.[/]")
                return

            if n <= 0:
                self._addNote(f"[bold {C_FAIL}]Image count must be at least 1.[/]")
                return

            if n > MAX_IMAGE_COUNT:
                self._addNote(f"[bold {C_FAIL}]Image count cannot exceed {MAX_IMAGE_COUNT}.[/]")
                return

            self._encodeCount = n

        self._encodePhrase = ""
        self._setState(AppState.ENCODE_PHRASE)
        self._addStep(self._promptMarkup(AppState.ENCODE_PHRASE))


    def _handlePhrase(self, value: str) -> None:
        if not value.strip():
            return

        normalized = " ".join(value.split())

        try:
            _, seedType, wordCount, _ = identifySeedType(normalized)

        except InvalidSeedWordsError as e:
            self._addInvalidWordsNote(e.words, e.prefix)
            from spicebag.frontend.widgets.secureInput import SecureInput
            self.query_one("#cmd-input", SecureInput).value = ""
            return

        except ValueError as e:
            self._addNote(Text(str(e), style=f"bold {C_FAIL}"))
            from spicebag.frontend.widgets.secureInput import SecureInput
            self.query_one("#cmd-input", SecureInput).value = ""
            return

        self._encodePhrase = normalized
        self._encodeSeedType = seedType
        self._wordCount = wordCount
        self._maskActiveInvalidNode()
        self._addDashbar(C_INP)
        self._setState(AppState.ENCODE_SALT)
        self._addStep(self._promptMarkup(AppState.ENCODE_SALT))


    def _handleSaltConfirm(self, rawValue: str) -> None:
        if normalizeSalt(rawValue) != normalizeSalt(self._encodeSalt):
            self._addNote(f"[bold {C_FAIL}]Salt does not match.[/]")
            return

        self._addDashbar(C_INP)
        self._setState(AppState.ENCODE_CELL)
        self._addStep(self._promptMarkup(AppState.ENCODE_CELL))

        if self._encodeCount == 1:
            self._beginColorSpacePrecompute()


    def _handleEncodeCell(self, value: str) -> None:
        self._addAnswer(value if value else str(DEFAULT_CELL_PX), f"bold {C_INP}")

        if not value:
            self._encodeCellPx = DEFAULT_CELL_PX

        else:
            try:
                px = int(value)

            except ValueError:
                self._addNote(f"[bold {C_FAIL}]Please enter a valid integer for cell size.[/]")
                return

            if px <= 0:
                self._addNote(f"[bold {C_FAIL}]Cell size must be at least 1 pixel.[/]")
                return

            if px > MAX_CELL_PX:
                self._addNote(f"[bold {C_FAIL}]Cell size cannot exceed {MAX_CELL_PX}px.[/]")
                return

            self._encodeCellPx = px

        self._setState(AppState.ENCODE_SAVE_PATH)
        self._addStep(self._promptMarkup(AppState.ENCODE_SAVE_PATH))


    def _handleSavePath(self, rawValue: str) -> None:
        self._addAnswer(rawValue.strip() or tildePath(IMAGES_DIR), f"bold {C_INP}")
        result = parseSavePath(rawValue.strip(), IMAGES_DIR)

        if isinstance(result, str):
            self._addNote(Text(result, style=f"bold {C_FAIL}"))
            return

        dirStr, stem = result
        self._encodeSavePath = dirStr
        self._encodeFileStem = stem
        self._setState(AppState.ENCODE_CONFIRM)
        confirmStep = self._addStep(self._promptMarkup(AppState.ENCODE_CONFIRM))

        if self._encodeCount == 1:
            self._enterConfirmSample(confirmStep)


    def _beginColorSpacePrecompute(self) -> None:
        self._precomputeToken += 1
        token = self._precomputeToken
        self._colorSpace = None
        self._activeSampleNode = None
        self._precomputePending = True
        self._precomputeWorker(self._encodePhrase, self._encodeSalt, token)


    @work(thread=True, exit_on_error=False)
    def _precomputeWorker(self, mnemonic: str, salt: str, token: int) -> None:
        from spicebag.backend.generator import precomputeColorSpace

        try:
            cs = precomputeColorSpace(mnemonic, salt)

        except Exception:
            cs = None

        self.app.call_from_thread(self._finishPrecompute, cs, token)


    def _finishPrecompute(self, cs, token: int) -> None:
        if token != self._precomputeToken:
            return

        self._precomputePending = False

        if cs is None:
            if self._state == AppState.ENCODE_CONFIRM and self._activeSampleNode is None:
                self._stopConfirmSpinner()
                self._rebuild(scrollToEnd=False)

            return

        self._colorSpace = cs

        if (self._state == AppState.ENCODE_CONFIRM and self._confirmStepNode is not None
                and self._activeSampleNode is None):
            self._attachSample(self._confirmStepNode, cs)


    def _cancelPrecompute(self) -> None:
        self._precomputeToken += 1
        self._precomputePending = False
        self._colorSpace = None
        self._stopConfirmSpinner()
        self._confirmStepNode = None



    ######## CONFIRM SAMPLE / SPINNER ########

    def _enterConfirmSample(self, confirmStep) -> None:
        self._confirmStepNode = confirmStep
        self._confirmBaseMarkup = self._promptMarkup(AppState.ENCODE_CONFIRM)

        if self._colorSpace is not None:
            self._attachSample(confirmStep, self._colorSpace)

        elif self._precomputePending:
            self._startConfirmSpinner()

        else:
            self._beginColorSpacePrecompute()
            self._startConfirmSpinner()


    def _attachSample(self, confirmStep, cs) -> None:
        from spicebag.frontend.tree import TreeNode

        self._stopConfirmSpinner()

        node = TreeNode(kind="imagesample", sampleSpace=cs, sampleClickable=True, sampleMasked=False)
        confirmStep.children.insert(0, node)
        self._activeSampleNode = node
        self._rebuild()
        self._updateUI()


    def _startConfirmSpinner(self) -> None:
        self._spinnerFrame = 0
        self._renderSpinnerFrame()

        if self._spinnerTimer is None:
            self._spinnerTimer = self.set_interval(0.1, self._tickSpinner)


    def _tickSpinner(self) -> None:
        self._spinnerFrame = (self._spinnerFrame + 1) % len(BRAILLE_SPINNER)
        self._renderSpinnerFrame()


    def _renderSpinnerFrame(self) -> None:
        node = self._confirmStepNode

        if node is None:
            return

        frame = BRAILLE_SPINNER[self._spinnerFrame]
        text = Text.from_markup(self._confirmBaseMarkup)
        text.append("  ")
        text.append(frame, style=C_DIM)
        node.text = text
        self._rebuild(scrollToEnd=False)


    def _stopConfirmSpinner(self) -> None:
        if self._spinnerTimer is not None:
            self._spinnerTimer.stop()
            self._spinnerTimer = None

        node = self._confirmStepNode

        if node is not None and self._confirmBaseMarkup:
            node.text = Text.from_markup(self._confirmBaseMarkup)


    def _handleEncodeConfirm(self, rawValue: str = "") -> None:
        """While the last click was on a cell, ENTER recolors the selected cell, even on a blank input bar; the image
        is written by ENTER on a blank bar once the bar itself was clicked."""
        if self._hueInputActive() and self._lastClickOnCell and self._hueCell is not None and not rawValue.strip():
            from spicebag.backend.generator import rerollCell

            if rerollCell(self._colorSpace, *self._hueCell):
                self._rebuild(scrollToEnd=False)

            return

        if rawValue.strip() and self._hueInputActive():
            self._handleHueRange(rawValue)
            return

        if self._encodeCount == 1 and self._colorSpace is None and self._precomputePending:
            self._triggerInputError()
            return

        self._stopHueBlink()
        if self._activeSampleNode is not None:
            self._activeSampleNode.sampleClickable = False
            self._activeSampleNode.sampleHover = None
            self._setSampleSelection(None)
            self._cellNav = False
            self._lastClickOnCell = False

        self._addDashbar(C_INP)
        self._runEncode()


    def _handleHueRange(self, rawValue: str) -> None:
        """Recolor the last clicked cell inside the typed hue range. The text stays in the bar: blinking once
        accepted, or left to fix after an error."""
        from spicebag.frontend.widgets.secureInput import SecureInput
        from spicebag.backend.generator import applyHueRange

        inp = self.query_one("#cmd-input", SecureInput)
        inp.value = rawValue
        inp.cursor_position = len(rawValue)

        parsed = parseHueRange(rawValue, final=True)
        if isinstance(parsed, str):
            self._showHueError(parsed)
            return

        if self._hueCell is None:
            self._showHueError("Click a cell first.")
            return

        start, span = typing.cast(tuple[int, int], parsed)
        if not applyHueRange(self._colorSpace, *self._hueCell, start, span):
            self._showHueError("No color in this hue range.")
            return

        self._clearHueError()
        self._cellNav = True
        self._rebuild(scrollToEnd=False)
        self._startHueBlink(rawValue)


    def _initHueRange(self, cell: tuple[int, int], hueRange: tuple[int, int], text: str) -> None:
        """A click with a valid range in the bar keeps the range for that cell without recoloring it yet."""
        from spicebag.backend.generator import setHueRange

        if not setHueRange(self._colorSpace, *cell, *hueRange):
            self._showHueError("No color in this hue range.")
            return

        self._clearHueError()
        self._startHueBlink(text)


    @work
    async def _runEncode(self) -> None:
        self._processing = True

        from pathlib import Path

        finalPath = ""
        filename = ""

        try:
            targetDir = Path(self._encodeSavePath) if self._encodeSavePath else IMAGES_DIR

            mnemonic = self._encodePhrase
            count = self._encodeCount
            salt = self._encodeSalt
            cellPx = self._encodeCellPx
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            if count == 1:
                stem = self._encodeFileStem if self._encodeFileStem else timestamp
                filename = stem + ".png"

            else:
                stem = self._encodeFileStem if self._encodeFileStem else f"x{count}_{timestamp}"
                filename = stem + ".zip"

            finalPath = str(targetDir / filename)

            try:
                os.makedirs(targetDir, exist_ok=True)

            except PermissionError:
                self._addNote(f"[bold {C_FAIL}]Permission denied. Cannot create or access the target directory.[/]")
                return

            except OSError as e:
                self._addNote(Text(f"Target directory is invalid: {e}", style=f"bold {C_FAIL}"))
                return

            try:
                with open(finalPath, "wb"):
                    pass

            except PermissionError:
                self._addNote(f"[bold {C_FAIL}]Permission denied. Cannot write to the specified path.[/]")
                return

            except OSError:
                self._addNote(f"[bold {C_FAIL}]Unable to write image to the specified path.[/]")
                return

            try:
                os.remove(finalPath)

            except OSError:
                pass

            loaderMsg = "Encoding seed image" if count == 1 else "Encoding seed images"
            self._startLoader(loaderMsg)

            try:
                if count == 1 and self._colorSpace is not None:
                    worker = self._runColorSpaceEncodeInThread(finalPath, cellPx)

                elif count == 1:
                    worker = self._runEncodeInThread(mnemonic, finalPath, cellPx, salt)

                else:
                    worker = self._runBulkEncodeInThread(mnemonic, finalPath, count, cellPx, salt)

                await worker.wait()

                if self._cancelFlag:
                    raise InterruptedError()

                fileUri = Path(finalPath).absolute().as_uri()
                successMsg = Text()
                successMsg.append("Image saved: ", style=f"bold {C_SUCC}")
                successMsg.append(filename, style=Style(color=C_IMG, link=fileUri))

                body = []
                if not self._shownSaltWarning:
                    body.append(Text(
                        "Memorize or store your salt safely, if provided. "
                        "Loss of salt will result in image decoding failure.",
                        style=C_DIM,
                    ))
                    self._shownSaltWarning = True

                self._stopLoader()
                self._addResult(successMsg, C_SUCC, body=body)

            except InterruptedError:
                try:
                    if finalPath and os.path.exists(finalPath):
                        os.remove(finalPath)

                except Exception:
                    pass

            except Exception as exc:
                self._stopLoader(warn=True)
                from textual.worker import WorkerFailed
                inner = exc.error if isinstance(exc, WorkerFailed) else exc
                self._addResult(
                    Text(f"{type(inner).__name__}: {inner}. Unable to write image.",
                         style=f"bold {C_FAIL}"),
                    C_FAIL,
                )

        finally:
            self._maskActiveSample()

            if self._cancelFlag:
                self._stopBranchFlicker()
                self._processing = False
                self._tabIndex = -1
                self._lastIdentifiedCommand = ""

                if self._encodingNode is not None:
                    self._encodingNode.connStyle = C_DIM

                self._addResult(Text("Operation aborted.", style=f"bold {C_FAIL}"), C_FAIL)

                try:
                    from spicebag.frontend.widgets.secureInput import SecureInput
                    inp = self.query_one("#cmd-input", SecureInput)
                    inp.value = ""

                except Exception:
                    pass

            elif self._processing:
                self._processing = False

                try:
                    from spicebag.frontend.widgets.secureInput import SecureInput
                    inp = self.query_one("#cmd-input", SecureInput)
                    if inp.value.lower() in "cancel":
                        inp.value = ""

                except Exception:
                    pass

            self._encodingNode = None
            self._resetEncodeState()


    @work(thread=True, exit_on_error=False)
    def _runEncodeInThread(self, mnemonic: str, path: str, cellPx: int, salt: str) -> None:
        progressCb, cancelCheck = self._workerHooks()

        try:
            encodeMnemonic(mnemonic, path, cellPx=cellPx, salt=salt, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    @work(thread=True, exit_on_error=False)
    def _runColorSpaceEncodeInThread(self, path: str, cellPx: int) -> None:
        from spicebag.backend.generator import renderColorSpaceToFile

        progressCb, cancelCheck = self._workerHooks()

        try:
            renderColorSpaceToFile(self._colorSpace, path, cellPx=cellPx, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    @work(thread=True, exit_on_error=False)
    def _runBulkEncodeInThread(self, mnemonic: str, path: str, count: int, cellPx: int, salt: str) -> None:
        progressCb, cancelCheck = self._workerHooks()

        try:
            bulkEncodeMnemonic(mnemonic, path, count, cellPx=cellPx, salt=salt, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    def _resetEncodeState(self) -> None:
        self._wordCount = 0
        self._encodeSalt = ""
        self._encodePhrase = ""
        self._encodeSeedType = ""
        self._encodeCount = 1
        self._encodeCellPx = DEFAULT_CELL_PX
        self._encodeSavePath = ""
        self._encodeFileStem = ""
        self._cancelPrecompute()
        self._activeSampleNode = None
        self._setState(AppState.IDLE)