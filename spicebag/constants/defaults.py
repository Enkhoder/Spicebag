######## LIBRARIES ########

from shamir_mnemonic.wordlist import WORDLIST as SLIP39_LIST
from shamir_mnemonic import Share
from mnemonic import Mnemonic



######## WORDLIST INITIALIZATION ########

BIP39 = Mnemonic("english")

BIP39_LIST = BIP39.wordlist

ELECTRUM_LIST = BIP39_LIST



######## CONSTANTS ########

FORBIDDEN_CHUNKS = {
    b'PLTE',
    b'tRNS',
    b'bKGD',
    b'sBIT',
    b'iCCP',
}

FEISTEL_ROUNDS = 10



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