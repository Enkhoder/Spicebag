######## LIBRARIES ########

from src.constants.theme import COMMANDS, CLIPBOARD_KEYS, AppState, blendHexColors
from textual.widgets.input import Selection
from textual.reactive import reactive
from textual.widgets import Input
from textual.strip import Strip
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
import unicodedata


######## SECURE INPUT ########

class SecureInput(Input):
    """Input widget with paste, copy, selection, and key-hold-repeat disabled."""

    isFilled = reactive(False)
    _errRatio = reactive(0.0, repaint=True)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_blink = True


    def watch_isFilled(self, value: bool) -> None:
        self.set_class(value, "filled")


    def watch_value(self, value: str) -> None:
        """Synchronously update autocomplete suggestion in the same transaction to prevent flickers."""
        typed = value.lower()
        state = getattr(self.screen, "_state", None)

        if getattr(self.screen, "_processing", False):
            if not typed:
                self._suggestion = ""
            elif "cancel".startswith(typed):
                self._suggestion = "cancel"
            else:
                self._suggestion = ""
            return

        if getattr(state, "name", None) != "IDLE" or not typed:
            self._suggestion = ""
            return

        if typed.startswith(" "):
            self._suggestion = ""
            return

        matches = [c for c in COMMANDS if c.startswith(typed)]

        if matches:
            best = "encode" if "encode" in matches else matches[0]
            if typed == best:
                self._suggestion = ""
            else:
                self._suggestion = best
        else:
            self._suggestion = ""


    def _resetSelection(self) -> None:
        """Forcefully clear selection while preserving cursor position."""
        if self.selection.start != self.selection.end:
            self.selection = Selection(self.cursor_position, self.cursor_position)


    def on_paste(self, event: events.Paste) -> None:
        event.stop()
        event.prevent_default()

        state = getattr(self.screen, "_state", None) if hasattr(self.screen, "_state") else None
        if state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM):
            return

        pasteTextRaw = event.text

        if state == AppState.ENCODE_PHRASE:
            wordCount = getattr(self.screen, "_wordCount", 0)
            words = ["".join(c for c in w if c.isalpha()) for w in pasteTextRaw.split()]
            words = [w for w in words if w]
            currentWords = len(self.value.split()) if self.value.strip() else 0
            cursorPos = min(self.cursor_position, len(self.value))
            atWordBoundary = cursorPos == 0 or self.value[cursorPos - 1] == " "
            remaining = max(0, wordCount - currentWords + (0 if atWordBoundary else 1))
            if len(words) > remaining:
                if hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()
                if hasattr(self.screen, "_triggerWordCountWarn"):
                    self.screen._triggerWordCountWarn()
                words = words[:remaining]
            pasteText = " ".join(words)
            if pasteText:
                self.insert_text_at_cursor(pasteText)
        else:
            if state in (AppState.ENCODE_COUNT, AppState.ENCODE_WORD_COUNT, AppState.ENCODE_CELL):
                cleanText = "".join(c for c in pasteTextRaw if c.isdigit())

                if self.cursor_position == 0:
                    cleanText = cleanText.lstrip("0")

                hasDirty = any(c for c in pasteTextRaw if not c.isdigit())

                if hasDirty and hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()

                if cleanText:
                    self.insert_text_at_cursor(cleanText)
            else:
                if state == AppState.IDLE:
                    pasteText = pasteTextRaw.replace("\n", "").replace("\r", "")
                    if pasteText:
                        self.insert_text_at_cursor(pasteText)
                else:
                    self.insert_text_at_cursor(pasteTextRaw)


    def on_key(self, event: events.Key) -> None:
        if getattr(self.screen, "_processing", False):
            if event.is_printable and event.character:
                char = event.character.lower()
                pos = self.cursor_position
                newValue = (self.value[:pos] + char + self.value[pos:]).lower()

                if "cancel".startswith(newValue):
                    return

                if hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()
                event.stop()
                event.prevent_default()
                return

            if event.key == "escape":
                if hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()
                event.stop()
                event.prevent_default()
                return

            if event.key == "enter":
                if self.value.lower() == "cancel":
                    if hasattr(self.screen, "_abortProcessing"):
                        self.screen._abortProcessing()
                else:
                    if hasattr(self.screen, "_triggerInputError"):
                        self.screen._triggerInputError()
                event.stop()
                event.prevent_default()
                return

            return

        if event.key in CLIPBOARD_KEYS:
            event.stop()
            event.prevent_default()
            return

        if event.key == "tab":
            if hasattr(self.screen, "cycleCommands"):
                self.screen.cycleCommands()

            event.stop()
            event.prevent_default()
            return


        state = getattr(self.screen, "_state", None) if hasattr(self.screen, "_state") else None

        if state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM, AppState.BANNER_CONFIRM):
            if event.key not in ("enter", "escape", "ctrl+s"):
                if hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()
                event.stop()
                event.prevent_default()
                return

        if state in (AppState.ENCODE_COUNT, AppState.ENCODE_WORD_COUNT, AppState.ENCODE_CELL):
            if event.is_printable and event.character:
                if not event.character.isdigit():
                    if hasattr(self.screen, "_triggerInputError"):
                        self.screen._triggerInputError()
                    event.stop()
                    event.prevent_default()
                    return

                if event.character == "0" and self.cursor_position == 0:
                    if hasattr(self.screen, "_triggerInputError"):
                        self.screen._triggerInputError()
                    event.stop()
                    event.prevent_default()
                    return



        if state == AppState.ENCODE_PHRASE:
            if event.is_printable and event.character:
                wordCount = getattr(self.screen, "_wordCount", 0)
                wordsNow = len(self.value.split()) if self.value.strip() else 0

                if event.character == " ":
                    if wordsNow >= wordCount or self.value.endswith(" "):
                        if hasattr(self.screen, "_triggerInputError"):
                            self.screen._triggerInputError()
                        if wordsNow >= wordCount:
                            if hasattr(self.screen, "_triggerWordCountWarn"):
                                self.screen._triggerWordCountWarn()
                        event.stop()
                        event.prevent_default()
                        return

                elif event.character.isalpha():
                    if wordsNow >= wordCount and self.value.endswith(" "):
                        if hasattr(self.screen, "_triggerInputError"):
                            self.screen._triggerInputError()
                        if hasattr(self.screen, "_triggerWordCountWarn"):
                            self.screen._triggerWordCountWarn()
                        event.stop()
                        event.prevent_default()
                        return

                else:
                    if hasattr(self.screen, "_triggerInputError"):
                        self.screen._triggerInputError()
                    event.stop()
                    event.prevent_default()
                    return


    def _guardLeftEdge(self, strip: Strip) -> Strip:
        if not strip._segments:
            return strip

        segs = list(strip._segments)
        first = segs[0]
        text = first.text

        if not text:
            return strip

        idx = 0

        while idx < len(text) and unicodedata.category(text[idx]).startswith("M"):
            idx += 1

        if idx == 0:
            return strip

        segs[0] = Segment(" " + text[idx:], first.style, first.control)
        return Strip(segs)


    def render_line(self, y: int) -> Strip:
        if self.value or y != 0:
            strip = self._guardLeftEdge(super().render_line(y))

            suggestion_suffix = ""
            if getattr(self, "_suggestion", "") and self._suggestion.lower().startswith(self.value.lower()):
                suggestion_suffix = self._suggestion[len(self.value):]

            newSegs = []
            for seg in strip._segments:
                style = seg.style
                isSuggestion = False

                if style:
                    if style.color and style.color.name == "#909090":
                        isSuggestion = True
                    elif "#909090" in str(style):
                        isSuggestion = True

                if suggestion_suffix and seg.text == suggestion_suffix:
                    isSuggestion = True

                if not isSuggestion:
                    style = style + Style(bold=True) if style else Style(bold=True)

                newSegs.append(Segment(seg.text, style, seg.control))

            return Strip(newSegs)

        console = self.app.console
        consoleOptions = self.app.console_options
        maxWidth = self.scrollable_content_region.width
        t = self._errRatio

        phColor = blendHexColors("#909090", "#B9646B", t)
        placeholderStyle = Style(color=phColor)

        placeholder = Text.from_markup(self.placeholder, justify="left", end="")
        placeholder.stylize(placeholderStyle)

        if self.has_focus:
            cursorBg = blendHexColors("#FFFFFF", "#FF4F5E", t)
            cursorFg = blendHexColors("#252525", "#35181A", t)
            cursorStyle = Style(bgcolor=cursorBg, color=cursorFg)

            if self._cursor_visible:
                if len(placeholder) == 0:
                    placeholder = Text(" ", end="")
                placeholder.stylize(cursorStyle, 0, 1)

        strip = Strip(console.render(placeholder, consoleOptions.update_width(maxWidth + 1)))
        return strip.apply_style(self.rich_style)
