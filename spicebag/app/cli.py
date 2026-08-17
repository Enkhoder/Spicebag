######## LIBRARIES ########

from typer.core import TyperGroup
from rich.console import Console
import typer
import sys



######## CLI SETUP ########

HELP_TEXT = (
    "Run with no arguments (spicebag) to open the interface, which is the only way to encode or "
    "decode. You cannot invoke either operation from the command line.\n"
    "\n"
    "Options:\n"
    "\n"
    "  --version  -V        Spicebag version\n"
    "  --help     -h        Show this message\n"
    "\n"
    "(c) 2026 [link=https://github.com/Enkhoder]Enkhoder[/link]"
)


class SpicebagGroup(TyperGroup):
    def get_help(self, ctx) -> str:
        console = Console(highlight=False, force_terminal=sys.stdout.isatty())
        with console.capture() as capture:
            console.print(HELP_TEXT)

        return capture.get().rstrip("\n")


app = typer.Typer(
    cls=SpicebagGroup,
    invoke_without_command=True,
    add_completion=False,
    subcommand_metavar="",
    context_settings={"help_option_names": ["--help", "-h"]}
)



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

    print(f"\033]0;Spicebag v{getVersion()}\007", end="", flush=True)
    tuiApp = SpicebagApp(terminalTheme=probeTerminalTheme())
    tuiApp.run()



######## ENTRY POINT ########

if __name__ == "__main__":
    app()