"""End-to-end smoke checks. Run with `python tests/smoke.py` from the repository root.

Exercises the encode/decode round trip for every standard and word count, asserts that
salted encodes stay non-deterministic, confirms the deliberately invalid fixtures still
fail, and checks that a wrong salt is rejected rather than decoded. Exits non-zero on any failure.
"""



######## LIBRARIES ########

from spicebag.backend.generator import (
    encodeMnemonic, bulkEncodeMnemonic, identifySeedType, precomputeColorSpace, applyHueRange, rerollCell,
    inHueRange, renderColorSpaceToFile
)
from spicebag.backend.decoder import decodeImage, WrongSaltError
from spicebag.frontend.theme import parseHueRange
import tempfile
import hashlib
import pathlib
import zipfile
import sys
import io



######## CONSTANTS ########

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples" / "images"

EXPECTED_FAILURES = {
    "Corrupted-png-compressed-pixels",
    "Corrupted-png-invalid-aspect-ratio",
    "Corrupted-png-invalid-color-space",
    "First-image-generated-using-old-algorithm-undecodable",
    "Previous-format-3.0-undecodable"
}

failures = []



######## HELPERS ########

def check(label: str, condition: bool, detail: object = "") -> None:
    print(("PASS " if condition else "FAIL ") + label + (f" | {detail}" if detail else ""))

    if not condition:
        failures.append(label)


def saltFor(stem):
    return stem.split("-seed-")[1] if "-seed-" in stem else ""



######## CHECKS ########

def decodeFixtures():
    """Every valid fixture decodes; every invalid one still raises."""
    phrases = {}

    for image in sorted(EXAMPLES.glob("*.png")):
        stem = image.stem

        try:
            mnemonic, seedType = decodeImage(str(image), salt=saltFor(stem))

        except Exception as e:
            check(f"{stem} rejected", stem in EXPECTED_FAILURES, str(e)[:48])
            continue

        check(f"{stem} decoded", stem not in EXPECTED_FAILURES, seedType)
        phrases[" ".join(mnemonic.split())] = seedType

    return phrases


def generatedPhrases():
    """BIP39 phrases for the word counts no fixture covers, from fixed entropy so every run checks the same ones."""
    from mnemonic import Mnemonic

    bip39 = Mnemonic("english")
    return {bip39.to_mnemonic(bytes(range(size))): "BIP39" for size in (20, 24, 28)}


def roundTrip(phrase, seedType, workDir):
    """Three encodes of the same phrase and salt must differ, and all must decode back."""
    wordCount = len(phrase.split())

    for salt in ("", "smokeSalt"):
        digests = []

        for i in range(3):
            target = workDir / f"{wordCount}-{i}.png"
            encodeMnemonic(phrase, str(target), cellPx=3, salt=salt)
            digests.append(hashlib.sha256(target.read_bytes()).hexdigest()[:12])
            recovered, recoveredType = decodeImage(str(target), salt=salt)

            if " ".join(recovered.split()) != phrase or recoveredType != seedType:
                check(f"{wordCount}w salt={salt!r} decodes to itself", False, recoveredType)
                return

        check(f"{wordCount}w salt={salt!r} round trip", True, seedType)
        check(f"{wordCount}w salt={salt!r} encodes are non-deterministic", len(set(digests)) == 3, digests)

        archive = workDir / f"{wordCount}.zip"
        bulkEncodeMnemonic(phrase, str(archive), 3, cellPx=3, salt=salt)
        bulkDigests = []

        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                extracted = workDir / "bulk.png"
                extracted.write_bytes(bundle.read(name))
                bulkDigests.append(hashlib.sha256(bundle.read(name)).hexdigest()[:12])
                recovered, _ = decodeImage(str(extracted), salt=salt)

                if " ".join(recovered.split()) != phrase:
                    check(f"{wordCount}w salt={salt!r} bulk decodes", False, name)
                    return

        check(f"{wordCount}w salt={salt!r} bulk images are unique", len(set(bulkDigests)) == 3)


def outcome(image, salt):
    try:
        return decodeImage(str(image), salt=salt)[0]

    except WrongSaltError:
        return "rejected"


def proofOfPhrase(phrase, workDir):
    """A wrong, missing or superfluous salt is rejected instead of yielding another valid phrase."""
    wordCount = len(phrase.split())
    salted = workDir / "proof-salted.png"
    plain = workDir / "proof-plain.png"
    encodeMnemonic(phrase, str(salted), cellPx=3, salt="smokeSalt")
    encodeMnemonic(phrase, str(plain), cellPx=3)

    accepted = [salt for salt in ("smokesalt", "smokeSalt ", "k", "m", "x") if outcome(salted, salt) != "rejected"]
    check(f"{wordCount}w wrong salts are rejected", not accepted, accepted)
    check(f"{wordCount}w salted image without its salt is rejected", outcome(salted, "") == "rejected")
    check(f"{wordCount}w unsalted image given a salt is rejected", outcome(plain, "k") == "rejected")


def hueParsing():
    """The hue range grammar: space-separated hues, hyphen only as a minus sign, upward arcs, one error each."""
    cases = {
        "20 120": (20, 100),
        "-20 -50": (340, 330),
        "10 -10": (10, 340),
        "- 20   -  50": (340, 330),
        "  7   -3  ": (7, 350),
        "20 20": (20, 0),
        "0 360": (0, 360),
        "10-50": "Hyphen is misplaced.",
        "20 -": "Hyphen is misplaced.",
        "20- 50-": "Hyphen is misplaced.",
        "--20 50": "Too many hyphens.",
        "400 10": "Hue out of range.",
        "10 20 30": "Too many hues.",
        "20": "Two hues are needed.",
    }

    for text, expected in cases.items():
        got = parseHueRange(text, final=True)
        check(f"hue range {text!r}", got == expected, got)

    check("hue range typing allows a dangling hyphen", parseHueRange("20 -", final=False) is None)


def hueRanges(phrase, workDir):
    """A hue range recolors a cell inside the arc, sticks for later rerolls, refuses an arc the word cannot reach,
    and the image still decodes."""
    cs = precomputeColorSpace(phrase, "k")
    neighbors = [cs.colorRGB[cell] for cell in ((1, 0), (0, 1))]
    applied = applyHueRange(cs, 0, 0, 0, 60)
    check("hue range applies to a salted cell", applied and inHueRange(cs.colorRGB[(0, 0)], 0, 60), cs.colorRGB[(0, 0)])
    check("hue range avoids neighbor colors", cs.colorRGB[(0, 0)] not in neighbors)

    rerolled = []
    for _ in range(20):
        rerollCell(cs, 0, 0)
        rerolled.append(inHueRange(cs.colorRGB[(0, 0)], 0, 60))

    check("rerolls stay inside the stored hue range", all(rerolled))
    check("grays fit every hue range", inHueRange((128, 128, 128), 300, 30) and inHueRange((0, 0, 0), 20, 0))

    image = workDir / "hue.png"
    renderColorSpaceToFile(cs, str(image), cellPx=2)
    check("image with a hue range decodes", decodeImage(str(image), salt="k")[0] == phrase)

    plain = precomputeColorSpace(" ".join(["abandon"] * 11 + ["about"]), "")
    before = plain.colorRGB[(0, 0)]
    refused = not applyHueRange(plain, 0, 0, 300, 30)
    check(
        "unreachable hue range is refused and changes nothing",
        refused and plain.colorRGB[(0, 0)] == before and (0, 0) not in plain.hueRanges
    )


def identityAgreement(phrase, seedType):
    """The encoder and the decoder must name the same standard."""
    _, name, _, _ = identifySeedType(phrase)
    check(f"{len(phrase.split())}w encoder/decoder agree on standard", name == seedType, f"{name} vs {seedType}")



######## ENTRY POINT ########

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

    print("======== FIXTURES ========")
    phrases = decodeFixtures()
    check("at least four distinct phrases recovered", len(phrases) >= 4, len(phrases))
    phrases.update(generatedPhrases())

    print()
    print("======== ROUND TRIP ========")

    with tempfile.TemporaryDirectory() as tmp:
        workDir = pathlib.Path(tmp)

        for phrase, seedType in phrases.items():
            identityAgreement(phrase, seedType)
            roundTrip(phrase, seedType, workDir)

        print()
        print("======== PROOF OF PHRASE ========")
        proofOfPhrase(min(phrases, key=lambda phrase: len(phrase.split())), workDir)

        print()
        print("======== HUE RANGES ========")
        hueParsing()
        hueRanges(min(phrases, key=lambda phrase: len(phrase.split())), workDir)

    print()

    if failures:
        print(f"FAILED ({len(failures)}):")

        for f in failures:
            print("   ", f)

        return 1

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())