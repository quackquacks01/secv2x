from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Sequence

from .encoding import canonical_json_bytes
from .models import TrajectoryEnvelope


LEAF_DOMAIN = b"KPQC-TRAJECTORY-LEAF-V1"
NODE_DOMAIN = b"KPQC-TRAJECTORY-NODE-V1"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_leaf(envelope: TrajectoryEnvelope) -> bytes:
    payload = canonical_json_bytes(envelope)
    return hashlib.sha256(
        LEAF_DOMAIN
        + envelope.segment_index.to_bytes(4, "big", signed=False)
        + payload
    ).digest()


def hash_node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_DOMAIN + left + right).digest()


@dataclass(frozen=True)
class MerkleProofItem:
    sibling_hex: str
    sibling_is_left: bool


class MerkleTree:
    def __init__(self, envelopes: Sequence[TrajectoryEnvelope]):
        if not envelopes:
            raise ValueError("envelopes must not be empty")

        self.envelopes = list(envelopes)
        current = [hash_leaf(item) for item in self.envelopes]
        self.levels: list[list[bytes]] = [current]

        while len(current) > 1:
            if len(current) % 2 == 1:
                current = current + [current[-1]]
            parent_level: list[bytes] = []
            for i in range(0, len(current), 2):
                parent_level.append(hash_node(current[i], current[i + 1]))
            self.levels.append(parent_level)
            current = parent_level

    @property
    def root_hex(self) -> str:
        return self.levels[-1][0].hex()

    def proof(self, index: int) -> list[MerkleProofItem]:
        if index < 0 or index >= len(self.envelopes):
            raise IndexError("leaf index out of range")

        proof: list[MerkleProofItem] = []
        current_index = index

        for level in self.levels[:-1]:
            effective_level = level if len(level) % 2 == 0 else level + [level[-1]]
            sibling_index = current_index - 1 if current_index % 2 else current_index + 1
            proof.append(
                MerkleProofItem(
                    sibling_hex=effective_level[sibling_index].hex(),
                    sibling_is_left=sibling_index < current_index,
                )
            )
            current_index //= 2

        return proof

    @staticmethod
    def verify(
        envelope: TrajectoryEnvelope,
        proof: Sequence[MerkleProofItem],
        expected_root_hex: str,
    ) -> bool:
        current = hash_leaf(envelope)
        for item in proof:
            sibling = bytes.fromhex(item.sibling_hex)
            current = (
                hash_node(sibling, current)
                if item.sibling_is_left
                else hash_node(current, sibling)
            )
        return hmac_compare_hex(current.hex(), expected_root_hex)


def hmac_compare_hex(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.lower(), b.lower())
