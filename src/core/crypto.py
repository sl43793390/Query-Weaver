"""Symmetric encryption helpers (Fernet / AES-128 in CBC + HMAC-SHA256).

The key is auto-generated on first launch and stored at `config/.key`.
The key file is excluded from version control via `.gitignore`.

Use `encrypt(plaintext)` / `decrypt(ciphertext)` for any string credentials
you want to persist to SQLite.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config.settings import KEY_FILE_PATH
from src.core.logger import logger


def _load_or_create_key() -> bytes:
    if KEY_FILE_PATH.exists():
        return KEY_FILE_PATH.read_bytes().strip()

    key = Fernet.generate_key()
    KEY_FILE_PATH.write_bytes(key)
    try:
        # Restrict permissions on POSIX systems.
        KEY_FILE_PATH.chmod(0o600)
    except OSError:  # pragma: no cover - Windows
        pass
    logger.info("Generated new encryption key at {}", KEY_FILE_PATH)
    return key


_FERNET = Fernet(_load_or_create_key())


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return a URL-safe base64 token."""
    if plaintext is None:
        return ""
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a token produced by `encrypt`. Returns "" on empty input."""
    if not token:
        return ""
    try:
        return _FERNET.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - corrupt key
        logger.error("Failed to decrypt token (invalid key or corrupted data): {}", exc)
        return ""


__all__ = ["encrypt", "decrypt"]
