from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class ResultCode(str, Enum):
    ACCEPT = "ACCEPT"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    VALID_UPDATE = "VALID_UPDATE"
    INVALID_UPDATE = "INVALID_UPDATE"
    PENDING_UPDATE = "PENDING_UPDATE"
    STALE = "STALE"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    UNVERIFIED_GOSSIP = "UNVERIFIED_GOSSIP"


@dataclass(frozen=True)
class TrajectoryEnvelope:
    segment_index: int
    t_start_ms: int
    t_end_ms: int
    road_id: str
    lane_id: str
    pos_min_mm: int
    pos_max_mm: int
    v_min_mmps: int
    v_max_mmps: int
    a_min_mmps2: int
    a_max_mmps2: int
    behavior_code: str


@dataclass(frozen=True)
class Commitment:
    subject_id: str
    session_id: str
    epoch: int
    sequence: int
    valid_from_ms: int
    valid_until_ms: int
    merkle_root: str
    parent_root: str | None
    context_digest: str | None
    signature_algorithm: str
    signature: str = ""

    @property
    def consistency_key(self) -> tuple[str, str, int, int]:
        return (
            self.subject_id,
            self.session_id,
            self.epoch,
            self.sequence,
        )

    @property
    def session_key(self) -> tuple[str, str, int]:
        return (
            self.subject_id,
            self.session_id,
            self.epoch,
        )

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "sequence": self.sequence,
            "valid_from_ms": self.valid_from_ms,
            "valid_until_ms": self.valid_until_ms,
            "merkle_root": self.merkle_root,
            "parent_root": self.parent_root,
            "context_digest": self.context_digest,
            "signature_algorithm": self.signature_algorithm,
        }

    def with_signature(self, signature: str) -> "Commitment":
        return replace(self, signature=signature)


@dataclass(frozen=True)
class WitnessReceipt:
    witness_id: str
    subject_id: str
    session_id: str
    epoch: int
    sequence: int
    merkle_root: str
    commitment_digest: str
    observed_at_ms: int
    signature_algorithm: str
    signature: str = ""
    decision: str = "OBSERVED"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "witness_id": self.witness_id,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "sequence": self.sequence,
            "merkle_root": self.merkle_root,
            "commitment_digest": self.commitment_digest,
            "observed_at_ms": self.observed_at_ms,
            "signature_algorithm": self.signature_algorithm,
            "decision": self.decision,
        }

    def with_signature(self, signature: str) -> "WitnessReceipt":
        return replace(self, signature=signature)


@dataclass(frozen=True)
class EvidenceBundle:
    commitment_a: Commitment
    commitment_b: Commitment
    witness_id: str
    detected_at_ms: int
    receipt_a: WitnessReceipt | None = None
    receipt_b: WitnessReceipt | None = None

    @property
    def consistency_key(self) -> tuple[str, str, int, int]:
        return self.commitment_a.consistency_key

    def to_dict(self) -> dict[str, Any]:
        return {
            "consistency_key": list(self.consistency_key),
            "witness_id": self.witness_id,
            "detected_at_ms": self.detected_at_ms,
            "commitment_a": self.commitment_a.__dict__,
            "commitment_b": self.commitment_b.__dict__,
            "receipt_a": None if self.receipt_a is None else self.receipt_a.__dict__,
            "receipt_b": None if self.receipt_b is None else self.receipt_b.__dict__,
        }


@dataclass(frozen=True)
class ProcessResult:
    code: ResultCode
    reason: str
    receipt: WitnessReceipt | None = None
    evidence: EvidenceBundle | None = None
