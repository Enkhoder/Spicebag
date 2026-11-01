######## LIBRARIES ########

from spicebag.frontend.theme import (
    ARROW_STEPS, CLIPBOARD_KEYS, HUE_EDIT_KEYS, PASTE_KEYS, SCREENSHOT_KEY, SYSTEM_KEYS, AppState,
    C_BG, C_DIM, C_FAIL, C_SUCC, C_WHITE,
    blendHexColors, matchCommand, parseHueRange
)
from spicebag.frontend.utils.clipboard import clearClipboard, readClipboard
from spicebag.backend.defaults import MAX_SEED_WORDS
from textual.reactive import reactive
from textual.widgets import Input
from rich.segment import Segment
from textual.strip import Strip
from rich.style import Style
from rich.text import Text
from textual import events
import unicodedata
import re



######## SECURE INPUT ########

class SecureInput(Input):
    """Input that filters typing and pasting per state, blocks the clipboard and selection keys, and draws its own
    command suggestion and placeholder."""

    _errRatio = reactive(0.0, repaint=True)
    _hueRatio = reactive(0.0, repaint=True)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ghost = ""


    @property
    def _value(self) -> Text:
        """Hidden input draws one bar per character in place of Textual's password dots."""
        if self.password:
            return Text("─" * len(self.value), no_wrap=True, overflow="ignore", end="")

        return super()._value


    def watch_value(self, value: str) -> None:
        """Synchronously update autocomplete suggestion in the same transaction to prevent flickers."""
        stripped = value.lower().strip()
        state = getattr(self.screen, "_state", None)

        if getattr(self.screen, "_processing", False):
            if stripped and "cancel".startswith(stripped):
                self._ghost = "cancel"[len(stripped):]

            else:
                self._ghost = ""

            return

        if getattr(state, "name", None) != "IDLE" or not stripped:
            self._ghost = ""
            return

        best = matchCommand(stripped)
        self._ghost = best[len(stripped):] if best else ""


    def _cursorColors(self) -> tuple[str, str]:
        """Cursor background and foreground, blended toward the green hue blink and then the red error flash, so
        an error shown during a blink still reads red."""
        background = blendHexColors(blendHexColors(C_WHITE, C_SUCC, self._hueRatio), C_FAIL, self._errRatio)
        foreground = blendHexColors(blendHexColors(C_BG, "#1A301E", self._hueRatio), "#35181A", self._errRatio)
        return background, foreground


    def get_component_rich_style(self, *names: str, partial: bool = False, default: Style | None = None) -> Style:
        style = super().get_component_rich_style(*names, partial=partial, default=default)
        if names != ("input--cursor",) or (self._hueRatio == 0 and self._errRatio == 0):
            return style

        background, foreground = self._cursorColors()
        return style + Style(bgcolor=background, color=foreground)


    def on_paste(self, event: events.Paste) -> None:
        event.stop()
        event.prevent_default()
        clearClipboard()

        state = getattr(self.screen, "_state", None) if hasattr(self.screen, "_state") else None
        if state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM):
            hueInputActive = getattr(self.screen, "_hueInputActive", None)
            if state == AppState.ENCODE_CONFIRM and hueInputActive is not None and hueInputActive():
                self._pasteHueRange(event.text)

            return

        pasteTextRaw = event.text

        if state == AppState.ENCODE_PHRASE:
            words = ["".join(c for c in w if c.isalpha()) for w in pasteTextRaw.split()]
            words = [w for w in words if w]
            currentWords = len(self.value.split()) if self.value.strip() else 0
            cursorPos = min(self.cursor_position, len(self.value))
            atWordBoundary = cursorPos == 0 or self.value[cursorPos - 1] == " "
            remaining = max(0, MAX_SEED_WORDS - currentWords + (0 if atWordBoundary else 1))
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
            if state in (AppState.ENCODE_COUNT, AppState.ENCODE_CELL):
                pasteText = pasteTextRaw.strip()
                cleanText = ""
                for char in pasteText:
                    if not char.isdigit():
                        break

                    cleanText += char

                trimmed = cleanText.lstrip("0") if self.cursor_position == 0 else cleanText
                if (cleanText != pasteText or not trimmed) and hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()

                if trimmed:
                    self.insert_text_at_cursor(trimmed)

            else:
                if state == AppState.IDLE:
                    pasteText = pasteTextRaw.replace("\n", "").replace("\r", "")
                    if pasteText:
                        self.insert_text_at_cursor(pasteText)

                else:
                    self.insert_text_at_cursor(pasteTextRaw)


    def on_mouse_down(self, event: events.MouseDown) -> None:
        handler = getattr(self.screen, "_onInputBarClick", None)
        if handler is not None:
            handler()


    @staticmethod
    def _hyphenThenSpace(value: str, pos: int, char: str) -> bool:
        """Whether inserting char at pos leaves a hyphen directly followed by a space, which a hue range refuses."""
        return char == " " and value[pos - 1:pos] == "-" or char == "-" and value[pos:pos + 1] == " "


    def _pasteHueRange(self, raw: str) -> None:
        """Paste into a hue range under the typing rules, up to the first character typing would refuse, which shows
        its reason. Whitespace is trimmed to single spaces between hues, and a hyphen between two hues, bare or with
        spaces on both sides, becomes that space: 60-120 and 60 - 120 go in as 60 120, and 60 - -120 as 60 -120."""
        pos = self.cursor_position
        before, after = self.value[:pos], self.value[pos:]
        text = re.sub(r"\s+", " ", raw)
        if not before or before.endswith(" "):
            text = text.lstrip(" ")

        tailMatch = re.search(r"[0-9] *$", before)
        tail = tailMatch.group() if tailMatch else ""
        text = re.sub(r"(?<=[0-9])-(?=[0-9])", " ", tail + text)
        text = re.sub(r"(?<=[0-9])( +)- +(?=-?[0-9])", r"\1", text)[len(tail):]

        accepted = ""
        refused = False
        error = None
        for char in text:
            typed = before + accepted
            if char not in "0123456789- " or self._hyphenThenSpace(typed + after, len(typed), char):
                refused = True
                break

            error = parseHueRange(typed + char + after, final=False)
            if error is not None:
                break

            accepted += char

        if not after or after.startswith(" "):
            accepted = accepted.rstrip(" ")

        if accepted:
            self.insert_text_at_cursor(accepted)

        if refused:
            self.screen._triggerInputError()

        elif error is not None:
            self.screen._showHueError(error)


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

        if event.key in PASTE_KEYS:
            event.stop()
            event.prevent_default()
            text = readClipboard()
            if text:
                self.on_paste(events.Paste(text))

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

        hueInputActive = getattr(self.screen, "_hueInputActive", None)
        if state == AppState.ENCODE_CONFIRM and hueInputActive is not None and hueInputActive():
            if event.key in ARROW_STEPS and getattr(self.screen, "_cellNav", False):
                self.screen._moveSampleSelection(*ARROW_STEPS[event.key])
                event.stop()
                event.prevent_default()
                return

            if event.key in ("up", "down"):
                event.stop()
                event.prevent_default()
                return

            if event.key in HUE_EDIT_KEYS:
                return

            if event.is_printable and event.character:
                pos = self.cursor_position
                if event.character not in "0123456789- " or self._hyphenThenSpace(self.value, pos, event.character):
                    self.screen._triggerInputError()
                    event.stop()
                    event.prevent_default()
                    return

                if event.character == " " and len(re.findall(r"\d+", self.value)) >= 2:
                    self.screen._showHueError("Too many hues.")
                    event.stop()
                    event.prevent_default()
                    return

                error = parseHueRange(self.value[:pos] + event.character + self.value[pos:], final=False)
                if error is not None:
                    self.screen._showHueError(error)
                    event.stop()
                    event.prevent_default()

                return

        if state in (AppState.ENCODE_CONFIRM, AppState.DECODE_CONFIRM, AppState.BANNER_CONFIRM):
            if event.key not in ("enter", "escape", SCREENSHOT_KEY) and event.key not in SYSTEM_KEYS:
                if hasattr(self.screen, "_triggerInputError"):
                    self.screen._triggerInputError()

                event.stop()
                event.prevent_default()
                return

        if state in (AppState.ENCODE_COUNT, AppState.ENCODE_CELL):
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
                wordsNow = len(self.value.split()) if self.value.strip() else 0

                if event.character == " ":
                    if wordsNow >= MAX_SEED_WORDS or self.value.endswith(" "):
                        if hasattr(self.screen, "_triggerInputError"):
                            self.screen._triggerInputError()

                        if wordsNow >= MAX_SEED_WORDS:
                            if hasattr(self.screen, "_triggerWordCountWarn"):
                                self.screen._triggerWordCountWarn()

                        event.stop()
                        event.prevent_default()
                        return

                elif event.character.isalpha():
                    if wordsNow >= MAX_SEED_WORDS and self.value.endswith(" "):
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
            ghost = self._ghost

            if not ghost:
                strip = self._guardLeftEdge(super().render_line(y))
                newSegs = [
                    Segment(
                        seg.text,
                        seg.style + Style(bold=True) if seg.style else Style(bold=True),
                        seg.control
                    )
                    for seg in strip._segments
                ]
                return Strip(newSegs)

            value = self.value
            insertAt = len(value.rstrip())
            ghostEnd = insertAt + len(ghost)

            ghostStyle = Style(color=blendHexColors(C_DIM, "#B9646B", self._errRatio))
            boldStyle = Style(bold=True)

            chars = list(value)
            if len(chars) < ghostEnd:
                chars += [" "] * (ghostEnd - len(chars))

            for i, g in enumerate(ghost):
                chars[insertAt + i] = g

            display = Text("".join(chars), no_wrap=True, overflow="ignore", end="")

            display.stylize(boldStyle, 0, insertAt)
            display.stylize(ghostStyle, insertAt, ghostEnd)
            display.stylize(boldStyle, ghostEnd, len(chars))

            if self._cursor_visible and self.has_focus:
                cursorCol = self.cursor_position
                cursorStyle = self.get_component_rich_style("input--cursor")

                if cursorCol >= len(display):
                    display.append(" ")

                display.stylize(cursorStyle, cursorCol, cursorCol + 1)

            console = self.app.console
            consoleOptions = self.app.console_options
            maxWidth = self.scrollable_content_region.width

            strip = Strip(console.render(display, consoleOptions.update_width(maxWidth + 1)))
            return strip.apply_style(self.rich_style)

        console = self.app.console
        consoleOptions = self.app.console_options
        maxWidth = self.scrollable_content_region.width
        t = self._errRatio

        phColor = blendHexColors(C_DIM, "#B9646B", t)
        placeholderStyle = Style(color=phColor)

        placeholder = Text.from_markup(self.placeholder, justify="left", end="")
        placeholder.stylize(placeholderStyle)

        if self.has_focus:
            cursorBg, cursorFg = self._cursorColors()
            cursorStyle = Style(bgcolor=cursorBg, color=cursorFg)

            if self._cursor_visible:
                if len(placeholder) == 0:
                    placeholder = Text(" ", end="")

                placeholder.stylize(cursorStyle, 0, 1)

        strip = Strip(console.render(placeholder, consoleOptions.update_width(maxWidth + 1)))
        return strip.apply_style(self.rich_style)