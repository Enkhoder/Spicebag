######## LIBRARIES ########

from pathlib import Path
import re
import os


######## CONSTANTS ########

ILLEGAL_STEM_CHARS = frozenset('<>:"/\\|?*\x00')

RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
})

_SLASH_RUN = re.compile(r"[/\\]{2,}")


######## HELPERS ########

def _stripQuotes(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]
    return raw


######## SAVE PATH PARSER ########

def parseSavePath(raw: str, defaultDir: Path) -> tuple[str, str] | str:
    """
    Parse a combined directory + filename stem string.

    Grammar:
        ""                       -> ("", "")              all defaults
        "<dir>"                  -> ("<dir>", "")          custom dir, default stem
        "<sep><stem>"            -> ("", "<stem>")         default dir, custom stem
        "<dir><sep><stem>"       -> ("<dir>", "<stem>")    both custom

    <sep> = two or more consecutive characters from [/\\].
    The LAST such run in the string is the separator.

    Returns:
        (dir_str, stem_str)  — empty string means "use default" for that field.
        str                  — error message if the input is invalid.
    """

    if not raw:
        return ("", "")

    raw = _stripQuotes(raw)

    if not raw:
        return ("", "")

    matches = list(_SLASH_RUN.finditer(raw))

    if not matches:
        dirStr = raw
        stem = ""

    else:
        last = matches[-1]
        dirStr = raw[:last.start()]
        stem = raw[last.end():]

        if not stem:
            return "Blank filename is not valid. Remove any trailing slashes."

    if stem:
        err = _validateStem(stem)

        if err:
            return err

    if dirStr:
        dirPath = Path(dirStr)
        isDefault = False
        try:
            isDefault = (dirPath.resolve() == defaultDir.resolve())
        except Exception:
            pass

        if not dirPath.exists() and not isDefault:
            return "Directory not found."

        if dirPath.exists() and not dirPath.is_dir():
            return "Path is not a directory."

    return (dirStr, stem)


######## DECODE PATH PARSER ########

def parseDecodePath(raw: str) -> tuple[str, str]:
    """
    Split a decode-path string into (directory, filename) on the LAST run of
    two or more characters from [/\\].

        "<sep><stem>"        -> ("", "<stem>")       default dir, custom file
        "<dir><sep><stem>"   -> ("<dir>", "<stem>")  both custom
        "<dir>"              -> ("<dir>", "")        no separator: dir only

    An empty filename means the input names a directory rather than a file;
    the caller decides which error applies (see _handleDecodePath).
    """

    raw = _stripQuotes(raw)
    matches = list(_SLASH_RUN.finditer(raw))

    if matches:
        last = matches[-1]
        return (raw[:last.start()], raw[last.end():])

    lastSep = max(raw.rfind("/"), raw.rfind(os.sep))

    if lastSep != -1:
        return (raw[:lastSep], raw[lastSep + 1:])

    return (raw, "")


def _validateStem(stem: str) -> str | None:
    if not stem or not stem.strip():
        return "Filename cannot consist of only whitespaces."

    if stem[0] == " ":
        return "Filename cannot begin with a space."

    if stem[-1] in (".", " "):
        return "Filename cannot end with a period or space."

    illegal_chars = set()
    for ch in stem:
        if ch in ILLEGAL_STEM_CHARS or ord(ch) < 32:
            illegal_chars.add(ch)

    if illegal_chars:
        sorted_chars = sorted(list(illegal_chars))
        formatted = []
        for ch in sorted_chars:
            if ord(ch) < 32:
                formatted.append(repr(ch).strip("'\""))
            else:
                formatted.append(ch)
        
        char_str = " ".join(formatted)
        if len(sorted_chars) > 1:
            return f"Filename contains illegal characters '{char_str}'."
        else:
            return f"Filename contains an illegal character '{char_str}'."

    baseName = stem.upper().rsplit(".", 1)[0]

    if baseName in RESERVED_NAMES:
        return f"'{stem}' uses a reserved system name and thus cannot be a filename."

    return None
