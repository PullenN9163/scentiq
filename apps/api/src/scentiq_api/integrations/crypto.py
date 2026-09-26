"""Encryption for provider refresh tokens at rest.

AES-256-GCM with a random 96-bit nonce. Each ciphertext names the key that
sealed it, so the key can be rotated: new tokens use the current key while
tokens sealed with a previous key stay readable until they are next refreshed.

The associated data binds a ciphertext to its owner and provider, so a token
copied onto another member's row fails to decrypt instead of being used.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_FORMAT_VERSION = "v1"
_NONCE_BYTES = 12


class TokenDecryptionError(Exception):
    """The ciphertext is malformed, tampered with, or sealed by an unknown key."""


def _key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


class TokenCipher:
    def __init__(self, keys: list[bytes]) -> None:
        if not keys:
            raise ValueError("At least one encryption key is required")
        if any(len(key) != 32 for key in keys):
            raise ValueError("Encryption keys must be 32 bytes")
        self._current = keys[0]
        self._by_id = {_key_id(key): key for key in keys}

    def encrypt(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        sealed = AESGCM(self._current).encrypt(nonce, plaintext.encode(), context.encode())
        payload = base64.urlsafe_b64encode(nonce + sealed).decode()
        return f"{_FORMAT_VERSION}:{_key_id(self._current)}:{payload}"

    def decrypt(self, ciphertext: str, *, context: str) -> str:
        try:
            version, key_id, payload = ciphertext.split(":", 2)
        except ValueError:
            raise TokenDecryptionError("malformed") from None
        key = self._by_id.get(key_id)
        if version != _FORMAT_VERSION or key is None:
            raise TokenDecryptionError("unknown_key")
        try:
            raw = base64.urlsafe_b64decode(payload.encode())
            opened = AESGCM(key).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], context.encode())
        except InvalidTag, ValueError:
            raise TokenDecryptionError("invalid") from None
        return opened.decode()

    def needs_rotation(self, ciphertext: str) -> bool:
        return not ciphertext.startswith(f"{_FORMAT_VERSION}:{_key_id(self._current)}:")
