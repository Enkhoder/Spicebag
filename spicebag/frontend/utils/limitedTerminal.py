######## LIBRARIES ########

import sys
import os



######## CONSTANTS ########

TRUECOLOR_VALUES = ("truecolor", "24bit")

TERMINAL_NAMES = {
    "Apple_Terminal": "Apple Terminal",
    "iTerm.app": "iTerm2",
    "vscode": "VS Code"
}



######## LIMITED TERMINAL DETECTION ########

def _isClassicConsoleHost() -> bool:
    """The classic Windows console host owns a real ConsoleWindowClass window. Windows Terminal, VS Code and
    other ConPTY hosts hand the process a PseudoConsoleWindow instead."""
    from ctypes import wintypes
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32")
    user32 = ctypes.WinDLL("user32")
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    hwnd = kernel32.GetConsoleWindow()
    if not hwnd:
        return False

    className = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, className, 256)
    return className.value == "ConsoleWindowClass"


def _windowsVersion() -> str:
    """The console host ships with Windows, so its version is the OS build, with the update revision when the
    registry has one."""
    major, minor, build = sys.getwindowsversion()[:3]
    version = f"{major}.{minor}.{build}"

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            revision, _ = winreg.QueryValueEx(key, "UBR")
            version += f".{revision}"

    except OSError:
        pass

    return version


def _posixTerminalLabel() -> str:
    program = os.environ.get("TERM_PROGRAM", "")
    name = TERMINAL_NAMES.get(program, program) or os.environ.get("TERM", "")
    version = os.environ.get("TERM_PROGRAM_VERSION", "") if program else ""

    return f"{name} v{version}" if version else name


def getLimitedTerminal() -> str | None:
    """Name and version of a terminal below the interface's baseline, empty when it reports no name, or None when
    the terminal meets the baseline. On Windows that is the classic console host; elsewhere, any terminal that does
    not advertise truecolor."""
    if sys.platform == "win32":
        try:
            return f"Windows Console Host v{_windowsVersion()}" if _isClassicConsoleHost() else None

        except Exception:
            return None

    if os.environ.get("COLORTERM", "").lower() in TRUECOLOR_VALUES:
        return None

    return _posixTerminalLabel()