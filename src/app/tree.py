######## LIBRARIES ########

from src.constants.theme import C_DIM, C_INP, C_IMG, C_WHITE, bannerGradientHex
from dataclasses import dataclass, field
from rich.console import Console
from rich.cells import cell_len
from rich.text import Text
import typing


######## TREE MODEL ########

@dataclass
class TreeNode:
    kind: str = "branch"
    text: Text = field(default_factory=Text)
    connStyle: str = C_DIM
    children: list["TreeNode"] = field(default_factory=list)
    body: list[Text] = field(default_factory=list)
    hints: list[Text] = field(default_factory=list)
    barWidth: int = 0
    sampleSpace: typing.Any = None
    sampleMasked: bool = False
    sampleClickable: bool = False


@dataclass
class RootNode:
    label: Text = field(default_factory=Text)
    bullet: str = C_WHITE
    children: list[TreeNode] = field(default_factory=list)
    rawLines: list[Text] | None = None
    kind: str = "command"


######## RENDERER ########

def _mkText(segments: list[tuple[str, str | None]]) -> Text:
    """Build a no-wrap Text from (string, style) prefix segments."""
    t = Text(no_wrap=True, end="")
    for s, style in segments:
        t.append(s, style=style)
    return t


def _prefixWidth(segments: list[tuple[str, str | None]]) -> int:
    return sum(cell_len(s) for s, _ in segments)


def _emitWrapped(
    out: list[Text],
    firstPrefix: list[tuple[str, str | None]],
    contPrefix: list[tuple[str, str | None]],
    text: Text,
    width: int,
    console: Console,
) -> None:
    """Emit `text` prefixed by firstPrefix (first line) / contPrefix (wraps),
    keeping every wrapped line hang-indented to the content column."""
    avail = max(1, width - _prefixWidth(firstPrefix))

    if text.plain:
        lines = text.wrap(console, avail)
    else:
        lines = [Text("")]

    if not lines:
        lines = [Text("")]

    for idx, line in enumerate(lines):
        row = _mkText(firstPrefix if idx == 0 else contPrefix)
        row.append_text(line)
        out.append(row)


def _appendSampleRow(rowText: Text, cs, cellR: int, masked: bool) -> None:
    """Append one block-row (6 cells per column) to an existing prefixed row."""
    if masked:
        totalCols = cs.cols * 6
        for x in range(totalCols):
            rowText.append("█", style=bannerGradientHex(x / max(1, totalCols - 1)))
    else:
        for c in range(cs.cols):
            r, g, b = cs.colorRGB[(cellR, c)]
            rowText.append("█" * 6, style=f"#{r:02X}{g:02X}{b:02X}")


def _renderChildren(
    children: list[TreeNode],
    prefix: list[tuple[str, str | None]],
    width: int,
    console: Console,
    out: list[Text],
    isRoot: bool,
    hitSink: list,
) -> None:
    lastIdx = len(children) - 1

    for i, child in enumerate(children):
        if child.kind in ("branch", "dashbar"):
            isLast = (i == lastIdx)
            connChar = "└" if isLast else "├"
            ext = [("    ", None)] if isLast else [("│", C_DIM), ("   ", None)]

            if child.kind == "dashbar":
                avail = max(1, width - _prefixWidth(prefix) - 1)
                barW = max(1, min(child.barWidth, avail))
                firstPrefix = prefix + [(connChar, child.connStyle)]
                contPrefix = prefix + [(" ", None)]

                barText = Text("─" * (barW - 1), style=child.connStyle)
                barText.append("●", style=C_INP)

                _emitWrapped(
                    out, firstPrefix, contPrefix,
                    barText,
                    width, console,
                )
            else:
                connSeg = [(connChar + "── ", child.connStyle)]
                _emitWrapped(out, prefix + connSeg, prefix + ext, child.text, width, console)

                for bodyLine in child.body:
                    _emitWrapped(out, prefix + ext, prefix + ext, bodyLine, width, console)
                for hintLine in child.hints:
                    hintPrefix = prefix + ext
                    _emitWrapped(out, hintPrefix, hintPrefix, hintLine, width, console)

                _renderChildren(child.children, prefix + ext, width, console, out, isRoot=False, hitSink=hitSink)

            if isRoot and not isLast and child.kind == "branch" and child.children:
                out.append(_mkText(prefix + [("│", C_DIM)]))

        elif child.kind == "imagesample":
            isLast = (i == lastIdx)
            cs = child.sampleSpace

            out.append(_mkText(prefix + [("│", C_DIM)]))

            blockStartCol = _prefixWidth(prefix) + 4
            if child.sampleClickable and not child.sampleMasked:
                hitSink.append((len(out), blockStartCol, cs.cols, cs.rows))

            totalLines = cs.rows * 3
            for k in range(totalLines):
                if k == 0:
                    conn = [("├── ", child.connStyle)]
                elif k == totalLines - 1:
                    conn = [(("└── " if isLast else "├── "), child.connStyle)]
                else:
                    conn = [("│   ", C_DIM)]

                rowText = _mkText(prefix + conn)
                _appendSampleRow(rowText, cs, k // 3, child.sampleMasked)
                out.append(rowText)

            if not isLast:
                out.append(_mkText(prefix + [("│", C_DIM)]))

        elif child.kind == "note":
            notePrefix = prefix + [("│", C_DIM), (" ", None)]
            _emitWrapped(out, notePrefix, notePrefix, child.text, width, console)

        elif child.kind == "shotgroup":
            headerPrefix = prefix + [("│", C_DIM), (" ", None)]
            _emitWrapped(out, headerPrefix, headerPrefix, child.text, width, console)

            lastShot = len(child.children) - 1
            for j, shot in enumerate(child.children):
                shotConn = "└" if j == lastShot else "├"
                firstPrefix = prefix + [("│", C_DIM), (" ", None), (shotConn + "── ", C_IMG)]
                contPrefix = prefix + [("│", C_DIM), (" ", None), ("    ", None)]
                _emitWrapped(out, firstPrefix, contPrefix, shot.text, width, console)


def renderBlocks(blocks: list[RootNode], width: int, console: Console) -> tuple[list[Text], tuple | None]:
    """Render the whole conversation forest into fully-styled, pre-wrapped lines.

    Returns the lines plus a hit descriptor for the single active clickable image
    sample, if any: (firstBlockLineIndex, blockStartCol, cols, rows)."""
    out: list[Text] = []
    hitSink: list = []
    width = max(8, width)

    for root in blocks:
        out.append(Text(""))

        bulletPrefix: list[tuple[str, str | None]] = [("●", root.bullet), (" ", None)]
        if root.children:
            labelCont: list[tuple[str, str | None]] = [("│", root.children[0].connStyle), (" ", None)]
        else:
            labelCont = [("  ", None)]
        _emitWrapped(out, bulletPrefix, labelCont, root.label, width, console)

        if root.rawLines is not None:
            out.append(Text(""))
            for raw in root.rawLines:
                _emitWrapped(out, [("  ", None)], [("  ", None)], raw, width, console)
            continue

        _renderChildren(root.children, [], width, console, out, isRoot=True, hitSink=hitSink)

    return out, (hitSink[0] if hitSink else None)
