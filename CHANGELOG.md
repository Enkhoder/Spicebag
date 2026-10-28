A minor release with two goals: the terminology now says what the optional secret actually is, a **passphrase**, and the seed phrase and passphrase are masked in the input bar as you type. Images and the image format are unchanged from 4.0.0, so every existing image decodes with the same secret as before.

```bash
pip install --upgrade spicebag
```

### Terminology

- **Salt is now passphrase.** What Spicebag used to call the salt is a secret, so it is now the passphrase everywhere: TUI prompts, the status bar, the help page, CLI mode prompts and errors, and the docs. Images made with one are **encrypted**, and images made without one are **unencrypted**.
- **What the passphrase is.** The passphrase is the secret that Argon2id derives every key from. Argon2id's own salt is the fixed constant `SpicebagDomain`, the same for every image, so one passphrase guess can be tested against every image at once. The passphrase has nothing to do with a wallet's BIP39 passphrase (the "25th word").
- **Python API.** The keyword `salt=` is now `passphrase=` in `encodeMnemonic`, `bulkEncodeMnemonic`, `precomputeColorSpace`, `cellPalettes` and `decodeImage`, and `WrongSaltError` is now `WrongPassphraseError`. Scripts that call these by the old names need the new ones.

### Input masking

- The seed phrase and passphrase are hidden while you type. <kbd>TAB</kbd> shows or hides them.
- Screenshots never capture them, even while shown.

### Fixes

- Under WSL, a pasted seed phrase or passphrase stayed on the clipboard after Spicebag wiped it. It is now cleared on the Windows side too.

### Windows executable

- Each GitHub Release now carries three zips: `Spicebag-X.Y.Z-windows-x64.zip` for most PCs, `Spicebag-X.Y.Z-windows-arm64.zip` for ARM devices such as Snapdragon laptops, and `Spicebag-X.Y.Z-windows-x86.zip` for 32-bit Windows only.