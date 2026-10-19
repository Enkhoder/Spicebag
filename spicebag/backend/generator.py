######## LIBRARIES ########

from spicebag.backend.colors import saltKeys, cellOrder, encodeWord, computeProof, composeOffset, computeFreeSize
from spicebag.backend.defaults import SEED_TYPE_STANDARDS, GRID_SIZES
from dataclasses import dataclass, field
from PIL import Image
import colorsys
import secrets
import zipfile
import bisect
import io



######## MNEMONIC IDENTIFIER ########

class InvalidSeedWordsError(ValueError):
    """Raised when a phrase contains words present in no wordlist. Carries the
    sorted offending words so the UI can mask them individually."""

    def __init__(self, words: list[str], prefix: str = "") -> None:
        self.words = list(words)
        self.prefix = prefix
        plural = "words" if len(self.words) > 1 else "word"
        masked = ", ".join("·" * len(w) for w in self.words)

        if prefix:
            message = f"{prefix}, invalid seed {plural}: {masked}"

        else:
            message = f"Invalid seed {plural}: {masked}"

        super().__init__(message)


def binarySearchWord(wordList: list[str], word: str) -> int:
    idx = bisect.bisect_left(wordList, word)

    if idx < len(wordList) and wordList[idx] == word:
        return idx

    return -1


def identifySeedType(rawInput: str):
    words = rawInput.lower().split()
    mnemonicStr = " ".join(words)
    wordCount = len(words)

    allValidWords = set()

    for _, _, wordList, _, _ in SEED_TYPE_STANDARDS:
        allValidWords.update(wordList)

    invalidWords = []
    seen = set()

    for w in words:
        if w not in allValidWords and w not in seen:
            invalidWords.append(w)
            seen.add(w)

    candidateStandards = [s for s in SEED_TYPE_STANDARDS if wordCount in s[1]]

    if invalidWords:
        invalidWords.sort()
        raise InvalidSeedWordsError(invalidWords, prefix="" if candidateStandards else "Invalid word count")

    if not candidateStandards:
        raise ValueError("Invalid word count.")

    for name, _, wordList, maxIdx, validator in candidateStandards:
        wordIndices = []
        allValid = True

        for w in words:
            idx = binarySearchWord(wordList, w)

            if idx == -1:
                allValid = False
                break

            wordIndices.append(idx)

        if allValid and validator(mnemonicStr):
            return wordIndices, name, wordCount, maxIdx

    raise ValueError("Mnemonic checksum failed. Unrecognized or invalid seed phrase.")



######## PNG GENERATOR ########

def encodeMnemonic(
    mnemonicRaw,
    imgPath,
    cellPx=100,
    salt="",
    cancelCheck=None,
    progressCallback=None
):
    indices, _, wordCount, maxIdx = identifySeedType(mnemonicRaw)
    cols, rows = GRID_SIZES[wordCount]
    colorTables, proofKey, rngSeed = saltKeys(salt)

    if salt and progressCallback:
        progressCallback(0.01)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Canceled")

    allCoords = cellOrder(cols, rows, rngSeed)
    proof = computeProof(proofKey, indices)
    freeSize = computeFreeSize(maxIdx)
    rng = secrets.SystemRandom()
    wordOffsets = [composeOffset(proof[i], rng.randrange(freeSize), maxIdx) for i in range(wordCount)]

    img = Image.new("RGB", (cols, rows))
    px = img.load()

    if px is None:
        raise ValueError("Failed to initialize image pixel access.")

    for i in range(wordCount):
        if cancelCheck and cancelCheck():
            raise InterruptedError("Canceled")

        color = encodeWord(
            indices[i],
            maxIndex=maxIdx,
            offset=wordOffsets[i],
            colorTables=colorTables
        )

        r, c = allCoords[i]
        px[c, r] = color

        if progressCallback:
            progressCallback((i + 1) / wordCount * 0.9)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Canceled")

    resizedImg = img.resize((cols * cellPx, rows * cellPx), Image.Resampling.NEAREST)
    resizedImg.save(imgPath, format="PNG", optimize=False, compress_level=1)

    if progressCallback:
        progressCallback(1.0)


def bulkEncodeMnemonic(mnemonicRaw, zipPath, count, cellPx=100, salt="", cancelCheck=None, progressCallback=None):
    indices, _, wordCount, maxIdx = identifySeedType(mnemonicRaw)
    cols, rows = GRID_SIZES[wordCount]
    colorTables, proofKey, rngSeed = saltKeys(salt)

    if salt and progressCallback:
        progressCallback(1 / (count + 1))

    allCoords = cellOrder(cols, rows, rngSeed)
    proof = computeProof(proofKey, indices)
    freeSize = computeFreeSize(maxIdx)
    rng = secrets.SystemRandom()
    wordOffsets = []

    for wIdx in range(wordCount):
        if count <= freeSize:
            free = rng.sample(range(freeSize), count)

        else:
            free = [rng.randrange(freeSize) for _ in range(count)]

        wordOffsets.append([composeOffset(proof[wIdx], f, maxIdx) for f in free])

    tinyImages = []

    for i in range(count):
        if cancelCheck and cancelCheck():
            raise InterruptedError("Canceled")

        img = Image.new("RGB", (cols, rows))

        px = img.load()

        if px is None:
            raise ValueError("Failed to initialize image pixel access.")

        for wIdx in range(wordCount):
            offset = wordOffsets[wIdx][i]

            color = encodeWord(
                indices[wIdx],
                maxIndex=maxIdx,
                offset=offset,
                colorTables=colorTables
            )

            r, c = allCoords[wIdx]
            px[c, r] = color

        tinyImages.append(img)

    with zipfile.ZipFile(zipPath, "w", compression=zipfile.ZIP_STORED) as zipf:
        for i, img in enumerate(tinyImages):
            if cancelCheck and cancelCheck():
                raise InterruptedError("Canceled")

            resizedImg = img.resize((cols * cellPx, rows * cellPx), Image.Resampling.NEAREST)
            imgByteArr = io.BytesIO()
            resizedImg.save(imgByteArr, format="PNG", optimize=False, compress_level=1)
            imgByteArr.seek(0)
            zipf.writestr(f"{i + 1}.png", imgByteArr.getvalue())
            imgByteArr.close()

            if progressCallback:
                if salt:
                    progressCallback((i + 2) / (count + 1))

                else:
                    progressCallback((i + 1) / count)



######## INTERACTIVE COLOR SPACE ########

@dataclass
class ColorSpace:
    cols: int
    rows: int
    maxIdx: int
    freeSize: int
    indices: list
    proof: list
    colorTables: list | None
    cellToWord: dict = field(default_factory=dict)
    colorRGB: dict = field(default_factory=dict)
    hueRanges: dict = field(default_factory=dict)


def precomputeColorSpace(mnemonicRaw, salt):
    indices, _, wordCount, maxIdx = identifySeedType(mnemonicRaw)
    cols, rows = GRID_SIZES[wordCount]
    colorTables, proofKey, rngSeed = saltKeys(salt)
    allCoords = cellOrder(cols, rows, rngSeed)
    cs = ColorSpace(cols, rows, maxIdx, computeFreeSize(maxIdx), indices, computeProof(proofKey, indices), colorTables)

    rng = secrets.SystemRandom()

    for i in range(wordCount):
        r, c = allCoords[i]
        cs.cellToWord[(r, c)] = i

        forbidden = set()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (nr, nc) in cs.colorRGB:
                forbidden.add(cs.colorRGB[(nr, nc)])

        offset = composeOffset(cs.proof[i], rng.randrange(cs.freeSize), maxIdx)
        color = encodeWord(indices[i], maxIndex=maxIdx, offset=offset, colorTables=colorTables)
        tries = 0

        while color in forbidden and tries < 256:
            offset = composeOffset(cs.proof[i], rng.randrange(cs.freeSize), maxIdx)
            color = encodeWord(indices[i], maxIndex=maxIdx, offset=offset, colorTables=colorTables)
            tries += 1

        cs.colorRGB[(r, c)] = color

    return cs


def colorHue(color) -> int | None:
    """Hue in whole degrees, or None for a gray, which has no hue."""
    r, g, b = color
    hue, saturation, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if saturation == 0:
        return None

    return round(hue * 360) % 360


def inHueRange(color, start: int, span: int) -> bool:
    """Whether a color's hue lies on the arc running upward from start for span degrees, both ends included. A gray
    has no hue, so it fits every arc."""
    hue = colorHue(color)
    return hue is None or (hue - start) % 360 <= span


def _hueCandidates(cs, r, c, start: int, span: int) -> list:
    """Every color of the cell's word inside the hue arc that differs from its orthogonal neighbors."""
    i = cs.cellToWord[(r, c)]
    neighbors = {
        cs.colorRGB[(nr, nc)]
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
        if (nr, nc) in cs.colorRGB
    }
    candidates = []
    for free in range(cs.freeSize):
        offset = composeOffset(cs.proof[i], free, cs.maxIdx)
        color = encodeWord(cs.indices[i], maxIndex=cs.maxIdx, offset=offset, colorTables=cs.colorTables)
        if color not in neighbors and inHueRange(color, start, span):
            candidates.append(color)

    return candidates


def _pickInHueRange(cs, r, c, start: int, span: int):
    """A random hue candidate of the cell, differing from its current color when another choice exists. None when
    the word has no color in the arc."""
    candidates = _hueCandidates(cs, r, c, start, span)
    if not candidates:
        return None

    fresh = [color for color in candidates if color != cs.colorRGB[(r, c)]]
    return secrets.choice(fresh or candidates)


def setHueRange(cs, r, c, start: int, span: int) -> bool:
    """Keep a hue arc for a cell's later rerolls without recoloring it. Changes nothing and returns False when the
    cell's word has no color in the arc."""
    if (r, c) not in cs.cellToWord or not _hueCandidates(cs, r, c, start, span):
        return False

    cs.hueRanges[(r, c)] = (start, span)
    return True


def applyHueRange(cs, r, c, start: int, span: int) -> bool:
    """Recolor a cell inside a hue arc and keep the arc for its later rerolls. Changes nothing and returns False
    when the cell's word has no color in the arc."""
    if (r, c) not in cs.cellToWord:
        return False

    color = _pickInHueRange(cs, r, c, start, span)
    if color is None:
        return False

    cs.hueRanges[(r, c)] = (start, span)
    cs.colorRGB[(r, c)] = color
    return True


def rerollCell(cs, r, c):
    if (r, c) not in cs.cellToWord:
        return False

    if (r, c) in cs.hueRanges:
        color = _pickInHueRange(cs, r, c, *cs.hueRanges[(r, c)])
        if color is None:
            return False

        cs.colorRGB[(r, c)] = color
        return True

    i = cs.cellToWord[(r, c)]

    forbidden = {cs.colorRGB[(r, c)]}
    for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
        if (nr, nc) in cs.colorRGB:
            forbidden.add(cs.colorRGB[(nr, nc)])

    free = secrets.SystemRandom().randrange(cs.freeSize)
    offset = composeOffset(cs.proof[i], free, cs.maxIdx)
    color = encodeWord(cs.indices[i], maxIndex=cs.maxIdx, offset=offset, colorTables=cs.colorTables)

    while color in forbidden:
        free = (free + 1) % cs.freeSize
        offset = composeOffset(cs.proof[i], free, cs.maxIdx)
        color = encodeWord(cs.indices[i], maxIndex=cs.maxIdx, offset=offset, colorTables=cs.colorTables)

    cs.colorRGB[(r, c)] = color
    return True


def cellPalettes(mnemonicRaw, salt, cells=None):
    """Every color each cell can take for this phrase and salt, sorted ascending, keyed by (row, col) in reading
    order, for the given cells or all of them. A cell's palette is its word's block with the proof fixed and the
    free bits left open."""
    cs = precomputeColorSpace(mnemonicRaw, salt)
    palettes = {}

    for (r, c), i in sorted(cs.cellToWord.items()):
        if cells is not None and (r, c) not in cells:
            continue

        palettes[(r, c)] = sorted({
            encodeWord(
                cs.indices[i],
                maxIndex=cs.maxIdx,
                offset=composeOffset(cs.proof[i], free, cs.maxIdx),
                colorTables=cs.colorTables
            )
            for free in range(cs.freeSize)
        })

    return palettes


def renderColorSpaceToFile(cs, imgPath, cellPx=100, cancelCheck=None, progressCallback=None):
    img = Image.new("RGB", (cs.cols, cs.rows))
    px = img.load()

    if px is None:
        raise ValueError("Failed to initialize image pixel access.")

    for (r, c), color in cs.colorRGB.items():
        if cancelCheck and cancelCheck():
            raise InterruptedError("Canceled")

        px[c, r] = color

    if progressCallback:
        progressCallback(0.5)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Canceled")

    resizedImg = img.resize((cs.cols * cellPx, cs.rows * cellPx), Image.Resampling.NEAREST)
    resizedImg.save(imgPath, format="PNG", optimize=False, compress_level=1)

    if progressCallback:
        progressCallback(1.0)