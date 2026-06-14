######## LIBRARIES ########

from argon2.low_level import hash_secret_raw, Type
from src.constants.defaults import PERMUTATIONS
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
    maskKey = hkdfExpand(masterKey, b"maskDomain")
    permKey = hkdfExpand(masterKey, b"permDomain")
    offsetKey = hkdfExpand(masterKey, b"offsetDomain")

    return maskKey, permKey, offsetKey


def deriveMask(maskKey: bytes, index: int, maxIndex: int) -> int:
    msg = index.to_bytes(4, "big")
    digest = hmac.new(maskKey, msg, hashlib.sha512).digest()

    return int.from_bytes(digest[:4], "big") % maxIndex


######## COLOR ENCODER / DECODER ########

def computeBlockSize(maxIndex: int) -> int:
    indexBits = maxIndex.bit_length() - 1
    blockBits = 24 - indexBits

    return 1 << blockBits


def encodeWord(wordIndex: int, mask: int = 0, shift: tuple[int, int, int] = (0, 0, 0), maxIndex: int = 2048, offset: int = -1) -> tuple[int, int, int]:
    maskedIndex = wordIndex ^ (mask % maxIndex)

    blockSize = computeBlockSize(maxIndex)

    if offset < 0:
        offset = secrets.randbelow(blockSize)

    base = maskedIndex * blockSize + offset

    r = (base >> 16) & 0xFF
    g = (base >> 8) & 0xFF
    b = base & 0xFF

    r = (r + shift[0]) % 256
    g = (g + shift[1]) % 256
    b = (b + shift[2]) % 256

    permIndex = (r + g + b) % 6
    perm = PERMUTATIONS[permIndex]

    rgb = [r, g, b]

    return (rgb[perm[0]], rgb[perm[1]], rgb[perm[2]])


def decodeColor(rgb: tuple[int, int, int], mask: int = 0, shift: tuple[int, int, int] = (0, 0, 0), maxIndex: int = 2048) -> int:
    r, g, b = rgb

    permIndex = (r + g + b) % 6
    perm = PERMUTATIONS[permIndex]

    canonical = [0, 0, 0]

    for i, p in enumerate(perm):
        canonical[p] = rgb[i]

    canR, canG, canB = canonical

    canR = (canR - shift[0]) % 256
    canG = (canG - shift[1]) % 256
    canB = (canB - shift[2]) % 256

    key = (canR << 16) | (canG << 8) | canB
    blockSize = computeBlockSize(maxIndex)

    maskedIndex = key // blockSize
    wordIndex = maskedIndex ^ (mask % maxIndex)

    if wordIndex >= maxIndex:
        raise ValueError("Decoded color value is out of range for the current seed standard.")

    return wordIndex