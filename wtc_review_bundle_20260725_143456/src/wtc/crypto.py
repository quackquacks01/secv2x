from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import binascii
import hashlib
import hmac
from typing import Protocol


class Signer(ABC):
    algorithm_name: str

    @abstractmethod
    def sign(self, message: bytes, private_key: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def verify(self, message: bytes, signature: str, public_key: bytes) -> bool:
        raise NotImplementedError


class MockHMACSigner(Signer):
    """
    테스트 전용 서명기.

    HMAC은 공개키 전자서명이 아니므로 논문 성능 결과나 보안 주장에 사용하면 안 됩니다.
    실제 AIMer/HAETAE 래퍼를 붙이기 전 프로토콜 흐름 검증용입니다.
    """

    algorithm_name = "MOCK-HMAC-SHA256"

    def sign(self, message: bytes, private_key: bytes) -> str:
        return hmac.new(private_key, message, hashlib.sha256).hexdigest()

    def verify(self, message: bytes, signature: str, public_key: bytes) -> bool:
        expected = self.sign(message, public_key)
        return hmac.compare_digest(expected, signature)


class RawByteSigner(Protocol):
    """Raw native signer interface whose signatures are bytes."""

    algorithm_name: str

    def keygen(self) -> tuple[bytes, bytes]:
        ...

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        ...

    def verify(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes,
    ) -> bool:
        ...


class Base64SignerAdapter(Signer):
    """
    Adapts a native byte-signature implementation to the protocol's string
    signature interface.  Base64 is an encoding layer only; it does not
    change the cryptographic algorithm.
    """

    def __init__(self, raw_signer: RawByteSigner):
        self.raw_signer = raw_signer
        self.algorithm_name = raw_signer.algorithm_name

    def keygen(self) -> tuple[bytes, bytes]:
        return self.raw_signer.keygen()

    def sign(self, message: bytes, private_key: bytes) -> str:
        raw_signature = self.raw_signer.sign(message, private_key)
        return base64.b64encode(raw_signature).decode("ascii")

    def verify(
        self,
        message: bytes,
        signature: str,
        public_key: bytes,
    ) -> bool:
        if not isinstance(signature, str):
            return False

        try:
            raw_signature = base64.b64decode(signature, validate=True)
        except (binascii.Error, ValueError, TypeError):
            return False

        return self.raw_signer.verify(message, raw_signature, public_key)
