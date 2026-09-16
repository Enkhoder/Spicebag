######## LIBRARIES ########

from pathlib import Path



######## CONSTANTS ########

ILLEGAL_STEM_CHARS = frozenset('<>:"/\\|?*\x00')

RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
})



######## HELPERS ########

def _stripQuotes(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        return raw[1:-1]

    return raw


def _validateStem(stem: str) -> str | None:
    if not stem or not stem.strip():
        return "Filename cannot consist of only whitespaces."

    if stem[0] == " ":
        return "Filename cannot begin with a space."

    if stem[-1] in (".", " "):
        return "Filename cannot end with a period or space."

    illegalChars = set()
    for ch in stem:
        if ch in ILLEGAL_STEM_CHARS or ord(ch) < 32:
            illegalChars.add(ch)

    if illegalChars:
        sortedChars = sorted(list(illegalChars))
        formatted = []
        for ch in sortedChars:
            if ord(ch) < 32:
                formatted.append(repr(ch).strip("'\""))

            else:
                formatted.append(ch)

        charStr = " ".join(formatted)

        if len(sortedChars) > 1:
            return f"Filename contains illegal characters: {charStr}"

        else:
            return f"Filename contains an illegal character: {charStr}"

    baseName = stem.upper().rsplit(".", 1)[0]

    if baseName in RESERVED_NAMES:
        return f"'{stem}' uses a reserved system name and thus cannot be a filename."

    return None



######## SAVE PATH PARSER ########

def parseSavePath(raw: str, defaultDir: Path) -> tuple[str, str] | str:
    """
    Parse a combined directory + filename stem string.

    A run of two or more consecutive separators (// \\ /\\ \\/) is an
    explicit separator: the part before is the directory, the part after
    is the stem, with no folder-priority check.

    A single separator does a folder-priority check: if the full path is
    an existing directory the stem defaults (image saved inside).

    Returns (dirStr, stem) or an error string.
    """

    if not raw:
        return ("", "")

    raw = _stripQuotes(raw)

    if not raw:
        return ("", "")

    lastSlash = max(raw.rfind('/'), raw.rfind('\\'))

    if lastSlash == -1:
        dirStr = raw
        stem = ""

    elif lastSlash == len(raw) - 1:
        slashRunStart = lastSlash
        while slashRunStart > 0 and raw[slashRunStart - 1] in ('/', '\\'):
            slashRunStart -= 1

        if slashRunStart < lastSlash:
            return "Custom filename cannot be blank."

        dirStr = raw[:lastSlash]
        stem = ""

        if not dirStr:
            return ("", "")

    else:
        slashRunStart = lastSlash
        while slashRunStart > 0 and raw[slashRunStart - 1] in ('/', '\\'):
            slashRunStart -= 1

        potentialDir = raw[:slashRunStart]
        potentialStem = raw[lastSlash + 1:]

        if slashRunStart < lastSlash:
            dirStr = potentialDir
            stem = potentialStem

        else:
            try:
                if Path(raw).is_dir():
                    dirStr = raw
                    stem = ""

                else:
                    dirStr = potentialDir
                    stem = potentialStem

            except OSError:
                dirStr = potentialDir
                stem = potentialStem

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
    Split a decode-path string into (directory, filename) on the last
    path separator (/ or \\).

        "<name>"         -> ("<name>", "")       no separator: treat as dir
        "<dir>/<stem>"   -> ("<dir>", "<stem>")  standard split
        "<dir>/"         -> ("<dir>", "")        trailing slash: empty stem
    """

    raw = _stripQuotes(raw)
    lastSlash = max(raw.rfind('/'), raw.rfind('\\'))

    if lastSlash == -1:
        return (raw, "")

    slashRunStart = lastSlash
    while slashRunStart > 0 and raw[slashRunStart - 1] in ('/', '\\'):
        slashRunStart -= 1

    return (raw[:slashRunStart], raw[lastSlash + 1:])