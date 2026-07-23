import base64

from src.wtc.crypto_kpqc import HAETAEMode2Signer


DLL_PATH = (
    r"C:\Users\wah43\kpqc\kpqc-work"
    r"\HAETAE\reference_implementation"
    r"\build\release\bin\libhaetae-mode2.dll"
)


def main() -> None:
    signer = HAETAEMode2Signer(DLL_PATH)

    public_key, private_key = signer.generate_keypair()

    message = b"WTC real HAETAE integration test"
    signature = signer.sign(message, private_key)

    valid = signer.verify(
        message,
        signature,
        public_key,
    )

    tampered = signer.verify(
        message + b"-tampered",
        signature,
        public_key,
    )

    signature_bytes = base64.b64decode(signature)

    print(f"algorithm       : {signer.algorithm_name}")
    print(f"public key size : {len(public_key)}")
    print(f"secret key size : {len(private_key)}")
    print(f"signature size  : {len(signature_bytes)}")
    print(f"valid signature : {valid}")
    print(f"tampered message: {tampered}")

    assert len(public_key) == 992
    assert len(private_key) == 1408
    assert len(signature_bytes) == 1474
    assert valid is True
    assert tampered is False

    print("HAETAE real integration: PASS")


if __name__ == "__main__":
    main()