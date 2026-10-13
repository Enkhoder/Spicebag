######## LIBRARIES ########

from spicebag.backend.defaults import FEISTEL_ROUNDS, PROOF_BITS, UNSALTED_PROOF_KEY
from argon2.low_level import hash_secret_raw, Type
import unicodedata
import hashlib
import random
import hmac



######## SEED ENCODER ########

def normalizeSalt(salt: str) -> str:
    """NFC form, so a salt typed or pasted with composed or decomposed accents is the same salt everywhere."""
    return unicodedata.normalize("NFC", salt)


def deriveMasterKey(salt: str) -> bytes:
    saltBytes = normalizeSalt(salt).encode("utf-8")

    return hash_secret_raw(
        secret=saltBytes,
        salt=b"SpicebagDomain",
        time_cost=4,
        memory_cost=2**18,
        parallelism=1,
        hash_len=64,
        type=Type.ID
    )


def hkdfExpand(key: bytes, info: bytes, length: int = 128) -> bytes:
    prk = hmac.new(b"\x00" * 64, key, hashlib.sha512).digest()

    t = b""
    okm = b""
    counter = 1

    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha512).digest()
        okm += t
        counter += 1

    return okm[:length]


def deriveSubkeys(masterKey: bytes):
    """Expand the Argon2id master key into the three salt-derived secrets the encoding needs: the
    color permutation, the cell shuffle and the proof of phrase. The free half of each block offset
    is deliberately absent: it is the encoding's only free variable and must come from
    secrets.SystemRandom(), never from the salt."""
    colorTables = deriveColorTables(hkdfExpand(masterKey, b"colorDomain"))
    permKey = hkdfExpand(masterKey, b"permDomain")
    proofKey = hkdfExpand(masterKey, b"proofDomain", 32)

    return colorTables, permKey, proofKey


def deriveColorTables(colorKey: bytes) -> list[list[int]]:
    """Precompute every Feistel round function output, one 4096-entry table per round, so a color
    permutation costs table lookups instead of one HMAC per round."""
    return [
        [
            int.from_bytes(hmac.digest(colorKey, bytes([roundIndex]) + half.to_bytes(2, "big"), "sha256")[:2], "big")
            & 0xFFF
            for half in range(4096)
        ]
        for roundIndex in range(FEISTEL_ROUNDS)
    ]


def permuteColor(value: int, colorTables: list[list[int]]) -> int:
    """Keyed bijection over all 2^24 colors: a balanced Feistel network on two 12-bit halves."""
    left, right = value >> 12, value & 0xFFF
    for table in colorTables:
        left, right = right, left ^ table[right]

    return (left << 12) | right


def unpermuteColor(value: int, colorTables: list[list[int]]) -> int:
    left, right = value >> 12, value & 0xFFF
    for table in reversed(colorTables):
        left, right = right ^ table[left], left

    return (left << 12) | right



######## COLOR ENCODER / DECODER ########

def computeBlockSize(maxIndex: int) -> int:
    indexBits = maxIndex.bit_length() - 1
    blockBits = 24 - indexBits

    return 1 << blockBits


def encodeWord(
    wordIndex: int,
    offset: int,
    maxIndex: int = 2048,
    colorTables: list[list[int]] | None = None
) -> tuple[int, int, int]:
    value = wordIndex * computeBlockSize(maxIndex) + offset

    if colorTables is not None:
        value = permuteColor(value, colorTables)

    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF

    return (r, g, b)


def decodeCell(
    rgb: tuple[int, int, int],
    maxIndex: int = 2048,
    colorTables: list[list[int]] | None = None
) -> tuple[int, int]:
    """Recover a cell's word index and the proof chunk carried in the top bits of its offset."""
    r, g, b = rgb

    value = (r << 16) | (g << 8) | b

    if colorTables is not None:
        value = unpermuteColor(value, colorTables)

    blockSize = computeBlockSize(maxIndex)
    wordIndex, offset = divmod(value, blockSize)

    return wordIndex, offset // computeFreeSize(maxIndex)



######## PROOF OF PHRASE ########

def computeFreeSize(maxIndex: int) -> int:
    """Colors left to chance within a word's block once PROOF_BITS of its offset carry the proof."""
    return computeBlockSize(maxIndex) >> PROOF_BITS


def computeProof(proofKey: bytes, wordIndices: list[int]) -> list[int]:
    """One PROOF_BITS chunk per word, cut in order from HMAC-SHA256 over the whole phrase. The proof
    depends only on the phrase and the key, so every image of a phrase and salt carries the same
    chunks, and rerolling a cell's free bits never touches another cell."""
    digest = hmac.digest(proofKey, b"".join(index.to_bytes(2, "big") for index in wordIndices), "sha256")
    bits = int.from_bytes(digest, "big")
    mask = (1 << PROOF_BITS) - 1

    return [(bits >> (256 - PROOF_BITS * (i + 1))) & mask for i in range(len(wordIndices))]


def composeOffset(proofChunk: int, free: int, maxIndex: int) -> int:
    return proofChunk * computeFreeSize(maxIndex) + free



######## SALT SETUP ########

def saltKeys(salt: str) -> tuple[list[list[int]] | None, bytes, int | None]:
    """The color tables, proof key and cell-shuffle seed a salt derives. Without a salt the colors are not
    permuted, the cells stay in reading order, and the proof is keyed by the public UNSALTED_PROOF_KEY."""
    if not salt:
        return None, UNSALTED_PROOF_KEY, None

    colorTables, permKey, proofKey = deriveSubkeys(deriveMasterKey(salt))
    return colorTables, proofKey, int.from_bytes(permKey[:8], "big")


def cellOrder(cols: int, rows: int, rngSeed: int | None) -> list[tuple[int, int]]:
    """Grid cells in word order: reading order, shuffled by the salt's seed when there is one. Encoder and
    decoder both take their layout from here, so it is the seeded RNG's only consumer."""
    coords = [(r, c) for r in range(rows) for c in range(cols)]
    if rngSeed is not None:
        random.Random(rngSeed).shuffle(coords)

    return coords