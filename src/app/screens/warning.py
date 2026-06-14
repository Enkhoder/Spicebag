######## LIBRARIES ########

from src.constants.theme import C_WHITE, C_INP, C_WARN, C_SUCC, gradientColor
from textual.containers import Vertical
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static
from textual.screen import Screen
from textual import events, work
import asyncio
import random
import string


######## WARNING SCREEN ########

class WarningScreen(Screen):
    """Initial security warning screen with 4-key sequential confirmation."""

    can_focus = False
    _displayProgress = reactive(0.0)

    BAR_SEG = 15
    VALID_CHARS = [c for c in string.ascii_lowercase if c != 'o']

    def __init__(self) -> None:
        super().__init__()
        self._keys: list[str] = random.sample(self.VALID_CHARS, 4)
        self._step = 0

        self._gradientColors: list[str] = []
        total = self.BAR_SEG * 4

        for i in range(total):
            self._gradientColors.append(gradientColor(i / max(1, total - 1)))


    def _warningBody(self) -> str:
        line1 = "• You are in a private, isolated location"

        if self._step == 0:
            line1 = f"[bold {C_WHITE}]{line1}[/]"
        elif self._step == 1:
            line1 = f"[{C_INP}]{line1}[/]"

        text = (
            f"[bold {C_WARN}]S E C U R I T Y   W A R N I N G[/]\n\n"
            f"[bold {C_WARN}]————————————————————————————————————————————————————————————[/]\n"
            "You are about to encode or decode a visual representation of\n"
            f"a wallet [bold {C_WARN}]SEED PHRASE[/].\n\n"
            f"Turning on [bold {C_WARN}]AIRPLANE MODE[/] is highly advised for heightened\n"
            f"security during this session.\n\n"
            f"Proceed [bold {C_WARN}]IF AND ONLY IF[/] all of the following are true:\n\n"
            f"{line1}\n"
        )

        if self._step >= 1:
            line2 = "• No one else can see your screen"

            if self._step == 1:
                line2 = f"[bold {C_WHITE}]{line2}[/]"
            elif self._step == 2:
                line2 = f"[{C_INP}]{line2}[/]"

            text += f"{line2}\n"
        else:
            text += "\n"

        if self._step >= 2:
            line3 = "• No recording / surveillance devices are present"

            if self._step == 2:
                line3 = f"[bold {C_WHITE}]{line3}[/]"
            elif self._step == 3:
                line3 = f"[{C_INP}]{line3}[/]"

            text += f"{line3}\n\n"
        else:
            text += "\n\n"

        if self._step >= 3:
            text += (
                f"This program provides [bold {C_WARN}]NO PROTECTION[/] against malware,\n"
                "coercion, and espionage in any form.\n\n"
                f"[bold {C_WARN}]PROCEED AT YOUR OWN RISK.[/]\n"
                f"[bold {C_WARN}]————————————————————————————————————————————————————————————[/]"
            )
        else:
            text += "\n\n\n\n"

        return text


    def compose(self) -> ComposeResult:
        with Vertical(id="warning-container"):
            yield Static(
                self._warningBody() + "\n" + self._promptLine(),
                id="warning-text"
            )
            yield Static(self._bar(), id="warning-bar")


    def _promptLine(self) -> str:
        key = self._keys[min(self._step, 3)]
        return (
            f"[bold {C_SUCC}]      ┌───┐[/]\n"
            f"Press "
            f"[bold {C_SUCC}]│ {key.upper()} │[/]"
            f" to [bold {C_SUCC}]continue[/], or press any other key to [bold {C_WARN}]abort[/].\n"
            f"[bold {C_SUCC}]      └───┘[/]"
        )


    def _bar(self) -> str:
        res = ""
        totalLit = int(self._displayProgress)

        for i in range(self.BAR_SEG * 4):
            if i < totalLit:
                res += f"[{self._gradientColors[i]}]█[/]"
            else:
                res += f"[#252525]█[/]"

        return res


    def watch__displayProgress(self, value: float) -> None:
        """Update the bar widget whenever progress changes (during animation)."""
        try:
            self.query_one("#warning-bar", Static).update(self._bar())
        except Exception:
            pass


    def _update(self) -> None:
        self.query_one("#warning-text", Static).update(
            self._warningBody() + "\n" + self._promptLine()
        )
        self.query_one("#warning-bar", Static).update(self._bar())


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
        if event.key == "ctrl+s":
            from src.app.handlers.screenshot import generateScreenshotPath, executePrint
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
            self.animate("_displayProgress", self._step * self.BAR_SEG, duration=0.3, easing="out_cubic")

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
        from src.app.screens.main import MainScreen
        self.app.switch_screen(MainScreen())
