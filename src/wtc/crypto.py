from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import hmac


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
