######## LIBRARIES ########

from src.constants.theme import C_FAIL, AppState, C_INP
from src.app.handlers.savePath import parseDecodePath, _validateStem
from src.core.decoder import decodeImage, validateImage
from rich.text import Text
from textual import work
import typing

######## DECODE HANDLER MIXIN ########

class DecodeHandlerMixin:
    if typing.TYPE_CHECKING:
        _decodePath: str
        _decodeSalt: str
        _decodeWordCount: int
        _decodeInProgress: bool
        _decodeAbortHandled: bool
        _decodeToken: int
        _state: AppState
        _processing: bool
        _decodeValidating: bool
        _curStep: typing.Any
        _encodingNode: typing.Any
        _cancelFlag: bool
        app: typing.Any
        def _showSeedGrid(self, words: list, seedType: str = ...) -> None: ...
        def _finalizeDecodeAbort(self) -> None: ...
        def _addNote(self, content: typing.Any) -> None: ...
        def _addDashbar(self, connStyle: str = ...) -> None: ...
        def _addStep(self, markup: str) -> typing.Any: ...
        def _addResult(self, text: typing.Any, connStyle: str,
                       body: typing.Any = ..., hints: typing.Any = ...) -> None: ...
        def _setState(self, state: AppState) -> None: ...
        def _promptMarkup(self, state: AppState) -> str: ...
        def _startLoader(self, baseMsgPlain: str) -> None: ...
        def _stopLoader(self, warn: bool = ...) -> None: ...
        def _stopBranchFlicker(self) -> None: ...
        def _updateProgress(self, percent: float) -> None: ...

    async def _handleDecodePath(self, rawValue: str) -> None:
        from src.constants.theme import OUTPUT_DIR
        from pathlib import Path

        if getattr(self, "_decodeValidating", False):
            return

        if not rawValue.strip():
            self._addNote(Text("Please enter an image file path.", style=f"bold {C_FAIL}"))
            return

        rawCheck = rawValue.strip()
        if (len(rawCheck) >= 2 and rawCheck[0] == rawCheck[-1]
                and rawCheck[0] in ('"', "'")):
            rawCheck = rawCheck[1:-1]

        defaultDir = OUTPUT_DIR / "encoded-images"
        dirStr, stem = parseDecodePath(rawValue)
        targetDir = Path(dirStr) if dirStr else defaultDir

        # ── No stem: trailing slash or bare directory name ───────────────────
        if not stem:
            if rawCheck.endswith(('/', '\\')):
                self._addNote(Text("Please enter the image filename.", style=f"bold {C_FAIL}"))
            elif self._isDir(targetDir):
                self._addNote(Text("The path is a directory. Please specify a PNG image file.",
                                   style=f"bold {C_FAIL}"))
            else:
                self._addNote(Text("Directory not found.", style=f"bold {C_FAIL}"))
            return

        # ── Stem given but the full path resolves to a directory ─────────────
        if self._isDir(targetDir / stem):
            self._addNote(Text("The path is a directory. Please specify a PNG image file.",
                               style=f"bold {C_FAIL}"))
            return

        # ── Filename given: directory must be valid, file must exist ─────────
        if not self._isDir(targetDir):
            self._addNote(Text("Directory not found.", style=f"bold {C_FAIL}"))
            return

        stemErr = _validateStem(stem)

        if stemErr is not None:
            self._addNote(Text(stemErr, style=f"bold {C_FAIL}"))
            return

        if "." not in stem:
            self._addNote(Text("File extension is missing.", style=f"bold {C_FAIL}"))
            return

        if not stem.lower().endswith(".png"):
            self._addNote(Text("Only PNG image files are supported.", style=f"bold {C_FAIL}"))
            return

        fileName = stem
        fullPath = targetDir / fileName

        if not self._isFile(fullPath):
            self._addNote(Text("File not found.", style=f"bold {C_FAIL}"))
            return

        # ── Image type / integrity (threaded — validateImage scans pixels) ──
        self._decodeValidating = True
        try:
            worker = self._validateImageInThread(str(fullPath))
            await worker.wait()
            err = worker.result
        finally:
            self._decodeValidating = False

        # The user may have pressed ESC (cancelling to IDLE) while validation
        # ran; only continue if we are still awaiting the path input.
        if self._state != AppState.DECODE_PATH:
            return

        if err is not None:
            self._addNote(Text(err, style=f"bold {C_FAIL}"))
            return

        self._decodePath = str(fullPath)
        self._decodeWordCount = self._readWordCount(str(fullPath))
        self._addDashbar(C_INP)
        self._setState(AppState.DECODE_SALT)
        self._addStep(self._promptMarkup(AppState.DECODE_SALT))


    @staticmethod
    def _readWordCount(path: str) -> int:
        from src.core.decoder import getGridDimensions
        from PIL import Image

        try:
            with Image.open(path) as img:
                width, height = img.size
            return getGridDimensions(width, height)[2]
        except Exception:
            return 0


    @staticmethod
    def _isDir(path) -> bool:
        try:
            return path.is_dir()
        except OSError:
            return False


    @staticmethod
    def _isFile(path) -> bool:
        try:
            return path.is_file()
        except OSError:
            return False


    @work(thread=True, exit_on_error=False)
    def _validateImageInThread(self, path: str) -> typing.Optional[str]:
        try:
            validateImage(path)
            return None
        except FileNotFoundError:
            return "File not found."
        except PermissionError:
            return "Permission denied. Make sure you have read access to the file."
        except ValueError as e:
            return str(e)
        except Exception:
            return "Invalid image format or failed to load pixel data."


    def _handleDecodeConfirm(self, value: str) -> None:
        self._addDashbar(C_INP)
        self._runDecode(self._decodeSalt)


    @work
    async def _runDecode(self, salt: str) -> None:
        self._processing = True
        self._decodeInProgress = True
        self._decodeAbortHandled = False
        self._decodeToken += 1
        token = self._decodeToken
        self._encodingNode = None

        # The image was already validated at the path-input stage, so the only
        # thing left to verify here is the salt. The progress bar advances one
        # uniform step per word recovered (see decodeImage); a wrong salt fails
        # validation wholesale and leaves the bar at 0%.
        self._startLoader("Decoding seed image")

        try:
            worker = self._runDecodeInThread(self._decodePath, salt)
            await worker.wait()

            if token != self._decodeToken or self._decodeAbortHandled:
                return

            if worker.error is not None:
                raise worker.error
            mnemonic = worker.result
            if not isinstance(mnemonic, tuple) or len(mnemonic) != 2:
                raise ValueError("Decoded result is not a valid string.")
            mnemonic, seedType = mnemonic

            words = mnemonic.split()
            self._stopLoader()
            self._showSeedGrid(words, seedType)

        except InterruptedError:
            if token == self._decodeToken and not self._decodeAbortHandled:
                self._finalizeDecodeAbort()

        except Exception:
            if token != self._decodeToken or self._decodeAbortHandled:
                return
            self._stopLoader(warn=True)
            saltError = "Salt is incorrect." if salt else "Image is salted."
            self._addResult(Text(saltError, style=f"bold {C_FAIL}"), C_FAIL)

        finally:
            if token == self._decodeToken and not self._decodeAbortHandled:
                self._stopBranchFlicker()
                self._processing = False
                self._decodeInProgress = False
                self._decodePath = ""
                self._decodeSalt = ""
                self._encodingNode = None
                self._setState(AppState.IDLE)


    @work(thread=True, exit_on_error=False)
    def _runDecodeInThread(self, path: str, salt: str) -> tuple[str, str]:
        def p_cb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)
        def c_check() -> bool:
            return getattr(self, "_cancelFlag", False)

        return decodeImage(
            path, salt=salt, progressCallback=p_cb, validate=False, cancelCheck=c_check
        )
