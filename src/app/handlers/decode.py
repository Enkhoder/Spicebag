######## LIBRARIES ########

from src.constants.theme import C_FAIL, AppState, C_SUCC, C_INP, C_WHITE
from src.app.handlers.savePath import parseDecodePath
from src.core.decoder import decodeImage, validateImage
from rich.text import Text
from textual import work
import typing
import re

######## DECODE HANDLER MIXIN ########

class DecodeHandlerMixin:
    if typing.TYPE_CHECKING:
        _decodePath: str
        _decodeSalt: str
        _state: AppState
        _processing: bool
        _decodeValidating: bool
        _curStep: typing.Any
        _encodingNode: typing.Any
        app: typing.Any
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

        defaultDir = OUTPUT_DIR / "encoded-images"
        dirStr, stem = parseDecodePath(rawValue)
        targetDir = Path(dirStr) if dirStr else defaultDir

        # ── Trailing separator with no filename (e.g. "<dir>//") ────────────
        if not stem and re.search(r"[/\\]{2,}", rawValue):
            self._addNote(Text("Please enter the image filename.", style=f"bold {C_FAIL}"))
            return

        # ── No separator: the input names a directory, not an image file ────
        if not stem:
            if self._isDir(targetDir):
                self._addNote(Text("The path is a directory. Please specify a PNG image file.",
                                   style=f"bold {C_FAIL}"))
            else:
                self._addNote(Text("Directory not found.", style=f"bold {C_FAIL}"))
            return

        # ── Filename given: directory must be valid, file must exist ────────
        if not self._isDir(targetDir):
            self._addNote(Text("Directory not found.", style=f"bold {C_FAIL}"))
            return

        fileName = stem if stem.lower().endswith(".png") else stem + ".png"
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
        self._addDashbar(C_INP)
        self._setState(AppState.DECODE_SALT)
        self._addStep(self._promptMarkup(AppState.DECODE_SALT))


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
        self._encodingNode = None

        # The image was already validated at the path-input stage, so the only
        # thing left to verify here is the salt. The progress bar advances one
        # uniform step per word recovered (see decodeImage).
        self._startLoader("Decoding seed image")

        try:
            worker = self._runDecodeInThread(self._decodePath, salt)
            await worker.wait()
            if worker.error is not None:
                raise worker.error
            mnemonic = worker.result
            if not isinstance(mnemonic, str):
                raise ValueError("Decoded result is not a valid string.")

            words = mnemonic.split()
            self._stopLoader()
            decoded = Text(f"Decoded: {len(words)} words recovered:", style=C_WHITE)
            wordLines = [Text(f"{i:>2}.  {w}", style=C_WHITE) for i, w in enumerate(words, 1)]
            self._addResult(decoded, C_SUCC, hints=wordLines)

        except Exception:
            self._stopLoader(warn=True)
            saltError = "Salt is incorrect." if salt else "Image is salted."
            self._addResult(Text(saltError, style=f"bold {C_FAIL}"), C_FAIL)

        finally:
            self._stopBranchFlicker()
            self._processing = False
            self._decodePath = ""
            self._decodeSalt = ""
            self._encodingNode = None
            self._setState(AppState.IDLE)


    @work(thread=True, exit_on_error=False)
    def _runDecodeInThread(self, path: str, salt: str) -> str:
        def p_cb(percent: float) -> None:
            self.app.call_from_thread(self._updateProgress, percent)

        return decodeImage(path, salt=salt, progressCallback=p_cb, validate=False)
