######## LIBRARIES ########

from src.constants.theme import C_FAIL, AppState, C_SUCC, C_DIM, C_INP, C_WHITE
from src.core.decoder import decodeImage
from rich.text import Text
from textual import work
import typing
import os

######## DECODE HANDLER MIXIN ########

class DecodeHandlerMixin:
    if typing.TYPE_CHECKING:
        _decodePath: str
        _decodeSalt: str
        _processing: bool
        _curStep: typing.Any
        _encodingNode: typing.Any
        def _addDashbar(self, connStyle: str = ...) -> None: ...
        def _addStep(self, markup: str) -> typing.Any: ...
        def _addResult(self, text: typing.Any, connStyle: str,
                       body: typing.Any = ..., hints: typing.Any = ...) -> None: ...
        def _setState(self, state: AppState) -> None: ...

    def _handleDecodeConfirm(self, value: str) -> None:
        self._addDashbar(C_INP)
        self._runDecode(self._decodeSalt)


    @work
    async def _runDecode(self, salt: str) -> None:
        self._processing = True
        self._encodingNode = None

        # The decode result mirrors encode: a "Decoding seed image" step holding
        # a C_SUCC "Decoded" child, or a C_FAIL child on failure.
        self._addStep(f"[{C_WHITE}]Decoding seed image[/]")

        try:
            if os.path.isdir(self._decodePath):
                self._addResult(
                    Text("The path is a directory. Please specify a PNG image file.",
                         style=f"bold {C_FAIL}"),
                    C_FAIL,
                )
                return

            try:
                worker = self._runDecodeInThread(self._decodePath, salt)
                await worker.wait()
                if worker.error is not None:
                    raise worker.error
                mnemonic = worker.result
                if not isinstance(mnemonic, str):
                    raise ValueError("Decoded result is not a valid string.")

                words = mnemonic.split()
                decoded = Text(f"Decoded: {len(words)} words recovered:", style=C_WHITE)
                wordLines = [Text(f"{i:>2}.  {w}", style=C_WHITE) for i, w in enumerate(words, 1)]
                self._addResult(decoded, C_SUCC, hints=wordLines)

            except ValueError as e:
                self._addResult(Text(str(e), style=f"bold {C_FAIL}"), C_FAIL)
            except FileNotFoundError:
                self._addResult(
                    Text("File not found. Please verify the file path and try again.",
                         style=f"bold {C_FAIL}"),
                    C_FAIL,
                )
            except PermissionError:
                self._addResult(
                    Text("Permission denied. Please ensure you have read access to the file.",
                         style=f"bold {C_FAIL}"),
                    C_FAIL,
                )
            except Exception:
                self._addResult(
                    Text("Invalid image format or failed to load pixel data.",
                         style=f"bold {C_FAIL}"),
                    C_FAIL,
                )
        finally:
            self._processing = False
            self._decodePath = ""
            self._decodeSalt = ""
            self._setState(AppState.IDLE)


    @work(thread=True, exit_on_error=False)
    def _runDecodeInThread(self, path: str, salt: str) -> str:
        return decodeImage(path, salt=salt)
