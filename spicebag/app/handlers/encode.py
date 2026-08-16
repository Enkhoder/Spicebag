######## LIBRARIES ########

from spicebag.constants.theme import WORD_COUNTS, C_SUCC, C_DIM, C_INP, C_FAIL, C_IMG, AppState
from spicebag.core.generator import identifySeedType, bulkEncodeMnemonic, encodeMnemonic, InvalidSeedWordsError
from spicebag.app.handlers.savePath import parseSavePath
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
        _words: list[str]
        _currentWordIdx: int
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
        _curStep: typing.Any
        _state: AppState
        app: typing.Any
        def _rebuild(self, scrollToEnd: bool = ...) -> None: ...
        def _triggerInputError(self) -> None: ...
        def _maskActiveSample(self) -> None: ...
        def set_interval(self, interval: float, callback: typing.Any) -> typing.Any: ...
        def _precomputeWorker(self, mnemonic: str, salt: str, token: int) -> None: ...
        def _addAnswer(self, value: str, style: str = ..., connStyle: str = ...) -> None: ...
        def _addDashbar(self, connStyle: str = ...) -> None: ...
        def _addNote(self, content: typing.Any) -> None: ...
        def _addInvalidWordsNote(self, words: list, prefix: str = ...) -> None: ...
        def _maskActiveInvalidNode(self) -> bool: ...
        def _addStep(self, markup: str) -> typing.Any: ...
        def _addResult(self, text: typing.Any, connStyle: str,
                       body: typing.Any = ..., hints: typing.Any = ...) -> None: ...
        def _promptMarkup(self, state: AppState) -> str: ...
        def _setState(self, state: AppState) -> None: ...
        def _updateProgress(self, percent: float) -> None: ...
        def _startLoader(self, baseMsgPlain: str) -> None: ...
        def _stopLoader(self, warn: bool = ...) -> None: ...
        def _stopBranchFlicker(self) -> None: ...
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

            if n > 2000:
                self._addNote(f"[bold {C_FAIL}]Image count cannot exceed 2000.[/]")
                return

            self._encodeCount = n

        self._setState(AppState.ENCODE_WORD_COUNT)
        self._addStep(self._promptMarkup(AppState.ENCODE_WORD_COUNT))


    def _handleWordCount(self, value: str) -> None:
        if not value:
            self._addNote(f"[bold {C_FAIL}]Please enter a word count.[/]")
            return

        self._addAnswer(value, f"bold {C_INP}")

        try:
            count = int(value)

        except ValueError:
            self._addNote(f"[bold {C_FAIL}]Please enter a number.[/]")
            return

        if count not in WORD_COUNTS:
            self._addNote(f"[bold {C_FAIL}]Invalid word count.[/]")
            return

        self._wordCount = count
        self._encodePhrase = ""
        self._setState(AppState.ENCODE_PHRASE)
        self._addStep(self._promptMarkup(AppState.ENCODE_PHRASE))


    def _handlePhrase(self, value: str) -> None:
        if not value.strip():
            self._addNote(f"[bold {C_FAIL}]Please enter a seed phrase.[/]")
            return

        normalized = " ".join(value.split())

        try:
            _, seedType, _, _ = identifySeedType(normalized, expectedLength=self._wordCount)

        except InvalidSeedWordsError as e:
            self._addInvalidWordsNote(e.words, e.prefix)
            from spicebag.app.widgets.secureInput import SecureInput
            self.query_one("#cmd-input", SecureInput).value = ""
            return

        except ValueError as e:
            self._addNote(Text(str(e), style=f"bold {C_FAIL}"))
            from spicebag.app.widgets.secureInput import SecureInput
            self.query_one("#cmd-input", SecureInput).value = ""
            return

        self._encodePhrase = normalized
        self._encodeSeedType = seedType
        self._maskActiveInvalidNode()
        self._addDashbar(C_INP)
        self._setState(AppState.ENCODE_SALT)
        self._addStep(self._promptMarkup(AppState.ENCODE_SALT))


    def _handleEncodeCell(self, value: str) -> None:
        self._addAnswer(value if value else "100", f"bold {C_INP}")

        if not value:
            self._encodeCellPx = 100

        else:
            try:
                px = int(value)

            except ValueError:
                self._addNote(f"[bold {C_FAIL}]Please enter a valid integer for cell size.[/]")
                return

            if px <= 0:
                self._addNote(f"[bold {C_FAIL}]Cell size must be at least 1 pixel.[/]")
                return

            if px > 2000:
                self._addNote(f"[bold {C_FAIL}]Cell size cannot exceed 2000px.[/]")
                return

            self._encodeCellPx = px

        self._setState(AppState.ENCODE_SAVE_PATH)
        self._addStep(self._promptMarkup(AppState.ENCODE_SAVE_PATH))


    def _handleSavePath(self, rawValue: str) -> None:
        from spicebag.constants.theme import OUTPUT_DIR

        defaultDir = OUTPUT_DIR / "encoded-images"
        result = parseSavePath(rawValue, defaultDir)

        if isinstance(result, str):
            self._addNote(Text(result, style=f"bold {C_FAIL}"))
            return

        dirStr, stem = result
        self._encodeSavePath = dirStr
        self._encodeFileStem = stem
        self._addDashbar(C_INP)
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
        from spicebag.core.generator import precomputeColorSpace

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
        from spicebag.app.tree import TreeNode

        self._stopConfirmSpinner()

        node = TreeNode(kind="imagesample", sampleSpace=cs, sampleClickable=True, sampleMasked=False)
        confirmStep.children.insert(0, node)
        self._activeSampleNode = node
        self._rebuild()


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


    def _handleEncodeConfirm(self, value: str) -> None:
        if self._encodeCount == 1 and self._colorSpace is None and self._precomputePending:
            self._triggerInputError()
            return

        if self._activeSampleNode is not None:
            self._activeSampleNode.sampleClickable = False

        self._addDashbar(C_INP)
        self._runEncode()


    @work
    async def _runEncode(self) -> None:
        self._processing = True

        from spicebag.constants.theme import OUTPUT_DIR
        from pathlib import Path

        finalPath = ""
        filename = ""

        try:
            if self._encodeSavePath:
                targetDir = Path(self._encodeSavePath)

            else:
                targetDir = OUTPUT_DIR / "encoded-images"

            mnemonic = self._encodePhrase
            wordCount = self._wordCount
            count = self._encodeCount
            salt = self._encodeSalt
            cellPx = self._encodeCellPx
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            if count == 1:
                stem = self._encodeFileStem if self._encodeFileStem else f"SeedImage{wordCount}_{timestamp}"
                filename = stem + ".png"

            else:
                stem = (self._encodeFileStem if self._encodeFileStem
                        else f"SeedImages{wordCount}x{count}_{timestamp}")
                filename = stem + ".zip"

            finalPath = str(targetDir / filename)

            # Pre-flight A: directory
            try:
                os.makedirs(targetDir, exist_ok=True)

            except PermissionError:
                self._addNote(f"[bold {C_FAIL}]Permission denied. Cannot create or access the target directory.[/]")
                return

            except OSError as e:
                self._addNote(Text(f"Target directory is invalid: {e}", style=f"bold {C_FAIL}"))
                return

            # Pre-flight B: writeability
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

            # Progress bar + encoding
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

                if getattr(self, "_cancelFlag", False):
                    raise InterruptedError()

                # Confirmed success — the result connector turns C_SUCC
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

            if getattr(self, "_cancelFlag", False):
                self._stopBranchFlicker()
                self._processing = False
                self._tabIndex = -1
                self._lastIdentifiedCommand = ""

                if self._encodingNode is not None:
                    self._encodingNode.connStyle = C_DIM

                self._addResult(Text("Operation aborted.", style=f"bold {C_FAIL}"), C_FAIL)

                try:
                    from spicebag.app.widgets.secureInput import SecureInput
                    inp = self.query_one("#cmd-input", SecureInput)
                    inp.value = ""
                    inp.isFilled = False

                except Exception:
                    pass

            elif self._processing:
                self._processing = False

                try:
                    from spicebag.app.widgets.secureInput import SecureInput
                    inp = self.query_one("#cmd-input", SecureInput)
                    if inp.value.lower() in "cancel":
                        inp.value = ""
                        inp.isFilled = False

                except Exception:
                    pass

            self._encodingNode = None
            self._resetEncodeState()


    @work(thread=True, exit_on_error=False)
    def _runEncodeInThread(self, mnemonic: str, path: str, cellPx: int, salt: str) -> None:
        def progressCb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)


        def cancelCheck() -> bool:
            return getattr(self, "_cancelFlag", False)

        try:
            encodeMnemonic(mnemonic, path, cellPx=cellPx, salt=salt, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    @work(thread=True, exit_on_error=False)
    def _runColorSpaceEncodeInThread(self, path: str, cellPx: int) -> None:
        from spicebag.core.generator import renderColorSpaceToFile

        def progressCb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)


        def cancelCheck() -> bool:
            return getattr(self, "_cancelFlag", False)

        try:
            renderColorSpaceToFile(self._colorSpace, path, cellPx=cellPx, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    @work(thread=True, exit_on_error=False)
    def _runBulkEncodeInThread(self, mnemonic: str, path: str, count: int, cellPx: int, salt: str) -> None:
        def progressCb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)


        def cancelCheck() -> bool:
            return getattr(self, "_cancelFlag", False)

        try:
            bulkEncodeMnemonic(mnemonic, path, count, cellPx=cellPx, salt=salt, cancelCheck=cancelCheck, progressCallback=progressCb)

        except InterruptedError:
            pass


    def _resetEncodeState(self) -> None:
        self._words = []
        self._wordCount = 0
        self._currentWordIdx = 0
        self._encodeSalt = ""
        self._encodePhrase = ""
        self._encodeSeedType = ""
        self._encodeCount = 1
        self._encodeCellPx = 100
        self._encodeSavePath = ""
        self._encodeFileStem = ""
        self._cancelPrecompute()
        self._activeSampleNode = None
        self._setState(AppState.IDLE)