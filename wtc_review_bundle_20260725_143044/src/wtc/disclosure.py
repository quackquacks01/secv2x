from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .commitment import commitment_digest_hex
from .encoding import canonical_json_bytes
from .merkle import MerkleProofItem, MerkleTree
from .models import Commitment, TrajectoryEnvelope


@dataclass(frozen=True)
class TrajectoryDisclosure:
    commitment_digest: str
    subject_id: str
    session_id: str
    epoch: int
    sequence: int
    slot_index: int
    envelope: TrajectoryEnvelope
    merkle_proof: tuple[MerkleProofItem, ...]
    disclosed_at_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_digest": self.commitment_digest,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "sequence": self.sequence,
            "slot_index": self.slot_index,
            "envelope": asdict(self.envelope),
            "merkle_proof": [
                asdict(item)
                for item in self.merkle_proof
            ],
            "disclosed_at_ms": self.disclosed_at_ms,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


def create_disclosure(
    commitment: Commitment,
    envelopes: Sequence[TrajectoryEnvelope],
    *,
    slot_index: int,
    disclosed_at_ms: int,
) -> TrajectoryDisclosure:
    if slot_index < 0 or slot_index >= len(envelopes):
        raise IndexError("slot_index is outside the trajectory plan")

    envelope = envelopes[slot_index]
    if envelope.segment_index != slot_index:
        raise ValueError(
            "envelope.segment_index must equal its Merkle leaf index"
        )

    tree = MerkleTree(envelopes)
    if tree.root_hex != commitment.merkle_root:
        raise ValueError(
            "the supplied envelopes do not match the signed commitment root"
        )

    return TrajectoryDisclosure(
        commitment_digest=commitment_digest_hex(commitment),
        subject_id=commitment.subject_id,
        session_id=commitment.session_id,
        epoch=commitment.epoch,
        sequence=commitment.sequence,
        slot_index=slot_index,
        envelope=envelope,
        merkle_proof=tuple(tree.proof(slot_index)),
        disclosed_at_ms=int(disclosed_at_ms),
    )


def verify_disclosure(
    commitment: Commitment,
    disclosure: TrajectoryDisclosure,
    *,
    enforce_slot_time: bool = False,
) -> bool:
    if disclosure.commitment_digest != commitment_digest_hex(commitment):
        return False
    if disclosure.subject_id != commitment.subject_id:
        return False
    if disclosure.session_id != commitment.session_id:
        return False
    if disclosure.epoch != commitment.epoch:
        return False
    if disclosure.sequence != commitment.sequence:
        return False
    if disclosure.slot_index != disclosure.envelope.segment_index:
        return False
    if enforce_slot_time and not (
        disclosure.envelope.t_start_ms
        <= disclosure.disclosed_at_ms
        < disclosure.envelope.t_end_ms
    ):
        return False

    return MerkleTree.verify(
        disclosure.envelope,
        disclosure.merkle_proof,
        commitment.merkle_root,
    )
