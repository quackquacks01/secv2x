from __future__ import annotations

import hashlib
from typing import Sequence

from .crypto import Signer
from .encoding import canonical_json_bytes
from .merkle import MerkleTree
from .models import Commitment, TrajectoryEnvelope


COMMITMENT_DOMAIN = b"KPQC-TRAJECTORY-COMMITMENT-V1"
CONTEXT_DOMAIN = b"KPQC-TRAJECTORY-CONTEXT-V1"


def commitment_message(commitment: Commitment) -> bytes:
    return COMMITMENT_DOMAIN + canonical_json_bytes(commitment.unsigned_dict())


def commitment_digest_hex(commitment: Commitment) -> str:
    return hashlib.sha256(commitment_message(commitment)).hexdigest()


def context_digest(reason: str, evidence_reference: str = "") -> str:
    return hashlib.sha256(
        CONTEXT_DOMAIN
        + canonical_json_bytes(
            {
                "reason": reason,
                "evidence_reference": evidence_reference,
            }
        )
    ).hexdigest()


class CommitmentFactory:
    def __init__(self, signer: Signer):
        self.signer = signer

    def create(
        self,
        *,
        subject_id: str,
        session_id: str,
        epoch: int,
        sequence: int,
        valid_from_ms: int,
        valid_until_ms: int,
        envelopes: Sequence[TrajectoryEnvelope],
        private_key: bytes,
        parent_root: str | None = None,
        update_reason: str | None = None,
        evidence_reference: str = "",
    ) -> Commitment:
        if valid_until_ms <= valid_from_ms:
            raise ValueError("valid_until_ms must be greater than valid_from_ms")
        if sequence == 0 and parent_root is not None:
            raise ValueError("initial commitment must not have parent_root")
        if sequence > 0 and parent_root is None:
            raise ValueError("updated commitment must have parent_root")

        root = MerkleTree(envelopes).root_hex
        digest = (
            context_digest(update_reason, evidence_reference)
            if update_reason is not None
            else None
        )

        unsigned = Commitment(
            subject_id=subject_id,
            session_id=session_id,
            epoch=epoch,
            sequence=sequence,
            valid_from_ms=valid_from_ms,
            valid_until_ms=valid_until_ms,
            merkle_root=root,
            parent_root=parent_root,
            context_digest=digest,
            signature_algorithm=self.signer.algorithm_name,
        )
        signature = self.signer.sign(
            commitment_message(unsigned),
            private_key,
        )
        return unsigned.with_signature(signature)

    def resign_with_root(
        self,
        commitment: Commitment,
        *,
        new_root: str,
        private_key: bytes,
    ) -> Commitment:
        unsigned = Commitment(
            subject_id=commitment.subject_id,
            session_id=commitment.session_id,
            epoch=commitment.epoch,
            sequence=commitment.sequence,
            valid_from_ms=commitment.valid_from_ms,
            valid_until_ms=commitment.valid_until_ms,
            merkle_root=new_root,
            parent_root=commitment.parent_root,
            context_digest=commitment.context_digest,
            signature_algorithm=commitment.signature_algorithm,
        )
        return unsigned.with_signature(
            self.signer.sign(commitment_message(unsigned), private_key)
        )
