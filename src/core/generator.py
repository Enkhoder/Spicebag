from src.utils.colors import deriveMasterKey, deriveSubkeys, deriveMask, encodeWord, computeBlockSize
from src.constants.defaults import (
    SEED_TYPE_STANDARDS,
    RGB_VALUE_SHIFTS
)
from dataclasses import dataclass, field
from PIL import Image
import secrets
import zipfile
import bisect
import random
import io



######## MNEMONIC IDENTIFIER ########

class InvalidSeedWordsError(ValueError):
    """Raised when a phrase contains words present in no wordlist. Carries the
    sorted offending words so the UI can mask them individually."""

    def __init__(self, words: list[str], prefix: str = "") -> None:
        self.words = list(words)
        self.prefix = prefix
        plural = "words" if len(self.words) > 1 else "word"
        blocks = " ".join("█" * len(w) for w in self.words)

        if prefix:
            message = f"{prefix}, invalid seed {plural} '{blocks}'."
        else:
            message = f"Invalid seed {plural} '{blocks}'."

        super().__init__(message)


def binarySearchWord(wordList: list[str], word: str) -> int:
    idx = bisect.bisect_left(wordList, word)

    if idx < len(wordList) and wordList[idx] == word:
        return idx

    return -1


def identifySeedType(rawInput: str, expectedLength: int | None = None):
    words = rawInput.lower().split()
    mnemonicStr = " ".join(words)
    numWords = len(words)

    allValidWords = set()

    for _, _, wordList, _, _ in SEED_TYPE_STANDARDS:
        allValidWords.update(wordList)

    invalidWords = []
    seen = set()

    for w in words:
        if w not in allValidWords and w not in seen:
            invalidWords.append(w)
            seen.add(w)

    missingMsg = ""

    if expectedLength is not None and numWords < expectedLength:
        n = expectedLength - numWords
        suffix = "words" if n > 1 else "word"
        missingMsg = f"Missing {n} {suffix}"

    if invalidWords:
        invalidWords.sort()

    if missingMsg and invalidWords:
        raise InvalidSeedWordsError(invalidWords, prefix=missingMsg)

    elif missingMsg:
        raise ValueError(f"{missingMsg}.")

    elif invalidWords:
        raise InvalidSeedWordsError(invalidWords)

    candidateStandards = [s for s in SEED_TYPE_STANDARDS if numWords in s[1]]

    if not candidateStandards:
        raise ValueError(f"Excessive word count: {numWords} words.")

    for name, _, wordList, maxIdx, validator in candidateStandards:
        wordIndices = []
        allValid = True

        for w in words:
            idx = binarySearchWord(wordList, w)

            if idx == -1:
                allValid = False
                break

            wordIndices.append(idx)

        if allValid:
            if name == "SLIP39":
                from shamir_mnemonic import Share

                try:
                    Share.from_mnemonic(mnemonicStr)
                    return wordIndices, name, numWords, maxIdx

                except Exception:
                    pass

            elif validator(mnemonicStr):
                return wordIndices, name, numWords, maxIdx

    raise ValueError("Mnemonic checksum failed. Unrecognized or invalid seed phrase.")



######## PNG GENERATOR ########

def encodeMnemonic(mnemonicRaw, imgPath, cellPx=100, salt="", precomputed=None, precomputedMnemonic=None, cancelCheck=None, progressCallback=None):
    if precomputedMnemonic is not None:
        indices, standard, numWords, maxIdx = precomputedMnemonic
    else:
        indices, standard, numWords, maxIdx = identifySeedType(mnemonicRaw)

    if standard == "SLIP39":
        if numWords == 20:
            cols, rows = (4, 5)

        else:
            cols, rows = (3, 11)

    else:
        mapping = {
            12: (3, 4),
            15: (3, 5),
            18: (3, 6),
            21: (3, 7),
            24: (4, 6)
        }
        cols, rows = mapping[numWords]

    if precomputed is not None:
        maskKey, rngSeed = precomputed

    elif salt:
        masterKey = deriveMasterKey(salt)
        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")
        if progressCallback:
            progressCallback(0.01)

    else:
        maskKey = None
        rngSeed = None

    if cancelCheck and cancelCheck():
        raise InterruptedError("Cancelled")

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]

    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    blockSize = computeBlockSize(maxIdx)
    rng = random.Random(rngSeed) if rngSeed is not None else secrets.SystemRandom()
    wordOffsets = [rng.randrange(blockSize) for _ in range(numWords)]

    img = Image.new("RGB", (cols, rows))
    px = img.load()

    if px is None:
        raise ValueError("Failed to initialize image pixel access.")

    for i in range(numWords):
        if cancelCheck and cancelCheck():
            raise InterruptedError("Cancelled")

        wordMask = deriveMask(maskKey, i, maxIdx) if maskKey is not None else 0
        currentShift = RGB_VALUE_SHIFTS[i]

        color = encodeWord(
            indices[i],
            mask=wordMask,
            shift=currentShift,
            maxIndex=maxIdx,
            offset=wordOffsets[i]
        )

        r, c = allCoords[i]
        px[c, r] = color

        if progressCallback:
            progressCallback((i + 1) / numWords * 0.9)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Cancelled")

    resizedImg = img.resize((cols * cellPx, rows * cellPx), Image.Resampling.NEAREST)
    resizedImg.save(imgPath, format="PNG", optimize=False, compress_level=1)

    if progressCallback:
        progressCallback(1.0)


def bulkEncodeMnemonic(mnemonicRaw, zipPath, count, cellPx=100, salt="", cancelCheck=None, progressCallback=None):
    indices, standard, numWords, maxIdx = identifySeedType(mnemonicRaw)

    if standard == "SLIP39":
        if numWords == 20:
            cols, rows = (4, 5)

        else:
            cols, rows = (3, 11)

    else:
        mapping = {
            12: (3, 4),
            15: (3, 5),
            18: (3, 6),
            21: (3, 7),
            24: (4, 6)
        }
        cols, rows = mapping[numWords]

    if salt:
        masterKey = deriveMasterKey(salt)
        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")
        rng = random.Random(rngSeed)

        if progressCallback:
            progressCallback(1 / (count + 1))

    else:
        maskKey = None
        rngSeed = None
        rng = secrets.SystemRandom()

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]

    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    blockSize = computeBlockSize(maxIdx)
    wordOffsets = []

    for _ in range(numWords):
        if count <= blockSize:
            wordOffsets.append(rng.sample(range(blockSize), count))

        else:
            wordOffsets.append([rng.randrange(blockSize) for _ in range(count)])

    tinyImages = []

    for i in range(count):
        if cancelCheck and cancelCheck():
            raise InterruptedError("Cancelled")

        img = Image.new("RGB", (cols, rows))
        px = img.load()

        if px is None:
            raise ValueError("Failed to initialize image pixel access.")

        for wIdx in range(numWords):
            wordMask = deriveMask(maskKey, wIdx, maxIdx) if maskKey is not None else 0
            currentShift = RGB_VALUE_SHIFTS[wIdx]
            offset = wordOffsets[wIdx][i]

            color = encodeWord(
                indices[wIdx],
                mask=wordMask,
                shift=currentShift,
                maxIndex=maxIdx,
                offset=offset
            )

            r, c = allCoords[wIdx]
            px[c, r] = color

        tinyImages.append(img)

    with zipfile.ZipFile(zipPath, "w", compression=zipfile.ZIP_STORED) as zipf:
        for i, img in enumerate(tinyImages):
            if cancelCheck and cancelCheck():
                raise InterruptedError("Cancelled")

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
    numWords: int
    maxIdx: int
    blockSize: int
    indices: list
    masks: list
    shifts: list
    cellToWord: dict = field(default_factory=dict)
    offsets: dict = field(default_factory=dict)
    colorRGB: dict = field(default_factory=dict)


def gridDimensions(standard, numWords):
    if standard == "SLIP39":
        return (4, 5) if numWords == 20 else (3, 11)

    mapping = {
        12: (3, 4),
        15: (3, 5),
        18: (3, 6),
        21: (3, 7),
        24: (4, 6)
    }

    return mapping[numWords]


def precomputeColorSpace(mnemonicRaw, salt, cancelCheck=None, progressCallback=None):
    indices, standard, numWords, maxIdx = identifySeedType(mnemonicRaw)
    cols, rows = gridDimensions(standard, numWords)

    if salt:
        masterKey = deriveMasterKey(salt)
        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")

        if progressCallback:
            progressCallback(0.5)

    else:
        maskKey = None
        rngSeed = None

    if cancelCheck and cancelCheck():
        raise InterruptedError("Cancelled")

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]

    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    blockSize = computeBlockSize(maxIdx)
    masks = [deriveMask(maskKey, i, maxIdx) if maskKey is not None else 0 for i in range(numWords)]
    shifts = [RGB_VALUE_SHIFTS[i] for i in range(numWords)]

    cs = ColorSpace(cols, rows, numWords, maxIdx, blockSize, indices, masks, shifts)

    rng = secrets.SystemRandom()

    for i in range(numWords):
        r, c = allCoords[i]
        cs.cellToWord[(r, c)] = i

        forbidden = set()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (nr, nc) in cs.colorRGB:
                forbidden.add(cs.colorRGB[(nr, nc)])

        offset = rng.randrange(blockSize)
        color = encodeWord(indices[i], mask=masks[i], shift=shifts[i], maxIndex=maxIdx, offset=offset)
        tries = 0

        while color in forbidden and tries < 256:
            offset = rng.randrange(blockSize)
            color = encodeWord(indices[i], mask=masks[i], shift=shifts[i], maxIndex=maxIdx, offset=offset)
            tries += 1

        cs.offsets[(r, c)] = offset
        cs.colorRGB[(r, c)] = color

    if progressCallback:
        progressCallback(1.0)

    return cs


def rerollCell(cs, r, c):
    if (r, c) not in cs.cellToWord:
        return False

    i = cs.cellToWord[(r, c)]

    forbidden = {cs.colorRGB[(r, c)]}
    for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
        if (nr, nc) in cs.colorRGB:
            forbidden.add(cs.colorRGB[(nr, nc)])

    offset = secrets.SystemRandom().randrange(cs.blockSize)
    color = encodeWord(cs.indices[i], mask=cs.masks[i], shift=cs.shifts[i], maxIndex=cs.maxIdx, offset=offset)

    while color in forbidden:
        offset = (offset + 1) % cs.blockSize
        color = encodeWord(cs.indices[i], mask=cs.masks[i], shift=cs.shifts[i], maxIndex=cs.maxIdx, offset=offset)

    cs.offsets[(r, c)] = offset
    cs.colorRGB[(r, c)] = color
    return True


def renderColorSpaceToFile(cs, imgPath, cellPx=100, cancelCheck=None, progressCallback=None):
    img = Image.new("RGB", (cs.cols, cs.rows))
    px = img.load()

    if px is None:
        raise ValueError("Failed to initialize image pixel access.")

    for (r, c), color in cs.colorRGB.items():
        if cancelCheck and cancelCheck():
            raise InterruptedError("Cancelled")

        px[c, r] = color

    if progressCallback:
        progressCallback(0.5)

    if cancelCheck and cancelCheck():
        raise InterruptedError("Cancelled")

    resizedImg = img.resize((cs.cols * cellPx, cs.rows * cellPx), Image.Resampling.NEAREST)
    resizedImg.save(imgPath, format="PNG", optimize=False, compress_level=1)

    if progressCallback:
        progressCallback(1.0)