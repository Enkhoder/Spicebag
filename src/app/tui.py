######## LIBRARIES ########

from src.app.widgets.secureInput import SecureInput
from src.app.screens.warning import WarningScreen
from src.constants.theme import CLIPBOARD_KEYS, C_BG
from textual.app import App
from textual import events



######## APP ROOT ########

class SpicebagApp(App):
    """Main Textual application root."""

    CSS_PATH = "tui.tcss"

    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), "bg": C_BG}

    def on_mount(self) -> None:
        self.push_screen(WarningScreen())


    def on_paste(self, event: events.Paste) -> None:
        if isinstance(self.screen, WarningScreen):
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


    async def action_pop_screen(self) -> None:
        """Disable default screen popping on ESC key."""
        pass


######## ENTRY POINT ########

if __name__ == "__main__":
    app = SpicebagApp()
    app.run()