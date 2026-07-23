from __future__ import annotations

import os
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
    """
    HAETAE mode2 怨듭떇 援ы쁽 DLL ?곕룞 ?대옒??

    怨듭떇 DLL???ㅼ젣 export:
      cryptolab_haetae_mode2_keypair
      cryptolab_haetae_mode2_signature
      cryptolab_haetae_mode2_verify
    """

    algorithm_name = "HAETAE-mode2"

    PUBLIC_KEY_BYTES = 992
    SECRET_KEY_BYTES = 1408
    SIGNATURE_BYTES = 1474

    def __init__(
        self,
        library_path: str | None = None,
        context: bytes = b"KpqC-WTC-v1",
    ):
        if library_path is None:
            raise ValueError(
                "library_path is required for HAETAE signer initialization"
            )

        path = Path(library_path).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"KpqC library not found: {library_path}"
            )

        if not isinstance(context, bytes):
            raise TypeError("context must be bytes")

        if len(context) > 255:
            raise ValueError("HAETAE context must be at most 255 bytes")

        self.context = context
        self.library_path = path

        self.public_key_bytes = self.PUBLIC_KEY_BYTES
        self.secret_key_bytes = self.SECRET_KEY_BYTES
        self.signature_bytes = self.SIGNATURE_BYTES

        # Windows?먯꽌 DLL ?섏〈 ?쇱씠釉뚮윭由щ? 李얠쓣 ???덈룄濡?寃쎈줈瑜??좎??쒕떎.
        self._dll_directory_handles: list[object] = []

        if os.name == "nt":
            dependency_directories = [
                path.parent,
                Path(r"C:\msys64\ucrt64\bin"),
            ]

            for directory in dependency_directories:
                if directory.is_dir():
                    handle = os.add_dll_directory(str(directory))
                    self._dll_directory_handles.append(handle)

        self.lib = CDLL(str(path))
        self._bind_haetae_functions()

    def _bind_haetae_functions(self) -> None:
        self._keypair = getattr(
            self.lib,
            "cryptolab_haetae_mode2_keypair",
        )
        self._keypair.argtypes = [
            POINTER(c_ubyte),
            POINTER(c_ubyte),
        ]
        self._keypair.restype = c_int

        self._signature = getattr(
            self.lib,
            "cryptolab_haetae_mode2_signature",
        )
        self._signature.argtypes = [
            POINTER(c_ubyte),   # signature
            POINTER(c_size_t),  # signature length
            POINTER(c_ubyte),   # message
            c_size_t,           # message length
            POINTER(c_ubyte),   # context
            c_size_t,           # context length
            POINTER(c_ubyte),   # secret key
        ]
        self._signature.restype = c_int

        self._verify = getattr(
            self.lib,
            "cryptolab_haetae_mode2_verify",
        )
        self._verify.argtypes = [
            POINTER(c_ubyte),   # signature
            c_size_t,           # signature length
            POINTER(c_ubyte),   # message
            c_size_t,           # message length
            POINTER(c_ubyte),   # context
            c_size_t,           # context length
            POINTER(c_ubyte),   # public key
        ]
        self._verify.restype = c_int

    @staticmethod
    def _bytes_buffer(data: bytes):
        """
        鍮??곗씠?곕룄 C ?⑥닔???꾨떖?????덈룄濡?理쒖냼 1諛붿씠??踰꾪띁瑜?留뚮뱺??
        """
        if len(data) == 0:
            return (c_ubyte * 1)()

        return (c_ubyte * len(data)).from_buffer_copy(data)

    def keygen(self) -> tuple[bytes, bytes]:
        public_key = (c_ubyte * self.public_key_bytes)()
        secret_key = (c_ubyte * self.secret_key_bytes)()

        result = self._keypair(public_key, secret_key)

        if result != 0:
            raise RuntimeError(
                f"HAETAE keypair generation failed: return code={result}"
            )

        return bytes(public_key), bytes(secret_key)

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")

        if len(private_key) != self.secret_key_bytes:
            raise ValueError(
                "Invalid HAETAE secret key length: "
                f"expected={self.secret_key_bytes}, "
                f"actual={len(private_key)}"
            )

        signature = (c_ubyte * self.signature_bytes)()
        signature_length = c_size_t(0)

        message_buffer = self._bytes_buffer(message)
        context_buffer = self._bytes_buffer(self.context)
        secret_key_buffer = self._bytes_buffer(private_key)

        result = self._signature(
            signature,
            byref(signature_length),
            message_buffer,
            c_size_t(len(message)),
            context_buffer,
            c_size_t(len(self.context)),
            secret_key_buffer,
        )

        if result != 0:
            raise RuntimeError(
                f"HAETAE signing failed: return code={result}"
            )

        if signature_length.value > self.signature_bytes:
            raise RuntimeError(
                "HAETAE returned an oversized signature: "
                f"{signature_length.value}"
            )

        return bytes(signature[:signature_length.value])

    def verify(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes,
    ) -> bool:
        if not isinstance(message, bytes):
            return False

        if not isinstance(signature, bytes):
            return False

        if len(signature) != self.signature_bytes:
            return False

        if len(public_key) != self.public_key_bytes:
            return False

        signature_buffer = self._bytes_buffer(signature)
        message_buffer = self._bytes_buffer(message)
        context_buffer = self._bytes_buffer(self.context)
        public_key_buffer = self._bytes_buffer(public_key)

        result = self._verify(
            signature_buffer,
            c_size_t(len(signature)),
            message_buffer,
            c_size_t(len(message)),
            context_buffer,
            c_size_t(len(self.context)),
            public_key_buffer,
        )

        return result == 0