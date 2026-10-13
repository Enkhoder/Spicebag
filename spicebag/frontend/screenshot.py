######## LIBRARIES ########

from spicebag.frontend.theme import blendHexColors, SCREENSHOTS_DIR
from spicebag.frontend.utils.terminalColors import FALLBACK_THEME
from rich.terminal_theme import TerminalTheme
from textual.screen import Screen
from rich.console import Console
from textual.app import App
import time
import io
import os
import re



######## SCREENSHOT FONT ########

FONT_CDN = "https://cdn.jsdelivr.net/gh/JetBrains/JetBrainsMono@2.304/fonts/ttf"

SVG_FORMAT = """<svg class="rich-terminal" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <style>

    @font-face {{
        font-family: "JetBrains Mono NL";
        src: local("JetBrains Mono NL Regular"), local("JetBrainsMonoNL-Regular"),
                url("%(cdn)s/JetBrainsMonoNL-Regular.ttf") format("truetype");
        font-style: normal;
        font-weight: 400;
    }}
    @font-face {{
        font-family: "JetBrains Mono NL";
        src: local("JetBrains Mono NL Bold"), local("JetBrainsMonoNL-Bold"),
                url("%(cdn)s/JetBrainsMonoNL-Bold.ttf") format("truetype");
        font-style: normal;
        font-weight: 700;
    }}

    .{unique_id}-matrix {{
        font-family: "JetBrains Mono NL", monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}

    .{unique_id}-title {{
        font-size: 18px;
        font-weight: bold;
        font-family: arial;
    }}

    {styles}
    </style>

    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>

    {chrome}
    <g transform="translate({terminal_x}, {terminal_y})" clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
""" % { "cdn": FONT_CDN }



######## SCREENSHOT HANDLERS ########

def exportScreenshot(app: App, theme: TerminalTheme) -> str:
    """Render the current screen to SVG using the live terminal palette."""
    width, height = app.size

    console = Console(
        width=width,
        height=height,
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        record=True,
        legacy_windows=False,
        safe_box=False
    )
    console.print(app.screen._compositor.render_update(full=True, screen_stack=app._background_screens))

    return console.export_svg(title=app.title, theme=theme, code_format=SVG_FORMAT)


def bezelColor(bgHex: str) -> str:
    luminance = (
        0.2126 * int(bgHex[1:3], 16)
        + 0.7152 * int(bgHex[3:5], 16)
        + 0.0722 * int(bgHex[5:7], 16)
    )
    return blendHexColors(bgHex, "#000000" if luminance > 128 else "#FFFFFF", 0.10)


def cleanSvg(app: App, svg: str, bgHex: str) -> str:
    svg = re.sub(r"<!--.*?-->", "", svg)

    svg = re.sub(r"<title>.*?</title>", "", svg, flags=re.DOTALL | re.IGNORECASE)
    svg = re.sub(r"<desc>.*?</desc>", "", svg, flags=re.DOTALL | re.IGNORECASE)
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.DOTALL | re.IGNORECASE)

    svg = re.sub(r'<text class="[^"]+-title"[^>]*>.*?</text>', "", svg)

    svg = re.sub(
        r'(<svg class="rich-terminal" viewBox="0 0 [\d.]+ )([\d.]+)',
        lambda m: m.group(1) + str(float(m.group(2)) + 24.4),
        svg
    )

    svg = re.sub(
        r'(<rect fill="[^"]+" stroke="[^"]+"[^>]*?height=")([\d.]+)',
        lambda m: m.group(1) + str(float(m.group(2)) + 24.4),
        svg
    )

    svg = re.sub(
        r'(<clipPath id="[^"]+-clip-terminal">\s*<rect[^>]*?height=")([\d.]+)',
        lambda m: m.group(1) + str(float(m.group(2)) + 24.4),
        svg
    )

    svg = re.sub(
        r'(<g transform="translate\()(\d+(?:\.\d+)?),([\d.]+)(\)"\s+clip-path="url\(#[^"]+-clip-terminal\)">)',
        lambda m: m.group(1) + m.group(2) + ",41" + m.group(4),
        svg
    )

    vbMatch = re.search(r'viewBox="0 0 ([\d.]+)', svg)
    totalSvgW = float(vbMatch.group(1)) if vbMatch else app.size.width * 12.2 + 18
    xRight = totalSvgW - 1
    xRightArc = xRight - 16

    topBezelPath = (
        f'<path fill="{bezelColor(bgHex)}"'
        f' d="M 1,41 V 17 A 16,16 0 0 1 17,1 H {xRightArc} A 16,16 0 0 1 {xRight},17 V 41 Z"/>'
    )

    def _rewriteFrame(m: re.Match) -> str:
        tag = m.group(0)
        tag = re.sub(r'\brx="\d+"', 'rx="16"', tag)
        tag = re.sub(r'\s*stroke(?:-width)?="[^"]*"', '', tag)
        tag = re.sub(r'\s*shape-rendering="[^"]*"', '', tag)
        return tag + topBezelPath

    svg = re.sub(r'<rect\s+fill="[^"]+"\s+stroke="[^"]+"[^/]*/>', _rewriteFrame, svg, count=1)

    width = app.size.width * 12.2
    height = app.size.height * 24.4
    newHeight = height + 24.4

    bgRect = (
        f'\n    <rect fill="{bgHex}" x="0" y="0"'
        f' width="{width}" height="{newHeight}" rx="0"/>'
    )

    svg = re.sub(
        r'(<g transform="translate\([^)]+\)" clip-path="url\(#[^"]+-clip-terminal\)">)',
        r'\1' + bgRect,
        svg
    )

    svg = re.sub(
        r'viewBox="0 0 ([\d.]+) ([\d.]+)"',
        lambda m: f'viewBox="1 1 {round(float(m.group(1)) - 2, 2)} {round(float(m.group(2)) - 2, 2)}"',
        svg,
        count=1
    )

    return svg.strip()


async def executePrint(screen: Screen, path: str, inline: bool = False) -> None:
    """Any decoded seed grid or invalid-word note on screen is captured fully masked, whatever its reveal or
    hover state, and secret input is blanked for the capture."""
    if os.path.exists(path + ".svg"):
        if hasattr(screen, "_triggerInputError"):
            screen._triggerInputError()

        return

    state = getattr(screen, "_state", None)
    inp = None
    oldValue = ""
    oldPlaceholder = ""
    shouldRestore = False

    stateName = getattr(state, "name", "")

    if stateName in ("ENCODE_PHRASE", "ENCODE_SALT", "ENCODE_SALT_CONFIRM", "DECODE_SALT"):
        try:
            from spicebag.frontend.widgets.secureInput import SecureInput
            inp = screen.query_one("#cmd-input", SecureInput)
            oldValue = inp.value
            oldPlaceholder = inp.placeholder
            inp.value = ""
            inp.placeholder = ""
            shouldRestore = True

        except Exception:
            pass

    emitSaved = getattr(screen, "_emitScreenshotSaved", None)
    emitError = getattr(screen, "_emitScreenshotError", None)

    sampleNode = getattr(screen, "_activeSampleNode", None)
    maskSample = False
    if sampleNode is not None and not sampleNode.sampleMasked:
        maskSample = True
        sampleNode.sampleMasked = True

    textNodes = []
    seen = set()
    for region in getattr(screen, "_hoverRegions", []):
        node = region[3]
        if not hasattr(node, "screenshotMask"):
            continue

        if id(node) not in seen:
            seen.add(id(node))
            if not node.screenshotMask:
                node.screenshotMask = True
                textNodes.append(node)

    _rebuild = getattr(screen, "_rebuild", None)
    if (maskSample or textNodes) and _rebuild:
        _rebuild(scrollToEnd=False)

    theme = getattr(screen.app, "terminalTheme", FALLBACK_THEME)

    try:
        try:
            svg = exportScreenshot(screen.app, theme)

        finally:
            if shouldRestore and inp:
                inp.value = oldValue
                inp.placeholder = oldPlaceholder

            if maskSample and sampleNode is not None:
                sampleNode.sampleMasked = False

            for node in textNodes:
                node.screenshotMask = False

            if (maskSample or textNodes) and _rebuild:
                _rebuild(scrollToEnd=False)

        svg = cleanSvg(screen.app, svg, theme.background_color.hex.upper())
        svgPath = path + ".svg"

        with open(svgPath, "w", encoding="utf-8") as f:
            f.write(svg)

        if emitSaved:
            displayPath = os.path.basename(svgPath)
            emitSaved(displayPath, inline)

        setattr(screen, "_anyCommandRun", True)

    except FileNotFoundError:
        if not inline and emitError:
            emitError("Export failed: Target directory does not exist or is invalid.")

    except PermissionError:
        if not inline and emitError:
            emitError("Screenshot permission denied. Please ensure you have write access to this location.")

    except Exception:
        if not inline and emitError:
            emitError("Export failed: Unable to write screenshot to the specified path.")


def generateScreenshotPath() -> str:
    targetDir = SCREENSHOTS_DIR
    targetDir.mkdir(parents=True, exist_ok=True)
    return str(targetDir / f"Screenshot_{time.strftime('%Y%m%d_%H%M%S')}")