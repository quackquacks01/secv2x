from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import binascii
import ctypes
from ctypes import POINTER, byref, c_int, c_size_t, c_uint8
import hashlib
import hmac
import os
from pathlib import Path
import secrets


class Signer(ABC):
    algorithm_name: str

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """
        반환 순서: (public_key, private_key)
        """
        raise NotImplementedError

    @abstractmethod
    def sign(self, message: bytes, private_key: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def verify(
        self,
        message: bytes,
        signature: str,
        public_key: bytes,
    ) -> bool:
        raise NotImplementedError


class MockHMACSigner(Signer):
    """
    테스트 전용 서명기.

    HMAC은 공개키 전자서명이 아니므로 논문 성능 결과나 보안 주장에
    사용하면 안 됩니다. 프로토콜 흐름 검증용입니다.
    """

    algorithm_name = "MOCK-HMAC-SHA256"

    def generate_keypair(self) -> tuple[bytes, bytes]:
        key = secrets.token_bytes(32)

        # HMAC은 대칭키이므로 테스트 편의를 위해 동일한 키를 반환합니다.
        return key, key

    def sign(self, message: bytes, private_key: bytes) -> str:
        return hmac.new(
            private_key,
            message,
            hashlib.sha256,
        ).hexdigest()

    def verify(
        self,
        message: bytes,
        signature: str,
        public_key: bytes,
    ) -> bool:
        expected = self.sign(message, public_key)
        return hmac.compare_digest(expected, signature)


class HAETAEMode2Signer(Signer):
    """
    HAETAE mode2 공식 C 구현을 ctypes로 호출하는 서명기.

    네이티브 함수:
      cryptolab_haetae_mode2_keypair
      cryptolab_haetae_mode2_signature
      cryptolab_haetae_mode2_verify
    """

    algorithm_name = "HAETAE-mode2"

    PUBLIC_KEY_BYTES = 992
    SECRET_KEY_BYTES = 1408
    SIGNATURE_BYTES = 1474

    KEYPAIR_FUNCTION = "cryptolab_haetae_mode2_keypair"
    SIGN_FUNCTION = "cryptolab_haetae_mode2_signature"
    VERIFY_FUNCTION = "cryptolab_haetae_mode2_verify"

    def __init__(
        self,
        dll_path: str | Path,
        context: bytes = b"KpqC-WTC-v1",
        dependency_directories: list[str | Path] | None = None,
    ) -> None:
        self.dll_path = Path(dll_path).expanduser().resolve()

        if not self.dll_path.is_file():
            raise FileNotFoundError(
                f"HAETAE DLL을 찾을 수 없습니다: {self.dll_path}"
            )

        if not isinstance(context, bytes):
            raise TypeError("context는 bytes 형식이어야 합니다.")

        if len(context) > 255:
            raise ValueError("HAETAE context는 255바이트 이하여야 합니다.")

        self.context = context

        # os.add_dll_directory() 반환 객체가 제거되지 않도록 보관합니다.
        self._dll_directory_handles: list[object] = []

        if os.name == "nt":
            directories = [
                self.dll_path.parent,
                Path(r"C:\msys64\ucrt64\bin"),
            ]

            if dependency_directories:
                directories.extend(
                    Path(directory)
                    for directory in dependency_directories
                )

            for directory in directories:
                if directory.is_dir():
                    handle = os.add_dll_directory(str(directory))
                    self._dll_directory_handles.append(handle)

        # MinGW로 빌드된 C 함수는 cdecl이므로 CDLL을 사용합니다.
        self._library = ctypes.CDLL(str(self.dll_path))

        self._configure_functions()

    def _configure_functions(self) -> None:
        self._keypair = getattr(
            self._library,
            self.KEYPAIR_FUNCTION,
        )
        self._keypair.argtypes = [
            POINTER(c_uint8),
            POINTER(c_uint8),
        ]
        self._keypair.restype = c_int

        self._signature = getattr(
            self._library,
            self.SIGN_FUNCTION,
        )
        self._signature.argtypes = [
            POINTER(c_uint8),        # sig
            POINTER(c_size_t),       # siglen
            POINTER(c_uint8),        # message
            c_size_t,                # message length
            POINTER(c_uint8),        # context
            c_size_t,                # context length
            POINTER(c_uint8),        # secret key
        ]
        self._signature.restype = c_int

        self._verify = getattr(
            self._library,
            self.VERIFY_FUNCTION,
        )
        self._verify.argtypes = [
            POINTER(c_uint8),        # signature
            c_size_t,                # signature length
            POINTER(c_uint8),        # message
            c_size_t,                # message length
            POINTER(c_uint8),        # context
            c_size_t,                # context length
            POINTER(c_uint8),        # public key
        ]
        self._verify.restype = c_int

    @staticmethod
    def _to_buffer(data: bytes):
        if not data:
            return None

        return (c_uint8 * len(data)).from_buffer_copy(data)

    def generate_keypair(self) -> tuple[bytes, bytes]:
        public_key = (c_uint8 * self.PUBLIC_KEY_BYTES)()
        private_key = (c_uint8 * self.SECRET_KEY_BYTES)()

        result = self._keypair(public_key, private_key)

        if result != 0:
            raise RuntimeError(
                f"HAETAE keypair 생성 실패: return code={result}"
            )

        return bytes(public_key), bytes(private_key)

    def sign(self, message: bytes, private_key: bytes) -> str:
        if not isinstance(message, bytes):
            raise TypeError("message는 bytes 형식이어야 합니다.")

        if len(private_key) != self.SECRET_KEY_BYTES:
            raise ValueError(
                "HAETAE private key 길이가 잘못되었습니다. "
                f"expected={self.SECRET_KEY_BYTES}, "
                f"actual={len(private_key)}"
            )

        signature = (c_uint8 * self.SIGNATURE_BYTES)()
        signature_length = c_size_t(0)

        message_buffer = self._to_buffer(message)
        context_buffer = self._to_buffer(self.context)
        private_key_buffer = self._to_buffer(private_key)

        result = self._signature(
            signature,
            byref(signature_length),
            message_buffer,
            len(message),
            context_buffer,
            len(self.context),
            private_key_buffer,
        )

        if result != 0:
            raise RuntimeError(
                f"HAETAE 서명 생성 실패: return code={result}"
            )

        if signature_length.value > self.SIGNATURE_BYTES:
            raise RuntimeError(
                "HAETAE가 허용된 버퍼보다 큰 서명을 반환했습니다: "
                f"{signature_length.value}"
            )

        signature_bytes = bytes(
            signature[:signature_length.value]
        )

        # 기존 Signer 인터페이스가 str을 사용하므로 Base64로 반환합니다.
        return base64.b64encode(signature_bytes).decode("ascii")

    def verify(
        self,
        message: bytes,
        signature: str,
        public_key: bytes,
    ) -> bool:
        if not isinstance(message, bytes):
            return False

        if len(public_key) != self.PUBLIC_KEY_BYTES:
            return False

        try:
            signature_bytes = base64.b64decode(
                signature,
                validate=True,
            )
        except (binascii.Error, ValueError, TypeError):
            return False

        if len(signature_bytes) != self.SIGNATURE_BYTES:
            return False

        signature_buffer = self._to_buffer(signature_bytes)
        message_buffer = self._to_buffer(message)
        context_buffer = self._to_buffer(self.context)
        public_key_buffer = self._to_buffer(public_key)

        result = self._verify(
            signature_buffer,
            len(signature_bytes),
            message_buffer,
            len(message),
            context_buffer,
            len(self.context),
            public_key_buffer,
        )

        # KpqC/NIST API 관례상 0이 검증 성공입니다.
        return result == 0