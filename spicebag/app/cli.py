######## LIBRARIES ########

from typer.core import TyperGroup
import platform
import typer
import sys



######## CLI SETUP ########

HELP_TEXT = (
    "\n"
    "Usage: spicebag [option]\n"
    "\n"
    "Run with no arguments to open the interface, which is the only way to encode and decode.\n"
    "\n"
    "Options:\n"
    "  --version  -V        Spicebag version\n"
    "  --help     -h        Show this message"
    "\n"
)


class SpicebagGroup(TyperGroup):
    def get_help(self, ctx) -> str:
        return HELP_TEXT


app = typer.Typer(
    cls=SpicebagGroup,
    invoke_without_command=True,
    add_completion=False,
    subcommand_metavar="",
    context_settings={"help_option_names": ["--help", "-h"]}
)



######## TERMINAL TITLE ########

def setTerminalTitle(title: str) -> None:
    """Set the window title natively on Windows, where a legacy console prints OSC 0 literally."""
    if platform.system() == "Windows":
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
        return

    if sys.stdout.isatty():
        print(f"\033]0;{title}\007", end="", flush=True)



######## FLAGS ########

def versionCallback(value: bool) -> None:
    if value:
        from spicebag.constants.theme import getVersion

        print(f"Spicebag {getVersion()}")

        raise typer.Exit()



######## COMMANDS ########

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=versionCallback, is_eager=True)
):
    from spicebag.utils.terminalColors import probeTerminalTheme
    from spicebag.constants.theme import getVersion
    from spicebag.app.tui import SpicebagApp

    setTerminalTitle(f"Spicebag v{getVersion()}")
    tuiApp = SpicebagApp(terminalTheme=probeTerminalTheme())
    tuiApp.run()



######## ENTRY POINT ########

if __name__ == "__main__":
    app()