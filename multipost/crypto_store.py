"""Secret encryption for stored accounts.

Priority:
1. Windows DPAPI (ctypes, no dependency) - real per-user encryption. The blob
   can only be decrypted by the same Windows user on the same PC.
2. Fernet (cryptography package) with a local key file - used on dev machines.
3. XOR+base64 fallback - OBFUSCATION ONLY, used when neither is available
   (e.g. unit tests on a bare VM). Never relied on for the shipped Windows app,
   where DPAPI is always present.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys

_PREFIX_DPAPI = "dpapi:"
_PREFIX_FERNET = "fernet:"
_PREFIX_XOR = "xor:"


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI operation failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _fernet(key_file: str):
    from cryptography.fernet import Fernet

    if os.path.exists(key_file):
        key = open(key_file, "rb").read().strip()
    else:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(key)
    return Fernet(key)


def _xor(data: bytes, key_file: str) -> bytes:
    if os.path.exists(key_file):
        seed = open(key_file, "rb").read()
    else:
        seed = os.urandom(32)
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(seed)
    stream = b""
    counter = 0
    while len(stream) < len(data):
        stream += hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
        counter += 1
    return bytes(a ^ b for a, b in zip(data, stream))


def encrypt_str(plain: str, data_dir: str) -> str:
    if not plain:
        return ""
    raw = plain.encode("utf-8")
    if sys.platform == "win32":
        return _PREFIX_DPAPI + base64.b64encode(_dpapi(raw, True)).decode()
    key_file = os.path.join(data_dir, ".fernet.key")
    try:
        return _PREFIX_FERNET + _fernet(key_file).encrypt(raw).decode()
    except ImportError:
        xor_key = os.path.join(data_dir, ".xor.key")
        return _PREFIX_XOR + base64.b64encode(_xor(raw, xor_key)).decode()


def decrypt_str(blob: str, data_dir: str) -> str:
    if not blob:
        return ""
    if blob.startswith(_PREFIX_DPAPI):
        return _dpapi(base64.b64decode(blob[len(_PREFIX_DPAPI):]), False).decode("utf-8")
    if blob.startswith(_PREFIX_FERNET):
        return _fernet(os.path.join(data_dir, ".fernet.key")).decrypt(
            blob[len(_PREFIX_FERNET):].encode()).decode("utf-8")
    if blob.startswith(_PREFIX_XOR):
        raw = base64.b64decode(blob[len(_PREFIX_XOR):])
        return _xor(raw, os.path.join(data_dir, ".xor.key")).decode("utf-8")
    # Legacy plain value (pre-encryption file): accept and let the store re-save.
    return blob
