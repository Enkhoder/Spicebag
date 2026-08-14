######## LIBRARIES ########

import typer



######## CLI SETUP ########

app = typer.Typer(invoke_without_command=True)



######## COMMANDS ########

@app.callback()
def main(ctx: typer.Context):
    """Spicebag: Visual Mnemonic Encoder / Decoder"""
    if ctx.invoked_subcommand is None:
        from spicebag.constants.theme import getVersion
        from spicebag.app.tui import SpicebagApp

        print(f"\033]0;Spicebag v{getVersion()}\007", end="", flush=True)
        tuiApp = SpicebagApp()
        tuiApp.run()


@app.command()
def encode(
    mnemonic: str = typer.Argument(..., help="The seed phrase to encode"),
    path: str = typer.Argument(..., help="Path to save the PNG file"),
    salt: str = typer.Option("", help="Optional salt for encryption"),
    cellPx: int = typer.Option(100, "--cell-px", help="Size of each color cell in pixels")
):
    """Encode a seed phrase into a color-coded PNG."""
    from spicebag.core.generator import encodeMnemonic

    try:
        encodeMnemonic(mnemonic, path, cellPx=cellPx, salt=salt)
        typer.secho(f"Successfully encoded to {path}", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Encoding failed: {e}", fg=typer.colors.RED)

        raise typer.Exit(code=1)


@app.command()
def decode(
    path: str = typer.Argument(..., help="Path to the PNG file to decode"),
    salt: str = typer.Option("", help="Optional salt used during encryption")
):
    """Decode a color-coded PNG back into a seed phrase."""
    from spicebag.core.decoder import decodeImage

    try:
        mnemonic, _ = decodeImage(path, salt=salt)
        typer.secho("\nDecoded Seed Phrase:", fg=typer.colors.GREEN)
        typer.echo(mnemonic)

    except Exception as e:
        typer.secho(f"Decoding failed: {e}", fg=typer.colors.RED)

        raise typer.Exit(code=1)



######## ENTRY POINT ########

if __name__ == "__main__":
    app()