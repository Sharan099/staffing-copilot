"""AES-256-GCM encryption for manager API keys. MASTER_KEY is server-only."""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from api.config import get_master_key


def encrypt_api_key(plaintext: str) -> tuple[str, str]:
    """Return (ciphertext_hex, iv_hex). Plaintext is never stored."""
    key = get_master_key()
    iv = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return ciphertext.hex(), iv.hex()


def decrypt_api_key(ciphertext_hex: str, iv_hex: str) -> str:
    """Decrypt in-memory only — never log the return value."""
    key = get_master_key()
    plaintext = AESGCM(key).decrypt(
        bytes.fromhex(iv_hex),
        bytes.fromhex(ciphertext_hex),
        None,
    )
    return plaintext.decode("utf-8")
