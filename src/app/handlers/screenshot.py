######## LIBRARIES ########

from src.constants.theme import OUTPUT_DIR
from textual.screen import Screen
from textual.app import App
import time
import os
import re



######## SCREENSHOT HANDLERS ########

def cleanSvg(app: App, svg: str) -> str:
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
        r'(<rect fill="#292929"[^>]*?height=")([\d.]+)',
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

    bgMatch = re.search(
        r'<rect fill="(#[0-9a-fA-F]{6})" x="0"[^>]+shape-rendering="crispEdges"',
        svg
    )
    detectedBg = bgMatch.group(1).upper() if bgMatch else "#121212"

    vbMatch = re.search(r'viewBox="0 0 ([\d.]+)', svg)
    totalSvgW = float(vbMatch.group(1)) if vbMatch else app.size.width * 12.2 + 18
    xRight = totalSvgW - 1
    xRightArc = xRight - 16

    topBezelPath = (
        f'<path fill="#292929"'
        f' d="M 1,41 V 17 A 16,16 0 0 1 17,1 H {xRightArc} A 16,16 0 0 1 {xRight},17 V 41 Z"/>'
    )

    def _rewriteFrame(m: re.Match) -> str:
        tag = m.group(0)
        tag = tag.replace('fill="#292929"', f'fill="{detectedBg}"')
        tag = re.sub(r'\brx="\d+"', 'rx="16"', tag)
        tag = re.sub(r'\s*stroke(?:-width)?="[^"]*"', '', tag)
        tag = re.sub(r'\s*shape-rendering="[^"]*"', '', tag)
        return tag + topBezelPath

    svg = re.sub(r'<rect\s+fill="#292929"[^/]*/>', _rewriteFrame, svg, count=1)

    width = app.size.width * 12.2
    height = app.size.height * 24.4
    newHeight = height + 24.4

    bgRect = (
        f'\n    <rect fill="{detectedBg}" x="0" y="0"'
        f' width="{width}" height="{newHeight}" rx="0"/>'
    )

    svg = re.sub(
        r'(<g transform="translate\([^)]+\)" clip-path="url\(#[^"]+-clip-terminal\)">)',
        r'\1' + bgRect,
        svg
    )

    svg = re.sub(r'#121212', '#0C0C0C', svg, flags=re.IGNORECASE)

    return svg.strip()


async def executePrint(screen: Screen, path: str, inline: bool = False) -> None:
    if os.path.exists(path + ".svg"):
        if hasattr(screen, "_triggerInputError"):
            screen._triggerInputError()
        return

    state = getattr(screen, "_state", None)
    inp = None
    old_value = ""
    old_placeholder = ""
    should_restore = False

    state_name = getattr(state, "name", "")

    if state_name in ("ENCODE_PHRASE", "ENCODE_SALT", "DECODE_SALT", "DECODE_PATH", "ENCODE_SAVE_PATH"):
        try:
            from src.app.widgets.secureInput import SecureInput
            inp = screen.query_one("#cmd-input", SecureInput)
            old_value = inp.value
            old_placeholder = inp.placeholder
            inp.value = ""
            inp.placeholder = ""
            should_restore = True

        except Exception:
            pass

    emitSaved = getattr(screen, "_emitScreenshotSaved", None)
    emitError = getattr(screen, "_emitScreenshotError", None)

    sampleNode = getattr(screen, "_activeSampleNode", None)
    maskSample = False
    if sampleNode is not None and not sampleNode.sampleMasked:
        maskSample = True
        sampleNode.sampleMasked = True

    # Any decoded seed grid or invalid-word note currently on screen must capture
    # as fully masked, regardless of reveal/hover state.
    textNodes = []
    seen = set()
    for region in getattr(screen, "_hoverRegions", []):
        node = region[3]
        if id(node) not in seen:
            seen.add(id(node))
            if not node.screenshotMask:
                node.screenshotMask = True
                textNodes.append(node)

    _rebuild = getattr(screen, "_rebuild", None)
    if (maskSample or textNodes) and _rebuild:
        _rebuild(scrollToEnd=False)

    try:
        try:
            svg = screen.app.export_screenshot()
        finally:
            if should_restore and inp:
                inp.value = old_value
                inp.placeholder = old_placeholder
            if maskSample and sampleNode is not None:
                sampleNode.sampleMasked = False
            for node in textNodes:
                node.screenshotMask = False
            if (maskSample or textNodes) and _rebuild:
                _rebuild(scrollToEnd=False)

        svg = cleanSvg(screen.app, svg)
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
    target_dir = OUTPUT_DIR / "app-screenshots"
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir / f"Screenshot_{time.strftime('%Y%m%d_%H%M%S')}")