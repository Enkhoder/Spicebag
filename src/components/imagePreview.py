######## LIBRARIES ########

from src.constants.defaults import RGB_VALUE_SHIFTS
from src.core.generator import identifySeedType
from src.components.colorCell import ColorCell
from src.utils.colors import encodeWord
from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import Static


######## IMAGE PREVIEW ########

class ImagePreview(Static):
    """A container that dynamically renders a grid of ColorCells representing the mnemonic."""

    def compose(self) -> ComposeResult:
        yield Grid(id="preview-grid")


    def updatePreview(self, mnemonic: str, maskKey: bytes | None = None, maxIdx: int = 2048) -> None:
        """Re-render the grid based on the mnemonic phrase."""
        try:
            indices, standard, numWords, currentMaxIdx = identifySeedType(mnemonic)

        except ValueError:
            # If invalid, clear the grid
            self._clearGrid()
            return

        if standard == "SLIP39":
            cols, rows = (4, 5) if numWords == 20 else (3, 11)

        else:
            mapping = {12: (3, 4), 15: (3, 5), 18: (3, 6), 21: (3, 7), 24: (4, 6)}
            cols, rows = mapping.get(numWords, (3, 4))

        grid = self.query_one("#preview-grid", Grid)
        self._clearGrid()

        grid.styles.grid_size_columns = cols
        grid.styles.grid_size_rows = rows

        from src.utils.colors import deriveMask

        for i in range(numWords):
            wordMask = deriveMask(maskKey, i, currentMaxIdx) if maskKey else 0
            color = encodeWord(indices[i], mask=wordMask, shift=RGB_VALUE_SHIFTS[i], maxIndex=currentMaxIdx)
            r = i // cols
            c = i % cols
            cell = ColorCell(r=color[0], g=color[1], b=color[2], coord=(r, c))
            grid.mount(cell)


    def _clearGrid(self) -> None:
        """Remove all children from the grid."""
        grid = self.query_one("#preview-grid", Grid)
        grid.remove_children()