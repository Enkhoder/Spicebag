######## LIBRARIES ########

import subprocess
import platform
import time
import sys
import os



######## CONSTANTS ########

CF_UNICODETEXT = 13

GMEM_MOVEABLE = 0x0002

WM_RENDERFORMAT = 0x0305

WM_RENDERALLFORMATS = 0x0306

WM_DESTROYCLIPBOARD = 0x0307

PM_REMOVE = 0x0001

HWND_MESSAGE = -3

PRIVACY_FORMATS = (
    "ExcludeClipboardContentFromMonitorProcessing",
    "CanIncludeInClipboardHistory",
    "CanUploadToCloudClipboard"
)



######## WINDOWS ########

def _win32():
    from ctypes import wintypes
    import ctypes

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardOwner.restype = wintypes.HWND
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    return ctypes, user32, kernel32


def _openClipboard(user32, owner=None) -> bool:
    for _ in range(10):
        if user32.OpenClipboard(owner):
            return True

        time.sleep(0.05)

    return False


def _placeData(ctypes, user32, kernel32, clipFormat: int, data: bytes) -> bool:
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        return False

    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False

    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)

    if not user32.SetClipboardData(clipFormat, handle):
        kernel32.GlobalFree(handle)
        return False

    return True


def _pasteOnceWindows(text: str) -> str:
    """Offer the text by delayed rendering. The clipboard holds only a promise, with the privacy formats password
    managers use so Windows keeps it out of history, cloud sync and clipboard monitors. The text exists on the
    clipboard only inside the one WM_RENDERFORMAT the first paste triggers, and the clipboard is emptied as soon
    as that paste lets go of it. Leaving early, Ctrl+C included, never renders the promise."""
    from ctypes import wintypes

    ctypes, user32, kernel32 = _win32()
    windowProcType = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                        wintypes.LPARAM)

    class WindowClass(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", windowProcType),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR)
        ]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WindowClass)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
                                    wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = ctypes.c_ssize_t
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    state = {"rendered": False, "released": False}

    def windowProc(hwnd, message, wParam, lParam):
        if message == WM_RENDERFORMAT:
            if not state["rendered"]:
                state["rendered"] = _placeData(ctypes, user32, kernel32, CF_UNICODETEXT,
                                               (text.replace("\n", "\r\n") + "\0").encode("utf-16-le"))

            return 0

        if message == WM_RENDERALLFORMATS:
            return 0

        if message == WM_DESTROYCLIPBOARD:
            state["released"] = True
            return 0

        return user32.DefWindowProcW(hwnd, message, wParam, lParam)

    callback = windowProcType(windowProc)
    instance = kernel32.GetModuleHandleW(None)
    className = f"SpicebagPasteOnce{id(callback)}"
    windowClass = WindowClass(lpfnWndProc=callback, hInstance=instance, lpszClassName=className)

    if not user32.RegisterClassW(ctypes.byref(windowClass)):
        return "unavailable"

    hwnd = user32.CreateWindowExW(0, className, className, 0, 0, 0, 0, 0, wintypes.HWND(HWND_MESSAGE), None,
                                  instance, None)

    try:
        if not hwnd or not _openClipboard(user32, hwnd):
            return "unavailable"

        try:
            if not user32.EmptyClipboard():
                return "unavailable"

            state["released"] = False
            disabled = (0).to_bytes(4, "little")
            for name in PRIVACY_FORMATS:
                clipFormat = user32.RegisterClipboardFormatW(name)
                if not clipFormat or not _placeData(ctypes, user32, kernel32, clipFormat, disabled):
                    return "unavailable"

            user32.SetClipboardData(CF_UNICODETEXT, None)

        finally:
            user32.CloseClipboard()

        message = wintypes.MSG()

        while True:
            while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))

            if state["rendered"]:
                return "pasted"

            if state["released"]:
                return "replaced"

            time.sleep(0.02)

    finally:
        if hwnd:
            for _ in range(500):
                if user32.GetClipboardOwner() != hwnd:
                    break

                if user32.OpenClipboard(hwnd):
                    user32.EmptyClipboard()
                    user32.CloseClipboard()

                else:
                    time.sleep(0.02)

            user32.DestroyWindow(hwnd)

        user32.UnregisterClassW(className, instance)


def _readWindows() -> str | None:
    ctypes, user32, kernel32 = _win32()

    if not _openClipboard(user32):
        return None

    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None

        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None

        try:
            return ctypes.wstring_at(pointer)

        finally:
            kernel32.GlobalUnlock(handle)

    finally:
        user32.CloseClipboard()


def _clearWindows() -> bool:
    _, user32, _ = _win32()

    if not _openClipboard(user32):
        return False

    try:
        return bool(user32.EmptyClipboard())

    finally:
        user32.CloseClipboard()



######## MACOS / LINUX ########

def _runCommand(command: list[str], text: str = "", capture: bool = False) -> str | None:
    try:
        result = subprocess.run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5
        )
        return result.stdout.decode("utf-8", "replace") if result.stdout is not None else ""

    except (OSError, subprocess.SubprocessError):
        return None


def _pasteOnceWayland(text: str) -> str:
    """wl-copy serves exactly one paste and exits. Kept in the foreground, so the run waits for that paste."""
    try:
        process = subprocess.Popen(
            ["wl-copy", "--foreground", "--paste-once"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    except OSError:
        return "unavailable"

    try:
        try:
            process.stdin.write(text.encode("utf-8"))
            process.stdin.close()

        except OSError:
            process.kill()
            return "unavailable"

        return "pasted" if process.wait() == 0 else "unavailable"

    except KeyboardInterrupt:
        process.kill()
        _runCommand(["wl-copy", "--clear"])
        raise



######## CLIPBOARD ########

def clipboardBlocker() -> str | None:
    """The subsystem whose clipboard bridge spends a one-time paste itself, or None. WSLg mirrors the Linux
    clipboard to Windows and reads every new selection the moment it is offered, before the user can paste."""
    if sys.platform.startswith("linux"):
        if "WSL_DISTRO_NAME" in os.environ or "microsoft" in platform.release().lower():
            return "WSL"

    return None


def pasteOnce(text: str) -> str:
    """Offer text for exactly one paste, anywhere, then leave the clipboard empty, blocking until the paste.
    Returns "pasted", "replaced" when something else took the clipboard first, "copied" where one-time paste is
    unsupported and the text was copied plainly, or "unavailable". The text reaches pbcopy and wl-copy over
    stdin, never argv."""
    if sys.platform == "win32":
        return _pasteOnceWindows(text)

    if sys.platform == "darwin":
        return "copied" if _runCommand(["pbcopy"], text) is not None else "unavailable"

    if sys.platform.startswith("linux"):
        return _pasteOnceWayland(text)

    return "unavailable"


def readClipboard() -> str | None:
    if sys.platform == "win32":
        return _readWindows()

    if sys.platform == "darwin":
        return _runCommand(["pbpaste"], capture=True)

    if sys.platform.startswith("linux"):
        return _runCommand(["wl-paste", "--no-newline"], capture=True)

    return None


def clearClipboard() -> bool:
    if sys.platform == "win32":
        return _clearWindows()

    if sys.platform == "darwin":
        return _runCommand(["pbcopy"]) is not None

    if sys.platform.startswith("linux"):
        return _runCommand(["wl-copy", "--clear"]) is not None

    return False