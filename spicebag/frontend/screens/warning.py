######## LIBRARIES ########

from spicebag.frontend.theme import C_BG, C_WHITE, C_INP, C_FAIL, C_SUCC, SCREENSHOT_KEY, gradientColor
from textual.containers import Vertical
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static
from textual.screen import Screen
from textual import events, work
from rich.cells import cell_len
from rich.text import Text
import asyncio
import random
import string
import re



######## WARNING SCREEN ########

class WarningScreen(Screen):
    """Initial security warning screen with 4-key sequential confirmation."""

    can_focus = False
    _displayProgress = reactive(0.0)

    VALID_CHARS = [c for c in string.ascii_lowercase if c != 'o']

    def __init__(self) -> None:
        super().__init__()
        self._keys: list[str] = random.sample(self.VALID_CHARS, 4)
        self._step = 0
        self._blockWidth = 60


    def _bullet(self, body: str, index: int) -> str:
        """The bullet being confirmed is bold white, the one just confirmed turns C_INP."""
        if self._step == index:
            return f"[bold {C_WHITE}]{body}[/]"

        if self._step == index + 1:
            return f"[{C_INP}]{body}[/]"

        return body


    def _paragraphs(self) -> list:
        """The body as (markup, hanging indent, shown) paragraphs, None for a blank line and RULE for a separator.
        Paragraphs not revealed yet still take their wrapped height as blank lines, so the block never jumps."""
        rule = "RULE"
        return [
            (f"[bold {C_FAIL}]S E C U R I T Y   W A R N I N G[/]", 0, True),
            None,
            rule,
            (f"You are about to encode or decode a visual representation of a wallet [{C_FAIL}]seed phrase[/].", 0, True),
            None,
            (f"Turning off [{C_FAIL}]all connections[/] is highly advised for heightened security during this session.",
             0, True),
            None,
            (f"Proceed [{C_FAIL}]if and only if[/] all of the following are true:", 0, True),
            None,
            (self._bullet("• You are in a private, isolated location", 0), 2, True),
            (self._bullet("• No one else can see your screen", 1), 2, self._step >= 1),
            (self._bullet("• No recording / surveillance devices are present", 2), 2, self._step >= 2),
            None,
            (f"This program provides [{C_FAIL}]no protection[/] against malware, coercion, and espionage in any form.",
             0, self._step >= 3),
            None,
            (f"[bold {C_FAIL}]PROCEED AT YOUR OWN RISK.[/]", 0, self._step >= 3),
            (rule, 0, self._step >= 3),
        ]


    def _promptLines(self, width: int) -> list[Text]:
        """The key box sits around the key after "Press ", always on the first line. Wrapped continuation fills the
        bottom border's line after the box, then further lines start at the left edge."""
        key = self._keys[min(self._step, 3)]
        box = len("Press │ K │ ")
        rest = Text.from_markup(
            f"to [bold {C_SUCC}]continue[/], or press any other key to [bold {C_FAIL}]abort[/]."
        )
        parts = _wrapNearest(rest, [width - box, width - box, width])
        first = Text.from_markup(f"Press [bold {C_SUCC}]│ {key.upper()} │[/] ") + parts[0]
        bottom = Text.from_markup(f"[bold {C_SUCC}]      ╰───╯[/]")
        if len(parts) > 1:
            bottom += Text(" ") + parts[1]

        return [Text.from_markup(f"[bold {C_SUCC}]      ╭───╮[/]"), first, bottom, *parts[2:]]


    def _layout(self) -> Text:
        """Wrap the message to 2.5 times the two side margins combined, 5/7 of the screen width. Once a paragraph
        wraps, the block snaps to its longest line, the word boundary nearest that width; when nothing needs to
        wrap, the block keeps the full width. The separators and the bar match the block, which stays centered."""
        screenWidth = self.size.width or self.app.size.width or 84
        width = max(24, round(screenWidth * 5 / 7))
        lines: list = []
        wrappedAny = False
        for paragraph in self._paragraphs():
            if paragraph is None:
                lines.append(Text(""))
                continue

            if paragraph == "RULE":
                lines.append("RULE")
                continue

            markup, indent, shown = paragraph
            if markup == "RULE":
                lines.append("RULE" if shown else Text(""))
                continue

            wrapped = _wrapNearest(Text.from_markup(markup), [width, width - indent])
            wrappedAny = wrappedAny or len(wrapped) > 1
            wrapped = [line if i == 0 else Text(" " * indent) + line for i, line in enumerate(wrapped)]
            lines.extend(wrapped if shown else [Text("") for _ in wrapped])

        prompt = self._promptLines(width)
        lines.extend(prompt)
        longest = max(cell_len(line.plain) for line in lines if isinstance(line, Text))
        self._blockWidth = longest if wrappedAny or len(prompt) > 3 else max(longest, width)
        separator = Text("—" * self._blockWidth, style=f"bold {C_FAIL}")
        return Text("\n").join(separator if line == "RULE" else line for line in lines)


    def compose(self) -> ComposeResult:
        with Vertical(id="warning-container"):
            yield Static(id="warning-text")
            yield Static(id="warning-bar")


    def on_mount(self) -> None:
        self._update()


    def on_resize(self) -> None:
        self._update()


    def _bar(self) -> str:
        """The bar spans the block width and fills a quarter per confirmed key."""
        width = self._blockWidth
        lit = round(self._displayProgress / 4 * width)
        return "".join(
            f"[{gradientColor(i / max(1, width - 1)) if i < lit else C_BG}]█[/]"
            for i in range(width)
        )


    def watch__displayProgress(self, value: float) -> None:
        """Update the bar widget whenever progress changes (during animation)."""
        try:
            self.query_one("#warning-bar", Static).update(self._bar())

        except Exception:
            pass


    def _update(self) -> None:
        text = self.query_one("#warning-text", Static)
        bar = self.query_one("#warning-bar", Static)
        text.update(self._layout())
        text.styles.width = self._blockWidth
        bar.styles.width = self._blockWidth
        bar.update(self._bar())


    def on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        event.prevent_default()


    def on_mouse_up(self, event: events.MouseUp) -> None:
        event.stop()
        event.prevent_default()


    def on_mouse_move(self, event: events.MouseMove) -> None:
        event.stop()
        event.prevent_default()


    def on_key(self, event: events.Key) -> None:
        if event.key == SCREENSHOT_KEY:
            from spicebag.frontend.screenshot import generateScreenshotPath, executePrint
            import os
            path = generateScreenshotPath()

            if not hasattr(self.app, "_warningScreenshots"):
                setattr(self.app, "_warningScreenshots", [])

            basename = os.path.basename(path + ".svg")
            shots = getattr(self.app, "_warningScreenshots")
            if basename not in shots:
                shots.append(basename)

            self.run_worker(executePrint(self, path))
            event.stop()
            event.prevent_default()
            return

        if self._step >= 4:
            return

        char = event.character.lower() if event.is_printable and event.character else None

        if char == self._keys[self._step]:
            self._step += 1
            self.animate("_displayProgress", float(self._step), duration=0.3, easing="out_cubic")

            if self._step == 4:
                self._update()
                self._proceed()

            else:
                self._update()

        else:
            if self._step == 0:
                self.app.exit()
                return

            self._step = 0
            self.animate("_displayProgress", 0.0, duration=0.3, easing="out_cubic")
            self._keys = random.sample(self.VALID_CHARS, 4)
            self._update()


    @work(exclusive=True)
    async def _proceed(self) -> None:
        await asyncio.sleep(0.5)
        from spicebag.frontend.screens.main import MainScreen
        self.app.switch_screen(MainScreen())



######## WORD WRAP ########

def _wrapNearest(text: Text, widths: list[int]) -> list[Text]:
    """Break text between words only, at the boundary nearest the width: a word that crosses it stays on the line
    when its end lands closer to the width than the break before it would. Line i uses widths[i], the last width
    repeating."""
    plain = text.plain
    words = [(match.start(), match.end()) for match in re.finditer(r"\S+", plain)]
    if not words:
        return [text]

    lines = []
    lineStart, lineEnd = words[0]
    for start, end in words[1:]:
        width = widths[min(len(lines), len(widths) - 1)]
        current = cell_len(plain[lineStart:lineEnd])
        extended = cell_len(plain[lineStart:end])
        if extended <= width or (current < width and extended - width < width - current):
            lineEnd = end
            continue

        lines.append(text[lineStart:lineEnd])
        lineStart, lineEnd = start, end

    lines.append(text[lineStart:lineEnd])
    return lines