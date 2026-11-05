import os

from cryptography.fernet import Fernet


def _cipher() -> Fernet:
    key = os.getenv("UPLOAD_PASSWORD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("UPLOAD_PASSWORD_ENCRYPTION_KEY is not configured.")
    return Fernet(key.encode())


def encrypt_upload_password(password: str) -> str:
    return _cipher().encrypt(password.encode()).decode()


def decrypt_upload_password(encrypted_password: str) -> str:
    return _cipher().decrypt(encrypted_password.encode()).decode()
