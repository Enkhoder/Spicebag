######## LIBRARIES ########

from textual.message import Message
from textual.widgets import Static
from rich.text import Text
from textual import events



######## OPTIONS BAR ########

class OptionsBar(Static):

    class Selected(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()


    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._options: list[str] = []
        self._selectedIdx: int = -1
        self._hoveredIdx: int = -1
        self._isInteractive: bool = False
        self._positions: list[tuple[int, int]] = []
        self._suffix: Text = Text()
        self._optionsEndPos: int = 0
        self._escSpan: tuple[int, int] | None = None
        self._escHovered: bool = False
        self._staticContent: str | Text | None = None


    def setInteractive(
        self, options: list[str], selectedIdx: int, suffix: Text | None = None
    ) -> None:
        self._options = options
        self._selectedIdx = selectedIdx
        self._hoveredIdx = -1
        self._escHovered = False
        self._isInteractive = True
        self._suffix = suffix if suffix is not None else Text()
        self._computePositions()

        self._escSpan = None
        if self._suffix:
            suffixPlain = self._suffix.plain
            dotIdx = suffixPlain.rfind("·")
            escIdx = suffixPlain.find("ESC", dotIdx) if dotIdx != -1 else -1
            if escIdx == -1:
                escIdx = suffixPlain.find("ESC")

            if escIdx != -1:
                start = self._optionsEndPos + escIdx
                self._escSpan = (start, self._optionsEndPos + len(suffixPlain))

        self.update(self._buildText())


    def setStatic(self, content: str | Text) -> None:
        self._isInteractive = False
        self._hoveredIdx = -1
        self._escHovered = False
        self._options = []
        self._positions = []
        self._staticContent = content

        plain = content.plain if isinstance(content, Text) else Text.from_markup(content).plain
        dotIdx = plain.rfind("·")
        escIdx = plain.find("ESC", dotIdx) if dotIdx != -1 else -1
        if escIdx == -1:
            escIdx = plain.find("ESC")

        self._escSpan = (escIdx, len(plain)) if escIdx != -1 else None

        self.update(content)


    def _computePositions(self) -> None:
        self._positions = []
        pos = 0
        for i, opt in enumerate(self._options):
            if i > 0:
                pos += 5

            self._positions.append((pos, pos + len(opt)))
            pos += len(opt)

        self._optionsEndPos = pos


    def _buildText(self) -> Text:
        from spicebag.constants.theme import C_DIM, C_INP, C_WHITE
        text = Text()
        for i, opt in enumerate(self._options):
            if i > 0:
                text.append("  ·  ", style=C_DIM)

            if i == self._selectedIdx:
                text.append(opt, style=f"bold {C_INP}")

            elif i == self._hoveredIdx:
                text.append(opt, style=C_WHITE)

            else:
                text.append(opt, style=C_DIM)

        text.append_text(self._suffix)
        if self._escHovered and self._escSpan is not None:
            text.stylize("underline", self._escSpan[0], self._escSpan[1])

        return text


    def _rebuildStatic(self) -> None:
        if self._staticContent is None:
            return

        if isinstance(self._staticContent, Text):
            t = self._staticContent.copy()

        else:
            t = Text.from_markup(self._staticContent)

        if self._escHovered and self._escSpan is not None:
            t.stylize("underline", self._escSpan[0], self._escSpan[1])

        self.update(t)


    def _hitTest(self, x: int) -> int:
        try:
            padLeft = self.styles.padding.left

        except Exception:
            padLeft = 0

        cx = x - padLeft
        if cx < 0:
            return -1

        for i, (start, end) in enumerate(self._positions):
            if start <= cx < end:
                return i

        return -1


    def on_mouse_move(self, event: events.MouseMove) -> None:
        try:
            padLeft = self.styles.padding.left

        except Exception:
            padLeft = 0

        cx = event.x - padLeft
        escHovered = self._escSpan is not None and self._escSpan[0] <= cx < self._escSpan[1]

        if self._isInteractive:
            idx = self._hitTest(event.x)
            if idx == self._selectedIdx:
                idx = -1

            if idx != self._hoveredIdx or escHovered != self._escHovered:
                self._hoveredIdx = idx
                self._escHovered = escHovered
                self.update(self._buildText())

        else:
            if escHovered != self._escHovered:
                self._escHovered = escHovered
                self._rebuildStatic()


    def on_leave(self, _event: events.Leave) -> None:
        optChanged = self._isInteractive and self._hoveredIdx != -1
        escChanged = self._escHovered
        if not optChanged and not escChanged:
            return

        if optChanged:
            self._hoveredIdx = -1

        self._escHovered = False
        if self._isInteractive:
            self.update(self._buildText())

        else:
            self._rebuildStatic()


    def on_click(self, event: events.Click) -> None:
        try:
            padLeft = self.styles.padding.left

        except Exception:
            padLeft = 0

        cx = event.x - padLeft

        if self._isInteractive:
            idx = self._hitTest(event.x)
            if idx != -1:
                self.post_message(OptionsBar.Selected(self._options[idx]))
                return

        if self._escSpan is not None:
            start, end = self._escSpan
            if start <= cx < end:
                try:
                    actionCancel = getattr(self.screen, "action_cancel", None)
                    if callable(actionCancel):
                        actionCancel()

                except Exception:
                    pass