# Examples

Sample inputs and outputs for testing Spicebag. **None of these seed phrases hold funds.**

## `phrases/`

Plain-text dummy mnemonics, one per supported word count.

| File | Words | Standard |
|------|-------|----------|
| `12-word-phrase.txt` | 12 | Electrum |
| `20-word-phrase.txt` | 20 | SLIP39 |
| `24-word-phrase.txt` | 24 | BIP39 |
| `33-word-phrase.txt` | 33 | SLIP39 |

## `images/`

Encoded PNGs. **The filename carries the salt**: do not rename these files, or they become undecodable.

| File | Salt |
|------|------|
| `12-seedless.png`, `20-seedless.png`, `24-seedless.png`, `33-seedless.png` | none |
| `12-seed-Z3wjBTmDso1eLQ.png` | `Z3wjBTmDso1eLQ` |
| `20-seed-f607we26jY30a4bPFr.png` | `f607we26jY30a4bPFr` |
| `24-seed-1r0WG9A94Jhl2Erv.png` | `1r0WG9A94Jhl2Erv` |
| `24-seed-∣⫃┼►⁉₅䯑⦜➗ⷕ⩼⣢⩹ⴱ⽨ⶃ⪐⏔.png` | the non-ASCII string in the filename |
| `33-seed-XjpJxIjOiPQ94DR.png` | `XjpJxIjOiPQ94DR` |

Deliberately invalid images, kept as decoder regression cases:

| File | Why it fails |
|------|--------------|
| `Corrupted-png-1.png`, `Corrupted-png-2.png` | fail PNG chunk / cell-integrity validation |
| `24-seed-0x59756E-interchanged.png` | cells swapped after encoding |
| `First-image-generated-using-old-algorithm-undecodable.png` | produced by a superseded encoding algorithm |

## Usage

Start the interface, type `decode`, and give it a path from the table above along with the matching salt. There is no command-line decode subcommand: a salt passed as an argument would be left behind in the shell history.

```bat
run.bat
```