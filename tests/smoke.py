"""End-to-end smoke checks. Run with `python tests/smoke.py` from the repository root.

Exercises the encode/decode round trip across every supported standard and word count,
asserts that salted encodes stay non-deterministic, and confirms the deliberately invalid
fixtures still fail. Exits non-zero on the first failure.
"""

######## LIBRARIES ########

from spicebag.core.generator import encodeMnemonic, bulkEncodeMnemonic, identifySeedType
from spicebag.core.decoder import decodeImage
import tempfile
import hashlib
import zipfile
import pathlib
import sys
import io



######## CONSTANTS ########

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples" / "images"

EXPECTED_FAILURES = {
    "Corrupted-png-1",
    "Corrupted-png-2",
    "24-seed-0x59756E-interchanged",
    "First-image-generated-using-old-algorithm-undecodable"
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

    print()
    print("======== ROUND TRIP ========")

    with tempfile.TemporaryDirectory() as tmp:
        workDir = pathlib.Path(tmp)

        for phrase, seedType in phrases.items():
            identityAgreement(phrase, seedType)
            roundTrip(phrase, seedType, workDir)

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