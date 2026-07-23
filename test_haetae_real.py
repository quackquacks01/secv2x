from pathlib import Path

from src.wtc.crypto_kpqc import HAETAESigner


DLL_PATH = (
    Path(__file__).resolve().parent
    / "native"
    / "haetae"
    / "libhaetae-mode2.dll"
)


def main() -> None:
    signer = HAETAESigner(str(DLL_PATH))

    public_key, secret_key = signer.keygen()

    message = b"WTC real HAETAE integration test"
    signature = signer.sign(message, secret_key)

    valid = signer.verify(
        message,
        signature,
        public_key,
    )

    tampered_message_valid = signer.verify(
        message + b"-tampered",
        signature,
        public_key,
    )

    tampered_signature = bytearray(signature)
    tampered_signature[0] ^= 0x01

    tampered_signature_valid = signer.verify(
        message,
        bytes(tampered_signature),
        public_key,
    )

    print(f"algorithm          : {signer.algorithm_name}")
    print(f"public key bytes   : {len(public_key)}")
    print(f"secret key bytes   : {len(secret_key)}")
    print(f"signature bytes    : {len(signature)}")
    print(f"valid signature    : {valid}")
    print(f"tampered message   : {tampered_message_valid}")
    print(f"tampered signature : {tampered_signature_valid}")

    assert len(public_key) == 992
    assert len(secret_key) == 1408
    assert len(signature) == 1474
    assert valid is True
    assert tampered_message_valid is False
    assert tampered_signature_valid is False

    print("HAETAE REAL INTEGRATION: PASS")


if __name__ == "__main__":
    main()