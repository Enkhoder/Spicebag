######## LIBRARIES ########

from src.constants.theme import invertedGradientHex, C_WHITE, C_DIM, C_INP, C_IMG, C_WC, C_SUCC, C_FAIL
from src.core.generator import ColorSpace, precomputeColorSpace, rerollCell
from textual.containers import Vertical
from textual.app import ComposeResult
from textual.widgets import Static
from textual.screen import Screen
from rich.console import Group
from typing import Optional
from rich.text import Text
from textual import events
import math
import time


HELP_DEMO_SEED = "legal winner thank year wave sausage worth useful legal winner thank yellow"

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

COMMAND_ROWS = [
    ("encode", C_IMG,  "seed phrase  →  encoded image"),
    ("decode", C_WC,   "encoded image  →  seed phrase"),
    ("clear",  C_DIM,  "wipe the screen"),
    ("banner", C_INP,  "toggle ASCII / mascot banner"),
    ("help",   C_SUCC, "open this guide"),
    ("exit",   C_DIM, "close Spicebag"),
]

PATH_EXAMPLES = [
    ("safe/cold",                    "cold.png saved in the safe folder"),
    ("safe/name.png/cold.png",       "cold.png inside a .png-named folder"),
    ("C:/Users/username/folder/cold.png", "decode or save to this exact file"),
]



######## HELP SCREEN ########

class HelpScreen(Screen):
    """Self-contained, single-column guide shown over the menu. Any key returns,
    leaving the menu underneath exactly as it was."""

    can_focus = False

    def __init__(self) -> None:
        super().__init__()
        self._frame = 0
        self._readyAt = 0.0
        self._timer = None
        self._words = HELP_DEMO_SEED.split()

        try:
            self._colorSpace: Optional[ColorSpace] = precomputeColorSpace(HELP_DEMO_SEED, "")
        except Exception:
            self._colorSpace = None


    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static(self._renderBody(), id="help-body")


    def on_mount(self) -> None:
        self._readyAt = time.time() + 0.25
        self._timer = self.set_interval(0.5, self._tick)


    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()

        if time.time() < self._readyAt:
            return

        if self._timer is not None:
            self._timer.stop()
            self._timer = None

        self.app.pop_screen()


    # ──────────────────────────── ANIMATION ─────────────────────────────────

    def _tick(self) -> None:
        self._frame += 1
        self._advanceColorGrid()

        try:
            self.query_one("#help-body", Static).update(self._renderBody())
        except Exception:
            pass


    def _advanceColorGrid(self) -> None:
        cs = self._colorSpace
        if cs is None:
            return

        cells = list(cs.cellToWord.keys())
        if not cells:
            return

        stride = max(1, len(cells) // 4)
        start = (self._frame * stride) % len(cells)
        for k in range(stride):
            r, c = cells[(start + k) % len(cells)]
            rerollCell(cs, r, c)


    def _revealCount(self) -> int:
        numWords = len(self._words)
        holdMask = 2
        holdReveal = 4
        cycle = holdMask + numWords + holdReveal
        phase = self._frame % cycle

        if phase < holdMask:
            return 0
        if phase < holdMask + numWords:
            return phase - holdMask + 1
        return numWords


    # ──────────────────────────── VISUALS ───────────────────────────────────

    def _colorGrid(self, cs) -> Group:
        lines = []
        for r in range(cs.rows):
            line = Text("    ")
            for c in range(cs.cols):
                rgb = cs.colorRGB.get((r, c))
                if rgb is None:
                    continue
                line.append("██████", style=f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
                line.append("  ")
            lines.append(line)
        return Group(*lines)


    def _seedGrid(self) -> Group:
        words = self._words
        revealCount = self._revealCount()
        cols = 3

        lines = []
        for r in range(4):
            line = Text("    ")
            for c in range(cols):
                idx = r * cols + c
                if idx >= len(words):
                    break
                if c > 0:
                    line.append("  ")

                line.append(f"{idx + 1:>2}", style=C_DIM)
                line.append(". ", style=C_DIM)

                if idx < revealCount:
                    word = words[idx]
                    line.append(word, style=C_WC)
                    pad = 8 - len(word)
                    if pad > 0:
                        line.append(" " * pad)
                else:
                    for k in range(8):
                        line.append("█", style=invertedGradientHex((c * 8 + k) / (cols * 8 - 1)))
            lines.append(line)
        return Group(*lines)


    # ──────────────────────────── SECTIONS ──────────────────────────────────

    def _intro(self) -> Group:
        hint = Text("Press any key to return to the menu.", style=C_DIM)
        line = Text(
            "Spicebag hides a wallet seed phrase inside a PNG of\ncolour, then reads it back — fully offline.",
            style=C_WHITE,
        )
        return Group(hint, Text(""), line)


    def _commandsSection(self) -> Group:
        rows = [Text.from_markup(f"[bold {C_WHITE}]COMMANDS[/]")]

        for name, color, desc in COMMAND_ROWS:
            row = Text("  ")
            row.append(f"{name:<8}", style=f"bold {color}")
            row.append(desc, style=C_DIM)
            rows.append(row)

        esc = Text("  ")
        esc.append(f"{'ESC':<8}", style=f"bold {C_WHITE}")
        esc.append("cancel a prompt, or step back — anytime", style=C_DIM)
        rows.append(esc)
        return Group(*rows)


    def _encodeSection(self) -> Group:
        cs = self._colorSpace
        head = Text.from_markup(f"[bold {C_IMG}]ENCODE[/][{C_DIM}]  ·  seed phrase → image[/]")

        body = Text("  ")
        body.append(
            "Asked in turn: how many images, word count, the\n  phrase, a salt, tile size, and where to save.\n",
            style=C_DIM,
        )
        body.append("  • A count above 1 saves a batch (up to 2000)\n    as one ZIP.\n", style=C_DIM)
        body.append("  • At the confirm step a preview appears — click\n    any tile to re-roll its colour", style=C_DIM)

        if cs is not None:
            exp = int(cs.numWords * math.log10(cs.blockSize))
            body.append(". One phrase has\n    over ", style=C_DIM)
            body.append(f"10{str(exp).translate(SUPERSCRIPT)}", style=f"bold {C_IMG}")
            body.append(" images, so no two copies match.", style=C_DIM)
        else:
            body.append(".", style=C_DIM)

        parts = [head, body]
        if cs is not None:
            parts += [Text(""), self._colorGrid(cs)]
        return Group(*parts)


    def _decodeSection(self) -> Group:
        head = Text.from_markup(f"[bold {C_WC}]DECODE[/][{C_DIM}]  ·  image → seed phrase[/]")

        body = Text("  ")
        body.append(
            "Asked for the image path, then the salt (if one\n  was used). The phrase shows for 3 seconds, then\n  "
            "hides — hover a tile to reveal it again.",
            style=C_DIM,
        )
        return Group(head, body, Text(""), self._seedGrid())


    def _saltSection(self) -> Group:
        head = Text.from_markup(f"[bold {C_INP}]SALT[/][{C_DIM}]  ·  optional, strongly advised[/]")

        body = Text("  ")
        body.append(
            "A secret that scrambles the whole image. Lose the\n  exact salt and the image can never be decoded —\n  "
            "there is no recovery, so keep it as safely as the\n  seed phrase itself.",
            style=C_DIM,
        )
        return Group(head, body)


    def _filePathsSection(self) -> Group:
        head = Text.from_markup(
            f"[bold {C_WHITE}]FILE PATHS[/][{C_DIM}]  ·  type a standard file path (/ or \\)[/]"
        )

        rows = [head]
        for path, meaning in PATH_EXAMPLES:
            row = Text("  ")
            row.append(f"{path:<32}", style=C_IMG)
            row.append(meaning, style=C_DIM)
            rows.append(row)

        tip = Text("  ")
        tip.append("TAB", style=f"bold {C_WHITE}")
        tip.append(
            " autofills the default folder. If the last path\n"
            "  component is an existing folder, default name is used.",
            style=C_DIM,
        )
        rows.append(tip)
        return Group(*rows)


    def _internalsSection(self) -> Group:
        head = Text.from_markup(f"[bold {C_WHITE}]HOW IT WORKS[/]")
        cs = self._colorSpace

        body = Text("  ")
        if cs is not None:
            body.append("Each tile is one word. The ", style=C_DIM)
            body.append(f"{1 << 24:,}", style=C_WHITE)
            body.append(" possible\n  colours split into ", style=C_DIM)
            body.append(f"{cs.maxIdx:,}", style=C_WHITE)
            body.append(" blocks of ", style=C_DIM)
            body.append(f"{cs.blockSize:,}", style=C_WHITE)
            body.append(" — one\n  block per word, a random shade chosen inside it.\n  "
                        "A salt reshuffles the blocks and tile order.", style=C_DIM)
        else:
            body.append("Each tile is one word; a salt scrambles the\n  colours so the image reads as noise.", style=C_DIM)
        return Group(head, body)


    # ──────────────────────────── ASSEMBLY ──────────────────────────────────

    def _renderBody(self) -> Group:
        gap = Text("")
        sections = [
            self._intro(),
            self._commandsSection(),
            self._encodeSection(),
            self._decodeSection(),
            self._saltSection(),
            self._filePathsSection(),
            self._internalsSection(),
        ]

        out = []
        for i, section in enumerate(sections):
            out.append(section)
            if i < len(sections) - 1:
                out.append(gap)
        return Group(*out)
