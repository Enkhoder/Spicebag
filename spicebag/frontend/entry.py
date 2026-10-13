######## LIBRARIES ########

from typer.core import TyperGroup
import platform
import textwrap
import difflib
import shutil
import typer
import sys
import os



######## ENVIRONMENT ########

for name in [name for name in os.environ if name.upper().startswith("TEXTUAL")]:
    del os.environ[name]



######## CLI SETUP ########

HELP_USAGE = "Usage: spicebag [option]"

HELP_SECTIONS = (
    ("Options", (
        ("--encode,  -e", "Seed phrase -> encoded image"),
        ("--decode,  -d", "Encoded image -> seed phrase"),
        ("--palette, -p", "Seed phrase -> every color each cell can take"),
        ("--version, -V", "Spicebag version"),
        ("--help,    -h", "Show this message")
    )),
    ("Encode save paths", (
        ("(blank)", "Default name in ~/Spicebag/images"),
        ("~/safe/image", "image.png in folder 'safe', or default name inside folder 'image'"),
        ("~/safe//image", "image.png in folder 'safe', even if 'image' is a folder"),
        ("//image", "image.png in ~/Spicebag/images")
    )),
    ("Decode paths", (
        ("~/safe/image.png", "Reads image.png in folder 'safe'"),
        ("//image.png", "Reads image.png in ~/Spicebag/images"),
        ("image.png", "Read as a folder named 'image.png' with no file, invalid input")
    )),
    ("Palette cells", (
        ("(blank), *", "Every cell"),
        ("0 1", "Cell [0][1]"),
        ("0-2 1-2", "Rows 0 to 2, columns 1 to 2"),
        ("1-3 0 1 2", "Rows 1 to 3 in column 0, and cell [1][2]")
    ))
)

HELP_INDENT = 4

HELP_GAP = 8

UNKNOWN_INPUT_TEXT = "No such {kind}: {token}{suggestion}"

SUGGESTION_TEXT = "\nDid you mean {flag}?"


def suggestFlag(token: str, flags: set[str]) -> str | None:
    """Closest long flag to a mistyped token, compared without dashes or case, so --hekp, --ENCODE and a bare
    encode all find their flag. Suggests only; nothing runs."""
    longFlags = {flag.lstrip("-"): flag for flag in flags if flag.startswith("--")}
    matches = difflib.get_close_matches(token.lstrip("-").lower(), longFlags, n=1, cutoff=0.6)

    return longFlags[matches[0]] if matches else None


def renderHelp(width: int) -> str:
    """Side by side while the longest row fits the width, every description HELP_GAP columns past the longest
    entry of any section. Otherwise each description moves under its entry, one HELP_INDENT deeper, wrapped to
    the width. The last column stays free, since some consoles wrap a line that fills it. A row with no
    description is a note: it sits at HELP_INDENT, wraps to the width, and plays no part in the layout."""
    allRows = [row for _, rows in HELP_SECTIONS for row in rows if len(row) == 2]
    column = HELP_INDENT + max(len(entry) for entry, _ in allRows) + HELP_GAP
    stacked = column + max(len(description) for _, description in allRows) >= width
    wrapWidth = max(width - 1 - 2 * HELP_INDENT, 1)
    lines = [HELP_USAGE]

    for title, rows in HELP_SECTIONS:
        lines.append(f"{title}:")
        for row in rows:
            if len(row) == 1:
                lines.extend(
                    " " * HELP_INDENT + part
                    for part in textwrap.wrap(row[0], max(width - 1 - HELP_INDENT, 1), break_long_words=False)
                )
                continue

            entry, description = row
            if stacked:
                lines.append(" " * HELP_INDENT + entry)
                lines.extend(
                    " " * 2 * HELP_INDENT + part
                    for part in textwrap.wrap(description, wrapWidth, break_long_words=False, break_on_hyphens=False)
                )

            else:
                lines.append(" " * HELP_INDENT + entry.ljust(column - HELP_INDENT) + description)

    return "\n".join(lines)


class SpicebagGroup(TyperGroup):
    def get_help(self, ctx) -> str:
        return renderHelp(shutil.get_terminal_size().columns)


    def parse_args(self, ctx, args: list[str]) -> list[str]:
        args = [token for token in args if token != "-"]
        flags = {name for param in self.get_params(ctx) for name in param.opts}

        for token in args:
            if token not in flags:
                kind = "option" if token.startswith("-") else "command"
                flag = suggestFlag(token, flags)
                suggestion = SUGGESTION_TEXT.format(flag=flag) if flag else ""
                print(UNKNOWN_INPUT_TEXT.format(kind=kind, token=token, suggestion=suggestion), file=sys.stderr)
                raise typer.Exit(2)

        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=SpicebagGroup,
    invoke_without_command=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
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
        from spicebag.frontend.theme import getVersion

        print(f"Spicebag {getVersion()}")

        raise typer.Exit()


def encodeCallback(value: bool) -> None:
    if value:
        from spicebag.frontend.cli import runEncode

        raise typer.Exit(runEncode())


def decodeCallback(value: bool) -> None:
    if value:
        from spicebag.frontend.cli import runDecode

        raise typer.Exit(runDecode())


def paletteCallback(value: bool) -> None:
    if value:
        from spicebag.frontend.cli import runPalette

        raise typer.Exit(runPalette())



######## COMMANDS ########

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=versionCallback, is_eager=True),
    encode: bool = typer.Option(False, "--encode", "-e", callback=encodeCallback, is_eager=True),
    decode: bool = typer.Option(False, "--decode", "-d", callback=decodeCallback, is_eager=True),
    palette: bool = typer.Option(False, "--palette", "-p", callback=paletteCallback, is_eager=True)
):
    from spicebag.frontend.utils.terminalColors import probeTerminalTheme
    from spicebag.frontend.theme import getVersion
    from spicebag.frontend.tui import SpicebagApp

    setTerminalTitle(f"Spicebag v{getVersion()}")
    tuiApp = SpicebagApp(terminalTheme=probeTerminalTheme())
    tuiApp.run()