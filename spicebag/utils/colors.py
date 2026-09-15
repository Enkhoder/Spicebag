######## LIBRARIES ########

from spicebag.constants.defaults import FEISTEL_ROUNDS
from argon2.low_level import hash_secret_raw, Type
import hashlib
import secrets
import hmac



######## SEED ENCODER ########

def deriveMasterKey(salt: str) -> bytes:
    if not salt:
        return b"\x00" * 32

    saltBytes = salt.encode("utf-8")

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
    """Expand the Argon2id master key into the two salt-derived secrets the encoding needs.
    Block offsets are deliberately absent: they are the encoding's only free variable and must
    come from secrets.SystemRandom(), never from the salt."""
    colorTables = deriveColorTables(hkdfExpand(masterKey, b"colorDomain"))
    permKey = hkdfExpand(masterKey, b"permDomain")

    return colorTables, permKey


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
    maxIndex: int = 2048,
    offset: int = -1,
    colorTables: list[list[int]] | None = None
) -> tuple[int, int, int]:
    blockSize = computeBlockSize(maxIndex)

    if offset < 0:
        offset = secrets.randbelow(blockSize)

    value = wordIndex * blockSize + offset

    if colorTables is not None:
        value = permuteColor(value, colorTables)

    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF

    return (r, g, b)


def decodeColor(rgb: tuple[int, int, int], maxIndex: int = 2048, colorTables: list[list[int]] | None = None) -> int:
    r, g, b = rgb

    value = (r << 16) | (g << 8) | b

    if colorTables is not None:
        value = unpermuteColor(value, colorTables)

    wordIndex = value // computeBlockSize(maxIndex)

    if wordIndex >= maxIndex:
        raise ValueError("Decoded color value is out of range for the current seed standard.")

    return wordIndex