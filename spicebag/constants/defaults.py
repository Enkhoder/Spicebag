######## LIBRARIES ########

from shamir_mnemonic.wordlist import WORDLIST as SLIP39_LIST
from shamir_mnemonic import Share
from mnemonic import Mnemonic
from pathlib import Path



######## WORDLIST INITIALIZATION ########

BIP39 = Mnemonic("english")

BIP39_LIST = BIP39.wordlist


def loadElectrumWords():
    cachePath = Path(__file__).parent / "electrum-english.txt"

    with open(cachePath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


ELECTRUM_LIST = loadElectrumWords()



######## CONSTANTS ########

FORBIDDEN_CHUNKS = {
    b'PLTE',
    b'tRNS',
    b'bKGD',
    b'sBIT',
    b'iCCP',
}

PERMUTATIONS = [
    (0, 1, 2),
    (1, 2, 0),
    (2, 0, 1),
    (1, 0, 2),
    (2, 1, 0),
    (0, 2, 1),
]

RGB_VALUE_SHIFTS = [
    (2, -7, 1), (-8, 2, -8), (1, -8, 2),
    (-8, 4, -5), (9, 0, 4), (-5, 2, -3),
    (5, -3, 6), (0, 2, -8), (7, -4, 7),
    (-1, 3, -5), (2, -6, 6), (-2, 4, -9),
    (7, -7, 5), (-7, 2, -4), (7, 0, 9),
    (-3, 6, -9), (9, -9, 5), (-9, 5, -7),
    (4, -9, 6), (-6, 9, -6), (7, -6, 2),
    (-7, 7, -2), (4, 0, 7), (-6, 6, -3),
    (0, -3, 5), (-3, 5, -4), (7, -5, 9),
    (-4, 5, -7), (1, -3, 8), (-2, 1, -7),
    (8, -5, 2), (-5, 1, -6), (6, -4, 2)
]



######## SEED TYPE STANDARDS ########

def validateBIP39(mnemonicStr: str) -> bool:
    return BIP39.check(mnemonicStr)


def validateElectrum(mnemonic: str) -> bool:
    import hmac
    import hashlib

    try:
        h = hmac.new(b"Seed version", mnemonic.encode('utf-8'), hashlib.sha512).hexdigest()

        return h.startswith(('01', '100', '101'))

    except Exception:
        return False


def validateSLIP39(mnemonic: str) -> bool:
    try:
        Share.from_mnemonic(mnemonic)

        return True

    except Exception:
        return False


SEED_TYPE_STANDARDS = [
    ("BIP39", (12, 15, 18, 21, 24), BIP39_LIST, 2048, validateBIP39),
    ("Electrum", (12, 24), ELECTRUM_LIST, 2048, validateElectrum),
    ("SLIP39", (20, 33), SLIP39_LIST, 1024, validateSLIP39)
]

WORD_COUNT_MAX_INDEX = {
    wordCount: maxIdx
    for _, wordCounts, _, maxIdx, _ in SEED_TYPE_STANDARDS
    for wordCount in wordCounts
}