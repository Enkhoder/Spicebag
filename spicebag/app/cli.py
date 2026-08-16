######## LIBRARIES ########

import typer



######## CLI SETUP ########

app = typer.Typer(invoke_without_command=True)



######## COMMANDS ########

@app.callback()
def main():
    """Spicebag: Visual Mnemonic Encoder / Decoder

    Run with no arguments to open the interface, which is the only way
    to encode or decode.

    No subcommand accepts a seed phrase or a salt. A command argument
    is written to the shell history and is readable from the process
    list, and neither can be retracted afterwards.
    """
    from spicebag.constants.theme import getVersion
    from spicebag.app.tui import SpicebagApp

    print(f"\033]0;Spicebag v{getVersion()}\007", end="", flush=True)
    tuiApp = SpicebagApp()
    tuiApp.run()



######## ENTRY POINT ########

if __name__ == "__main__":
    app()