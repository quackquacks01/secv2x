import base64
import hashlib
import hmac

from wtc.crypto import Base64SignerAdapter


class FakeRawSigner:
    algorithm_name = "FAKE-RAW"

    def keygen(self) -> tuple[bytes, bytes]:
        key = b"k" * 32
        return key, key

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        return hmac.new(private_key, message, hashlib.sha256).digest()

    def verify(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes,
    ) -> bool:
        expected = self.sign(message, public_key)
        return hmac.compare_digest(expected, signature)


def test_base64_signer_adapter_round_trip() -> None:
    signer = Base64SignerAdapter(FakeRawSigner())
    public_key, private_key = signer.keygen()

    signature = signer.sign(b"message", private_key)

    assert isinstance(signature, str)
    assert len(base64.b64decode(signature, validate=True)) == 32
    assert signer.verify(b"message", signature, public_key)
    assert not signer.verify(b"tampered", signature, public_key)
    assert not signer.verify(b"message", "not-base64!", public_key)
