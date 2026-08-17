######## LIBRARIES ########

from rich.terminal_theme import TerminalTheme
import platform
import time
import sys
import os
import re



######## FALLBACK PALETTE ########

FALLBACK_BG = (12, 12, 12)
FALLBACK_FG = (217, 217, 217)

FALLBACK_ANSI = [
    (26, 26, 26), (244, 0, 95), (152, 224, 36), (253, 151, 31),
    (157, 101, 255), (244, 0, 95), (88, 209, 235), (196, 197, 181),
    (98, 94, 76), (244, 0, 95), (152, 224, 36), (224, 213, 97),
    (157, 101, 255), (244, 0, 95), (88, 209, 235), (246, 246, 239)
]

FALLBACK_THEME = TerminalTheme(FALLBACK_BG, FALLBACK_FG, FALLBACK_ANSI[:8], FALLBACK_ANSI[8:])



######## OSC QUERY ########

OSC_QUERY = "\x1b]11;?\x07\x1b]10;?\x07" + "".join(f"\x1b]4;{i};?\x07" for i in range(16))

OSC_REPLY = re.compile(r"\x1b\](\d+);(?:(\d+);)?rgb:([\dA-Fa-f]+)/([\dA-Fa-f]+)/([\dA-Fa-f]+)")

EXPECTED_REPLIES = 18

DRAIN_GRACE = 0.03

WINDOWS_ANSI_SLOTS = [0, 4, 2, 6, 1, 5, 3, 7, 8, 12, 10, 14, 9, 13, 11, 15]

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200



######## REPLY PARSING ########

def scaleComponent(raw: str) -> int:
    return round(int(raw, 16) * 255 / (16 ** len(raw) - 1))


def repliesComplete(buffer: str) -> bool:
    """Count terminated replies only, so the reader never stops mid-sequence."""
    return buffer.count("\x07") + buffer.count("\x1b\\") >= EXPECTED_REPLIES


def parseOscReplies(buffer: str) -> tuple | None:
    background = None
    foreground = None
    palette = {}

    for match in OSC_REPLY.finditer(buffer):
        code, index, red, green, blue = match.groups()
        triplet = (scaleComponent(red), scaleComponent(green), scaleComponent(blue))

        if code == "11":
            background = triplet

        elif code == "10":
            foreground = triplet

        elif code == "4" and index is not None and int(index) < 16:
            palette[int(index)] = triplet

    if background is None or foreground is None:
        return None

    return background, foreground, [palette.get(i, FALLBACK_ANSI[i]) for i in range(16)]



######## PLATFORM READERS ########

def readRepliesPosix(timeout: float) -> str:
    import termios
    import select
    import tty

    descriptor = sys.stdin.fileno()
    saved = termios.tcgetattr(descriptor)
    buffer = ""

    try:
        tty.setraw(descriptor)
        sys.stdout.write(OSC_QUERY)
        sys.stdout.flush()

        deadline = time.monotonic() + timeout
        while not repliesComplete(buffer):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            ready, _, _ = select.select([descriptor], [], [], remaining)
            if not ready:
                break

            buffer += os.read(descriptor, 4096).decode("utf-8", "replace")

        while select.select([descriptor], [], [], DRAIN_GRACE)[0]:
            buffer += os.read(descriptor, 4096).decode("utf-8", "replace")

    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)

    return buffer


def readRepliesWindows(timeout: float) -> str:
    import ctypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.GetStdHandle.argtypes = [ctypes.c_uint32]
    kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    inputHandle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    outputHandle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    savedInput = ctypes.c_uint32()
    savedOutput = ctypes.c_uint32()

    if not kernel32.GetConsoleMode(inputHandle, ctypes.byref(savedInput)):
        return ""

    if not kernel32.GetConsoleMode(outputHandle, ctypes.byref(savedOutput)):
        return ""

    probeInput = (savedInput.value | ENABLE_VIRTUAL_TERMINAL_INPUT) & ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT)
    probeOutput = savedOutput.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING

    if not kernel32.SetConsoleMode(outputHandle, probeOutput):
        return ""

    if not kernel32.SetConsoleMode(inputHandle, probeInput):
        kernel32.SetConsoleMode(outputHandle, savedOutput.value)
        return ""

    buffer = ""

    try:
        sys.stdout.write(OSC_QUERY)
        sys.stdout.flush()

        deadline = time.monotonic() + timeout
        while not repliesComplete(buffer) and time.monotonic() < deadline:
            if msvcrt.kbhit():
                buffer += msvcrt.getwch()

            else:
                time.sleep(0.004)

        drainDeadline = time.monotonic() + DRAIN_GRACE
        while time.monotonic() < drainDeadline:
            if msvcrt.kbhit():
                buffer += msvcrt.getwch()
                drainDeadline = time.monotonic() + DRAIN_GRACE

            else:
                time.sleep(0.002)

    finally:
        kernel32.SetConsoleMode(inputHandle, savedInput.value)
        kernel32.SetConsoleMode(outputHandle, savedOutput.value)

    return buffer


def readWindowsConsoleRegistry() -> tuple | None:
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Console")

    except OSError:
        return None

    try:
        table = []
        for i in range(16):
            packed, _ = winreg.QueryValueEx(key, f"ColorTable{i:02d}")
            table.append((packed & 0xFF, (packed >> 8) & 0xFF, (packed >> 16) & 0xFF))

        screenColors, _ = winreg.QueryValueEx(key, "ScreenColors")

    except OSError:
        return None

    finally:
        winreg.CloseKey(key)

    background = table[(screenColors >> 4) & 0x0F]
    foreground = table[screenColors & 0x0F]

    return background, foreground, [table[slot] for slot in WINDOWS_ANSI_SLOTS]



######## PUBLIC API ########

def probeTerminalTheme(timeout: float = 0.2) -> TerminalTheme:
    """Resolve the live terminal palette, falling back to a fixed dark theme."""
    isWindows = platform.system() == "Windows"

    if sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        try:
            buffer = readRepliesWindows(timeout) if isWindows else readRepliesPosix(timeout)

        except Exception:
            buffer = ""

        resolved = parseOscReplies(buffer)
        if resolved is not None:
            background, foreground, ansi = resolved
            return TerminalTheme(background, foreground, ansi[:8], ansi[8:])

    if isWindows:
        try:
            resolved = readWindowsConsoleRegistry()

        except Exception:
            resolved = None

        if resolved is not None:
            background, foreground, ansi = resolved
            return TerminalTheme(background, foreground, ansi[:8], ansi[8:])

    return FALLBACK_THEME