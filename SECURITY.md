# Security Policy

Spicebag handles cryptocurrency wallet seed phrases. A vulnerability here can cost people
their funds permanently, so please report privately rather than opening a public issue.

## Reporting a vulnerability

Use GitHub's private reporting: **Security → Report a vulnerability** on
[the repository](https://github.com/Enkhoder/Spicebag/security/advisories/new).

Please include what you did, what happened, what you expected, and the versions of Spicebag
and Python involved. **NEVER INCLUDE A REAL SEED PHRASE!** Use one of the dummy phrases in
[`examples/phrases/`](examples/phrases) or generate a throwaway.

Expect an acknowledgment within a few days. Because this is a single-maintainer project,
please allow reasonable time for a fix before public disclosure.

## What counts

Anything that could expose a seed phrase or make one unrecoverable:

- A phrase or salt reaching the scrollback, the status bar, an exported screenshot, a log,
  a crash trace, or any file other than the intended output image
- Two different phrases encoding to the same image, or an image decoding to the wrong phrase
- Encodes that are reproducible from the phrase and salt alone, which would let two files be
  correlated as sharing both
- Weakening of the salt handling: Argon2id parameters, HKDF domain separation, or the XOR
  mask derivation
- A crafted PNG causing code execution, or bypassing the chunk and cell-integrity validation
- Dependency or supply-chain issues affecting the published package

## What does not

The threat model is stated in the README and enforced by the warning screen at startup.
Out of scope:

- Malware, keyloggers, screen capture, or a compromised operating system. Spicebag offers no
  protection against a machine that is already owned.
- Anyone who can see your screen, your camera, or your keyboard
- Losing the salt. It is never stored anywhere, by design, and an image encoded with a lost
  salt is unrecoverable.
- Brute-forcing a weak salt. Argon2id raises the cost but cannot rescue a guessable passphrase.
- Word lengths visible in the masked invalid-word notice. Only words absent from every
  wordlist are shown that way, so they are typos rather than seed words.

## Releases

Published to PyPI through GitHub Actions using
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/). No long-lived API token
exists on any maintainer machine or in repository secrets; PyPI mints a short-lived one per
workflow run. The publishing job runs in a protected environment requiring manual approval.

Verify what you installed against the tagged source at
[the releases page](https://github.com/Enkhoder/Spicebag/releases).