######## LIBRARIES ########

from textual.widgets import Static
from textual.events import Click



######## COLOR CELL ########

class ColorCell(Static):
    """A color cell widget that displays a specific RGB color and reveals its details on click."""

    def __init__(self, r: int, g: int, b: int, coord: tuple[int, int], **kwargs):
        super().__init__("", **kwargs)
        self.r = r
        self.g = g
        self.b = b
        self.coord = coord
        self.styles.background = f"rgb({r},{g},{b})"
        self.styles.width = "1fr"
        self.styles.height = "1fr"
        self.styles.border = ("blank", "transparent")
        self.add_class("color-cell")


    def on_click(self, event: Click) -> None:
        """Reveal RGB details via notification on click."""
        self.app.notify(
            f"Cell {self.coord}: RGB({self.r}, {self.g}, {self.b})",
            title="Color Details",
            timeout=3
        )