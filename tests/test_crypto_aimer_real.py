from __future__ import annotations

import os
from pathlib import Path

import pytest

from wtc.crypto_aimer import AIMer128fSigner


DLL_PATH = Path(__file__).resolve().parents[1] / "native" / "aimer" / "libaimer-128f.dll"

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not DLL_PATH.is_file(),
    reason="real AIMer-128f Windows DLL is unavailable",
)


def test_aimer_real_round_trip_and_tamper_detection() -> None:
    signer = AIMer128fSigner(DLL_PATH)
    public_key, private_key = signer.keygen()
    message = b"WTC AIMer real integration test"
    signature = signer.sign(message, private_key)

    assert len(public_key) == 32
    assert len(private_key) == 48
    assert len(signature) == 5888
    assert signer.verify(message, signature, public_key)
    assert not signer.verify(message + b"-tampered", signature, public_key)

    modified = bytearray(signature)
    modified[0] ^= 1
    assert not signer.verify(message, bytes(modified), public_key)
