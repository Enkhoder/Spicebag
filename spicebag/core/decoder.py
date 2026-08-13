######## LIBRARIES ########

from spicebag.constants.defaults import (
    BIP39_LIST,
    ELECTRUM_LIST,
    SLIP39_LIST,
    FORBIDDEN_CHUNKS,
    RGB_VALUE_SHIFTS,
    validateBIP39,
    validateElectrum
)
from spicebag.utils.colors import deriveMasterKey, deriveSubkeys, deriveMask, decodeColor
from PIL import Image
import random
import struct



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

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        fmt = detectFileFormat(data)

        if fmt is not None:
            raise ValueError(f"The file is in {fmt}. Please select a PNG file.")

        raise ValueError("PNG contains forbidden chunks or unacceptable color space.")

    i = 8

    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i+4])[0]
        chunk = data[i+4:i+8]

        if chunk in FORBIDDEN_CHUNKS:
            raise ValueError("PNG contains forbidden chunks or unacceptable color space.")

        i += 12 + length


def getGridDimensions(width: int, height: int):
    if width * 4 == height * 3:
        return 3, 4, 12, 2048

    if width * 5 == height * 3:
        return 3, 5, 15, 2048

    if width * 2 == height:
        return 3, 6, 18, 2048

    if width * 5 == height * 4:
        return 4, 5, 20, 1024

    if width * 7 == height * 3:
        return 3, 7, 21, 2048

    if width * 3 == height * 2:
        return 4, 6, 24, 2048

    if width * 11 == height * 3:
        return 3, 11, 33, 1024

    raise ValueError("Invalid image aspect ratio.")


def extractRGB(pixel):
    badColorSpace = ValueError("PNG contains forbidden chunks or unacceptable color space.")

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
    validatePNGStructure(path)

    img = Image.open(path)
    pixels = img.load()

    if pixels is None:
        raise ValueError("Failed to load image pixel data.")

    width, height = img.size
    cols, rows, wordCount, _ = getGridDimensions(width, height)

    if width % cols != 0 or height % rows != 0:
        raise ValueError("Invalid cell aspect ratio.")

    cellWidth = width // cols
    cellHeight = height // rows

    contaminated = 0

    for r in range(rows):
        for c in range(cols):
            basePx = pixels[c * cellWidth, r * cellHeight]
            baseColor = extractRGB(basePx)
            cellBad = False

            for y in range(r * cellHeight, (r + 1) * cellHeight):
                for x in range(c * cellWidth, (c + 1) * cellWidth):
                    if extractRGB(pixels[x, y]) != baseColor:
                        cellBad = True
                        break

                if cellBad:
                    break

            if cellBad:
                contaminated += 1

    if contaminated:
        noun = "cell" if contaminated == 1 else "cells"
        raise ValueError(f"{contaminated} contaminated {noun} detected.")

    return True



######## IMAGE DECODER ########

def resolveMnemonic(wordIndices, wordCount):
    if wordCount in (12, 15, 18, 21, 24):
        mnemonic = " ".join([BIP39_LIST[idx] for idx in wordIndices])

        if validateBIP39(mnemonic):
            return (mnemonic, "BIP39")

    if wordCount in (12, 24):
        mnemonic = " ".join([ELECTRUM_LIST[idx] for idx in wordIndices])

        if validateElectrum(mnemonic):
            return (mnemonic, "Electrum")

    if wordCount in (20, 33):
        mnemonic = " ".join([SLIP39_LIST[idx] for idx in wordIndices])

        try:
            from shamir_mnemonic import Share
            Share.from_mnemonic(mnemonic)

            return (mnemonic, "SLIP39")

        except Exception:
            pass

    return None


def decodeImage(imagePath, salt="", progressCallback=None, validate=True, cancelCheck=None):
    if validate:
        validateImage(imagePath)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Cancelled")

    img = Image.open(imagePath)
    pixels = img.load()

    if pixels is None:
        raise ValueError("Failed to load image pixel data.")

    width, height = img.size
    cols, rows, wordCount, maxIdx = getGridDimensions(width, height)

    cellWidth = width // cols
    cellHeight = height // rows

    if salt:
        masterKey = deriveMasterKey(salt)

        if cancelCheck and cancelCheck():
            raise InterruptedError("Cancelled")

        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")

    else:
        maskKey = None
        rngSeed = None

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]

    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    wordIndices = []

    for i in range(wordCount):
        if cancelCheck and cancelCheck():
            raise InterruptedError("Cancelled")

        r, c = allCoords[i]

        basePx = pixels[c * cellWidth, r * cellHeight]
        baseColor = extractRGB(basePx)

        wordMask = deriveMask(maskKey, i, maxIdx) if maskKey is not None else 0
        currentShift = RGB_VALUE_SHIFTS[i]

        wordIndices.append(
            decodeColor(
                baseColor,
                mask=wordMask,
                shift=currentShift,
                maxIndex=maxIdx
            )
        )

    # A wrong salt yields in-range but incorrect indices, so the phrase fails
    # validation wholesale. The progress bar only advances for words that belong
    # to a successfully recovered mnemonic — a failed decode therefore stays 0%.
    result = resolveMnemonic(wordIndices, wordCount)

    if result is None:
        if progressCallback is not None:
            progressCallback(0.0)

        raise ValueError("Image or salt is incorrect.")

    mnemonic, seedType = result

    if progressCallback is not None:
        for i in range(wordCount):
            progressCallback((i + 1) / wordCount)

    return (mnemonic, seedType)