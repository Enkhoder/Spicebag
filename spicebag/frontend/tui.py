######## LIBRARIES ########

from spicebag.frontend.theme import CLIPBOARD_KEYS, EXIT_ESC_BURST, C_BG
from spicebag.frontend.utils.terminalColors import FALLBACK_THEME
from spicebag.frontend.widgets.secureInput import SecureInput
from spicebag.frontend.utils.clipboard import clearClipboard
from spicebag.frontend.screens.warning import WarningScreen
from rich.terminal_theme import TerminalTheme
from rich.traceback import Traceback
from rich.segment import Segments
from textual.app import App
from textual import events
import rich
import time



######## APP ROOT ########

class SpicebagApp(App):
    """Main Textual application root."""

    CSS_PATH = "tui.tcss"

    def __init__(self, terminalTheme: TerminalTheme | None = None) -> None:
        super().__init__()
        self.terminalTheme = terminalTheme or FALLBACK_THEME
        self.escInBurst = False
        self._lastEscAt = 0.0


    def _fatal_error(self) -> None:
        """Textual's version prints the value of every local variable in the traceback, which can include the
        seed phrase or the passphrase. This prints the same traceback without them."""
        self.bell()
        traceback = Traceback(show_locals=False, width=None, suppress=[rich])
        self._exit_renderables.append(Segments(self.console.render(traceback, self.console.options)))
        self._close_messages_no_wait()


    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), "bg": C_BG}


    def on_mount(self) -> None:
        self.ansi_theme_dark = self.terminalTheme
        self.ansi_theme_light = self.terminalTheme
        self.push_screen(WarningScreen())


    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, events.Key) and event.key == "escape" and not event.is_forwarded:
            now = time.monotonic()
            self.escInBurst = now - self._lastEscAt < EXIT_ESC_BURST
            self._lastEscAt = now

        await super().on_event(event)


    def on_paste(self, event: events.Paste) -> None:
        if isinstance(self.screen, WarningScreen):
            clearClipboard()
            event.stop()
            event.prevent_default()
            return

        try:
            inp = self.screen.query_one("#cmd-input", SecureInput)

        except Exception:
            inp = None

        if inp and not inp.has_focus:
            inp.focus()
            inp.on_paste(event)
            return

        clearClipboard()


    def on_key(self, event: events.Key) -> None:
        if isinstance(self.screen, WarningScreen):
            return

        try:
            inp = self.screen.query_one("#cmd-input", SecureInput)

        except Exception:
            inp = None

        if not inp:
            return

        if event.key in CLIPBOARD_KEYS:
            inp.focus()
            return

        if event.is_printable or event.key in ("backspace", "delete", "tab", "enter"):
            if not inp.has_focus:
                inp.focus()


    def on_app_blur(self, event: events.AppBlur) -> None:
        handler = getattr(self.screen, "_onAppBlur", None)
        if handler is not None:
            handler()