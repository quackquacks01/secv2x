from __future__ import annotations

import os
from ctypes import CDLL, POINTER, byref, c_int, c_size_t, c_ubyte
from pathlib import Path


class AIMer128fSigner:
    """Raw byte-signature wrapper for the local AIMer-128f reference DLL."""

    algorithm_name = "AIMer-128f"

    def __init__(
        self,
        library_path: str | os.PathLike[str],
        context: bytes = b"KpqC-WTC-v1",
    ) -> None:
        path = Path(library_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"AIMer library not found: {path}")
        if not isinstance(context, bytes):
            raise TypeError("context must be bytes")
        if len(context) > 255:
            raise ValueError("AIMer context must be at most 255 bytes")

        self.library_path = path
        self.context = context
        self._dll_directory_handles: list[object] = []

        if os.name == "nt":
            for directory in (path.parent, Path(r"C:\msys64\ucrt64\bin")):
                if directory.is_dir():
                    self._dll_directory_handles.append(
                        os.add_dll_directory(str(directory))
                    )

        self.lib = CDLL(str(path))
        self._bind_functions()

        self.public_key_bytes = int(self._public_key_bytes())
        self.secret_key_bytes = int(self._secret_key_bytes())
        self.signature_bytes = int(self._signature_bytes())

        expected = (32, 48, 5888)
        actual = (
            self.public_key_bytes,
            self.secret_key_bytes,
            self.signature_bytes,
        )
        if actual != expected:
            raise RuntimeError(
                f"Unexpected AIMer-128f sizes: expected={expected}, actual={actual}"
            )

    def _bind_functions(self) -> None:
        self._public_key_bytes = self.lib.kpqc_aimer_128f_publickeybytes
        self._public_key_bytes.argtypes = []
        self._public_key_bytes.restype = c_size_t

        self._secret_key_bytes = self.lib.kpqc_aimer_128f_secretkeybytes
        self._secret_key_bytes.argtypes = []
        self._secret_key_bytes.restype = c_size_t

        self._signature_bytes = self.lib.kpqc_aimer_128f_signaturebytes
        self._signature_bytes.argtypes = []
        self._signature_bytes.restype = c_size_t

        self._keypair = self.lib.kpqc_aimer_128f_keypair
        self._keypair.argtypes = [POINTER(c_ubyte), POINTER(c_ubyte)]
        self._keypair.restype = c_int

        self._signature = self.lib.kpqc_aimer_128f_signature
        self._signature.argtypes = [
            POINTER(c_ubyte),
            POINTER(c_size_t),
            POINTER(c_ubyte),
            c_size_t,
            POINTER(c_ubyte),
            c_size_t,
            POINTER(c_ubyte),
        ]
        self._signature.restype = c_int

        self._verify = self.lib.kpqc_aimer_128f_verify
        self._verify.argtypes = [
            POINTER(c_ubyte),
            c_size_t,
            POINTER(c_ubyte),
            c_size_t,
            POINTER(c_ubyte),
            c_size_t,
            POINTER(c_ubyte),
        ]
        self._verify.restype = c_int

    @staticmethod
    def _buffer_from_bytes(data: bytes):
        if not data:
            return (c_ubyte * 1)()
        return (c_ubyte * len(data)).from_buffer_copy(data)

    def keygen(self) -> tuple[bytes, bytes]:
        public_key = (c_ubyte * self.public_key_bytes)()
        secret_key = (c_ubyte * self.secret_key_bytes)()
        result = self._keypair(public_key, secret_key)
        if result != 0:
            raise RuntimeError(f"AIMer keypair generation failed: return code={result}")
        return bytes(public_key), bytes(secret_key)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        if len(private_key) != self.secret_key_bytes:
            raise ValueError(
                "Invalid AIMer secret key length: "
                f"expected={self.secret_key_bytes}, actual={len(private_key)}"
            )

        signature = (c_ubyte * self.signature_bytes)()
        signature_length = c_size_t(0)
        result = self._signature(
            signature,
            byref(signature_length),
            self._buffer_from_bytes(message),
            c_size_t(len(message)),
            self._buffer_from_bytes(self.context),
            c_size_t(len(self.context)),
            self._buffer_from_bytes(private_key),
        )
        if result != 0:
            raise RuntimeError(f"AIMer signing failed: return code={result}")
        if signature_length.value != self.signature_bytes:
            raise RuntimeError(
                "Unexpected AIMer signature length: "
                f"expected={self.signature_bytes}, actual={signature_length.value}"
            )
        return bytes(signature)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        if not isinstance(message, bytes) or not isinstance(signature, bytes):
            return False
        if len(signature) != self.signature_bytes:
            return False
        if len(public_key) != self.public_key_bytes:
            return False

        result = self._verify(
            self._buffer_from_bytes(signature),
            c_size_t(len(signature)),
            self._buffer_from_bytes(message),
            c_size_t(len(message)),
            self._buffer_from_bytes(self.context),
            c_size_t(len(self.context)),
            self._buffer_from_bytes(public_key),
        )
        return result == 0
