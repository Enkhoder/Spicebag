######## LIBRARIES ########

from spicebag.backend.defaults import (
    WORD_COUNT_MAX_INDEX,
    SEED_TYPE_STANDARDS,
    FORBIDDEN_CHUNKS,
    GRID_SIZES
)
from spicebag.backend.colors import saltKeys, cellOrder, decodeCell, computeProof
from PIL import Image
import struct



######## CONSTANTS ########

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

BAD_PNG_TEXT = "PNG contains forbidden chunks or unacceptable color space."



######## PNG VALIDATOR ########

def detectFileFormat(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "JPG"

    if data[:4] == b"%PDF":
        return "PDF"

    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"

    if data[:2] == b"BM":
        return "BMP"

    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"

    if data[:4] == b"PK\x03\x04":
        return "ZIP"

    return None


def validatePNGStructure(path) -> None:
    with open(path, "rb") as f:
        data = f.read()

    if not data.startswith(PNG_SIGNATURE):
        fmt = detectFileFormat(data)

        if fmt is not None:
            raise ValueError(f"The file is in {fmt}. Please select a PNG file.")

        raise ValueError(BAD_PNG_TEXT)

    i = 8

    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i+4])[0]
        chunk = data[i+4:i+8]

        if chunk in FORBIDDEN_CHUNKS:
            raise ValueError(BAD_PNG_TEXT)

        i += 12 + length


def getGridDimensions(width: int, height: int):
    """Recover (cols, rows, wordCount, maxIdx) from the image aspect ratio. Cross-multiplied
    so the comparison stays exact in integers. Every ratio in GRID_SIZES is distinct, so at
    most one entry can match."""
    for wordCount, (cols, rows) in GRID_SIZES.items():
        if width * rows == height * cols:
            return cols, rows, wordCount, WORD_COUNT_MAX_INDEX[wordCount]

    raise ValueError("Wrong aspect ratio.")


def extractRGB(pixel):
    badColorSpace = ValueError(BAD_PNG_TEXT)

    if not isinstance(pixel, tuple):
        raise badColorSpace

    if len(pixel) == 3:
        r, g, b = pixel

    elif len(pixel) == 4:
        r, g, b, a = pixel

        if a != 255:
            raise badColorSpace

    else:
        raise badColorSpace

    for v in (r, g, b):
        if type(v) is not int or not (0 <= v <= 255):
            raise badColorSpace

    return (r, g, b)


def validateImage(path) -> bool:
    """Verify every pixel inside each cell is identical. Each cell is counted as one block through
    Pillow rather than pixel by pixel in Python: asking for at most one color returns nothing once a
    second color appears, which keeps a 2000px-per-cell image in seconds rather than minutes."""
    validatePNGStructure(path)

    img = Image.open(path)

    if img.mode not in ("RGB", "RGBA"):
        raise ValueError(BAD_PNG_TEXT)

    if img.mode == "RGBA" and img.getchannel("A").getextrema() != (255, 255):
        raise ValueError(BAD_PNG_TEXT)

    width, height = img.size
    cols, rows, _, _ = getGridDimensions(width, height)

    if width % cols != 0 or height % rows != 0:
        raise ValueError("Invalid cell aspect ratio.")

    cellWidth = width // cols
    cellHeight = height // rows

    contaminated = 0

    for r in range(rows):
        for c in range(cols):
            cell = img.crop((c * cellWidth, r * cellHeight, (c + 1) * cellWidth, (r + 1) * cellHeight))

            if cell.getcolors(maxcolors=1) is None:
                contaminated += 1

    if contaminated:
        raise ValueError("Dirty cell." if contaminated == 1 else "Dirty cells.")

    return True


def imageError(path) -> str | None:
    """Why an image cannot be decoded, in the words both the TUI app and CLI mode show, or None when it
    passes validation."""
    try:
        validateImage(path)

    except FileNotFoundError:
        return "Image not found."

    except PermissionError:
        return "Permission denied. Make sure you have read access to the image."

    except ValueError as e:
        return str(e)

    except Exception:
        return "Invalid image format or failed to load pixel data."

    return None



######## IMAGE DECODER ########

class WrongSaltError(ValueError):
    """The phrase read with this salt does not carry its proof: a wrong salt, a missing salt, a salt given for
    an unsalted image, an altered image, or an image made before 4.0.0."""


def resolveMnemonic(wordIndices, wordCount):
    """Try each standard that admits this word count, in declaration order, and return the
    first phrase that passes its checksum."""
    for name, wordCounts, wordList, _, validator in SEED_TYPE_STANDARDS:
        if wordCount not in wordCounts:
            continue

        mnemonic = " ".join([wordList[idx] for idx in wordIndices])

        if validator(mnemonic):
            return (mnemonic, name)

    return None


def readCells(pixels, coords, cellWidth, cellHeight, maxIdx, colorTables, cancelCheck=None):
    """Word index and proof chunk of each cell, in word order."""
    wordIndices = []
    proofChunks = []

    for r, c in coords:
        if cancelCheck and cancelCheck():
            raise InterruptedError("Canceled")

        wordIndex, proofChunk = decodeCell(
            extractRGB(pixels[c * cellWidth, r * cellHeight]),
            maxIndex=maxIdx,
            colorTables=colorTables
        )
        wordIndices.append(wordIndex)
        proofChunks.append(proofChunk)

    return wordIndices, proofChunks


def decodeImage(imagePath, salt="", progressCallback=None, validate=True, cancelCheck=None):
    """A wrong salt still yields in-range indices, and a random phrase passes a 12-word checksum about one time
    in fifteen. The proof of phrase is what rejects it: every chunk must match the HMAC of the phrase under this
    salt's key. A salt given for an unsalted image fails the same way, through the same steps, so the decoder has
    nothing to tell it apart from a wrong salt by. The progress bar only advances for a phrase that proves itself."""
    if validate:
        validateImage(imagePath)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Canceled")

    img = Image.open(imagePath)
    pixels = img.load()

    if pixels is None:
        raise ValueError("Failed to load image pixel data.")

    width, height = img.size
    cols, rows, wordCount, maxIdx = getGridDimensions(width, height)

    cellWidth = width // cols
    cellHeight = height // rows

    colorTables, proofKey, rngSeed = saltKeys(salt)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Canceled")

    coords = cellOrder(cols, rows, rngSeed)
    wordIndices, proofChunks = readCells(pixels, coords, cellWidth, cellHeight, maxIdx, colorTables, cancelCheck)
    proven = proofChunks == computeProof(proofKey, wordIndices)
    result = resolveMnemonic(wordIndices, wordCount) if proven else None

    if result is None:
        if progressCallback is not None:
            progressCallback(0.0)

        raise WrongSaltError("Image or salt is incorrect.")

    mnemonic, seedType = result

    if progressCallback is not None:
        for i in range(wordCount):
            progressCallback((i + 1) / wordCount)

    return (mnemonic, seedType)