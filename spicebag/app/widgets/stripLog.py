######## LIBRARIES ########

from textual.scroll_view import ScrollView
from textual.geometry import Size
from rich.console import Console
from rich.segment import Segment
from typing import Any, Sequence
from textual.strip import Strip
from rich.text import Text



######## RASTERIZERS ########

def renderStrips(lines: Sequence[Text], console: Console) -> list[Strip]:
    """Rasterize pre-wrapped lines into Strips, exactly one Strip per input line.

    Every line the tree renderer emits is already wrapped to the target width and carries no_wrap,
    so rendering each at its own cell length neither truncates nor pads it. The 1:1 mapping is
    load-bearing: hover and click regions address the document by line index, so a line that
    rasterized to two Strips (or none) would silently shift every line below it."""
    options = console.options.update(overflow="ignore", no_wrap=True)
    out: list[Strip] = []

    for line in lines:
        segments = console.render(line, options.update_width(max(1, line.cell_len)))
        strips = Strip.from_lines(list(Segment.split_lines(segments)))
        out.append(strips[0] if strips else Strip.blank(0))

    return out


def renderRenderable(renderable: Any, width: int, console: Console) -> list[Strip]:
    """Rasterize one Rich renderable, such as the mascot banner table, into Strips."""
    segments = console.render(renderable, console.options.update_width(width))

    return Strip.from_lines(list(Segment.split_lines(segments)))



######## STRIP LOG ########

class StripLog(ScrollView):
    """Scrolling view over a pre-rasterized document, which the screen swaps in line by line.

    A RichLog stood here until the documents outgrew it. RichLog only appends, so any change to an
    earlier line meant clearing it and re-writing every line, which re-measured and re-wrapped the
    whole history on each frame. Holding the Strips instead lets a screen hand back the identical
    Strip objects for everything it did not touch, so only the lines that moved are re-cropped."""

    ALLOW_SELECT = False

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._strips: list[Strip] = []
        self._lineCache: dict[tuple[int, int, int], Strip] = {}


    def setLines(self, strips: list[Strip], widest: int) -> None:
        """Swap in a new document, dropping only the cropped lines that moved.

        The screen hands back the identical Strip objects for every section it did not rebuild, so
        identity is enough to tell which lines are stale."""
        previous = self._strips

        if len(previous) != len(strips):
            self._lineCache.clear()

        else:
            stale = {i for i, (old, new) in enumerate(zip(previous, strips)) if old is not new}
            for key in [key for key in self._lineCache if key[0] in stale]:
                del self._lineCache[key]

        self._strips = strips
        self.virtual_size = Size(widest, len(strips))
        self.refresh()


    def scrollToEnd(self) -> None:
        self.scroll_to(y=max(0, len(self._strips) - self.scrollable_content_region.height), animate=False)


    def notify_style_update(self) -> None:
        self._lineCache.clear()
        super().notify_style_update()


    def render_line(self, y: int) -> Strip:
        scrollX, scrollY = self.scroll_offset
        width = self.scrollable_content_region.width
        idx = scrollY + y

        key = (idx, scrollX, width)
        cached = self._lineCache.get(key)
        if cached is not None:
            return cached

        richStyle = self.rich_style
        if 0 <= idx < len(self._strips):
            strip = self._strips[idx].crop_extend(scrollX, scrollX + width, richStyle).apply_style(richStyle)

        else:
            strip = Strip.blank(width, richStyle)

        self._lineCache[key] = strip
        return strip