"""
ophix.core.crypto
~~~~~~~~~~~~~~~~~~
Shared encryption helpers for export/import management commands.

Two cipher schemes, selected by the "cipher" key in an export payload:

  "fernet" (the original, default when the key is absent entirely — for
  files produced before this module existed): a random 16-byte salt is
  generated per export run, and Fernet's own per-call random IV means every
  encrypt() of the same plaintext produces different ciphertext. Non-
  deterministic by design — fine for periodic backups, useless for a git-
  backed history that wants an empty diff when nothing real changed.

  "stable-aesgcmsiv": deterministic. Key derivation uses this server's own
  fixed STABLE_EXPORT_SALT (settings.py — generated once, persisted to
  .env, and never rotated), and the nonce is derived from the plaintext
  itself (HMAC-SHA256 of the plaintext under the derived key, truncated to
  12 bytes) rather than from randomness. Identical plaintext always
  encrypts to identical ciphertext on this server, which is what lets
  ophix-revisions produce an empty git diff across unchanged exports.

  Deliberate trade-off: two fields sharing the same plaintext value (within
  one export, or across exports from this one server over time) reveal
  that equality to anyone who can read the ciphertext. AES-GCM-SIV (RFC
  8452) is used instead of plain AES-GCM specifically because it is
  nonce-misuse-resistant — reusing a nonce under the same key degrades only
  to that equality leak, not to full key or authentication-tag compromise,
  which is what would happen under plain GCM. That resistance is what makes
  a deliberately-repeating nonce a reasoned choice here rather than a bug.

  The fixed salt is per-install, not a single constant shared by every
  Ophix server. Two servers encrypting with the same passphrase still
  derive unrelated keys, so stable-mode ciphertext is never comparable
  across servers even when they happen to share a vaulted passphrase.

Every export/import command that encrypts should go through
build_export_cipher() / build_import_cipher() rather than touching Fernet,
AESGCMSIV, or PBKDF2 directly, so every encrypted export/import command
stays on one code path.
"""

import base64
import hashlib
import hmac

PBKDF2_ITERATIONS = 480_000


class DecryptionError(Exception):
    """Wrong passphrase or corrupted/tampered ciphertext."""


def _derive_pbkdf2_key(passphrase: str, salt: bytes) -> bytes:
    """Raw 32-byte derived key. Fernet specifically wants its key
    base64-encoded — callers that need that do the encoding themselves,
    it's not part of what a KDF derivation returns in general."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS
    )
    return kdf.derive(passphrase.encode())


class _FernetCipher:
    name = "fernet"

    def __init__(self, passphrase: str, salt: bytes = None):
        import os
        from cryptography.fernet import Fernet
        self.salt = salt if salt is not None else os.urandom(16)
        key = base64.urlsafe_b64encode(_derive_pbkdf2_key(passphrase, self.salt))
        self._fernet = Fernet(key)

    @property
    def salt_b64(self) -> str:
        return base64.urlsafe_b64encode(self.salt).decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        from cryptography.fernet import InvalidToken
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            raise DecryptionError("Incorrect passphrase or corrupted data.")


class _StableCipher:
    name = "stable-aesgcmsiv"

    def __init__(self, passphrase: str, salt: bytes = None):
        if salt is None:
            from django.conf import settings
            salt = base64.urlsafe_b64decode(settings.STABLE_EXPORT_SALT)
        self.salt = salt
        self._key = _derive_pbkdf2_key(passphrase, self.salt)

    @property
    def salt_b64(self) -> str:
        return base64.urlsafe_b64encode(self.salt).decode()

    def _nonce_for(self, plaintext: str) -> bytes:
        return hmac.new(self._key, plaintext.encode(), hashlib.sha256).digest()[:12]

    def encrypt(self, plaintext: str) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
        nonce = self._nonce_for(plaintext)
        ciphertext = AESGCMSIV(self._key).encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def decrypt(self, token: str) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
        from cryptography.exceptions import InvalidTag
        raw = base64.urlsafe_b64decode(token)
        nonce, ciphertext = raw[:12], raw[12:]
        try:
            return AESGCMSIV(self._key).decrypt(nonce, ciphertext, None).decode()
        except InvalidTag:
            raise DecryptionError("Incorrect passphrase or corrupted data.")


_CIPHER_CLASSES = {
    "fernet": _FernetCipher,
    "stable-aesgcmsiv": _StableCipher,
}


def build_export_cipher(passphrase, stable: bool = False):
    """Returns None if no passphrase was given (caller writes plaintext).
    Otherwise a cipher with .encrypt(str) -> str, .decrypt(str) -> str,
    .name, and .salt_b64 — embed .name as payload["cipher"] and .salt_b64
    as payload["salt"] so import_* can reconstruct the same cipher later."""
    if not passphrase:
        return None
    cls = _StableCipher if stable else _FernetCipher
    return cls(passphrase)


def build_import_cipher(cipher_name, passphrase: str, salt_b64):
    """cipher_name and salt_b64 come from the export payload's "cipher" and
    "salt" keys. cipher_name defaults to "fernet" for files exported before
    this module existed (no "cipher" key at all)."""
    cls = _CIPHER_CLASSES.get(cipher_name or "fernet")
    if cls is None:
        raise DecryptionError(f"Unknown cipher '{cipher_name}' in export file.")
    salt = base64.urlsafe_b64decode(salt_b64) if salt_b64 else None
    return cls(passphrase, salt=salt)
