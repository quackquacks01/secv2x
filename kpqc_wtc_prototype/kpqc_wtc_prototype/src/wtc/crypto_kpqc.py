from __future__ import annotations

from abc import ABC
from ctypes import (
    CDLL,
    POINTER,
    byref,
    cast,
    c_int,
    c_size_t,
    c_ubyte,
    c_ulonglong,
    create_string_buffer,
    memmove,
)
from pathlib import Path


class KpqcSigner(ABC):
    algorithm_name = "KPQC"

    def __init__(self, library_path: str | None = None):
        self.lib = self._load_library(library_path)
        self.public_key_bytes = self._get_size("crypto_sign_publickeybytes")
        self.secret_key_bytes = self._get_size("crypto_sign_secretkeybytes")
        self.signature_bytes = self._get_size("crypto_sign_bytes")
        self._bind_functions()

    def _load_library(self, library_path: str | None) -> CDLL:
        if library_path is None:
            raise ValueError("library_path is required for KpqC signer initialization")

        path = Path(library_path)
        if not path.exists():
            raise FileNotFoundError(f"KpqC library not found: {library_path}")
        return CDLL(str(path))

    def _get_size(self, function_name: str) -> int:
        func = getattr(self.lib, function_name, None)
        if func is None:
            raise AttributeError(f"Library missing required function: {function_name}")
        func.restype = c_size_t
        return int(func())

    def _bind_functions(self) -> None:
        self.lib.crypto_sign_keypair.argtypes = [POINTER(c_ubyte), POINTER(c_ubyte)]
        self.lib.crypto_sign_keypair.restype = c_int

        self.lib.crypto_sign_signature.argtypes = [
            POINTER(c_ubyte),
            POINTER(c_ulonglong),
            POINTER(c_ubyte),
            c_ulonglong,
            POINTER(c_ubyte),
        ]
        self.lib.crypto_sign_signature.restype = c_int

        self.lib.crypto_sign_verify.argtypes = [
            POINTER(c_ubyte),
            c_ulonglong,
            POINTER(c_ubyte),
            c_ulonglong,
            POINTER(c_ubyte),
        ]
        self.lib.crypto_sign_verify.restype = c_int

    def _buffer(self, size: int) -> POINTER(c_ubyte):
        return (c_ubyte * size)()

    def keygen(self) -> tuple[bytes, bytes]:
        public_key = self._buffer(self.public_key_bytes)
        secret_key = self._buffer(self.secret_key_bytes)
        result = self.lib.crypto_sign_keypair(public_key, secret_key)
        if result != 0:
            raise RuntimeError("KpqC keypair generation failed")
        return bytes(public_key), bytes(secret_key)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        signature = self._buffer(self.signature_bytes)
        signature_length = c_ulonglong(0)
        message_buffer = (c_ubyte * len(message)).from_buffer_copy(message)
        private_key_buffer = (c_ubyte * len(private_key)).from_buffer_copy(private_key)

        result = self.lib.crypto_sign_signature(
            signature,
            byref(signature_length),
            message_buffer,
            c_ulonglong(len(message)),
            private_key_buffer,
        )
        if result != 0:
            raise RuntimeError("KpqC signing failed")
        return bytes(signature)[: signature_length.value]

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        signature_buffer = (c_ubyte * len(signature)).from_buffer_copy(signature)
        message_buffer = (c_ubyte * len(message)).from_buffer_copy(message)
        public_key_buffer = (c_ubyte * len(public_key)).from_buffer_copy(public_key)

        result = self.lib.crypto_sign_verify(
            signature_buffer,
            c_ulonglong(len(signature)),
            message_buffer,
            c_ulonglong(len(message)),
            public_key_buffer,
        )
        return result == 0


class AIMerSigner(KpqcSigner):
    algorithm_name = "AIMer"

    def __init__(self, library_path: str | None = None):
        super().__init__(library_path)


class HAETAESigner(KpqcSigner):
    algorithm_name = "HAETAE"

    def __init__(self, library_path: str | None = None):
        super().__init__(library_path)
