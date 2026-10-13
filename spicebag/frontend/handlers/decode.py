######## LIBRARIES ########

from spicebag.frontend.theme import C_FAIL, C_INP, IMAGES_DIR, AppState
from spicebag.backend.decoder import decodeImage, imageError
from spicebag.backend.paths import locateImage
from rich.text import Text
from textual import work
import typing



######## CONSTANTS ########

IMAGE_PATH_ERRORS = {
    "filename": "Please enter the image filename.",
    "folder": "The path is a directory. Please specify a PNG image file.",
    "noDir": "Directory not found.",
    "noExtension": "File extension is missing.",
    "notPng": "Only PNG image is supported.",
    "missing": "Image not found."
}



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
        _encodingNode: typing.Any
        def _showSeedGrid(self, words: list, seedType: str = ...) -> None: ...
        def _addNote(self, content: typing.Any) -> None: ...
        def _addAnswer(self, value: str, style: str = ..., connStyle: str = ...) -> None: ...
        def _addDashbar(self, connStyle: str = ...) -> None: ...
        def _addStep(self, markup: str) -> typing.Any: ...
        def _addResult(self, text: typing.Any, connStyle: str, body: typing.Any = ...) -> None: ...
        def _setState(self, state: AppState) -> None: ...
        def _promptMarkup(self, state: AppState) -> str: ...
        def _startLoader(self, baseMsgPlain: str) -> None: ...
        def _stopLoader(self, warn: bool = ...) -> None: ...
        def _stopBranchFlicker(self) -> None: ...
        def _workerHooks(self) -> tuple[typing.Any, typing.Any]: ...

    async def _handleDecodePath(self, rawValue: str) -> None:
        if self._decodeValidating:
            return

        if not rawValue.strip():
            return

        self._addAnswer(rawValue.strip(), f"bold {C_INP}")
        fullPath, reason = locateImage(rawValue, IMAGES_DIR)
        if fullPath is None:
            self._addNote(Text(IMAGE_PATH_ERRORS[reason], style=f"bold {C_FAIL}"))
            return

        self._decodeValidating = True
        try:
            worker = self._validateImageInThread(fullPath)
            await worker.wait()
            err = worker.result

        finally:
            self._decodeValidating = False

        if self._state != AppState.DECODE_PATH:
            return

        if err is not None:
            self._addNote(Text(err, style=f"bold {C_FAIL}"))
            return

        self._decodePath = fullPath
        self._decodeWordCount = self._readWordCount(fullPath)
        self._setState(AppState.DECODE_SALT)
        self._addStep(self._promptMarkup(AppState.DECODE_SALT))


    @staticmethod
    def _readWordCount(path: str) -> int:
        from spicebag.backend.decoder import getGridDimensions
        from PIL import Image

        try:
            with Image.open(path) as img:
                width, height = img.size

            return getGridDimensions(width, height)[2]

        except Exception:
            return 0


    @work(thread=True, exit_on_error=False)
    def _validateImageInThread(self, path: str) -> typing.Optional[str]:
        return imageError(path)


    def _handleDecodeConfirm(self) -> None:
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

        self._startLoader("Decoding seed image")

        try:
            worker = self._runDecodeInThread(self._decodePath, salt)
            await worker.wait()

            if token != self._decodeToken or self._decodeAbortHandled:
                return

            mnemonic, seedType = typing.cast(tuple[str, str], worker.result)
            self._stopLoader()
            self._showSeedGrid(mnemonic.split(), seedType)

        except Exception:
            if token != self._decodeToken or self._decodeAbortHandled:
                return

            self._stopLoader(warn=True)
            saltError = "Salt is incorrect." if salt else "Image is salted or predates v4.0.0."
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
        progressCb, cancelCheck = self._workerHooks()
        return decodeImage(
            path, salt=salt, progressCallback=progressCb, validate=False, cancelCheck=cancelCheck
        )