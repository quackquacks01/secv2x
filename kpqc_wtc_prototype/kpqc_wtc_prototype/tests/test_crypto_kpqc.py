from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wtc.crypto_kpqc import AIMerSigner, HAETAESigner


def test_missing_library_path_raises_value_error() -> None:
    with pytest.raises(ValueError, match="library_path is required"):
        AIMerSigner()


def test_invalid_library_path_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        HAETAESigner("/does/not/exist.so")


def test_kpqc_signer_loads_nist_style_api(tmp_path: Path) -> None:
    dummy_library_path = tmp_path / "libkpqc_dummy.so"
    dummy_library_path.write_bytes(b"")

    mock_lib = MagicMock()
    mock_lib.crypto_sign_publickeybytes.return_value = 16
    mock_lib.crypto_sign_secretkeybytes.return_value = 32
    mock_lib.crypto_sign_bytes.return_value = 64
    mock_lib.crypto_sign_keypair.return_value = 0
    mock_lib.crypto_sign_signature.return_value = 0
    mock_lib.crypto_sign_verify.return_value = 0

    with patch("wtc.crypto_kpqc.CDLL", return_value=mock_lib):
        signer = AIMerSigner(str(dummy_library_path))

        public_key, secret_key = signer.keygen()
        assert len(public_key) == 16
        assert len(secret_key) == 32

        signature = signer.sign(b"test-message", secret_key)
        assert isinstance(signature, bytes)
        assert signer.verify(b"test-message", signature, public_key)

        mock_lib.crypto_sign_keypair.assert_called_once()
        mock_lib.crypto_sign_signature.assert_called_once()
        mock_lib.crypto_sign_verify.assert_called_once()
