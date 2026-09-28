"""Encryption for the published portfolio file.

Format (JSON), decrypted in the browser with Web Crypto (docs/js/data/crypto.js):
    {"v":1,"alg":"AES-256-GCM","kdf":"PBKDF2-SHA256","iter":N,"salt":b64,"iv":b64,"ct":b64}
    key = PBKDF2-HMAC-SHA256(passphrase, salt, N) ; ct = AES-GCM(key, iv, json) incl. 16-byte tag
"""
from __future__ import annotations

import base64
import json
import os
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class Cipher(Protocol):
    def encrypt(self, obj, previous: dict | None = None) -> dict: ...
    def decrypt(self, blob: dict): ...


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


class AesGcmCipher:
    ITERATIONS = 600_000

    PAD_BLOCK = 8192   # ciphertext size only reveals "under 8 KB", not how many holdings you have

    def __init__(self, passphrase: str, iterations: int = ITERATIONS, pad_block: int = PAD_BLOCK):
        if not passphrase:
            raise ValueError("passphrase required")
        self._pw = passphrase.encode("utf-8")
        self.iterations, self.pad_block = iterations, pad_block

    def _key(self, salt: bytes, iterations: int) -> bytes:
        return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations).derive(self._pw)

    def encrypt(self, obj, previous: dict | None = None) -> dict:
        """Fresh IV every call. Re-uses the previous file's salt (if it decrypts with this
        passphrase) so browsers that saved the derived key stay unlocked between runs."""
        salt = os.urandom(16)
        if previous:
            try:
                self.decrypt(previous)
                salt = base64.b64decode(previous["salt"])
            except Exception:
                pass
        iv = os.urandom(12)
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self.pad_block:
            data += b" " * (-len(data) % self.pad_block)   # trailing spaces are valid JSON
        ct = AESGCM(self._key(salt, self.iterations)).encrypt(iv, data, None)
        return {"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": self.iterations,
                "salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ct)}

    def decrypt(self, blob: dict):
        d = base64.b64decode
        key = self._key(d(blob["salt"]), int(blob["iter"]))
        return json.loads(AESGCM(key).decrypt(d(blob["iv"]), d(blob["ct"]), None))
