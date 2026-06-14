from flask import Flask, request, jsonify, send_file, render_template
from shamir_mnemonic.wordlist import WORDLIST as SLIP39_LIST
from argon2.low_level import hash_secret_raw, Type
from shamir_mnemonic import Share
from mnemonic import Mnemonic
from pathlib import Path
from PIL import Image
import requests
import textwrap
import hashlib
import secrets
import zipfile
import random
import struct
import hmac
import io
import os

app = Flask(__name__)

######## HELPERS AND CONSTANTS ########

def loadElectrumWords():
    cachePath = "electrum-english.txt"
    if not os.path.exists(cachePath):
        url = "https://raw.githubusercontent.com/spesmilo/electrum/master/electrum/wordlist/english.txt"
        response = requests.get(url)
        with open(cachePath, "w", encoding = "utf-8") as f:
            f.write(response.text)
    with open(cachePath, "r", encoding = "utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

ALLOWED_CHUNKS = {b'IHDR', b'IDAT', b'IEND', b'tIME', b'tEXt', b'iTXt', b'zTXt', b'sRGB', b'gAMA', b'pHYs'}
BIP39 = Mnemonic("english")
BIP39_LIST = BIP39.wordlist
ELECTRUM_LIST = loadElectrumWords()
FORBIDDEN_CHUNKS = {b'PLTE', b'tRNS', b'bKGD', b'sBIT', b'iCCP'}

PERMUTATIONS = [
    (0, 1, 2),  # RGB
    (1, 2, 0),  # GBR
    (2, 0, 1),  # BRG
    (1, 0, 2),  # GRB
    (2, 1, 0),  # BGR
    (0, 2, 1),  # RBG
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

def validateElectrum(mnemonic: str) -> bool:
    try:
        h = hmac.new(b"Seed version", mnemonic.encode('utf-8'), hashlib.sha512).hexdigest()
        return h.startswith(('01', '100', '101'))
    except:
        return False

SEED_TYPE_STANDARDS = [
    ("BIP39", (12, 15, 18, 21, 24), BIP39_LIST, 2048, lambda s: BIP39.check(s)),
    ("ELECTRUM", (12, 24), ELECTRUM_LIST, 2048, lambda s: validateElectrum(s)),
    ("SLIP39", (20, 33), SLIP39_LIST, 1024, lambda s: all(w in SLIP39_LIST for w in s.split()))
]

######## Core Logic ########

def isAcceptablePNG(data: bytes):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i+4])[0]
        chunk = data[i+4:i+8]
        if chunk in FORBIDDEN_CHUNKS:
            return False
        i += 12 + length
    return True

def computeBlockSize(maxIndex: int) -> int:
    indexBits = maxIndex.bit_length() - 1
    blockBits = 24 - indexBits
    return 1 << blockBits

def encodeWord(wordIndex, mask=0, shift=(0, 0, 0), offset=0, maxIndex=2048):
    maskedIndex = wordIndex ^ (mask % maxIndex)
    blockSize = computeBlockSize(maxIndex)
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
    return tuple(rgb[p] for p in perm)

def decodeColor(rgb, mask=0, shift=(0, 0, 0), maxIndex=2048):
    r, g, b = rgb
    permIndex = (r + g + b) % 6
    perm = PERMUTATIONS[permIndex]

    canonical = [0, 0, 0]
    for i, p in enumerate(perm):
        canonical[p] = rgb[i]

    R, G, B = canonical
    R = (R - shift[0]) % 256
    G = (G - shift[1]) % 256
    B = (B - shift[2]) % 256

    key = (R << 16) | (G << 8) | B
    blockSize = computeBlockSize(maxIndex)

    maskedIndex = key // blockSize
    wordIndex = maskedIndex ^ (mask % maxIndex)

    if wordIndex >= maxIndex:
        raise ValueError("Unacceptable color space.")

    return wordIndex

def deriveMasterKey(salt: str) -> bytes:
    if not salt:
        return b"\x00" * 32
    return hash_secret_raw(
        secret=salt.encode("utf-8"),
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

def identifySeedType(rawInput: str):
    words = rawInput.lower().split()
    mnemonicStr = " ".join(words)
    numWords = len(words)

    candidateStandards = [s for s in SEED_TYPE_STANDARDS if numWords in s[1]]
    if not candidateStandards:
        raise ValueError(f"Invalid mnemonic length: {numWords} word(s). Valid: 12, 15, 18, 20, 21, 24, 33.")

    allValidWords = set()
    for _, _, wordList, _, _ in candidateStandards:
        allValidWords.update(wordList)

    invalidWords = []
    seen = set()
    for w in words:
        if w not in allValidWords and w not in seen:
            invalidWords.append(w)
            seen.add(w)

    if invalidWords:
        invalidWords.sort()
        maskedWords = [f"{w[0]}•••{w[-1]}" for w in invalidWords]
        raise ValueError(f"Invalid seed word(s): " + ", ".join(maskedWords))

    for name, _, wordList, maxIdx, validator in candidateStandards:
        if all(w in wordList for w in words):
            if validator(mnemonicStr):
                indices = [wordList.index(w) for w in words]
                return indices, name, numWords, maxIdx

    raise ValueError("Mnemonic checksum failed. Unrecognized or invalid seed phrase.")

def getGridDimensions(width, height):
    if width * 4 == height * 3: return 3, 4, 12, 2048
    if width * 5 == height * 3: return 3, 5, 15, 2048
    if width * 2 == height: return 3, 6, 18, 2048
    if width * 5 == height * 4: return 4, 5, 20, 1024
    if width * 7 == height * 3: return 3, 7, 21, 2048
    if width * 3 == height * 2: return 4, 6, 24, 2048
    if width * 11 == height * 3: return 3, 11, 33, 1024
    raise ValueError("Invalid image aspect ratio.")

def encodeMnemonicToBytes(mnemonicRaw, cellPx=100, salt="", precomputed=None):
    indices, standard, numWords, maxIdx = identifySeedType(mnemonicRaw)

    if standard == "SLIP39":
        cols, rows = (4, 5) if numWords == 20 else (3, 11)
    else:
        mapping = {12: (3, 4), 15: (3, 5), 18: (3, 6), 21: (3, 7), 24: (4, 6)}
        cols, rows = mapping[numWords]

    if precomputed is not None:
        maskKey, rngSeed = precomputed
    elif salt:
        masterKey = deriveMasterKey(salt)
        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")
    else:
        maskKey = None
        rngSeed = None

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]
    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    img = Image.new("RGB", (cols * cellPx, rows * cellPx))
    px = img.load()

    for i in range(numWords):
        wordMask = deriveMask(maskKey, i, maxIdx) if maskKey is not None else 0
        currentShift = RGB_VALUE_SHIFTS[i]

        color = encodeWord(indices[i], mask=wordMask, shift=currentShift, maxIndex=maxIdx)

        r, c = allCoords[i]
        for y in range(r * cellPx, (r + 1) * cellPx):
            for x in range(c * cellPx, (c + 1) * cellPx):
                px[x, y] = color

    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format="PNG", optimize=False)
    imgByteArr.seek(0)
    return imgByteArr

def extractRGB(pixel):
    if not isinstance(pixel, tuple): raise ValueError("Invalid pixel format.")
    if len(pixel) == 3: r, g, b = pixel
    elif len(pixel) == 4:
        r, g, b, a = pixel
        if a != 255: raise ValueError("Alpha channel must be fully opaque (0xFF).")
    else: raise ValueError("Unsupported color model.")
    for v in (r, g, b):
        if type(v) is not int or not (0 <= v <= 255):
            raise ValueError("Color channel is outside semantic 8-bit range.")
    return (r, g, b)

def decodeImageFromBytes(file_bytes, salt=""):
    data = file_bytes.read()
    if not isAcceptablePNG(data):
        raise ValueError("PNG contains forbidden chunks or unacceptable color space.")
    
    file_bytes.seek(0)
    img = Image.open(file_bytes)
    pixels = img.load()
    width, height = img.size

    cols, rows, numWords, maxIdx = getGridDimensions(width, height)
    if width % cols != 0 or height % rows != 0:
        raise ValueError("Invalid cell aspect ratio.")
    
    cellWidth = width // cols
    cellHeight = height // rows

    for r in range(rows):
        for c in range(cols):
            basePx = pixels[c * cellWidth, r * cellHeight]
            baseColor = extractRGB(basePx)
            for y in range(r * cellHeight, (r + 1) * cellHeight):
                for x in range(c * cellWidth, (c + 1) * cellWidth):
                    if extractRGB(pixels[x, y]) != baseColor:
                        raise ValueError("Non-monochromatic cell(s) detected. Image might have been compressed.")

    if salt:
        masterKey = deriveMasterKey(salt)
        maskKey, permKey, _ = deriveSubkeys(masterKey)
        rngSeed = int.from_bytes(permKey[:8], "big")
    else:
        maskKey = None
        rngSeed = None

    allCoords = [(r, c) for r in range(rows) for c in range(cols)]
    if rngSeed is not None:
        random.Random(rngSeed).shuffle(allCoords)

    wordIndices = []
    for i in range(numWords):
        r, c = allCoords[i]
        basePx = pixels[c * cellWidth, r * cellHeight]
        baseColor = extractRGB(basePx)

        wordMask = deriveMask(maskKey, i, maxIdx) if maskKey is not None else 0
        currentShift = RGB_VALUE_SHIFTS[i]

        wordIndices.append(decodeColor(baseColor, mask=wordMask, shift=currentShift, maxIndex=maxIdx))

    if numWords in (12, 15, 18, 21, 24):
        mnemonic = " ".join(BIP39_LIST[idx] for idx in wordIndices)
        if BIP39.check(mnemonic): return mnemonic

    if numWords in (12, 24):
        mnemonic = " ".join(ELECTRUM_LIST[idx] for idx in wordIndices)
        if validateElectrum(mnemonic): return mnemonic

    if numWords in (20, 33):
        mnemonic = " ".join(SLIP39_LIST[idx] for idx in wordIndices)
        try:
            Share.from_mnemonic(mnemonic)
            return mnemonic
        except Exception:
            pass

    raise ValueError("Mnemonic checksum failed. Salt is incorrect.")

######## Flask Routes ########

VALID_WORD_COUNTS = [12, 15, 18, 20, 21, 24, 33]
ALL_VALID_WORDS = set(BIP39_LIST) | set(ELECTRUM_LIST) | set(SLIP39_LIST)

@app.route('/api/wordlist', methods=['GET'])
def api_wordlist():
    return jsonify({'words': sorted(ALL_VALID_WORDS)})

@app.route('/api/validate', methods=['POST'])
def api_validate():
    data = request.get_json(force=True)
    mnemonic_raw = data.get('mnemonic', '').strip().lower()
    words = mnemonic_raw.split()
    numWords = len(words)

    result = {
        'valid': False,
        'invalidWords': [],
        'invalidLength': False,
        'checksumFail': False,
        'errors': []
    }

    # Check individual words
    for i, w in enumerate(words):
        if w and w not in ALL_VALID_WORDS:
            result['invalidWords'].append(i)

    if result['invalidWords']:
        result['errors'].append(f"Unrecognized word(s) at position(s): {', '.join(str(i+1) for i in result['invalidWords'])}")

    # Check word count
    if numWords not in VALID_WORD_COUNTS:
        result['invalidLength'] = True
        result['errors'].append(f"Invalid mnemonic length: {numWords} word(s). Valid counts: {', '.join(str(c) for c in VALID_WORD_COUNTS)}.")

    # Only check checksum if all words are valid AND length is valid
    if not result['invalidWords'] and not result['invalidLength']:
        mnemonicStr = " ".join(words)
        checksumPassed = False
        for name, counts, wordList, maxIdx, validator in SEED_TYPE_STANDARDS:
            if numWords in counts and all(w in wordList for w in words):
                try:
                    if validator(mnemonicStr):
                        checksumPassed = True
                        break
                except:
                    pass
        if not checksumPassed:
            result['checksumFail'] = True
            result['errors'].append("Mnemonic checksum failed. The seed phrase is not valid for any supported standard.")
        else:
            result['valid'] = True

    return jsonify(result)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/encode', methods=['POST'])
def api_encode():
    try:
        data = request.form
        mnemonic_raw = data.get('mnemonic', '').strip()
        salt = data.get('salt', '')
        cell_px = int(data.get('cellPx', 100))
        
        img_io = encodeMnemonicToBytes(mnemonic_raw, cell_px, salt)
        return send_file(img_io, mimetype='image/png', as_attachment=True, download_name='spicebag_mnemonic.png')
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/encode_bulk', methods=['POST'])
def api_encode_bulk():
    try:
        data = request.form
        mnemonic_raw = data.get('mnemonic', '').strip()
        salt = data.get('salt', '')
        cell_px = int(data.get('cellPx', 100))
        count = int(data.get('count', 1))

        if salt:
            masterKey = deriveMasterKey(salt)
            maskKey, permKey, _ = deriveSubkeys(masterKey)
            rngSeed = int.from_bytes(permKey[:8], "big")
            precomputed = (maskKey, rngSeed)
        else:
            precomputed = None

        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w', compression=zipfile.ZIP_STORED) as zipf:
            for i in range(1, count + 1):
                img_io = encodeMnemonicToBytes(mnemonic_raw, cell_px, salt, precomputed)
                zipf.writestr(f"{i}.png", img_io.getvalue())
        
        zip_io.seek(0)
        return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name='spicebag_mnemonics.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/decode', methods=['POST'])
def api_decode():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file uploaded'}), 400
        file = request.files['image']
        salt = request.form.get('salt', '')
        
        file_bytes = io.BytesIO(file.read())
        mnemonic = decodeImageFromBytes(file_bytes, salt)
        return jsonify({'mnemonic': mnemonic})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(port=8888, debug=True)
